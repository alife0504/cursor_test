"""integration tests 共用 fixture。

依 PLAN.md 第 P2 章節設計：
- 需要 docker compose up（timescaledb / redis / qdrant 全 healthy）
- 從專案根目錄的 .env 讀密碼
"""

from __future__ import annotations

import os
from datetime import UTC
from pathlib import Path

import pytest

# 從 backend/tests/integration/conftest.py 往上 3 層 = 專案根目錄
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv(path: Path) -> dict[str, str]:
    """簡易 .env 解析（不依賴 python-dotenv）。"""
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


@pytest.fixture(scope="session")
def env_vars() -> dict[str, str]:
    """讀 .env，與 os.environ 合併（os.environ 優先）。"""
    file_env = _load_dotenv(PROJECT_ROOT / ".env")
    merged: dict[str, str] = {**file_env}
    # os.environ 優先（CI 可覆寫）
    for k in (
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_SUPERUSER_PASSWORD",
        "TA_MIGRATION_PASSWORD",
        "TA_SERVICE_RW_PASSWORD",
        "TA_AGENT_RO_PASSWORD",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_PASSWORD",
        "QDRANT_HOST",
        "QDRANT_PORT",
        "QDRANT_API_KEY",
    ):
        if k in os.environ:
            merged[k] = os.environ[k]
    return merged


@pytest.fixture(scope="session")
def pg_host(env_vars: dict[str, str]) -> str:
    return env_vars.get("POSTGRES_HOST", "localhost")


@pytest.fixture(scope="session")
def pg_port(env_vars: dict[str, str]) -> int:
    return int(env_vars.get("POSTGRES_PORT", "5432"))


@pytest.fixture(scope="session")
def pg_db(env_vars: dict[str, str]) -> str:
    return env_vars.get("POSTGRES_DB", "tradingagents_tw")


@pytest.fixture(scope="session")
def redis_host(env_vars: dict[str, str]) -> str:
    return env_vars.get("REDIS_HOST", "localhost")


@pytest.fixture(scope="session")
def redis_port(env_vars: dict[str, str]) -> int:
    return int(env_vars.get("REDIS_PORT", "6379"))


@pytest.fixture(scope="session")
def qdrant_host(env_vars: dict[str, str]) -> str:
    return env_vars.get("QDRANT_HOST", "localhost")


@pytest.fixture(scope="session")
def qdrant_port(env_vars: dict[str, str]) -> int:
    return int(env_vars.get("QDRANT_PORT", "6333"))


# ════════════════════════════════════════════════════════
# Phase 8 auth fixtures
# ════════════════════════════════════════════════════════


# 確保 lifespan probe 跳過（與既有 test_health_endpoints.py 一致）
os.environ.setdefault("PYTEST_RUNNING", "true")
# 測試需要 /auth/password-reset 回傳 dev_token（正式預設 False，不外露 → 見 auth_router）
os.environ.setdefault("EXPOSE_RESET_TOKEN_IN_RESPONSE", "true")


@pytest.fixture(scope="session")
def auth_app():
    """共用的 FastAPI app — 加一條測試專用 admin probe endpoint 給 RBAC 測試。

    避免在 production code 留測試專用路徑。app 是 module-singleton，所以
    重複定義 endpoint 會被 idempotently 加（fastapi 不會擋）。
    """
    from fastapi import Depends

    from app.api.dependencies import admin_only
    from app.main import app

    # 加掛測試專用 endpoint
    if not any(getattr(r, "path", "") == "/_test/admin-only" for r in app.routes):

        @app.get("/_test/admin-only", tags=["_test"])
        async def _admin_only_probe(user=Depends(admin_only)):
            return {"ok": True, "role": user.role}

    return app


@pytest.fixture
def auth_client(auth_app):
    """TestClient（一個 test function 一份；確保 lifespan 跑完）。"""
    from starlette.testclient import TestClient

    with TestClient(auth_app) as c:
        yield c


def _docker_services_reachable() -> bool:
    """測試前確認 docker 起來（DB + Redis）。

    port 從 settings 讀（跟 app 實際連線一致），不能寫死 5432/6379：
    Windows 把 6379 列入保留 port，本機 compose 是用 REDIS_PORT=16379 發佈的，
    寫死會讓整合測試在這台機器永遠 skip。
    """
    import socket

    from app.core.config import settings

    checks = [
        (settings.POSTGRES_HOST, int(settings.POSTGRES_PORT)),
        (settings.REDIS_HOST, int(settings.REDIS_PORT)),
    ]
    for host, port in checks:
        try:
            with socket.create_connection((host, port), timeout=1):
                pass
        except OSError:
            return False
    return True


