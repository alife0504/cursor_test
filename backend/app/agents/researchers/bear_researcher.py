"""BearResearcher — 多輪看空研究員（鏡像 Bull）。"""

from __future__ import annotations

import time
from typing import Any

from app.agents.llm_helpers import llm_call_with_schema, record_llm_usage
from app.agents.prompts_loader import load_prompt, render_template
from app.agents.researchers.bull_researcher import _format_analyses
from app.agents.schemas import BearArgument
from app.agents.state import AgentState
from app.core.database import rw_session
from app.core.logging_config import get_logger
from app.llm.base_provider import BaseLLMProvider

logger = get_logger(__name__)


class BearResearcher:
    role: str = "bear"

    def __init__(self, llm: BaseLLMProvider | None = None) -> None:
        if llm is None:
            raise RuntimeError("BearResearcher 需要注入 llm")
        self.llm = llm

    async def argue(self, state: AgentState) -> dict[str, Any]:
        analyses = state.get("analyses") or {}
        debate_history = state.get("debate_history") or []
        bear_args = state.get("bear_arguments") or []
        symbol = state.get("symbol", "?")
        analysis_id = state.get("analysis_id")
        total_rounds = int(state.get("debate_rounds", 1) or 1)
        round_num = len(bear_args) + 1

        # 對手最新 (bull)
        opponent_block = "(本輪為第一輪，對方尚未發言)"
        for h in reversed(debate_history):
            if h.get("role") == "bull":
                opponent_block = f"Bull（第 {h.get('round')} 輪）：\n{h.get('content', '')}"
                break

        self_history_block = "(無)"
        if bear_args:
            self_history_block = "\n---\n".join(
                f"Bear 第 {i + 1} 輪：{a}" for i, a in enumerate(bear_args)
            )

        user_prompt = render_template(
            "debate_template",
            symbol=symbol,
            company_name=symbol,
            market=state.get("market_code", "?"),
            analyses_block=_format_analyses(analyses),
            round_num=round_num,
            total_rounds=total_rounds,
            role="bear",
            opponent_block=opponent_block,
            self_history_block=self_history_block,
        )
        system_prompt = load_prompt("bear_researcher_system")

        t0 = time.monotonic()
        result, usage = await llm_call_with_schema(
            self.llm,
            system_prompt,
            user_prompt,
            BearArgument,
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
                        user_id=None,
                        provider=self.llm.name,
                        model=getattr(self.llm, "default_model", "unknown"),
                        usage=usage,
                        purpose=f"debate.bear.round{round_num}",
                        latency_ms=latency_ms,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("bear_researcher.usage_record_failed", error=str(exc))

        argument_json = result.model_dump_json()
        logger.info(
            "researcher.bear.done",
            symbol=symbol,
            round=round_num,
            confidence=result.confidence,
            tokens=usage.total_tokens,
        )

        return {
            "bear_arguments": [argument_json],
            "debate_history": [
                {
                    "role": "bear",
                    "round": round_num,
                    "content": argument_json,
                    "tokens": usage.total_tokens,
                }
            ],
            "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0)
            + usage.total_tokens,
        }


__all__ = ["BearResearcher"]
