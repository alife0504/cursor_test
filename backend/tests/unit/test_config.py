"""config.py 單元測試（依 PLAN 第 P3 章節 R）。

驗證：
- 從 .env 載入
- SECRET_KEY < 32 bytes raise
- SECRET_KEY ≠ DATA_ENCRYPTION_KEY
- pool size defaults
- CORS_ORIGINS 解析
"""

from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from app.core.config import Settings

pytestmark = pytest.mark.unit


def _make_kwargs(**overrides: object) -> dict[str, object]:
    """產生最小可建立 Settings 所需的所有 required 欄位。"""
    valid_secret = base64.urlsafe_b64encode(b"a" * 32).decode()
    valid_data_key = base64.urlsafe_b64encode(b"b" * 32).decode()
    base = {
        "SECRET_KEY": valid_secret,
        "DATA_ENCRYPTION_KEY": valid_data_key,
        "POSTGRES_SUPERUSER_PASSWORD": "test-pwd-1",
        "TA_MIGRATION_PASSWORD": "test-pwd-2",
        "TA_SERVICE_RW_PASSWORD": "test-pwd-3",
        "TA_AGENT_RO_PASSWORD": "test-pwd-4",
        "REDIS_PASSWORD": "redis-pwd",
        "QDRANT_API_KEY": "qdrant-key",
    }
    base.update(overrides)
    return base


def test_settings_loads_from_env_via_kwargs() -> None:
    """直接傳 kwargs 應可建立 Settings。"""
    s = Settings(**_make_kwargs())  # type: ignore[arg-type]
    assert s.APP_VERSION == "0.3.0"
    assert s.LOG_LEVEL == "INFO"
    assert s.LOG_FORMAT == "json"


def test_secret_key_too_short_raises() -> None:
    """SECRET_KEY < 32 bytes 應 raise。"""
    short_key = base64.urlsafe_b64encode(b"a" * 16).decode()  # 只有 16 bytes
    with pytest.raises(ValidationError) as exc_info:
        Settings(**_make_kwargs(SECRET_KEY=short_key))  # type: ignore[arg-type]
    assert "32 bytes" in str(exc_info.value) or "SECRET_KEY" in str(exc_info.value)


def test_secret_key_invalid_base64_raises() -> None:
    """SECRET_KEY 非 base64 應 raise。"""
    with pytest.raises(ValidationError) as exc_info:
        Settings(**_make_kwargs(SECRET_KEY="not!@#valid$%base64"))  # type: ignore[arg-type]
    assert "SECRET_KEY" in str(exc_info.value)


def test_secret_key_equals_data_encryption_key_raises() -> None:
    """SECRET_KEY 與 DATA_ENCRYPTION_KEY 相同應 raise。"""
    same_key = base64.urlsafe_b64encode(b"x" * 32).decode()
    with pytest.raises(ValidationError) as exc_info:
        Settings(**_make_kwargs(SECRET_KEY=same_key, DATA_ENCRYPTION_KEY=same_key))  # type: ignore[arg-type]
    assert "分離" in str(exc_info.value) or "different" in str(exc_info.value).lower()


def test_pool_size_defaults() -> None:
    """連線池預設值依 PLAN 14.1 章。"""
    s = Settings(**_make_kwargs())  # type: ignore[arg-type]
    assert s.POOL_SIZE_RW == 20
    assert s.POOL_SIZE_RO == 30
    assert s.POOL_SIZE_REDIS == 50
    assert s.STATEMENT_TIMEOUT_MS == 30000
    assert s.LOCK_TIMEOUT_MS == 10000


def test_cors_origins_default() -> None:
    """CORS_ORIGINS 預設只允許 localhost:3000。"""
    s = Settings(**_make_kwargs())  # type: ignore[arg-type]
    assert s.CORS_ORIGINS == ["http://localhost:3000"]


def test_cors_origins_parsed_from_json_string() -> None:
    """CORS_ORIGINS 可用 JSON 字串設定。"""
    s = Settings(**_make_kwargs(CORS_ORIGINS='["https://a.com", "https://b.com"]'))  # type: ignore[arg-type]
    assert s.CORS_ORIGINS == ["https://a.com", "https://b.com"]


def test_dsn_helpers() -> None:
    """postgres_dsn_* helpers 產出正確 URL。"""
    s = Settings(**_make_kwargs(POSTGRES_HOST="db.local", POSTGRES_PORT=5433))  # type: ignore[arg-type]
    assert "ta_service_rw:test-pwd-3@db.local:5433" in s.postgres_dsn_rw
    assert "ta_agent_ro:test-pwd-4@db.local:5433" in s.postgres_dsn_ro
    assert "ta_migration:test-pwd-2@db.local:5433" in s.postgres_dsn_migration


def test_redis_url_with_db() -> None:
    """redis_url(db=N) 產出正確 URL。"""
    s = Settings(**_make_kwargs(REDIS_HOST="cache.local"))  # type: ignore[arg-type]
    assert s.redis_url(db=3) == "redis://:redis-pwd@cache.local:6379/3"
    assert s.redis_url(db=0) == "redis://:redis-pwd@cache.local:6379/0"


def test_prod_env_rejects_localhost_cors() -> None:
    """prod 環境 CORS_ORIGINS 含 localhost 應 raise。"""
    with pytest.raises(ValidationError) as exc_info:
        Settings(  # type: ignore[arg-type]
            **_make_kwargs(
                APP_ENV="prod",
                CSP_PROD_ENABLED=True,
                CORS_ORIGINS=["http://localhost:3000"],
            )
        )
    assert "localhost" in str(exc_info.value)
