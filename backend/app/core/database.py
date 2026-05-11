"""DB 連線層 — 兩個 engine（rw / ro）+ 雙 sessionmaker + lifespan helper。

依 PLAN.md 第 14.1 章連線池 + 第 19.1 章帳號分離。

設計：
- rw_engine：用 ta_service_rw（DML only）→ 後端業務 router 用
- ro_engine：用 ta_agent_ro（SELECT only）→ Agent / Tool 用
- migration 用獨立 ta_migration（不在 lifespan 開）

lifespan startup：
- 建 engine（依 settings 的 pool size + timeout）
- 跑 fail-fast probe（連一次 SELECT 1）

lifespan shutdown：
- engine.dispose()
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.event import listens_for
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

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
_rw_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_ro_sessionmaker: async_sessionmaker[AsyncSession] | None = None


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


# ── lifespan helper ────────────────────────────────────


async def test_db_connection() -> None:
    """startup 時 fail-fast probe：兩個 engine 各跑一次 SELECT 1。"""
    from sqlalchemy import text

    rw = get_rw_engine()
    async with rw.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
    logger.info("db.rw_engine.ready", pool_size=settings.POOL_SIZE_RW)

    ro = get_ro_engine()
    async with ro.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
    logger.info("db.ro_engine.ready", pool_size=settings.POOL_SIZE_RO)


async def dispose_db_connections() -> None:
    """shutdown 時關閉 connection pool。"""
    global _rw_engine, _ro_engine, _rw_sessionmaker, _ro_sessionmaker
    if _rw_engine is not None:
        await _rw_engine.dispose()
        _rw_engine = None
        _rw_sessionmaker = None
    if _ro_engine is not None:
        await _ro_engine.dispose()
        _ro_engine = None
        _ro_sessionmaker = None
    logger.info("db.engines.disposed")


__all__ = [
    "dispose_db_connections",
    "get_ro_engine",
    "get_ro_session",
    "get_rw_engine",
    "get_rw_session",
    "test_db_connection",
]
