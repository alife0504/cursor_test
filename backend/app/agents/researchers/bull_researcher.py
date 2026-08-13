"""BullResearcher — 多輪看多研究員。

P13 設計：
- 吃 state.analyses（各 analyst 結論 JSON 字串）+ state.debate_history（對方上一輪）
- LLM 結構化輸出 BullArgument
- 累積到 state.bull_arguments + state.debate_history
"""

from __future__ import annotations

import time
from typing import Any

from app.agents.llm_helpers import llm_call_with_schema, record_llm_usage
from app.agents.prompts_loader import load_prompt, render_template
from app.agents.schemas import BullArgument
from app.agents.state import AgentState, resolve_agent_model
from app.core.database import rw_session
from app.core.logging_config import get_logger
from app.llm.base_provider import BaseLLMProvider

logger = get_logger(__name__)


class BullResearcher:
    """單例 Researcher — 每次呼叫 argue() 跑一輪辯論。"""

    role: str = "bull"

    def __init__(self, llm: BaseLLMProvider | None = None) -> None:
        if llm is None:
            raise RuntimeError("BullResearcher 需要注入 llm")
        self.llm = llm

    async def argue(self, state: AgentState) -> dict[str, Any]:
        analyses = state.get("analyses") or {}
        debate_history = state.get("debate_history") or []
        bull_args = state.get("bull_arguments") or []
        symbol = state.get("symbol", "?")
        analysis_id = state.get("analysis_id")
        total_rounds = int(state.get("debate_rounds", 1) or 1)
        round_num = len(bull_args) + 1

        # 對手上一輪 (bear)
        opponent_block = "(本輪為第一輪，對方尚未發言)"
        for h in reversed(debate_history):
            if h.get("role") == "bear":
                opponent_block = f"Bear（第 {h.get('round')} 輪）：\n{h.get('content', '')}"
                break

        self_history_block = "(無)"
        if bull_args:
            self_history_block = "\n---\n".join(
                f"Bull 第 {i + 1} 輪：{a}" for i, a in enumerate(bull_args)
            )

        analyses_block = _format_analyses(analyses)

        user_prompt = render_template(
            "debate_template",
            symbol=symbol,
            company_name=symbol,  # 多輪辯論不一定要 fetch company_info；保留 symbol 足夠
            market=state.get("market_code", "?"),
            analyses_block=analyses_block,
            round_num=round_num,
            total_rounds=total_rounds,
            role="bull",
            opponent_block=opponent_block,
            self_history_block=self_history_block,
        )
        system_prompt = load_prompt("bull_researcher_system")

        t0 = time.monotonic()
        result, usage = await llm_call_with_schema(
            self.llm,
            system_prompt,
            user_prompt,
            BullArgument,
            model=resolve_agent_model(state, "bull"),
            max_tokens=1500,
            temperature=0.5,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        if analysis_id:
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
                        purpose=f"debate.bull.round{round_num}",
                        latency_ms=latency_ms,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("bull_researcher.usage_record_failed", error=str(exc))

        argument_json = result.model_dump_json()
        logger.info(
            "researcher.bull.done",
            symbol=symbol,
            round=round_num,
            confidence=result.confidence,
            tokens=usage.total_tokens,
        )

        return {
            "bull_arguments": [argument_json],
            "debate_history": [
                {
                    "role": "bull",
                    "round": round_num,
                    "content": argument_json,
                    "tokens": usage.total_tokens,
                }
            ],
            "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0)
            + usage.total_tokens,
        }


def _format_analyses(analyses: dict[str, str]) -> str:
    """把各 analyst 結論串成可讀區塊。"""
    if not analyses:
        return "(無分析師結論)"
    parts: list[str] = []
    for name, content in analyses.items():
        parts.append(f"### {name}\n{content}")
    return "\n\n".join(parts)


__all__ = ["BullResearcher"]
