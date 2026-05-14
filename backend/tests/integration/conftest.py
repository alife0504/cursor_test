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
    """測試前確認 docker 起來（DB + Redis）。"""
    import socket

    for host, port in [("localhost", 5432), ("localhost", 6379)]:
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
        for db in (3, 5):  # JWT_BLACKLIST, WS_TICKET
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
