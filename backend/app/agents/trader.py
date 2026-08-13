"""Trader — 把 ResearchManager 的研究計畫轉成具體交易提案（還原原版 trader）。

設計：
- 吃 state.investment_plan（研究計畫）+ state.analyses（四位分析師結論）。
- LLM 結構化輸出 TraderProposal（BUY/HOLD/SELL + 建議部位 %）。
- 寫 state.trader_proposal，供風險辯論團隊評估。
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from app.agents.llm_helpers import llm_call_with_schema, record_llm_usage
from app.agents.prompts_loader import load_prompt
from app.agents.schemas import TraderProposal
from app.agents.state import AgentState, resolve_agent_model
from app.core.database import rw_session
from app.core.logging_config import get_logger
from app.llm.base_provider import BaseLLMProvider, TokenUsage

logger = get_logger(__name__)


class Trader:
    """單例 Trader — 跑 propose() 一次。"""

    role: str = "trader"

    def __init__(self, llm: BaseLLMProvider | None = None) -> None:
        if llm is None:
            raise RuntimeError("Trader 需要注入 llm")
        self.llm = llm

    async def propose(self, state: AgentState) -> dict[str, Any]:
        symbol = state.get("symbol", "?")
        analysis_id = state.get("analysis_id")

        user_prompt = _render_trader_user(state)
        system_prompt = load_prompt("trader_system")

        t0 = time.monotonic()
        degraded = False
        try:
            result, usage = await llm_call_with_schema(
                self.llm,
                system_prompt,
                user_prompt,
                TraderProposal,
                model=resolve_agent_model(state, "trader"),
                max_tokens=1500,
                temperature=0.3,
            )
        except Exception as exc:
            # 優雅降級：交易員提案失敗不該炸掉整次昂貴分析；以保守 HOLD、零部位占位，
            # 交由風險團隊與 RiskManager 續行（最終仍走人工核准）。
            logger.warning("trader.degraded", symbol=symbol, error=str(exc))
            result = TraderProposal(
                action="HOLD",
                conviction=20,
                suggested_position_pct=Decimal("0"),
                rationale_zh=(
                    "⚠️ 交易員提案產生失敗（LLM 或 schema 驗證未通過），為避免中斷整體分析，"
                    "暫以保守 HOLD、零部位作為占位提案，交由風險團隊與風險經理續行評估；"
                    "建議待資料源／模型恢復後重跑以取得正式交易提案。"
                ),
                key_risks=["交易員提案降級為占位 HOLD，未反映真實風險評估"],
            )
            usage = TokenUsage(
                input_tokens=0, output_tokens=0, total_tokens=0, cost_usd=Decimal("0")
            )
            degraded = True
        latency_ms = int((time.monotonic() - t0) * 1000)

        if analysis_id and not degraded:
            try:
                async with rw_session() as session:
                    await record_llm_usage(
                        session,
                        analysis_id=analysis_id,
                        user_id=state.get("user_id"),
                        provider=self.llm.name,
                        model=(
                            getattr(self.llm, "last_used_model", None)
                            or getattr(self.llm, "default_model", "unknown")
                        ),
                        usage=usage,
                        purpose="trader.propose",
                        latency_ms=latency_ms,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("trader.usage_record_failed", error=str(exc))

        logger.info(
            "trader.done",
            symbol=symbol,
            action=result.action,
            conviction=result.conviction,
            position_pct=str(result.suggested_position_pct),
            tokens=usage.total_tokens,
        )

        return {
            "trader_proposal": result.model_dump(mode="json"),
            "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0)
            + usage.total_tokens,
        }


def _render_trader_user(state: AgentState) -> str:
    analyses = state.get("analyses") or {}
    plan = state.get("investment_plan") or "(無研究計畫)"
    analyses_text = "\n\n".join(f"### {name}\n{txt}" for name, txt in analyses.items())
    if not analyses_text:
        analyses_text = "(無分析師結論)"
    return (
        f"## 個股\n- 代號：{state.get('symbol', '?')}\n"
        f"- 市場：{state.get('market_code', '?')}\n\n"
        f"## 研究經理的研究計畫\n{plan}\n\n"
        f"## 分析師結論\n{analyses_text}\n\n"
        "## 你的任務\n請依研究計畫與分析師結論，提出具體交易提案，並依 TraderProposal schema 結構化輸出。"
    )


__all__ = ["Trader"]
