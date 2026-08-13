"""ResearchManager — 綜合所有分析師 + Bull/Bear 辯論 → 結構化最終 signal + report_md。

依 PLAN.md 第 18.2 章 + 第 20.4 章報告產出規範。

設計：
- 不再用 placeholder_manager，本 manager 才是 P13 之後的「真實 manager」。
- 寫 state["signal"] + state["report_md"]，這兩個欄位是 LangGraph 的「終結欄位」。
- 額外把 signal 拆 action / confidence / target_price / stop_loss / take_profit 寫進 DB（在 run_analysis task 內），manager 本身不直接寫 DB。
"""

from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any

from app.agents.llm_helpers import llm_call_with_schema, record_llm_usage
from app.agents.prompts_loader import load_prompt
from app.agents.schemas import FinalSignal
from app.agents.state import AgentState, resolve_agent_model
from app.core.database import rw_session
from app.core.logging_config import get_logger
from app.llm.base_provider import BaseLLMProvider

logger = get_logger(__name__)


class ResearchManager:
    """單例 — 跑 synthesize() 一次。"""

    role: str = "manager"

    def __init__(self, llm: BaseLLMProvider | None = None) -> None:
        if llm is None:
            raise RuntimeError("ResearchManager 需要注入 llm")
        self.llm = llm

    async def synthesize(self, state: AgentState) -> dict[str, Any]:
        symbol = state.get("symbol", "?")
        analysis_id = state.get("analysis_id")
        analyses = state.get("analyses") or {}
        debate_history = state.get("debate_history") or []

        user_prompt = _render_manager_user(state)
        system_prompt = load_prompt("research_manager_system")

        t0 = time.monotonic()
        signal, usage = await llm_call_with_schema(
            self.llm,
            system_prompt,
            user_prompt,
            FinalSignal,
            model=resolve_agent_model(state, "manager"),
            max_tokens=3000,
            temperature=0.3,
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
                        purpose="manager.synthesize",
                        latency_ms=latency_ms,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("manager.usage_record_failed", error=str(exc))

        report_md = _render_report_md(state, signal, analyses, debate_history)

        logger.info(
            "manager.synthesize.done",
            symbol=symbol,
            action=signal.action,
            confidence=signal.confidence,
            debate_winner=signal.debate_winner,
            tokens=usage.total_tokens,
            latency_ms=latency_ms,
        )

        # serialized signal（Decimal → str；保 JSON 友善）
        signal_dict = signal.model_dump(mode="json")

        return {
            "signal": signal_dict,
            "report_md": report_md,
            # 完整架構：研究經理的決策理由即「研究計畫」，供 Trader / 風險團隊使用。
            # 風險層關閉時這個 signal 即最終（向後相容）；開啟時會被 RiskManager 覆寫。
            "investment_plan": signal.reasoning_zh,
            "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0)
            + usage.total_tokens,
        }


# ── render helpers ─────────────────────────────────────


def _render_manager_user(state: AgentState) -> str:
    """組成 manager 的 user prompt。"""
    analyses = state.get("analyses") or {}
    debate_history = state.get("debate_history") or []

    analyses_text = "\n\n".join(f"### {name}\n{txt}" for name, txt in analyses.items())
    if not analyses_text:
        analyses_text = "(無分析師結論)"

    debate_text = "\n\n".join(
        f"**{h.get('role')} 第 {h.get('round')} 輪**：\n{h.get('content', '')}"
        for h in debate_history
    )
    if not debate_text:
        debate_text = "(無辯論記錄)"

    return (
        f"## 個股\n- 代號：{state.get('symbol', '?')}\n"
        f"- 市場：{state.get('market_code', '?')}\n"
        f"- 區域：{state.get('region', '?')}\n\n"
        f"## 分析師結論\n{analyses_text}\n\n"
        f"## Bull/Bear 辯論\n{debate_text}\n\n"
        "## 你的任務\n"
        "請綜合以上所有材料，做出明確的 BUY / HOLD / SELL 決策，並依 FinalSignal schema 結構化輸出。"
    )


def _render_report_md(
    state: AgentState,
    signal: FinalSignal,
    analyses: dict[str, str],
    debate_history: list[dict[str, Any]],
) -> str:
    """產出最終 Markdown 報告。"""
    symbol = state.get("symbol", "?")
    market = state.get("market_code", "?")
    started_at = state.get("started_at", "")

    def _price(v: Decimal | None) -> str:
        return f"{v}" if v is not None else "未提供"

    parts: list[str] = [
        f"# {symbol}（{market}）投資分析報告",
        "",
        f"> 啟動時間：{started_at}",
        f"> 模型：{state.get('llm_model', '')} | 辯論輪數：{state.get('debate_rounds', 0)}",
        "",
        "## 最終建議",
        "",
        f"- **行動**：`{signal.action}`",
        f"- **信心**：{signal.confidence} / 100",
        f"- **時間視野**：{signal.time_horizon}",
        f"- **建議部位**：{signal.position_size_pct}%",
        f"- **目標價區間**：{_price(signal.target_price_low)} ~ {_price(signal.target_price_high)}",
        f"- **停損價**：{_price(signal.stop_loss)}",
        f"- **辯論贏家**：{signal.debate_winner}",
        "",
        "## 決策理由",
        "",
        signal.reasoning_zh,
        "",
        "## 主要風險",
        "",
    ]
    for r in signal.risk_factors:
        parts.append(f"- {r}")
    parts.append("")

    parts.append("## 各分析師結論")
    parts.append("")
    for name, content in analyses.items():
        parts.append(f"### {name}")
        parts.append("")
        parts.extend(_fenced_block(content))

    if debate_history:
        parts.append("## Bull/Bear 辯論紀錄")
        parts.append("")
        for h in debate_history:
            parts.append(f"### {h.get('role')} - Round {h.get('round')}")
            parts.append("")
            parts.extend(_fenced_block(str(h.get("content", ""))))

    return "\n".join(parts)


def _fenced_block(content: str) -> list[str]:
    """把 analyst / 辯論內容包成 Markdown 區塊（含結尾空行）。

    內容是合法 JSON（正常情況）→ 美化後放進 ```json``` 區塊；
    否則（如優雅降級時寫入的「⚠️ 資料不足…」純文字警語）→ 直接純文字，
    避免把中文警語塞進 json fence 造成 Markdown 渲染破版。
    """
    text = content if isinstance(content, str) else str(content)
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError, TypeError):
        return [text, ""]
    pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
    return ["```json", pretty, "```", ""]


__all__ = ["ResearchManager"]