@pytest.fixture(scope="session", autouse=True)
def _skip_if_docker_down() -> None:
    """整批 auth integration tests 在 docker 不可達時 skip。"""
    if not _docker_services_reachable():
        pytest.skip(
            "Docker services (postgres / redis) 不可達；請先跑 `make up` 啟動",
            allow_module_level=True,
        )


@pytest.fixture(autouse=True)
def _reset_redis_pools_per_test():
    """Phase 20 修正 — function-scoped autouse：清理跨 event-loop 殘留的 Redis pool。

    背景：部分整合測試用 `asyncio.run()` 直接跑 LangGraph（test_full_tw_pipeline /
    test_us_full_pipeline / test_cross_market_e2e / test_analysis_pipeline_stub）。
    graph_builder._stream_wrap 會呼叫 publish_event() → get_redis(PUBSUB)，把
    Redis pool 綁到 asyncio.run 的「臨時 event loop」。loop 結束後 pool 仍留在
    app.core.redis_client._pools 全域 dict；下個 test（走 TestClient 的 lifespan）
    重用就會炸 "Future attached to different loop"，造成隨機 ERROR/FAIL。

    解法：每個 test 結束後 clear() `_pools` 全域 dict（不真正關閉連線，避免
    從錯的 loop call aclose），下次 get_redis_pool() 會 lazy 重建 fresh pool。
    """
    yield
    try:
        from app.core import redis_client as _rc

        _rc._pools.clear()
    except Exception:  # noqa: S110 — 測試清理用，忽略失敗無礙
        pass


@pytest.fixture
async def db_session_maker():
    """每個 test 開獨立 async engine，避免 TestClient 與 pytest-asyncio 跨 loop。

    TestClient 內部跑自己的 event loop（啟 lifespan），但 pytest-asyncio 的 test func
    在不同 loop 跑。共用同一個 engine 會炸 "Future attached to different loop"。
    每 test 一個小 engine（pool_size=2）成本可接受。
    """
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from app.core.config import settings

    engine = create_async_engine(
        settings.postgres_dsn_rw,
        echo=False,
        pool_size=2,
        max_overflow=1,
        pool_pre_ping=True,
    )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield maker
    finally:
        await engine.dispose()


class _TestUserHandle:
    """測試用「身份卡」— 在 session 關閉後仍可安全讀屬性。"""

    __slots__ = ("email", "id", "must_change_password", "onboarding_completed", "role")

    def __init__(self, id, email, role, must_change_password, onboarding_completed):
        self.id = id
        self.email = email
        self.role = role
        self.must_change_password = must_change_password
        self.onboarding_completed = onboarding_completed


@pytest.fixture
async def make_test_user(db_session_maker):
    """factory：建立測試專用 user，函式結束自動清掉。

    用法：
        user, password = await make_test_user(role="ADMIN", must_change=False)
        # user 是 _TestUserHandle（有 .id / .email / .role）
    """
    import uuid as _uuid

    from sqlalchemy import delete

    from app.core.security import hash_password
    from app.models.user import (
        PasswordHistory,
        PasswordResetToken,
        User,
        UserSession,
    )

    created_ids: list[_uuid.UUID] = []

    async def _factory(
        *,
        role: str = "VIEWER",
        password: str = "TestPwd2026!Ab",  # noqa: S107 — test 預設密碼，符合複雜度政策
        email: str | None = None,
        must_change: bool = False,
        onboarding_completed: bool = True,
        is_active: bool = True,
    ):
        actual_email = email or f"phase8-{_uuid.uuid4().hex[:8]}@test.example.com"
        async with db_session_maker() as s:
            user = User(
                email=actual_email,
                password_hash=hash_password(password),
                full_name=f"Test {role}",
                role=role,
                must_change_password=must_change,
                onboarding_completed=onboarding_completed,
                is_active=is_active,
                preferred_timezone="Asia/Taipei",
                preferred_language="zh-TW",
            )
            s.add(user)
            await s.commit()
            await s.refresh(user)
            handle = _TestUserHandle(
                id=user.id,
                email=user.email,
                role=user.role,
                must_change_password=user.must_change_password,
                onboarding_completed=user.onboarding_completed,
            )
            created_ids.append(user.id)
        return handle, password

    yield _factory

    # cleanup — 依 FK 順序刪
    if created_ids:
        async with db_session_maker() as s:
            await s.execute(delete(PasswordHistory).where(PasswordHistory.user_id.in_(created_ids)))
            await s.execute(delete(UserSession).where(UserSession.user_id.in_(created_ids)))
            await s.execute(
                delete(PasswordResetToken).where(PasswordResetToken.user_id.in_(created_ids))
            )
            await s.execute(delete(User).where(User.id.in_(created_ids)))
            await s.commit()


