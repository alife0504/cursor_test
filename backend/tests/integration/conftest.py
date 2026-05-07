"""integration tests 共用 fixture。

依 PLAN.md 第 P2 章節設計：
- 需要 docker compose up（timescaledb / redis / qdrant 全 healthy）
- 從專案根目錄的 .env 讀密碼
"""

from __future__ import annotations

import os
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
