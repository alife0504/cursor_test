"""state_trim 單元測試 — debate_history 摘要壓縮。

依 PLAN.md 第 14.9 章 + Phase 12 prompt 條 M（≥ 4 個測試）。
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from app.agents.state import make_initial_state
from app.agents.state_trim import (
    MAX_DEBATE_HISTORY,
    MAX_STATE_SIZE_BYTES,
    estimate_state_size,
    trim_debate_history,
)

pytestmark = pytest.mark.unit


def _state_with_history(n: int) -> Any:
    state = make_initial_state(
        symbol="2330",
        market="TWSE",
        region="TW",
        analyst_types=["market"],
        llm_model="gemini-2.0-flash",
        debate_rounds=1,
        trace_id="trace-x",
        analysis_id="00000000-0000-0000-0000-000000000000",
        started_at="2026-05-16T00:00:00+00:00",
    )
    state["debate_history"] = [
        {"role": "bull" if i % 2 == 0 else "bear", "content": f"訊息 #{i}"} for i in range(n)
    ]
    return state


def test_estimate_state_size_returns_positive_int() -> None:
    state = _state_with_history(0)
    size = estimate_state_size(state)
    assert isinstance(size, int)
    assert size > 0
    assert size < MAX_STATE_SIZE_BYTES


@pytest.mark.asyncio
async def test_trim_skips_when_under_threshold() -> None:
    """訊息數 <= MAX_DEBATE_HISTORY → 不應 trim。"""
    state = _state_with_history(MAX_DEBATE_HISTORY)
    new_state = await trim_debate_history(state, llm=None)
    assert new_state["debate_history"] == state["debate_history"]
    assert len(new_state["debate_history"]) == MAX_DEBATE_HISTORY


@pytest.mark.asyncio
async def test_trim_compresses_when_over_threshold_no_llm() -> None:
    """訊息數 > MAX_DEBATE_HISTORY 且無 LLM → 用 fallback 截斷摘要。"""
    state = _state_with_history(10)
    new_state = await trim_debate_history(state, llm=None)
    history = new_state["debate_history"]
    # 1 summary + MAX_DEBATE_HISTORY 筆
    assert len(history) == 1 + MAX_DEBATE_HISTORY
    assert history[0]["role"] == "summary"
    assert history[0]["trimmed_count"] == 10 - MAX_DEBATE_HISTORY
    # 後 N 筆應與原 state 的後 N 筆相同
    assert history[1:] == state["debate_history"][-MAX_DEBATE_HISTORY:]


@pytest.mark.asyncio
async def test_trim_keeps_state_immutable() -> None:
    """trim 應回新 state，不修改傳入。"""
    state = _state_with_history(10)
    original_len = len(state["debate_history"])
    new_state = await trim_debate_history(state, llm=None)
    assert new_state is not state
    assert len(state["debate_history"]) == original_len  # 原 state 未變


@pytest.mark.asyncio
async def test_trim_uses_llm_when_provided() -> None:
    """提供 LLM 時應呼叫 LLM 產 summary。"""
    from decimal import Decimal

    from app.llm.base_provider import LLMResponse, TokenUsage

    class _FakeLLM:
        called_with: ClassVar[dict[str, Any]] = {}

        async def generate(  # type: ignore[no-untyped-def]
            self,
            system: str,
            user: str,
            *,
            tools=None,
            model=None,
            max_tokens=2048,
            temperature=0.3,
        ) -> LLMResponse:
            _FakeLLM.called_with = {"system": system, "user": user, "max_tokens": max_tokens}
            return LLMResponse(
                content="假摘要 OK",
                tool_calls=[],
                usage=TokenUsage(
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                    cost_usd=Decimal("0.0001"),
                ),
                model="fake",
            )

    state = _state_with_history(10)
    new_state = await trim_debate_history(state, llm=_FakeLLM())  # type: ignore[arg-type]
    assert new_state["debate_history"][0]["content"] == "假摘要 OK"
    assert _FakeLLM.called_with["system"]  # 確認被呼叫