# NOTE: 不在 pytest loop 直接 await get_redis().flushdb()
# 原因：TestClient lifespan 跑在自己的 loop 建 redis pool；pytest-asyncio 是另一個 loop。
# 跨 loop 用同一個 pool 會炸 "Future attached to different loop"。
# 解法：用同步 redis 連線清資料（在 conftest level）。


def _now_utc():
    from datetime import datetime

    return datetime.now(UTC)


@pytest.fixture
def flush_rate_limit(env_vars):
    """提供 callable：清 rate limit Redis (db 2)。
    給「需要多次 login / 多次 POST」的 test 在 loop 中呼叫，避開 L1/L2 rate limit。
    """
    import redis as redis_sync

    pwd = env_vars.get("REDIS_PASSWORD", "")
    host = env_vars.get("REDIS_HOST", "localhost")
    port = int(env_vars.get("REDIS_PORT", "6379"))

    def _flush() -> None:
        try:
            client = redis_sync.Redis(
                host=host, port=port, db=2, password=pwd, socket_connect_timeout=2
            )
            client.flushdb()
            client.close()
        except Exception as exc:  # pragma: no cover  - noqa: S110
            _ = exc

    return _flush


# ════════════════════════════════════════════════════════
# Phase 10 fixtures — stock / watchlist / market 測試共用
# ════════════════════════════════════════════════════════


async def _login_get_access_and_csrf(client, email: str, password: str) -> tuple[str, str]:
    """登入並回 (access_token, csrf_cookie)。給 P10 router 測試共用。"""
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    csrf = r.cookies.get("csrf_token") or ""
    return r.json()["data"]["access_token"], csrf


@pytest.fixture
def login_helper():
    """提供 callable：login_helper(auth_client, email, password) → (access, csrf)。"""
    return _login_get_access_and_csrf


@pytest.fixture
async def seed_stocks(db_session_maker):
    """建立測試用 stock_list 行；自動清理（cascade 連動 stock_prices）。

    Idempotent：若 symbol 已存在（例如 P7 seed 已寫入真實股號），
    使用 ON CONFLICT DO NOTHING 跳過；cleanup 也只刪本批新建的 row。
    """
    import uuid as _uuid

    from sqlalchemy import delete, select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.price import StockPrice
    from app.models.stock import StockList

    test_created_symbols: list[str] = []

    async def _factory(rows: list[dict]) -> list[str]:
        """rows 結構：[{symbol, market, name, industry?, is_active?}, ...]。"""
        async with db_session_maker() as s:
            symbols = [r["symbol"] for r in rows]
            # 找出本批中「事前不存在」的，才是真正由本 test 建立、需要清理的
            pre_existing = set(
                (await s.execute(select(StockList.symbol).where(StockList.symbol.in_(symbols))))
                .scalars()
                .all()
            )
            for r in rows:
                sym = r["symbol"]
                stmt = (
                    pg_insert(StockList)
                    .values(
                        symbol=sym,
                        market=r.get("market", "TWSE"),
                        name=r.get("name", f"測試{sym}"),
                        industry=r.get("industry"),
                        is_active=r.get("is_active", True),
                    )
                    .on_conflict_do_nothing(index_elements=["symbol"])
                )
                await s.execute(stmt)
                if sym not in pre_existing:
                    test_created_symbols.append(sym)
            await s.commit()
        return [r["symbol"] for r in rows]

    yield _factory

    if test_created_symbols:
        async with db_session_maker() as s:
            # P11：可能有 router/service 建了 analysis_reports / pending_orders
            # 直接 FK 到 stock_list.symbol；要先清掉這些後代才能刪 stock_list
            from app.models.analysis import AnalysisReport
            from app.models.order import PendingOrder, PortfolioPosition

            await s.execute(delete(StockPrice).where(StockPrice.symbol.in_(test_created_symbols)))
            await s.execute(
                delete(PortfolioPosition).where(PortfolioPosition.symbol.in_(test_created_symbols))
            )
            await s.execute(
                delete(PendingOrder).where(PendingOrder.symbol.in_(test_created_symbols))
            )
            await s.execute(
                delete(AnalysisReport).where(AnalysisReport.symbol.in_(test_created_symbols))
            )
            await s.execute(delete(StockList).where(StockList.symbol.in_(test_created_symbols)))
            await s.commit()
            _ = _uuid


