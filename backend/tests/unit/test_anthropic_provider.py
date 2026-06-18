"""AnthropicProvider 單元測試 — pricing / health_check / generate（mock SDK）。

依 PLAN.md 第 14.4 章。
不打真 Anthropic API；用 monkeypatch 替換 client。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from app.core.errors import ExternalServiceError
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base_provider import LLM_PROVIDER_REGISTRY

pytestmark = pytest.mark.unit


@pytest.fixture
def settings_with_key(monkeypatch: pytest.MonkeyPatch) -> Any:
    from app.core.config import settings as _s

    monkeypatch.setattr(_s, "ANTHROPIC_API_KEY", SecretStr("fake-anthropic-key"), raising=False)
    return _s


@pytest.fixture
def settings_without_key(monkeypatch: pytest.MonkeyPatch) -> Any:
    from app.core.config import settings as _s

    monkeypatch.setattr(_s, "ANTHROPIC_API_KEY", None, raising=False)
    return _s


def test_anthropic_registered() -> None:
    assert "anthropic" in LLM_PROVIDER_REGISTRY
    assert LLM_PROVIDER_REGISTRY["anthropic"] is AnthropicProvider


def test_default_model(settings_with_key: Any) -> None:
    prov = AnthropicProvider(settings_with_key)
    assert prov.name == "anthropic"
    assert prov.default_model == "claude-haiku-4-5"


def test_pricing_haiku(settings_with_key: Any) -> None:
    """claude-haiku-4-5：input $1.00/1M, output $5.00/1M。

    1000 input + 500 output → 0.001*1 + 0.005*0.5 = 0.001 + 0.0025 = 0.0035
    """
    prov = AnthropicProvider(settings_with_key)
    cost = prov.calc_cost("claude-haiku-4-5", 1000, 500)
    assert cost == Decimal("0.003500")


def test_pricing_sonnet(settings_with_key: Any) -> None:
    """claude-sonnet-4-6：input $3.00/1M, output $15.00/1M。"""
    prov = AnthropicProvider(settings_with_key)
    cost = prov.calc_cost("claude-sonnet-4-6", 2000, 1000)
    # 0.003 * 2 + 0.015 * 1 = 0.006 + 0.015 = 0.021
    assert cost == Decimal("0.021000")


def test_pricing_unknown(settings_with_key: Any) -> None:
    prov = AnthropicProvider(settings_with_key)
    assert prov.calc_cost("nope", 1000, 500) == Decimal("0")


@pytest.mark.asyncio
async def test_health_check_no_key_false(settings_without_key: Any) -> None:
    prov = AnthropicProvider(settings_without_key)
    assert await prov.health_check() is False


@pytest.mark.asyncio
async def test_generate_no_key_raises(settings_without_key: Any) -> None:
    prov = AnthropicProvider(settings_without_key)
    with pytest.raises(ExternalServiceError):
        await prov.generate(system="s", user="u")


@pytest.mark.asyncio
async def test_generate_parses_content_and_usage(
    settings_with_key: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mock messages.create：驗證 content 從 list[ContentBlock] 抽出 + usage 對。"""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "hello from claude"

    fake_usage = MagicMock()
    fake_usage.input_tokens = 200
    fake_usage.output_tokens = 100

    fake_resp = MagicMock()
    fake_resp.content = [text_block]
    fake_resp.usage = fake_usage
    fake_resp.stop_reason = "end_turn"

    fake_messages = MagicMock()
    fake_messages.create = AsyncMock(return_value=fake_resp)
    fake_client = MagicMock()
    fake_client.messages = fake_messages

    prov = AnthropicProvider(settings_with_key)
    monkeypatch.setattr(prov, "_client", fake_client, raising=False)

    resp = await prov.generate(system="sys", user="ask")
    assert resp.content == "hello from claude"
    assert resp.usage.input_tokens == 200
    assert resp.usage.output_tokens == 100
    assert resp.usage.total_tokens == 300
    # 預設模型 claude-haiku-4-5：200*0.001/1000 + 100*0.005/1000 = 0.0002 + 0.0005 = 0.0007
    assert resp.usage.cost_usd == Decimal("0.000700")
    assert resp.finish_reason == "end_turn"
