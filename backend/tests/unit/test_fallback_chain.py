"""LLMFallbackChain 單元測試 — PLAN 14.4。

包含：
- primary 成功時直接回（不切 fallback）
- primary 失敗 → 切到 fallback 第一個
- CB OPEN 的 provider 直接跳過
- 全部 fail → raise ExternalServiceError
- record_success 重置 CB
- generate (BaseLLMProvider 相容介面) 回 LLMResponse
- chain 中 fallback 順序裡的 provider 不存在 → 跳過（不 raise）
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.errors import ExternalServiceError
from app.llm.base_provider import LLMResponse, TokenUsage
from app.llm.fallback_chain import FALLBACK_CHAIN, LLMFallbackChain

pytestmark = pytest.mark.unit


class _FakeCB:
    """async-mock 友善的 CircuitBreaker stub。"""

    def __init__(self, state: str = "CLOSED") -> None:
        self._state = state
        self.record_success = AsyncMock()
        self.record_failure = AsyncMock()

    @property
    def state(self) -> str:
        return self._state

    def set_state(self, s: str) -> None:
        self._state = s


class _FakeProvider:
    """假 provider — 控制 generate 是否拋；自帶 cb。"""

    def __init__(self, name: str, *, raise_exc: BaseException | None = None) -> None:
        self.name = name
        self.default_model = f"{name}-model"
        self.cb = _FakeCB()
        self._raise = raise_exc
        self.call_count = 0

    async def generate(
        self,
        system: str,
        user: str,
        *,
        tools: Any = None,
        model: Any = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> LLMResponse:
        self.call_count += 1
        if self._raise is not None:
            raise self._raise
        return LLMResponse(
            content=f"reply from {self.name}",
            tool_calls=[],
            usage=TokenUsage(
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                cost_usd=Decimal("0.001"),
            ),
            model=self.default_model,
            finish_reason="stop",
        )

    async def health_check(self) -> bool:
        return self._raise is None


def test_fallback_chain_map_matches_plan() -> None:
    """PLAN 14.4：google → openai → anthropic（互相對稱）。"""
    assert FALLBACK_CHAIN["google"] == ["openai", "anthropic"]
    assert FALLBACK_CHAIN["openai"] == ["google", "anthropic"]
    assert FALLBACK_CHAIN["anthropic"] == ["google", "openai"]


@pytest.mark.asyncio
async def test_uses_primary_when_healthy() -> None:
    g = _FakeProvider("google")
    o = _FakeProvider("openai")
    chain = LLMFallbackChain({"google": g, "openai": o}, primary="google")
    resp, used = await chain.generate_with_chain("google", "s", "u")
    assert used == "google"
    assert resp.content == "reply from google"
    assert g.call_count == 1 and o.call_count == 0
    g.cb.record_success.assert_awaited_once()


@pytest.mark.asyncio
async def test_falls_back_when_primary_raises() -> None:
    g = _FakeProvider("google", raise_exc=RuntimeError("gemini down"))
    o = _FakeProvider("openai")
    chain = LLMFallbackChain({"google": g, "openai": o}, primary="google")
    resp, used = await chain.generate_with_chain("google", "s", "u")
    assert used == "openai"
    assert resp.content == "reply from openai"
    g.cb.record_failure.assert_awaited_once()
    o.cb.record_success.assert_awaited_once()


@pytest.mark.asyncio
async def test_skips_open_circuit_breakers() -> None:
    g = _FakeProvider("google")
    g.cb.set_state("OPEN")  # OPEN → 跳過
    o = _FakeProvider("openai")
    chain = LLMFallbackChain({"google": g, "openai": o}, primary="google")
    _resp, used = await chain.generate_with_chain("google", "s", "u")
    assert used == "openai"
    assert g.call_count == 0


@pytest.mark.asyncio
async def test_raises_when_all_fail() -> None:
    g = _FakeProvider("google", raise_exc=RuntimeError("g fail"))
    o = _FakeProvider("openai", raise_exc=RuntimeError("o fail"))
    a = _FakeProvider("anthropic", raise_exc=RuntimeError("a fail"))
    chain = LLMFallbackChain({"google": g, "openai": o, "anthropic": a}, primary="google")
    with pytest.raises(ExternalServiceError):
        await chain.generate_with_chain("google", "s", "u")


@pytest.mark.asyncio
async def test_records_success_resets_cb() -> None:
    g = _FakeProvider("google")
    chain = LLMFallbackChain({"google": g}, primary="google")
    await chain.generate_with_chain("google", "s", "u")
    assert g.cb.record_success.await_count == 1


@pytest.mark.asyncio
async def test_used_provider_name_returned_and_cached() -> None:
    g = _FakeProvider("google", raise_exc=RuntimeError("down"))
    a = _FakeProvider("anthropic")
    # primary=openai 不在 chain，跳過後接 google（fail）→ anthropic（success）
    chain = LLMFallbackChain({"google": g, "anthropic": a}, primary="openai")
    _resp, used = await chain.generate_with_chain("openai", "s", "u")
    assert used == "anthropic"
    assert chain.last_used_provider == "anthropic"
    # name property 動態反映
    assert chain.name == "anthropic"


@pytest.mark.asyncio
async def test_chain_respects_no_provider_for_chained_one() -> None:
    """primary 為 google，fallback 鏈中 openai 未配置 → 跳過 openai，試 anthropic。"""
    g = _FakeProvider("google", raise_exc=RuntimeError("g fail"))
    a = _FakeProvider("anthropic")
    # openai 不在 providers dict
    chain = LLMFallbackChain({"google": g, "anthropic": a}, primary="google")
    resp, used = await chain.generate_with_chain("google", "s", "u")
    assert used == "anthropic"
    assert resp.content == "reply from anthropic"


@pytest.mark.asyncio
async def test_generate_compatibility_interface() -> None:
    """LLMFallbackChain.generate(system, user) 對 BaseLLMProvider 介面相容。"""
    g = _FakeProvider("google")
    chain = LLMFallbackChain({"google": g}, primary="google")
    resp = await chain.generate("s", "u")
    assert isinstance(resp, LLMResponse)
    assert chain.last_used_provider == "google"


# ── 暫時性錯誤退避重試（v1.1；上游 v0.3.1 llm_max_retries）────────


class _FlakyProvider(_FakeProvider):
    """前 fail_times 次拋暫時性錯誤，之後成功。"""

    def __init__(self, name: str, *, fail_times: int, exc: BaseException) -> None:
        super().__init__(name)
        self._fail_times = fail_times
        self._exc = exc

    async def generate(self, *args: Any, **kwargs: Any) -> LLMResponse:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            raise self._exc
        return LLMResponse(
            content=f"reply from {self.name}",
            tool_calls=[],
            usage=TokenUsage(
                input_tokens=10, output_tokens=5, total_tokens=15, cost_usd=Decimal("0.001")
            ),
            model=self.default_model,
            finish_reason="stop",
        )


@pytest.mark.asyncio
async def test_transient_error_retries_same_provider_then_succeeds() -> None:
    """429 暫時性錯誤 → 同 provider 退避重試後成功（單一 provider 也能撐住）。"""
    g = _FlakyProvider("google", fail_times=2, exc=RuntimeError("429 rate limit exceeded"))
    chain = LLMFallbackChain({"google": g}, primary="google", max_retries=2, retry_base_delay=0.0)
    resp, used = await chain.generate_with_chain("google", "s", "u")
    assert used == "google"
    assert resp.content == "reply from google"
    assert g.call_count == 3  # 2 次失敗 + 第 3 次成功


@pytest.mark.asyncio
async def test_transient_error_exhausts_retries_and_raises() -> None:
    """單一 provider 持續 429 → 用盡重試（call_count == max_retries+1）後 raise。"""
    g = _FakeProvider("google", raise_exc=RuntimeError("503 service unavailable"))
    chain = LLMFallbackChain({"google": g}, primary="google", max_retries=2, retry_base_delay=0.0)
    with pytest.raises(ExternalServiceError):
        await chain.generate_with_chain("google", "s", "u")
    assert g.call_count == 3


@pytest.mark.asyncio
async def test_non_transient_error_not_retried() -> None:
    """非暫時性錯誤（schema/程式錯）→ 不重試，直接算失敗（call_count == 1）。"""
    g = _FakeProvider("google", raise_exc=ValueError("bad schema"))
    o = _FakeProvider("openai")
    chain = LLMFallbackChain(
        {"google": g, "openai": o}, primary="google", max_retries=2, retry_base_delay=0.0
    )
    _resp, used = await chain.generate_with_chain("google", "s", "u")
    assert used == "openai"
    assert g.call_count == 1  # 不重試
