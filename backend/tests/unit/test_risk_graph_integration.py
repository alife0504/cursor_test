"""完整風險架構 hermetic 整合測試 — 用 FakeLLM 把整條 risk 鏈跑到底（免真實 API / 配額）。

驗證：build_graph(risk_rounds=1) 的 trader → 積極/保守/中立風險辯論 → RiskManager → Verifier
全部執行、各 schema 都能解析、最終 signal 與報告正確產出。
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import pytest

from app.agents.graph_builder import build_graph, build_initial_state
from app.llm.base_provider import LLMResponse, TokenUsage

pytestmark = pytest.mark.unit

_LONG_ZH = "這是一段足夠長的繁體中文決策理由，用於通過 schema 的最小長度限制。" * 6


def _json_block(payload: str) -> str:
    return f"```json\n{payload}\n```"


class FakeLLM:
    """依 system prompt 內含的 schema 欄位名，回傳對應的 canned 合法 JSON。"""

    name = "fake"
    default_model = "fake-model"

    async def generate(
        self,
        system: str,
        user: str,
        *,
        tools: Any = None,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> LLMResponse:
        if "stance_action" in system:  # RiskArgument
            content = _json_block(
                '{"stance":"neutral","stance_action":"BUY","points":["論點一","論點二"],'
                '"confidence":60}'
            )
        elif "suggested_position_pct" in system:  # TraderProposal
            content = _json_block(
                '{"action":"BUY","conviction":65,"suggested_position_pct":10,'
                f'"rationale_zh":"{_LONG_ZH}","key_risks":["風險一"]}}'
            )
        elif "debate_winner" in system:  # FinalSignal（research/risk manager）
            content = _json_block(
                '{"action":"BUY","confidence":68,"target_price_low":"100",'
                '"target_price_high":"120","stop_loss":"90","time_horizon":"中期(1-3月)",'
                f'"position_size_pct":10,"reasoning_zh":"{_LONG_ZH}",'
                '"risk_factors":["風險一"],"debate_winner":"neutral"}'
            )
        elif "evidence_from" in system:  # Bull/BearArgument
            content = _json_block(
                '{"points":["論點一","論點二","論點三"],"confidence":60,"evidence_from":["market"]}'
            )
        else:
            content = _json_block('{"note":"unmatched"}')

        return LLMResponse(
            content=content,
            tool_calls=[],
            usage=TokenUsage(
                input_tokens=10, output_tokens=10, total_tokens=20, cost_usd=Decimal("0")
            ),
            model=self.default_model,
            finish_reason="stop",
        )


def test_full_risk_architecture_runs_to_completion() -> None:
    """risk_rounds=1：整條 trader→風險辯論→risk_manager→verifier 跑到底並產出最終決策。"""
    llm = FakeLLM()
    # tools=None → analysts 走 stub（不打 LLM）；risk 鏈用 FakeLLM
    g = build_graph(
        "2330",
        "TWSE",
        analyst_types=["market", "fundamental"],
        debate_rounds=1,
        risk_rounds=1,
        llm=llm,
        tools=None,
    )
    state = build_initial_state(
        symbol="2330",
        market="TWSE",
        analysis_id="",  # 空字串 → 跳過 DB usage / streaming，hermetic
        trace_id="t",
        analyst_types=["market", "fundamental"],
        llm_model="fake-model",
        debate_rounds=1,
    )
    final = asyncio.run(g.ainvoke(state, config={"recursion_limit": 50}))

    # trader 提案產生
    assert final.get("trader_proposal"), "trader_proposal 應產生"
    assert final["trader_proposal"]["action"] in ("BUY", "HOLD", "SELL")

    # 風險辯論 1 輪 = 3 位（積極/保守/中立）
    assert len(final.get("risk_debate_history") or []) == 3, "風險辯論應有 3 筆（1 輪×3 立場）"

    # 最終 signal（risk_manager → verifier 調整後）
    sig = final.get("signal") or {}
    assert sig.get("action") in ("BUY", "HOLD", "SELL")
    assert "verification" in sig, "Verifier 應已介入並寫入 verification"

    # 報告含完整架構區塊
    report = final.get("report_md") or ""
    assert "完整風險架構" in report
    assert "風險辯論紀錄" in report
    assert "交易員提案" in report
    assert "接地查核" in report  # (b) Verifier 查核結果已附進報告
