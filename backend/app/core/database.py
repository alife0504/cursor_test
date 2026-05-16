"""DB 連線層 — async engine（rw / ro）+ sync engine（celery）+ lifespan helper。

依 PLAN.md 第 14.1 章連線池 + 第 19.1 章帳號分離 + 第 14.10 章 DLQ。

設計：
- rw_engine（async）：ta_service_rw → 後端業務 router 用
- ro_engine（async）：ta_agent_ro → Agent / Tool 用
- migration_engine（async, ta_migration）：alembic env.py / data-pipeline 內部探測用
- sync_rw_engine（sync, ta_service_rw, psycopg2）：celery worker / task_failure signal 用
  Celery context 跑同步 SQLAlchemy 比 asyncio.run() 在 signal handler 中更穩定。

lifespan startup：
- 建 async engine（依 settings 的 pool size + timeout）
- 跑 fail-fast probe（連一次 SELECT 1）

lifespan shutdown：
- engine.dispose()
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.event import listens_for
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool, QueuePool

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ── Engine 工廠 ──────────────────────────────────────────


def _create_engine(dsn: str, pool_size: int, *, name: str) -> AsyncEngine:
    """建立 async engine 並掛 connect listener 設 timeout。"""
    engine = create_async_engine(
        dsn,
        echo=False,
        pool_size=pool_size,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=300,  # 5 min（避免 Postgres idle close）
        poolclass=AsyncAdaptedQueuePool,
        connect_args={
            # 避免長時間 idle session 被 PG 砍
            "server_settings": {
                "application_name": f"tradingagents-tw/{name}",
                "jit": "off",  # JIT 編譯有時拖慢小 query
            },
            "timeout": 10.0,
        },
    )

    # 每個新連線設 statement_timeout / lock_timeout
    @listens_for(engine.sync_engine, "connect")
    def _set_timeouts(dbapi_conn, _conn_record):  # type: ignore[no-untyped-def]
        try:
            cur = dbapi_conn.cursor()
            cur.execute(f"SET statement_timeout = '{settings.STATEMENT_TIMEOUT_MS}ms'")
            cur.execute(f"SET lock_timeout = '{settings.LOCK_TIMEOUT_MS}ms'")
            cur.execute("SET idle_in_transaction_session_timeout = '60s'")
            cur.close()
        except Exception as e:  # pragma: no cover
            # asyncpg 的 sync API 可能不一樣，listener 失敗就略過（後端會 raw SQL 補）
            logger.debug("db.connect_listener.skipped", error=str(e))

    return engine


# ── 全域 engine（lazy 初始化）────────────────────────────

_rw_engine: AsyncEngine | None = None
_ro_engine: AsyncEngine | None = None
_migration_engine: AsyncEngine | None = None
_rw_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_ro_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_migration_engine() -> AsyncEngine:
    """ta_migration 帳號 engine — alembic env.py 用，不開大 pool（DDL 是低頻）。

    注意：lifespan 預設不啟動此 engine。只有需要程式化跑 migration 的
    場景才呼叫（例如 data-pipeline/init_db.py 透過 subprocess 跑 alembic，
    或本機 health check 想 SELECT 表數）。
    """
    global _migration_engine
    if _migration_engine is None:
        _migration_engine = _create_engine(
            settings.postgres_dsn_migration, pool_size=2, name="migration"
        )
    return _migration_engine


def get_rw_engine() -> AsyncEngine:
    global _rw_engine, _rw_sessionmaker
    if _rw_engine is None:
        _rw_engine = _create_engine(settings.postgres_dsn_rw, settings.POOL_SIZE_RW, name="rw")
        _rw_sessionmaker = async_sessionmaker(
            _rw_engine, expire_on_commit=False, class_=AsyncSession
        )
    return _rw_engine


def get_ro_engine() -> AsyncEngine:
    global _ro_engine, _ro_sessionmaker
    if _ro_engine is None:
        _ro_engine = _create_engine(settings.postgres_dsn_ro, settings.POOL_SIZE_RO, name="ro")
        _ro_sessionmaker = async_sessionmaker(
            _ro_engine, expire_on_commit=False, class_=AsyncSession
        )
    return _ro_engine


# ── Session dependency（給 router / service 用） ─────────


async def get_rw_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency：開一個 RW session（後端業務用）。"""
    if _rw_sessionmaker is None:
        get_rw_engine()
    assert _rw_sessionmaker is not None
    async with _rw_sessionmaker() as session:
        yield session