@pytest.fixture
async def seed_ohlcv(db_session_maker):
    """建立測試用 stock_prices；caller 負責 seed 對應 stock_list（FK）。"""
    from sqlalchemy import delete

    from app.models.price import StockPrice

    inserted: list[tuple[str, object]] = []

    async def _factory(rows: list[dict]) -> int:
        """rows: [{symbol, date, open, high, low, close, volume?}, ...]。"""
        from decimal import Decimal

        async with db_session_maker() as s:
            for r in rows:
                p = StockPrice(
                    symbol=r["symbol"],
                    date=r["date"],
                    open=Decimal(str(r["open"])),
                    high=Decimal(str(r["high"])),
                    low=Decimal(str(r["low"])),
                    close=Decimal(str(r["close"])),
                    volume=int(r.get("volume", 0)),
                    source=r.get("source", "test"),
                )
                s.add(p)
                inserted.append((r["symbol"], r["date"]))
            await s.commit()
        return len(rows)

    yield _factory

    if inserted:
        async with db_session_maker() as s:
            for sym, d in inserted:
                await s.execute(
                    delete(StockPrice).where(StockPrice.symbol == sym, StockPrice.date == d)
                )
            await s.commit()


# ════════════════════════════════════════════════════════
# Phase 11 fixtures — analysis / orders / dlq
# ════════════════════════════════════════════════════════


@pytest.fixture
async def seed_analysis(db_session_maker):
    """建立測試用 analysis_reports 行；caller 提供 user_id + symbol。

    fixture 內部會自動確保 stock_list 中存在對應 symbol（ON CONFLICT IGNORE）。
    自動清理 debate_history + analysis_reports（不刪 stock_list，由 seed_stocks 管）。
    """
    import uuid as _uuid
    from decimal import Decimal

    from sqlalchemy import delete, select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.analysis import AnalysisReport, DebateMessage
    from app.models.stock import StockList

    created_ids: list[_uuid.UUID] = []
    auto_seeded_symbols: list[str] = []

    async def _factory(
        *,
        user_id,
        symbol: str = "2330",
        market: str = "TWSE",
        status: str = "queued",
        report_md: str | None = None,
        signal: str | None = None,
        confidence: Decimal | None = None,
    ):
        async with db_session_maker() as s:
            # 先確保 stock_list 中有 symbol（pkey 重複 ON CONFLICT DO NOTHING）
            pre = (
                await s.execute(select(StockList.symbol).where(StockList.symbol == symbol))
            ).scalar_one_or_none()
            if pre is None:
                await s.execute(
                    pg_insert(StockList)
                    .values(symbol=symbol, market=market, name=f"測試{symbol}", is_active=True)
                    .on_conflict_do_nothing(index_elements=["symbol"])
                )
                auto_seeded_symbols.append(symbol)
            row = AnalysisReport(
                user_id=user_id,
                symbol=symbol,
                market=market,
                status=status,
                llm_model="gemini-2.0-flash",
                report_md=report_md,
                signal=signal,
                confidence=confidence,
            )
            s.add(row)
            await s.commit()
            await s.refresh(row)
            created_ids.append(row.id)
            return row.id

    yield _factory

    if created_ids or auto_seeded_symbols:
        async with db_session_maker() as s:
            if created_ids:
                await s.execute(
                    delete(DebateMessage).where(DebateMessage.analysis_id.in_(created_ids))
                )
                await s.execute(delete(AnalysisReport).where(AnalysisReport.id.in_(created_ids)))
            if auto_seeded_symbols:
                # 順序：先清 FK 後代再刪 stock_list（router 可能建 analysis_reports / orders）
                from app.models.order import PendingOrder, PortfolioPosition

                await s.execute(
                    delete(PortfolioPosition).where(
                        PortfolioPosition.symbol.in_(auto_seeded_symbols)
                    )
                )
                await s.execute(
                    delete(PendingOrder).where(PendingOrder.symbol.in_(auto_seeded_symbols))
                )
                await s.execute(
                    delete(AnalysisReport).where(AnalysisReport.symbol.in_(auto_seeded_symbols))
                )
                await s.execute(delete(StockList).where(StockList.symbol.in_(auto_seeded_symbols)))
            await s.commit()


