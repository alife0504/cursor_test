"""BaseRiskAnalyst — 風險辯論員共用基底（積極/保守/中立）。

還原原版 risk_mgmt 的 aggressive/conservative/neutral debator；TW 化為：
- 繁中 + 台股脈絡 + 嚴格接地（只引用所提供資料）。
- 結構化輸出 RiskArgument（每方明確表態 stance_action + 證據點 + confidence），
  避免純自由文字辯論造成的失真。

每位風險分析師讀：trader_proposal（被辯論的對象）+ analyses + 對手上一輪論點 + 自己歷史，
累積到 state.risk_debate_history 與各自的 *_arguments。
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, ClassVar

from app.agents.llm_helpers import llm_call_with_schema, record_llm_usage
from app.agents.prompts_loader import load_prompt
from app.agents.schemas import RiskArgument
from app.agents.state import AgentState, resolve_agent_model
from app.core.database import rw_session
from app.core.logging_config import get_logger
from app.llm.base_provider import BaseLLMProvider, TokenUsage

logger = get_logger(__name__)

_STANCE_ZH = {
    "aggressive": "積極型",
    "conservative": "保守型",
    "neutral": "中立型",
}


class BaseRiskAnalyst:
    """風險辯論員基底。子類設定 stance / system_prompt_name / arguments_key。"""

    stance: ClassVar[str] = "base"
    system_prompt_name: ClassVar[str] = ""
    arguments_key: ClassVar[str] = ""

    def __init__(self, llm: BaseLLMProvider | None = None) -> None:
        if llm is None:
            raise RuntimeError(f"{type(self).__name__} 需要注入 llm")
        self.llm = llm

    async def argue(self, state: AgentState) -> dict[str, Any]:
        analysis_id = state.get("analysis_id")
        own = state.get(self.arguments_key) or []
        round_num = len(own) + 1

        user_prompt = _render_risk_user(state, self.stance)
        system_prompt = load_prompt(self.system_prompt_name)

        t0 = time.monotonic()
        degraded = False
        try:
            result, usage = await llm_call_with_schema(
                self.llm,
                system_prompt,
                user_prompt,
                RiskArgument,
                model=resolve_agent_model(state, self.stance),
                max_tokens=1200,
                temperature=0.5,
            )
        except Exception as exc:
            # 優雅降級：單一風險辯論員失敗不該炸掉整次昂貴分析；補一筆保守 HOLD
            # placeholder（不計入有效票），讓辯論迴圈與後續 RiskManager 續行。
            logger.warning(
                "risk_analyst.degraded", stance=self.stance, round=round_num, error=str(exc)
            )
            result = RiskArgument(
                stance=self.stance,  # type: ignore[arg-type]
                stance_action="HOLD",
                points=[
                    f"⚠️ {_STANCE_ZH.get(self.stance, self.stance)}風險評估產生失敗，"
                    "本輪採保守 HOLD 立場（不應視為有效風險票）。",
                    "建議待資料源/模型恢復後重跑以取得完整風險辯論。",
                ],
                confidence=20,
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
                        purpose=f"risk.{self.stance}.round{round_num}",
                        latency_ms=latency_ms,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning(
                    "risk_analyst.usage_record_failed", stance=self.stance, error=str(exc)
                )

        arg_json = result.model_dump_json()
        logger.info(
            "risk_analyst.done",
            stance=self.stance,
            round=round_num,
            stance_action=result.stance_action,
            confidence=result.confidence,
            tokens=usage.total_tokens,
        )

        return {
            self.arguments_key: [arg_json],
            "risk_debate_history": [
                {"stance": self.stance, "round": round_num, "content": arg_json}
            ],
            "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0)
            + usage.total_tokens,
        }


def _latest_of(history: list[dict[str, Any]], stance: str) -> str:
    for h in reversed(history):
        if h.get("stance") == stance:
            return str(h.get("content", ""))
    return "(尚未發言)"


def _render_risk_user(state: AgentState, stance: str) -> str:
    analyses = state.get("analyses") or {}
    trader = state.get("trader_proposal") or {}
    history = state.get("risk_debate_history") or []

    analyses_text = "\n\n".join(f"### {name}\n{txt}" for name, txt in analyses.items())
    if not analyses_text:
        analyses_text = "(無分析師結論)"

    others = [s for s in ("aggressive", "conservative", "neutral") if s != stance]
    opponents = "\n\n".join(
        f"**{_STANCE_ZH.get(o, o)}（{o}）上一輪**：\n{_latest_of(history, o)}" for o in others
    )

    import json as _json

    trader_text = _json.dumps(trader, ensure_ascii=False, indent=2) if trader else "(無交易提案)"

    return (
        f"## 個股\n- 代號：{state.get('symbol', '?')}\n- 市場：{state.get('market_code', '?')}\n\n"
        f"## 被評估的交易提案（Trader）\n```json\n{trader_text}\n```\n\n"
        f"## 分析師結論\n{analyses_text}\n\n"
        f"## 對手上一輪論點\n{opponents}\n\n"
        f"## 你的任務\n以「{_STANCE_ZH.get(stance, stance)}」立場評估上述交易提案，"
        "回應對手論點，並依 RiskArgument schema 結構化輸出。"
    )


__all__ = ["BaseRiskAnalyst"]