async def get_ro_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency：開一個 RO session（Agent / Tool 用）。"""
    if _ro_sessionmaker is None:
        get_ro_engine()
    assert _ro_sessionmaker is not None
    async with _ro_sessionmaker() as session:
        yield session


@asynccontextmanager
async def ro_session() -> AsyncGenerator[AsyncSession, None]:
    """ta_agent_ro 的 async context manager — Agent / Tool / 非 FastAPI 場景用。

    用法：
        async with ro_session() as session:
            repo = OHLCVRepository(session)
            rows = await repo.get_range(...)

    安全核心：所有 Agent Tool 必須走此 session（read-only），
    防 prompt injection 注入 INSERT/UPDATE/DELETE。
    """
    if _ro_sessionmaker is None:
        get_ro_engine()
    assert _ro_sessionmaker is not None
    async with _ro_sessionmaker() as session:
        yield session


# ── 同步 engine / session（celery worker + signal handler 用） ─────

_sync_rw_engine: Engine | None = None
_sync_rw_sessionmaker: sessionmaker[Session] | None = None


def _build_sync_rw_dsn() -> str:
    """把 async DSN 改成 psycopg2 sync DSN（給 celery / signal 用）。"""
    pwd = settings.TA_SERVICE_RW_PASSWORD.get_secret_value()
    return (
        f"postgresql+psycopg2://ta_service_rw:{pwd}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )


def get_sync_rw_engine() -> Engine:
    """同步 ta_service_rw engine — celery worker / task_failure signal 用。

    pool 故意設小（celery worker concurrency=4，每 worker 1 conn 足夠）。
    """
    global _sync_rw_engine, _sync_rw_sessionmaker
    if _sync_rw_engine is None:
        _sync_rw_engine = create_engine(
            _build_sync_rw_dsn(),
            echo=False,
            pool_size=4,
            max_overflow=2,
            pool_pre_ping=True,
            pool_recycle=300,
            poolclass=QueuePool,
            connect_args={"application_name": "tradingagents-tw/sync_rw"},
        )

        @listens_for(_sync_rw_engine, "connect")
        def _set_timeouts(dbapi_conn, _conn_record):  # type: ignore[no-untyped-def]
            try:
                cur = dbapi_conn.cursor()
                cur.execute(f"SET statement_timeout = '{settings.STATEMENT_TIMEOUT_MS}ms'")
                cur.execute(f"SET lock_timeout = '{settings.LOCK_TIMEOUT_MS}ms'")
                cur.close()
            except Exception as e:  # pragma: no cover
                logger.debug("db.sync_connect_listener.skipped", error=str(e))

        _sync_rw_sessionmaker = sessionmaker(
            _sync_rw_engine, expire_on_commit=False, class_=Session
        )
    return _sync_rw_engine


@contextmanager
def sync_rw_session() -> Iterator[Session]:
    """同步 RW session context manager — celery task / signal handler 用。

    用法：
        with sync_rw_session() as s:
            s.add(...)
            s.commit()

    異常時自動 rollback；正常離開時 caller 負責 commit。
    """
    if _sync_rw_sessionmaker is None:
        get_sync_rw_engine()
    assert _sync_rw_sessionmaker is not None
    session = _sync_rw_sessionmaker()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_sync_rw_engine() -> None:
    """關閉 sync engine（celery worker shutdown 用）。"""
    global _sync_rw_engine, _sync_rw_sessionmaker
    if _sync_rw_engine is not None:
        _sync_rw_engine.dispose()
        _sync_rw_engine = None
        _sync_rw_sessionmaker = None


# ── lifespan helper ────────────────────────────────────


async def test_db_connection() -> None:
    """startup 時 fail-fast probe：兩個 engine 各跑一次 SELECT 1。

    P4 起：額外列舉 public schema 表數量，確認 alembic 已建立 baseline。
    若表數 < 20 → 警告（但不 raise，避免阻塞測試環境）。
    """
    from sqlalchemy import text

    rw = get_rw_engine()
    async with rw.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
        # P4：驗證 schema 已 migrate
        table_count = await conn.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
        )
        n_tables = table_count.scalar() or 0
        if n_tables < 20:
            logger.warning(
                "db.schema.incomplete",
                tables=n_tables,
                hint="run `make init-db` or `alembic upgrade head`",
            )
        else:
            logger.info("db.schema.ready", tables=n_tables)
    logger.info("db.rw_engine.ready", pool_size=settings.POOL_SIZE_RW)

    ro = get_ro_engine()
    async with ro.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
    logger.info("db.ro_engine.ready", pool_size=settings.POOL_SIZE_RO)


async def dispose_db_connections() -> None:
    """shutdown 時關閉 connection pool。"""
    global _rw_engine, _ro_engine, _migration_engine, _rw_sessionmaker, _ro_sessionmaker
    if _rw_engine is not None:
        await _rw_engine.dispose()
        _rw_engine = None
        _rw_sessionmaker = None
    if _ro_engine is not None:
        await _ro_engine.dispose()
        _ro_engine = None
        _ro_sessionmaker = None
    if _migration_engine is not None:
        await _migration_engine.dispose()
        _migration_engine = None
    logger.info("db.engines.disposed")


__all__ = [
    "dispose_db_connections",
    "dispose_sync_rw_engine",
    "get_migration_engine",
    "get_ro_engine",
    "get_ro_session",
    "get_rw_engine",
    "get_rw_session",
    "get_sync_rw_engine",
    "ro_session",
    "sync_rw_session",
    "test_db_connection",
]
