"""MarketAnalyst — 技術面分析師（TW + US）。

P13 完整版：
- 透過 ToolRegistry 抓近 60 日 OHLCV。
- 後端用 numpy/pandas 算技術指標（RSI、MACD、KD、BBANDS、MA20/60）。
- 渲染 prompt → LLM 結構化輸出 MarketAnalysisResult。
- 寫一筆 llm_usage 到 DB。
"""

from __future__ import annotations

import time
from typing import Any, ClassVar

from app.agents.base_analyst import BaseAnalyst, register_analyst
from app.agents.indicators import compute_indicators
from app.agents.llm_helpers import llm_call_with_schema, record_llm_usage
from app.agents.prompts_loader import load_prompt, render_template
from app.agents.schemas import MarketAnalysisResult
from app.agents.state import AgentState, resolve_agent_model
from app.core.database import rw_session
from app.core.errors import ExternalServiceError
from app.core.logging_config import get_logger
from app.data_sources.base import DataKind, MarketRegion

logger = get_logger(__name__)


@register_analyst
class MarketAnalyst(BaseAnalyst):
    """技術面分析師。

    支援：TW + US
    依賴資料：OHLCV
    """

    name: ClassVar[str] = "market"
    display_name_zh: ClassVar[str] = "技術面分析師"
    supported_regions: ClassVar[list[MarketRegion]] = [MarketRegion.TW, MarketRegion.US]
    required_data_kinds: ClassVar[list[DataKind]] = [DataKind.OHLCV]

    async def analyze(self, state: AgentState) -> dict[str, Any]:
        symbol = state.get("symbol", "?")
        analysis_id = state.get("analysis_id")
        region = (state.get("region") or "TW").upper()

        # 無 llm/tools → 回 stub（向下相容 P12 測試）
        if self.llm is None or self.tools is None:
            text = (
                f"[stub] {self.display_name_zh} 對 {symbol} 的技術面分析。"
                "（無 LLM/tools 注入，回 framework stub）"
            )
            logger.info("analyst.market.stub", symbol=symbol)
            return {"analyses": {self.name: text}}

        # 1. 抓近 60 日 OHLCV
        ohlcv = await self.tools.get_ohlcv(symbol, days_back=60)
        if not ohlcv:
            raise ExternalServiceError(
                message_zh=f"{symbol} 無 OHLCV 資料（近 60 日）",
                analyst="market",
                symbol=symbol,
                region=region,
            )

        # 2. 後端算技術指標（純 numpy）
        indicators = compute_indicators(ohlcv)
        latest = indicators["latest"]
        stats = indicators["stats"]

        # 公司資訊（補上 prompt 的 company_name / industry）
        company = await self.tools.get_company_info(symbol)

        # 3. 渲染 user prompt（依 region 切台股/美股模板，欄位完全相容）
        template_name = (
            "market_analyst_user_us_template"
            if region == "US"
            else "market_analyst_user_tw_template"
        )
        user_prompt = render_template(
            template_name,
            symbol=symbol,
            company_name=company.get("name") or symbol,
            industry=company.get("industry") or "未提供",
            market=company.get("market") or state.get("market_code") or "?",
            date_start=ohlcv[0].get("date"),
            date_end=ohlcv[-1].get("date"),
            price_low=_fmt(stats.get("price_low")),
            price_high=_fmt(stats.get("price_high")),
            price_last=_fmt(stats.get("price_last")),
            avg_volume=_fmt(latest.get("volume_avg_20"), int_=True),
            cum_return_pct=_fmt(stats.get("cum_return_pct")),
            rsi=_fmt(latest.get("rsi")),
            macd_line=_fmt(latest.get("macd")),
            macd_signal=_fmt(latest.get("macd_signal")),
            macd_hist=_fmt(latest.get("macd_hist")),
            kd_k=_fmt(latest.get("k")),
            kd_d=_fmt(latest.get("d")),
            bb_upper=_fmt(latest.get("bb_upper")),
            bb_middle=_fmt(latest.get("bb_middle")),
            bb_lower=_fmt(latest.get("bb_lower")),
            ma20=_fmt(latest.get("ma20")),
            ma60=_fmt(latest.get("ma60")),
            divergence_note=_divergence_note(indicators),
            ohlcv_table=_format_ohlcv_table(ohlcv[-10:]),
        )
        system_prompt = load_prompt("market_analyst_system")

        # 4. LLM call + schema validation
        t0 = time.monotonic()
        result, usage = await llm_call_with_schema(
            self.llm,
            system_prompt,
            user_prompt,
            MarketAnalysisResult,
            model=resolve_agent_model(state, self.name),
            max_tokens=2048,
            temperature=0.3,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        # 5. 寫 llm_usage
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
                        purpose="analyst.market",
                        latency_ms=latency_ms,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("market_analyst.usage_record_failed", error=str(exc))

        logger.info(
            "analyst.market.done",
            symbol=symbol,
            confidence=result.confidence,
            short_term_view=result.short_term_view,
            tokens=usage.total_tokens,
            latency_ms=latency_ms,
        )

        return {
            "analyses": {self.name: result.model_dump_json()},
            "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0)
            + usage.total_tokens,
        }


# ── 內部 helpers ─────────────────────────────────────────


def _fmt(v: Any, *, int_: bool = False) -> str:
    if v is None:
        return "無資料"
    try:
        if int_:
            return f"{int(float(v)):,}"
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _format_ohlcv_table(rows: list[dict[str, Any]]) -> str:
    """簡易 markdown 表格：日期 / O / H / L / C / Volume。"""
    if not rows:
        return "(無資料)"
    lines = ["| 日期 | 開 | 高 | 低 | 收 | 量 |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r.get('date', '')} | {_fmt(r.get('open'))} | "
            f"{_fmt(r.get('high'))} | {_fmt(r.get('low'))} | "
            f"{_fmt(r.get('close'))} | {_fmt(r.get('volume'), int_=True)} |"
        )
    return "\n".join(lines)


def _divergence_note(indicators: dict[str, Any]) -> str:
    """簡單偵測 RSI 與價格背離（5 日窗口）。"""
    series = indicators.get("series", {})
    closes_idx = indicators.get("rows", 0)
    rsi_seq = series.get("rsi") or []
    if len(rsi_seq) < 6 or closes_idx < 6:
        return "（資料不足，未做背離判斷）"
    last_rsi = rsi_seq[-1]
    rsi_5_ago = rsi_seq[-6]
    if last_rsi is None or rsi_5_ago is None:
        return "（RSI 資料不足，未做背離判斷）"
    price_last = indicators.get("stats", {}).get("price_last")
    if not price_last:
        return "（價格資料不足）"
    # 不嚴格背離分析，但給 LLM 一個方向提示
    if last_rsi < rsi_5_ago - 5:
        return f"RSI 5 日轉弱（從 {rsi_5_ago:.1f} → {last_rsi:.1f}）"
    if last_rsi > rsi_5_ago + 5:
        return f"RSI 5 日轉強（從 {rsi_5_ago:.1f} → {last_rsi:.1f}）"
    return "RSI 5 日動能持平"


__all__ = ["MarketAnalyst"]
