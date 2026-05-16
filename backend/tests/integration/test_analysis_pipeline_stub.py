"""end-to-end stub pipeline 整合測試 — graph → stub Analyst → manager → report_md。

依 Phase 12 prompt 條 Q（≥ 3 個測試）+ PLAN 14.9 章。

⚠️ Stub 測試：不打 LLM、不打 DB；只驗整條 langgraph 流程能跑完並寫合理欄位。
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.agents.graph_builder import build_graph, build_initial_state

pytestmark = pytest.mark.integration


def _state(symbol: str, market: str, analyst_types: list[str] | None = None) -> dict:
    return build_initial_state(
        symbol=symbol,
        market=market,
        analysis_id="00000000-0000-0000-0000-000000000099",
        trace_id="trace-stub",
        analyst_types=analyst_types,
        llm_model="gemini-2.0-flash",
        debate_rounds=1,
    )


def test_tw_pipeline_includes_all_four_analysts() -> None:
    """TW 跑完整 pipeline → analyses 應有 market/fundamental/news/sentiment 四個 key。"""
    g = build_graph("2330", "TWSE", debate_rounds=1)
    state = _state("2330", "TWSE")
    final = asyncio.run(g.ainvoke(state))
    analyses = final.get("analyses") or {}
    assert set(analyses.keys()) >= {"market", "fundamental", "news", "sentiment"}
    # 每個 Analyst 都應產出 [stub] 字串
    for name in ("market", "fundamental", "news", "sentiment"):
        assert "[stub]" in analyses[name], f"{name} 應為 stub 輸出"
    # placeholder_manager 應產出 report_md（且含 [stub] 標籤）
    assert final.get("report_md")
    assert "[stub]" in final["report_md"]


def test_us_pipeline_excludes_sentiment() -> None:
    """US 跑完整 pipeline → analyses 不應含 sentiment。"""
    g = build_graph("AAPL", "NASDAQ", debate_rounds=1)
    state = _state("AAPL", "NASDAQ")
    final = asyncio.run(g.ainvoke(state))
    analyses = final.get("analyses") or {}
    assert "sentiment" not in analyses
    # market/fundamental/news 必須有
    assert {"market", "fundamental", "news"}.issubset(analyses.keys())
    assert final.get("report_md")


def test_pipeline_writes_signal_and_started_at() -> None:
    """跑完應寫進 placeholder signal（action=HOLD）+ 保留 started_at。"""
    g = build_graph("2330", "TWSE", analyst_types=["market"], debate_rounds=0)
    state = _state("2330", "TWSE", analyst_types=["market"])
    started_at = state["started_at"]
    final = asyncio.run(g.ainvoke(state))
    # signal 必須寫
    signal = final.get("signal") or {}
    assert signal.get("action") == "HOLD"
    assert signal.get("confidence") == 50
    # started_at 不應在 graph 中被覆寫
    assert final.get("started_at") == started_at
    # ISO 格式
    datetime.fromisoformat(final["started_at"])


def test_pipeline_empty_analyst_types_still_completes() -> None:
    """analyst_types=[] → graph 仍應跑完（只有 manager），report_md 含「無 Analyst 結果」。"""
    g = build_graph("2330", "TWSE", analyst_types=[], debate_rounds=0)
    state = _state("2330", "TWSE", analyst_types=[])
    final = asyncio.run(g.ainvoke(state))
    # 沒 analyst → analyses 是空 dict
    assert final.get("analyses") == {} or final.get("analyses") is None
    assert "無 Analyst" in (final.get("report_md") or "")
