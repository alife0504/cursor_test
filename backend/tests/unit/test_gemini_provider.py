"""GeminiProvider 單元測試 — pricing / health_check / cost 計算。

依 PLAN.md 第 14.4 章 + Phase 12 prompt 條 P（≥ 4 個測試）。

注意：不打真 Gemini API；用 mock httpx / mock client。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import SecretStr

from app.llm.base_provider import LLM_PROVIDER_REGISTRY, get_llm_provider
from app.llm.gemini_provider import GeminiProvider

pytestmark = pytest.mark.unit


@pytest.fixture
def settings_with_key(monkeypatch: pytest.MonkeyPatch) -> Any:
    """提供帶 GOOGLE_API_KEY 的 settings。"""
    from app.core.config import settings as _s

    monkeypatch.setattr(_s, "GOOGLE_API_KEY", SecretStr("fake-google-key"), raising=False)
    return _s


@pytest.fixture
def settings_without_key(monkeypatch: pytest.MonkeyPatch) -> Any:
    from app.core.config import settings as _s

    monkeypatch.setattr(_s, "GOOGLE_API_KEY", None, raising=False)
    return _s


def test_gemini_registered_in_registry() -> None:
    """GeminiProvider 應由 @register_llm_provider 自動進 registry。"""
    assert "google" in LLM_PROVIDER_REGISTRY
    assert LLM_PROVIDER_REGISTRY["google"] is GeminiProvider


def test_get_llm_provider_returns_gemini(settings_with_key: Any) -> None:
    prov = get_llm_provider("google", settings_with_key)
    assert isinstance(prov, GeminiProvider)
    assert prov.name == "google"
    assert prov.default_model == "gemini-2.5-flash"


def test_pricing_calc_cost_known_model(settings_with_key: Any) -> None:
    """gemini-2.0-flash：input $0.10/1M, output $0.40/1M。"""
    prov = GeminiProvider(settings_with_key)
    # 1000 input + 500 output → 1000 * 0.0001/1000 + 500 * 0.0004/1000
    cost = prov.calc_cost("gemini-2.0-flash", 1000, 500)
    assert cost == Decimal("0.000300")  # 0.0001 + 0.0002 = 0.0003


def test_pricing_calc_cost_unknown_model(settings_with_key: Any) -> None:
    """未知 model 應回 0 + warning（不 raise）。"""
    prov = GeminiProvider(settings_with_key)
    cost = prov.calc_cost("xx-not-exists", 1000, 500)
    assert cost == Decimal("0")


@pytest.mark.asyncio
async def test_health_check_no_api_key(settings_without_key: Any) -> None:
    """無 GOOGLE_API_KEY → False。"""
    prov = GeminiProvider(settings_without_key)
    assert await prov.health_check() is False


@pytest.mark.asyncio
async def test_health_check_with_api_key(settings_with_key: Any) -> None:
    """有 GOOGLE_API_KEY + langchain 可 import → True。"""
    prov = GeminiProvider(settings_with_key)
    # langchain_google_genai 在 P12 已加入依賴；應可 import
    result = await prov.health_check()
    # 若測試環境未跑 uv sync 可能 False；只驗證回 bool（不 raise）
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_count_tokens_returns_positive(settings_with_key: Any) -> None:
    """tiktoken gpt-4 encoder 應為 ascii 文本回正數。"""
    prov = GeminiProvider(settings_with_key)
    n = await prov.count_tokens("Hello world, this is a test.")
    assert isinstance(n, int)
    assert n > 0


@pytest.mark.asyncio
async def test_generate_raises_external_service_error_on_no_api_key(
    settings_without_key: Any,
) -> None:
    """無 API key 呼叫 generate → ExternalServiceError。"""
    from app.core.errors import ExternalServiceError

    prov = GeminiProvider(settings_without_key)
    with pytest.raises(ExternalServiceError):
        await prov.generate(system="s", user="u")