@pytest.fixture
async def seed_pending_order(db_session_maker):
    """建立 pending_orders（caller 提供 user_id + analysis_id + symbol）。

    fixture 內部會 auto-seed stock_list 中 symbol（idempotent）。
    """
    import uuid as _uuid
    from decimal import Decimal

    from sqlalchemy import delete, select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.order import PendingOrder, PortfolioPosition
    from app.models.stock import StockList

    created_ids: list[_uuid.UUID] = []
    auto_seeded_symbols: list[str] = []

    async def _factory(
        *,
        user_id,
        symbol: str = "2330",
        market: str = "TWSE",
        side: str = "BUY",
        qty: int = 1000,
        analysis_id=None,
        target_price: Decimal | None = Decimal("600.0"),
        status: str = "PENDING",
    ):
        async with db_session_maker() as s:
            pre = (
                await s.execute(select(StockList.symbol).where(StockList.symbol == symbol))
            ).scalar_one_or_none()
            if pre is None:
                await s.execute(
                    pg_insert(StockList)
                    .values(symbol=symbol, market=market, name=f"測試{symbol}", is_active=True)
                    .on_conflict_do_nothing(index_elements=["symbol"])
                )
                auto_seeded_symbols.append(symbol)
            row = PendingOrder(
                user_id=user_id,
                symbol=symbol,
                market=market,
                side=side,
                qty=qty,
                analysis_id=analysis_id,
                target_price=target_price,
                status=status,
                version=1,
            )
            s.add(row)
            await s.commit()
            await s.refresh(row)
            created_ids.append(row.id)
            return row.id

    yield _factory

    if created_ids or auto_seeded_symbols:
        async with db_session_maker() as s:
            from sqlalchemy import select as _sel

            if created_ids:
                rows = (
                    (await s.execute(_sel(PendingOrder).where(PendingOrder.id.in_(created_ids))))
                    .scalars()
                    .all()
                )
                for r in rows:
                    await s.execute(
                        delete(PortfolioPosition).where(
                            PortfolioPosition.user_id == r.user_id,
                            PortfolioPosition.symbol == r.symbol,
                        )
                    )
                await s.execute(delete(PendingOrder).where(PendingOrder.id.in_(created_ids)))
            if auto_seeded_symbols:
                from app.models.analysis import AnalysisReport as _AR

                await s.execute(delete(_AR).where(_AR.symbol.in_(auto_seeded_symbols)))
                await s.execute(delete(StockList).where(StockList.symbol.in_(auto_seeded_symbols)))
            await s.commit()


@pytest.fixture
async def seed_dlq(db_session_maker):
    """建立 celery_dead_letters 行；自動清理。"""
    from sqlalchemy import delete

    from app.models.dlq import CeleryDeadLetter

    created_ids: list[int] = []

    async def _factory(
        *,
        task_name: str = "test.task",
        exception_type: str = "RuntimeError",
        exception: str = "test failure",
        resolved: bool = False,
    ):
        async with db_session_maker() as s:
            row = CeleryDeadLetter(
                task_name=task_name,
                exception_type=exception_type,
                exception=exception,
                resolved=resolved,
                args=[],
                kwargs={},
            )
            s.add(row)
            await s.commit()
            await s.refresh(row)
            created_ids.append(row.id)
            return row.id

    yield _factory

    if created_ids:
        async with db_session_maker() as s:
            await s.execute(delete(CeleryDeadLetter).where(CeleryDeadLetter.id.in_(created_ids)))
            await s.commit()


@pytest.fixture(autouse=True)
def _flush_auth_redis_dbs(env_vars):
    """每個 test 前用「同步」redis client 清 jwt_blacklist + ws_ticket。

    避免跨 asyncio loop 問題；redis-py 的 sync client 不綁定任何 loop。
    """
    try:
        import redis as redis_sync

        pwd = env_vars.get("REDIS_PASSWORD", "")
        host = env_vars.get("REDIS_HOST", "localhost")
        port = int(env_vars.get("REDIS_PORT", "6379"))
        for db in (2, 3, 5, 6):  # RATELIMIT, JWT_BLACKLIST, WS_TICKET, IDEMPOTENCY
            try:
                client = redis_sync.Redis(
                    host=host, port=port, db=db, password=pwd, socket_connect_timeout=2
                )
                client.flushdb()
                client.close()
            except Exception as exc:  # pragma: no cover  - noqa: S110
                # test 環境 redis 連不上時不擋 test；只是清不了快取
                _ = exc
    except Exception as exc:  # pragma: no cover  - noqa: S110
        _ = exc
    yield
