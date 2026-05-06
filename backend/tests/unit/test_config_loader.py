"""config.py 載入測試 — Phase 1 階段標 skip，P3 才實作。

這是 v7.0 Phase 1 的測試雛形（5/5）。
P3 會建立 backend/app/core/config.py 後，這些測試會被啟用。
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.skip(reason="config.py 在 P3 才建立")]


def test_settings_loads_from_env() -> None:
    """config.Settings 應能從 .env 載入。

    P3 實作後預期：
        from app.core.config import settings
        assert settings.APP_VERSION == "0.3.0"
    """


def test_secret_key_too_short_raises() -> None:
    """SECRET_KEY < 32 bytes 應在啟動時 raise。"""


def test_admin_email_must_be_valid() -> None:
    """ADMIN_EMAIL 必須是合法 email 格式。"""


def test_secret_key_and_data_encryption_key_must_differ() -> None:
    """SECRET_KEY 與 DATA_ENCRYPTION_KEY 必須不同。"""


def test_llm_default_provider_must_have_api_key() -> None:
    """LLM_DEFAULT_PROVIDER 對應的 API key 必須非空。"""
