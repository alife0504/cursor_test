"""OpenAIProvider 單元測試 — pricing / health_check / generate（mock SDK）。

依 PLAN.md 第 14.4 章。
不打真 OpenAI API；用 monkeypatch 替換 `AsyncOpenAI` client。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from app.core.errors import ExternalServiceError
from app.llm.base_provider import LLM_PROVIDER_REGISTRY
from app.llm.openai_provider import OpenAIProvider

pytestmark = pytest.mark.unit


@pytest.fixture
def settings_with_key(monkeypatch: pytest.MonkeyPatch) -> Any:
    from app.core.config import settings as _s

    monkeypatch.setattr(_s, "OPENAI_API_KEY", SecretStr("fake-openai-key"), raising=False)
    return _s


@pytest.fixture
def settings_without_key(monkeypatch: pytest.MonkeyPatch) -> Any:
    from app.core.config import settings as _s

    monkeypatch.setattr(_s, "OPENAI_API_KEY", None, raising=False)
    return _s


def test_openai_registered_in_registry() -> None:
    assert "openai" in LLM_PROVIDER_REGISTRY
    assert LLM_PROVIDER_REGISTRY["openai"] is OpenAIProvider


def test_openai_default_model(settings_with_key: Any) -> None:
    prov = OpenAIProvider(settings_with_key)
    assert prov.name == "openai"
    assert prov.default_model == "gpt-4o-mini"


def test_pricing_calc_cost_gpt4o_mini(settings_with_key: Any) -> None:
    """gpt-4o-mini：input $0.15/1M, output $0.60/1M。

    1000 input + 500 output → 0.00015*1 + 0.0006*0.5 = 0.00045
    """
    prov = OpenAIProvider(settings_with_key)
    cost = prov.calc_cost("gpt-4o-mini", 1000, 500)
    assert cost == Decimal("0.000450")


def test_pricing_calc_cost_gpt4o(settings_with_key: Any) -> None:
    prov = OpenAIProvider(settings_with_key)
    cost = prov.calc_cost("gpt-4o", 2000, 1000)
    # 0.0025 * 2 + 0.01 * 1 = 0.005 + 0.01 = 0.015
    assert cost == Decimal("0.015000")


def test_pricing_unknown_model_returns_zero(settings_with_key: Any) -> None:
    prov = OpenAIProvider(settings_with_key)
    assert prov.calc_cost("not-exists", 1000, 500) == Decimal("0")


@pytest.mark.asyncio
async def test_health_check_no_key_false(settings_without_key: Any) -> None:
    prov = OpenAIProvider(settings_without_key)
    assert await prov.health_check() is False


@pytest.mark.asyncio
async def test_generate_no_key_raises(settings_without_key: Any) -> None:
    prov = OpenAIProvider(settings_without_key)
    with pytest.raises(ExternalServiceError):
        await prov.generate(system="s", user="u")


@pytest.mark.asyncio
async def test_generate_returns_llm_response_with_mock(
    settings_with_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mock AsyncOpenAI.chat.completions.create，驗證 generate 解析 token usage / content。"""
    fake_msg = MagicMock()
    fake_msg.content = "hello world"
    fake_choice = MagicMock()
    fake_choice.message = fake_msg
    fake_choice.finish_reason = "stop"

    fake_usage = MagicMock()
    fake_usage.prompt_tokens = 100
    fake_usage.completion_tokens = 50
    fake_usage.total_tokens = 150

    fake_resp = MagicMock()
    fake_resp.choices = [fake_choice]
    fake_resp.usage = fake_usage

    fake_chat = MagicMock()
    fake_chat.completions = MagicMock()
    fake_chat.completions.create = AsyncMock(return_value=fake_resp)

    fake_client = MagicMock()
    fake_client.chat = fake_chat

    prov = OpenAIProvider(settings_with_key)
    monkeypatch.setattr(prov, "_client", fake_client, raising=False)

    resp = await prov.generate(system="sys", user="ask")
    assert resp.content == "hello world"
    assert resp.usage.input_tokens == 100
    assert resp.usage.output_tokens == 50
    assert resp.usage.total_tokens == 150
    # 100*0.00015/1000 + 50*0.0006/1000 = 0.000015 + 0.00003 = 0.000045
    assert resp.usage.cost_usd == Decimal("0.000045")
    assert resp.model == "gpt-4o-mini"
    assert resp.finish_reason == "stop"
