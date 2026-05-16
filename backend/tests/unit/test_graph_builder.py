"""graph_builder 單元測試 — build_graph + placeholder_manager。

依 PLAN.md 第 14.9 章 + 第 18.2 章 Plugin Pattern + Phase 12 prompt 條 N（≥ 5 個測試）。

注意：不跑真實 LLM；只驗證 graph 結構與 stub Analyst 流。
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents.base_analyst import ANALYST_REGISTRY
from app.agents.graph_builder import (
    build_graph,
    build_initial_state,
    placeholder_manager,
)

pytestmark = pytest.mark.unit


# ── ANALYST_REGISTRY 註冊驗證 ─────────────────────────────


def test_all_four_analysts_registered() -> None:
    """匯入 graph_builder 應觸發 4 個 Analyst 註冊。"""
    expected = {"market", "fundamental", "news", "sentiment"}
    actual = set(ANALYST_REGISTRY.keys()) & expected
    assert actual == expected, f"missing: {expected - actual}"


# ── build_graph 結構 ────────────────────────────────────


def test_build_graph_tw_includes_sentiment() -> None:
    """TW symbol 應含 sentiment node（TW only Analyst）。"""
    g = build_graph("2330", "TWSE", debate_rounds=1)
    nodes = set(g.get_graph().nodes.keys())
    assert "sentiment" in nodes, f"TW graph 應有 sentiment node；nodes={nodes}"
    assert "manager" in nodes


def test_build_graph_us_excludes_sentiment() -> None:
    """US symbol 應不含 sentiment（sentiment 是 TW only）。"""
    g = build_graph("AAPL", "NASDAQ", debate_rounds=1)
    nodes = set(g.get_graph().nodes.keys())
    assert "sentiment" not in nodes, f"US graph 不應含 sentiment；nodes={nodes}"
    assert "market" in nodes
    assert "fundamental" in nodes
    assert "news" in nodes


def test_build_graph_filters_by_analyst_types() -> None:
    """analyst_types 白名單應過濾掉未指定的 Analyst。"""
    g = build_graph("2330", "TWSE", analyst_types=["market"], debate_rounds=0)
    nodes = set(g.get_graph().nodes.keys())
    assert "market" in nodes
    assert "fundamental" not in nodes
    assert "news" not in nodes
    assert "sentiment" not in nodes


def test_build_graph_empty_analyst_types_skips_all_analysts() -> None:
    """analyst_types=[] 不應留下任何 Analyst（manager-only graph 仍能 build）。"""
    g = build_graph("2330", "TWSE", analyst_types=[], debate_rounds=0)
    nodes = set(g.get_graph().nodes.keys())
    assert "manager" in nodes
    # 4 個 Analyst 都不該存在
    for name in ("market", "fundamental", "news", "sentiment"):
        assert name not in nodes


# ── stub graph 跑得起來 ────────────────────────────────


def test_stub_graph_invocation_completes() -> None:
    """跑 stub graph 應在很短時間完成（無 LLM call）。"""
    g = build_graph("2330", "TWSE", analyst_types=["market"], debate_rounds=0)
    state = build_initial_state(
        symbol="2330",
        market="TWSE",
        analysis_id="00000000-0000-0000-0000-000000000001",
        trace_id="trace-t",
        analyst_types=["market"],
        llm_model="gemini-2.0-flash",
        debate_rounds=0,
    )
    final = asyncio.run(g.ainvoke(state))
    # stub 應寫進 analyses["market"]
    assert "market" in final.get("analyses", {})
    assert "[stub]" in final["analyses"]["market"]
    # placeholder_manager 應 fill report_md
    assert final.get("report_md") and "[stub]" in final["report_md"]
    # placeholder signal
    assert (final.get("signal") or {}).get("action") == "HOLD"


# ── placeholder_manager 單元 ─────────────────────────────


def test_placeholder_manager_builds_report() -> None:
    state = build_initial_state(
        symbol="2330",
        market="TWSE",
        analysis_id="00000000-0000-0000-0000-000000000002",
        trace_id="trace-q",
        analyst_types=["market"],
        llm_model="gemini-2.0-flash",
        debate_rounds=0,
    )
    state["analyses"] = {"market": "技術面內容 X"}
    result = asyncio.run(placeholder_manager(state))
    assert "report_md" in result
    assert "技術面內容 X" in result["report_md"]
    assert result["signal"]["action"] == "HOLD"
