"""ChipAnalyst — 籌碼面分析師（TW only）。

v1.1 正名：原 `SentimentAnalyst` 名稱誤植（實作一直是籌碼面），改名為 chip；
情緒面另立新的 SentimentAnalyst（新聞情緒聚合）。

- 抓近 30 日三大法人買賣超 + 融資融券 + 12 個月營收。
- 後端算累積外資/投信/自營商淨買賣超 + 融資融券變化。
- LLM 結構化輸出 ChipAnalysisResult。
"""

from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from app.agents.base_analyst import BaseAnalyst, register_analyst
from app.agents.llm_helpers import llm_call_with_schema, record_llm_usage
from app.agents.prompts_loader import load_prompt, render_template
from app.agents.schemas import ChipAnalysisResult
from app.agents.state import AgentState, resolve_agent_model
from app.core.database import rw_session
from app.core.errors import ExternalServiceError, ValidationError
from app.core.logging_config import get_logger
from app.data_sources.base import DataKind, MarketRegion

logger = get_logger(__name__)


@register_analyst
class ChipAnalyst(BaseAnalyst):
    """籌碼面分析師（台股 only）。"""

    name: ClassVar[str] = "chip"
    display_name_zh: ClassVar[str] = "籌碼面分析師"
    supported_regions: ClassVar[list[MarketRegion]] = [MarketRegion.TW]
    required_data_kinds: ClassVar[list[DataKind]] = [
        DataKind.INSTITUTIONAL,
        DataKind.MARGIN,
        DataKind.MONTHLY_REVENUE,
    ]

    async def analyze(self, state: AgentState) -> dict[str, Any]:
        symbol = state.get("symbol", "?")
        analysis_id = state.get("analysis_id")

        if self.llm is None or self.tools is None:
            text = (
                f"[stub] {self.display_name_zh} 對 {symbol} 的籌碼面分析。"
                "（無 LLM/tools 注入，回 framework stub）"
            )
            logger.info("analyst.chip.stub", symbol=symbol)
            return {"analyses": {self.name: text}}

        # Region 防呆（不該在 US 上跑）
        if state.get("region", "TW") != "TW":
            raise ValidationError(
                message_zh="ChipAnalyst 僅支援台股",
                symbol=symbol,
                region=state.get("region"),
            )

        company = await self.tools.get_company_info(symbol)

        try:
            institutional = await self.tools.get_institutional(symbol, days_back=30)
        except Exception as exc:
            logger.warning("chip.institutional.failed", symbol=symbol, error=str(exc))
            institutional = []

        try:
            margin = await self.tools.get_margin(symbol, days_back=30)
        except Exception as exc:
            logger.warning("chip.margin.failed", symbol=symbol, error=str(exc))
            margin = []

        try:
            monthly = await self.tools.get_monthly_revenue(symbol, months_back=12)
        except Exception as exc:
            logger.warning("chip.monthly_revenue.failed", symbol=symbol, error=str(exc))
            monthly = []

        # 至少一種資料才有意義；全空 → raise
        if not institutional and not margin and not monthly:
            raise ExternalServiceError(
                message_zh=f"{symbol} 無任何籌碼面資料（三大法人/融資融券/月營收皆空）",
                analyst="chip",
                symbol=symbol,
            )

        agg = _aggregate(institutional, margin)

        user_prompt = render_template(
            "chip_analyst_user_template",
            symbol=symbol,
            company_name=company.get("name") or symbol,
            industry=company.get("industry") or "未提供",
            foreign_buy=_fmt(agg.get("foreign_buy"), int_=True),
            foreign_sell=_fmt(agg.get("foreign_sell"), int_=True),
            foreign_net=_fmt(agg.get("foreign_net"), int_=True),
            trust_buy=_fmt(agg.get("trust_buy"), int_=True),
            trust_sell=_fmt(agg.get("trust_sell"), int_=True),
            trust_net=_fmt(agg.get("trust_net"), int_=True),
            dealer_buy=_fmt(agg.get("dealer_buy"), int_=True),
            dealer_sell=_fmt(agg.get("dealer_sell"), int_=True),
            dealer_net=_fmt(agg.get("dealer_net"), int_=True),
            total_net=_fmt(agg.get("total_net"), int_=True),
            institutional_table=_format_inst_table(institutional[-10:]),
            margin_balance_start=_fmt(agg.get("margin_balance_start"), int_=True),
            margin_balance_end=_fmt(agg.get("margin_balance_end"), int_=True),
            margin_balance_change=_fmt(agg.get("margin_balance_change"), int_=True),
            short_balance_start=_fmt(agg.get("short_balance_start"), int_=True),
            short_balance_end=_fmt(agg.get("short_balance_end"), int_=True),
            short_balance_change=_fmt(agg.get("short_balance_change"), int_=True),
            short_to_margin_ratio=_fmt(agg.get("short_to_margin_ratio")),
            # #3 籌碼動能（併入籌碼面）：由日級序列就地衍生，供 LLM 引用（非改決策邏輯）
            chip_momentum=_format_chip_momentum(_derive_chip_momentum(institutional, margin)),
            margin_table=_format_margin_table(margin[-10:]),
            latest_month=(
                f"{monthly[-1].get('year')}-{int(monthly[-1].get('month') or 0):02d}"
                if monthly
                else "無資料"
            ),
            latest_revenue=_fmt(monthly[-1].get("revenue") if monthly else None, int_=True),
            latest_yoy=_fmt(monthly[-1].get("revenue_yoy") if monthly else None),
            ytd_yoy=_fmt(monthly[-1].get("ytd_yoy") if monthly else None),
            monthly_revenue_table=_format_monthly_table(monthly),
        )
        system_prompt = load_prompt("chip_analyst_system")

        t0 = time.monotonic()
        result, usage = await llm_call_with_schema(
            self.llm,
            system_prompt,
            user_prompt,
            ChipAnalysisResult,
            model=resolve_agent_model(state, self.name),
            max_tokens=4096,  # 實測：本專案 schema(含中文 summary)+思考 token 需 ~2700，2048 會被截斷
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
                        purpose="analyst.chip",
                        latency_ms=latency_ms,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("chip_analyst.usage_record_failed", error=str(exc))

        logger.info(
            "analyst.chip.done",
            symbol=symbol,
            institutional_flow=result.institutional_flow,
            confidence=result.confidence,
            tokens=usage.total_tokens,
            latency_ms=latency_ms,
        )

        return {
            "analyses": {self.name: result.model_dump_json()},
            "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0)
            + usage.total_tokens,
        }


# ── 聚合 helpers ───────────────────────────────────────


def _aggregate(
    institutional: list[dict[str, Any]],
    margin: list[dict[str, Any]],
) -> dict[str, Any]:
    out: dict[str, Any] = {}

    def _sum(key: str) -> Decimal:
        total = Decimal("0")
        for r in institutional:
            v = _d(r.get(key))
            if v is not None:
                total += v
        return total

    out["foreign_buy"] = _sum("foreign_buy")
    out["foreign_sell"] = _sum("foreign_sell")
    out["foreign_net"] = _sum("foreign_net")
    out["trust_buy"] = _sum("trust_buy")
    out["trust_sell"] = _sum("trust_sell")
    out["trust_net"] = _sum("trust_net")
    out["dealer_buy"] = _sum("dealer_buy")
    out["dealer_sell"] = _sum("dealer_sell")
    out["dealer_net"] = _sum("dealer_net")
    out["total_net"] = out["foreign_net"] + out["trust_net"] + out["dealer_net"]

    if margin:
        first = margin[0]
        last = margin[-1]
        mb_s = _d(first.get("margin_balance")) or Decimal("0")
        mb_e = _d(last.get("margin_balance")) or Decimal("0")
        sb_s = _d(first.get("short_balance")) or Decimal("0")
        sb_e = _d(last.get("short_balance")) or Decimal("0")
        out["margin_balance_start"] = mb_s
        out["margin_balance_end"] = mb_e
        out["margin_balance_change"] = mb_e - mb_s
        out["short_balance_start"] = sb_s
        out["short_balance_end"] = sb_e
        out["short_balance_change"] = sb_e - sb_s
        if mb_e > 0:
            out["short_to_margin_ratio"] = sb_e / mb_e * Decimal("100")
    return out


def _derive_chip_momentum(
    institutional: list[dict[str, Any]],
    margin: list[dict[str, Any]],
) -> dict[str, Any]:
    """由日級籌碼序列衍生「籌碼動能」訊號（純算術、PIT 安全）。

    institutional / margin 由 get_* 回傳（由舊到新，皆為 <= 今日的已發生資料）：
    - 外資 / 投信「連續買超（或賣超）天數」：主力進出的持續性。
    - 外資近 5 日淨買賣超合計：短期資金動向強度。
    - 融資餘額趨勢：散戶槓桿的方向（增→追高、減→退場）。
    無足夠資料的欄位回 None（呼叫端顯示「資料不足」）。
    """
    out: dict[str, Any] = {}

    def _streak(key: str) -> tuple[int | None, str | None]:
        vals = [v for v in (_d(r.get(key)) for r in institutional) if v is not None]
        if not vals:
            return None, None
        latest = vals[-1]
        sign = 1 if latest > 0 else (-1 if latest < 0 else 0)
        s = 0
        if sign != 0:
            for v in reversed(vals):
                if (sign > 0 and v > 0) or (sign < 0 and v < 0):
                    s += 1
                else:
                    break
        return s, ("買超" if sign > 0 else ("賣超" if sign < 0 else "持平"))

    if institutional:
        fs, fdir = _streak("foreign_net")
        ts, tdir = _streak("trust_net")
        out["foreign_streak"], out["foreign_streak_dir"] = fs, fdir
        out["trust_streak"], out["trust_streak_dir"] = ts, tdir
        last5 = [(_d(r.get("foreign_net")) or Decimal("0")) for r in institutional[-5:]]
        out["foreign_net_5d"] = sum(last5) if last5 else None

    if len(margin) >= 2:
        mb_e = _d(margin[-1].get("margin_balance"))
        mb_s = _d(margin[0].get("margin_balance"))
        if mb_e is not None and mb_s is not None:
            out["margin_trend"] = "增加" if mb_e > mb_s else ("減少" if mb_e < mb_s else "持平")
    return out


def _format_chip_momentum(mo: dict[str, Any]) -> str:
    """把 _derive_chip_momentum 結果格式化成一行中文（給 LLM 引用）。"""
    if not mo:
        return "資料不足"
    parts: list[str] = []
    if mo.get("foreign_streak"):
        parts.append(f"外資連續 {mo['foreign_streak']} 日{mo.get('foreign_streak_dir')}")
    if mo.get("trust_streak"):
        parts.append(f"投信連續 {mo['trust_streak']} 日{mo.get('trust_streak_dir')}")
    if mo.get("foreign_net_5d") is not None:
        parts.append(f"外資近5日淨額 {_fmt(mo.get('foreign_net_5d'), int_=True)}")
    if mo.get("margin_trend"):
        parts.append(f"融資餘額{mo['margin_trend']}")
    return "；".join(parts) if parts else "資料不足"


def _d(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _fmt(v: Any, *, int_: bool = False) -> str:
    if v is None:
        return "無資料"
    try:
        if int_:
            return f"{int(float(v)):,}"
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _format_inst_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(無三大法人資料)"
    lines = [
        "| 日期 | 外資淨 | 投信淨 | 自營商淨 | 合計淨 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        fn = _d(r.get("foreign_net")) or Decimal("0")
        tn = _d(r.get("trust_net")) or Decimal("0")
        dn = _d(r.get("dealer_net")) or Decimal("0")
        lines.append(
            f"| {r.get('date', '')} | {fn:,.0f} | {tn:,.0f} | {dn:,.0f} | {fn + tn + dn:,.0f} |"
        )
    return "\n".join(lines)


def _format_margin_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(無融資融券資料)"
    lines = [
        "| 日期 | 融資餘額 | 融資增減 | 融券餘額 | 融券增減 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('date', '')} | "
            f"{_fmt(r.get('margin_balance'), int_=True)} | "
            f"{_fmt((r.get('margin_buy') or 0) - (r.get('margin_sell') or 0), int_=True)} | "
            f"{_fmt(r.get('short_balance'), int_=True)} | "
            # 融券增減＝融券賣出(短售,新增空單→餘額↑) − 融券買進(回補→餘額↓)＝short_sell − short_buy。
            # 原寫成 short_buy − short_sell 方向相反，會讓 LLM 把「增加空單(偏空)」讀成「回補(偏多)」。
            f"{_fmt((r.get('short_sell') or 0) - (r.get('short_buy') or 0), int_=True)} |"
        )
    return "\n".join(lines)


def _format_monthly_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(無月營收資料)"
    lines = ["| 年月 | 營收 | YoY% | MoM% |", "|---|---|---|---|"]
    for r in rows[-12:]:
        ym = (
            f"{r.get('year')}-{int(r.get('month') or 0):02d}"
            if r.get("month") is not None
            else str(r.get("year"))
        )
        lines.append(
            f"| {ym} | {_fmt(r.get('revenue'), int_=True)} | "
            f"{_fmt(r.get('revenue_yoy'))} | {_fmt(r.get('revenue_mom'))} |"
        )
    return "\n".join(lines)


__all__ = ["ChipAnalyst"]
