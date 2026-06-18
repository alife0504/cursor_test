"""風險層終結節點優雅降級測試。

驗證 LLM／schema 失敗時，trader / 風險辯論員 / RiskManager 會 salvage 成保守結果，
而非拋出例外炸掉整次（昂貴的）分析。對應「穩定性：不可隨意中斷服務」需求。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app.agents.managers.risk_manager import RiskManager, _salvage_final_signal
from app.agents.risk_mgmt import AggressiveRiskAnalyst
from app.agents.trader import Trader

pytestmark = pytest.mark.unit


class RaisingLLM:
    """generate 永遠拋例外 → 觸發節點 salvage 路徑。"""

    name = "raising"
    default_model = "raising-model"
    last_used_model = None

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("simulated LLM failure")


def _state(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "symbol": "2330",
        "market_code": "TWSE",
        "region": "TW",
        "analysis_id": "",  # 空字串 → 跳過 DB usage 記錄，hermetic
        "user_id": "",
        "analyses": {},
        "investment_plan": "研究計畫",
        "trader_proposal": None,
        "risk_debate_history": [],
        "past_context": "",
        "report_md": "# 既有報告",
        "signal": None,
        "llm_usage_total_tokens": 0,
    }
    base.update(over)
    return base


def test_salvage_reuses_tentative_and_caps_confidence() -> None:
    state = _state(signal={"action": "BUY", "confidence": 90, "reasoning_zh": "x"})
    sig, report = _salvage_final_signal(state, "boom")
    assert sig["action"] == "BUY"  # 沿用研究經理暫定
    assert sig["confidence"] <= 50  # 下修信心
    assert sig["degraded"] is True
    assert "風險經理降級" in report


def test_salvage_holds_when_no_tentative() -> None:
    sig, _report = _salvage_final_signal(_state(signal=None), "boom")
    assert sig["action"] == "HOLD"
    assert sig["degraded"] is True


def test_trader_degrades_to_hold_on_llm_failure() -> None:
    out = asyncio.run(Trader(llm=RaisingLLM()).propose(_state()))
    assert out["trader_proposal"]["action"] == "HOLD"
    assert out["trader_proposal"]["conviction"] <= 30


def test_risk_debator_degrades_to_hold_on_llm_failure() -> None:
    out = asyncio.run(AggressiveRiskAnalyst(llm=RaisingLLM()).argue(_state()))
    history = out["risk_debate_history"]
    assert len(history) == 1
    arg = json.loads(history[0]["content"])
    assert arg["stance_action"] == "HOLD"


def test_risk_manager_synthesize_salvages_on_llm_failure() -> None:
    state = _state(signal={"action": "SELL", "confidence": 80, "reasoning_zh": "x"})
    out = asyncio.run(RiskManager(llm=RaisingLLM()).synthesize(state))
    assert out["signal"]["action"] == "SELL"  # 沿用暫定，不炸掉整圖
    assert out["signal"]["confidence"] <= 50
    assert "降級" in (out["report_md"] or "")
