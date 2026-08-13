"""RiskManager — 風險經理（還原原版 portfolio_manager）。

綜合「積極/保守/中立三方風險辯論」+ 交易員提案 + 研究計畫 + 歷史教訓（past_context），
產出**最終** FinalSignal（TW 3-level + position_size_pct）+ report_md。

設計：
- 這是完整架構下的「終結 manager」——最終 signal / report_md 由本節點寫（取代風險層關閉時
  ResearchManager 的暫定 signal）。
- 與 ResearchManager 共用 FinalSignal schema；差別在於輸入多了 trader + 風險辯論 + 記憶。
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


class RiskManager:
    """單例 — 跑 synthesize() 一次，產出最終決策。"""

    role: str = "risk_manager"

    def __init__(self, llm: BaseLLMProvider | None = None) -> None:
        if llm is None:
            raise RuntimeError("RiskManager 需要注入 llm")
        self.llm = llm

    async def synthesize(self, state: AgentState) -> dict[str, Any]:
        symbol = state.get("symbol", "?")
        analysis_id = state.get("analysis_id")

        user_prompt = _render_risk_manager_user(state)
        system_prompt = load_prompt("risk_manager_system")

        t0 = time.monotonic()
        try:
            signal, usage = await llm_call_with_schema(
                self.llm,
                system_prompt,
                user_prompt,
                FinalSignal,
                model=resolve_agent_model(state, "risk_manager"),
                max_tokens=3000,
                temperature=0.3,
            )
        except Exception as exc:
            # 終結節點優雅降級：風險經理綜合失敗不該讓整次昂貴分析全毀。回退到
            # 「風險層關閉時」行為——沿用研究經理暫定訊號（下修信心）或保守 HOLD；
            # 後續 Verifier 仍接地查核、最終人工核准。
            logger.warning("risk_manager.degraded", symbol=symbol, error=str(exc))
            salvage_signal, salvage_report = _salvage_final_signal(state, str(exc))
            return {
                "signal": salvage_signal,
                "report_md": salvage_report,
                "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0),
            }
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
                        purpose="risk_manager.synthesize",
                        latency_ms=latency_ms,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("risk_manager.usage_record_failed", error=str(exc))

        report_md = _render_risk_report_md(state, signal)

        logger.info(
            "risk_manager.synthesize.done",
            symbol=symbol,
            action=signal.action,
            confidence=signal.confidence,
            debate_winner=signal.debate_winner,
            tokens=usage.total_tokens,
            latency_ms=latency_ms,
        )

        return {
            "signal": signal.model_dump(mode="json"),
            "report_md": report_md,
            "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0)
            + usage.total_tokens,
        }


# ── 降級回退 ───────────────────────────────────────────


def _salvage_final_signal(state: AgentState, reason: str) -> tuple[dict[str, Any], str]:
    """風險經理失敗時的保守回退。

    優先沿用研究經理（ResearchManager）已寫入的暫定訊號並把信心下修至 ≤50；
    若無可用暫定訊號則保守給出 HOLD。回 (signal_dict, report_md)。
    """
    tentative = state.get("signal")
    lines = ["", "## ⚠️ 風險經理降級", "", f"- 風險經理綜合失敗：{reason}"]
    if isinstance(tentative, dict) and str(tentative.get("action")) in ("BUY", "HOLD", "SELL"):
        sig: dict[str, Any] = dict(tentative)
        try:
            sig["confidence"] = min(int(sig.get("confidence") or 0), 50)
        except (TypeError, ValueError):
            sig["confidence"] = 30
        sig["degraded"] = True
        lines.append("- 處置：沿用研究經理暫定結論並下修信心至 ≤50，待人工複核。")
    else:
        sig = {
            "action": "HOLD",
            "confidence": 30,
            "reasoning_zh": "風險經理綜合失敗且無可用暫定結論，保守給出 HOLD，待人工複核。",
            "degraded": True,
        }
        lines.append("- 處置：無可用暫定結論，保守給出 HOLD。")
    lines.append("")
    return sig, (state.get("report_md") or "") + "\n".join(lines)


# ── render helpers ─────────────────────────────────────


def _render_risk_manager_user(state: AgentState) -> str:
    analyses = state.get("analyses") or {}
    plan = state.get("investment_plan") or "(無研究計畫)"
    trader = state.get("trader_proposal") or {}
    risk_history = state.get("risk_debate_history") or []
    past_context = state.get("past_context") or ""

    analyses_text = "\n\n".join(f"### {name}\n{txt}" for name, txt in analyses.items())
    if not analyses_text:
        analyses_text = "(無分析師結論)"

    trader_text = json.dumps(trader, ensure_ascii=False, indent=2) if trader else "(無交易提案)"

    risk_text = "\n\n".join(
        f"**{h.get('stance')} 第 {h.get('round')} 輪**：\n{h.get('content', '')}"
        for h in risk_history
    )
    if not risk_text:
        risk_text = "(無風險辯論)"

    memory_block = f"\n## 歷史教訓（記憶）\n{past_context}\n" if past_context.strip() else ""

    return (
        f"## 個股\n- 代號：{state.get('symbol', '?')}\n"
        f"- 市場：{state.get('market_code', '?')}\n- 區域：{state.get('region', '?')}\n\n"
        f"## 研究計畫\n{plan}\n\n"
        f"## 交易員提案\n```json\n{trader_text}\n```\n\n"
        f"## 風險辯論（積極/保守/中立）\n{risk_text}\n"
        f"{memory_block}\n"
        "## 你的任務\n綜合以上所有材料，做出最終 BUY / HOLD / SELL 決策，"
        "用 position_size_pct 表達加碼/減碼強弱，並依 FinalSignal schema 結構化輸出。"
    )


def _render_risk_report_md(state: AgentState, signal: FinalSignal) -> str:
    symbol = state.get("symbol", "?")
    market = state.get("market_code", "?")
    started_at = state.get("started_at", "")

    def _price(v: Decimal | None) -> str:
        return f"{v}" if v is not None else "未提供"

    parts: list[str] = [
        f"# {symbol}（{market}）投資分析報告（完整風險架構）",
        "",
        f"> 啟動時間：{started_at}",
        f"> 模型：{state.get('llm_model', '')} | 辯論輪數：{state.get('debate_rounds', 0)}",
        "",
        "## 最終建議（風險經理綜合）",
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

    plan = state.get("investment_plan") or ""
    if plan:
        parts.extend(["## 研究計畫", "", plan, ""])

    trader = state.get("trader_proposal") or {}
    if trader:
        parts.extend(
            [
                "## 交易員提案",
                "",
                "```json",
                json.dumps(trader, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )

    risk_history = state.get("risk_debate_history") or []
    if risk_history:
        parts.extend(["## 風險辯論紀錄", ""])
        for h in risk_history:
            parts.append(f"### {h.get('stance')} - 第 {h.get('round')} 輪")
            parts.extend(["", "```json", str(h.get("content", "")), "```", ""])

    return "\n".join(parts)


__all__ = ["RiskManager"]
