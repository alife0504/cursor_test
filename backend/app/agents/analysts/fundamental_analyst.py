"""FundamentalAnalyst — 基本面分析師（TW + US）。

P13 完整版：
- 抓近 4 季財報 + 公司基本資料 + 月營收（TW only）。
- 後端算 PE / PB / ROE / 毛利率 / 營收年增。
- LLM 結構化輸出 FundamentalAnalysisResult。
"""

from __future__ import annotations

import time
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any, ClassVar

from app.agents.base_analyst import BaseAnalyst, register_analyst
from app.agents.llm_helpers import llm_call_with_schema, record_llm_usage
from app.agents.prompts_loader import load_prompt, render_template
from app.agents.schemas import FundamentalAnalysisResult
from app.agents.state import AgentState, resolve_agent_model
from app.core.database import rw_session
from app.core.errors import ExternalServiceError
from app.core.logging_config import get_logger
from app.data_sources.base import DataKind, MarketRegion

logger = get_logger(__name__)


@register_analyst
class FundamentalAnalyst(BaseAnalyst):
    """基本面分析師。

    支援：TW + US
    依賴資料：FINANCIAL + COMPANY_INFO（+ MONTHLY_REVENUE for TW）
    """

    name: ClassVar[str] = "fundamental"
    display_name_zh: ClassVar[str] = "基本面分析師"
    supported_regions: ClassVar[list[MarketRegion]] = [MarketRegion.TW, MarketRegion.US]
    required_data_kinds: ClassVar[list[DataKind]] = [
        DataKind.FINANCIAL,
        DataKind.COMPANY_INFO,
    ]

    async def analyze(self, state: AgentState) -> dict[str, Any]:
        symbol = state.get("symbol", "?")
        region = (state.get("region") or "TW").upper()
        analysis_id = state.get("analysis_id")

        if self.llm is None or self.tools is None:
            text = (
                f"[stub] {self.display_name_zh} 對 {symbol} 的基本面分析。"
                "（無 LLM/tools 注入，回 framework stub）"
            )
            logger.info("analyst.fundamental.stub", symbol=symbol)
            return {"analyses": {self.name: text}}

        company = await self.tools.get_company_info(symbol)
        if not company:
            raise ExternalServiceError(
                message_zh=f"{symbol} 無公司基本資料",
                analyst="fundamental",
                symbol=symbol,
            )

        financials = await self.tools.get_financial(symbol, quarters_back=4)
        if not financials:
            raise ExternalServiceError(
                message_zh=f"{symbol} 無近 4 季財報",
                analyst="fundamental",
                symbol=symbol,
            )

        monthly: list[dict[str, Any]] = []
        if region == "TW":
            try:
                monthly = await self.tools.get_monthly_revenue(symbol, months_back=12)
            except Exception as exc:
                logger.warning("fundamental.monthly_revenue.failed", symbol=symbol, error=str(exc))
                monthly = []

        ratios = _compute_ratios(financials, monthly)

        # 依 region 切模板（欄位 schema 完全相容）
        template_name = (
            "fundamental_analyst_user_us_template"
            if region == "US"
            else "fundamental_analyst_user_tw_template"
        )
        monthly_table_str = (
            _format_monthly_table(monthly)
            if monthly
            else (
                "(美股無月度營收公告制度；以季度財報為主)" if region == "US" else "(無月營收資料)"
            )
        )
        user_prompt = render_template(
            template_name,
            symbol=symbol,
            company_name=company.get("name") or symbol,
            industry=company.get("industry") or "未提供",
            market=company.get("market") or "?",
            capital=_fmt(company.get("capital")),
            employees=_fmt(company.get("employees"), int_=True),
            financials_table=_format_financials_table(financials),
            monthly_revenue_table=monthly_table_str,
            eps_ttm=_fmt(ratios.get("eps_ttm")),
            pe_ratio=_fmt(ratios.get("pe_ratio")),
            industry_pe_hint=_fmt(ratios.get("industry_pe_hint")),
            pb_ratio=_fmt(ratios.get("pb_ratio")),
            roe=_fmt(ratios.get("roe_pct")),
            gross_margin=_fmt(ratios.get("gross_margin_pct")),
            op_margin=_fmt(ratios.get("op_margin_pct")),
            revenue_yoy_latest=_fmt(ratios.get("revenue_yoy_pct")),
            # #2 月營收動能（併入基本面）：由 PIT 可見月營收就地衍生，供 LLM 引用（非改決策邏輯）
            revenue_momentum=_format_revenue_momentum(_derive_revenue_momentum(monthly)),
            fcf_ttm=_fmt(ratios.get("fcf_ttm"), int_=True),
        )
        system_prompt = load_prompt("fundamental_analyst_system")

        t0 = time.monotonic()
        result, usage = await llm_call_with_schema(
            self.llm,
            system_prompt,
            user_prompt,
            FundamentalAnalysisResult,
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
                        purpose="analyst.fundamental",
                        latency_ms=latency_ms,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("fundamental_analyst.usage_record_failed", error=str(exc))

        logger.info(
            "analyst.fundamental.done",
            symbol=symbol,
            valuation=result.valuation,
            confidence=result.confidence,
            tokens=usage.total_tokens,
            latency_ms=latency_ms,
        )

        return {
            "analyses": {self.name: result.model_dump_json()},
            "llm_usage_total_tokens": int(state.get("llm_usage_total_tokens", 0) or 0)
            + usage.total_tokens,
        }


# ── 比率計算（純後端，避免 LLM 算數）─────────────────


def _compute_ratios(
    financials: list[dict[str, Any]],
    monthly_revenue: list[dict[str, Any]],
) -> dict[str, Any]:
    """從財報計算 PE / ROE / 毛利率 等（無 spot price 故 PE/PB 暫 None）。"""
    is_rows = [r for r in financials if (r.get("statement_type") or "").upper() in ("IS", "INCOME")]
    bs_rows = [
        r for r in financials if (r.get("statement_type") or "").upper() in ("BS", "BALANCE")
    ]
    cf_rows = [
        r for r in financials if (r.get("statement_type") or "").upper() in ("CF", "CASHFLOW")
    ]

    out: dict[str, Any] = {
        "pe_ratio": None,  # 缺 spot price
        "pb_ratio": None,
        "industry_pe_hint": None,
    }

    eps_quarter = [_d(r.get("eps")) for r in is_rows[:4]]
    eps_quarter = [v for v in eps_quarter if v is not None]
    if eps_quarter:
        out["eps_ttm"] = sum(eps_quarter, Decimal("0"))

    ni_vals = [_d(r.get("net_income")) for r in is_rows[:4]]
    ni_vals = [v for v in ni_vals if v is not None]
    ni_sum = sum(ni_vals, Decimal("0")) if ni_vals else None

    equity_vals = [_d(r.get("total_equity")) for r in bs_rows[:4]]
    equity_vals = [v for v in equity_vals if v is not None]
    if equity_vals and ni_sum is not None:
        avg_equity = sum(equity_vals, Decimal("0")) / Decimal(len(equity_vals))
        try:
            out["roe_pct"] = (ni_sum / avg_equity * Decimal("100")) if avg_equity > 0 else None
        except (DivisionByZero, InvalidOperation):
            out["roe_pct"] = None

    if is_rows:
        latest = is_rows[0]
        rev = _d(latest.get("revenue"))
        # 毛利率優先用 gross_profit（TW/FinMind 直接提供）；cogs 是部分 US 源才有的欄位
        gross_profit = _d(latest.get("gross_profit"))
        cogs = _d(latest.get("cogs"))
        op_income = _d(latest.get("operating_income"))
        if rev and rev != 0:
            if gross_profit is not None:
                out["gross_margin_pct"] = gross_profit / rev * Decimal("100")
            elif cogs is not None:
                out["gross_margin_pct"] = (rev - cogs) / rev * Decimal("100")
            if op_income is not None:
                out["op_margin_pct"] = op_income / rev * Decimal("100")

    # 註：CF 已在 data_pipeline 還原成「單季」基準，故四季相加才是正確的 TTM
    fcf_sum = Decimal("0")
    fcf_has = False
    for r in cf_rows[:4]:
        # 模型欄位是 operating_cashflow；operating_cash_flow 為其他源的別名
        ocf = _d(r.get("operating_cashflow"))
        if ocf is None:
            ocf = _d(r.get("operating_cash_flow"))
        cx = _d(r.get("capex"))
        if ocf is not None:
            fcf_has = True
            fcf_sum += ocf
        if cx is not None:
            fcf_sum -= abs(cx)
    if fcf_has:
        out["fcf_ttm"] = fcf_sum

    if monthly_revenue:
        latest_m = monthly_revenue[-1]
        out["revenue_yoy_pct"] = _d(latest_m.get("revenue_yoy"))

    return out


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


def _derive_revenue_momentum(monthly_revenue: list[dict[str, Any]]) -> dict[str, Any]:
    """由 PIT 可見的月營收序列衍生「營收動能」訊號（純算術、PIT 安全）。

    monthly_revenue 由 get_monthly_revenue 回傳（已由 available_at<=pit 閘門過濾、由舊到新）。
    衍生皆為對已公告過去月的統計，不偷看未來：
    - 連續同向月數：最新月 YoY 為正→往回數連續正成長月數（負則數連續衰退）。
    - 近 3 月平均 YoY：短期動能強度。
    - 動能方向：最新 YoY 相對上一個可得 YoY（加速 / 減速 / 持平）。
    無足夠資料時回空 dict（呼叫端顯示「資料不足」）。
    """
    seq = [(_d(m.get("revenue_yoy"))) for m in monthly_revenue]
    yoys = [y for y in seq if y is not None]
    if not yoys:
        return {}
    latest = yoys[-1]
    sign = 1 if latest > 0 else (-1 if latest < 0 else 0)
    streak = 0
    if sign != 0:
        for y in reversed(yoys):
            if (sign > 0 and y > 0) or (sign < 0 and y < 0):
                streak += 1
            else:
                break
    last3 = yoys[-3:]
    avg3 = (sum(last3) / len(last3)) if last3 else None
    trend = None
    if len(yoys) >= 2:
        prev = yoys[-2]
        trend = "加速" if latest > prev else ("減速" if latest < prev else "持平")
    return {
        "yoy_latest": latest,
        "streak_months": streak,
        "streak_dir": "成長" if sign > 0 else ("衰退" if sign < 0 else "持平"),
        "yoy_3m_avg": avg3,
        "trend": trend,
    }


def _format_revenue_momentum(mo: dict[str, Any]) -> str:
    """把 _derive_revenue_momentum 的結果格式化成一行中文（給 LLM 引用）。"""
    if not mo:
        return "資料不足"
    parts = [f"最新月 YoY {_fmt(mo.get('yoy_latest'))}%"]
    if mo.get("streak_months"):
        parts.append(f"連續 {mo['streak_months']} 個月{mo.get('streak_dir')}")
    if mo.get("yoy_3m_avg") is not None:
        parts.append(f"近3月均 YoY {_fmt(mo.get('yoy_3m_avg'))}%")
    if mo.get("trend"):
        parts.append(f"動能{mo['trend']}")
    return "；".join(parts)


def _format_financials_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(無財報資料)"
    lines = [
        "| 年度 | 季 | 種類 | Revenue | NetIncome | EPS |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows[:12]:
        lines.append(
            f"| {r.get('fiscal_year')} | {r.get('fiscal_quarter')} | "
            f"{r.get('statement_type')} | {_fmt(r.get('revenue'))} | "
            f"{_fmt(r.get('net_income'))} | {_fmt(r.get('eps'))} |"
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


__all__ = ["FundamentalAnalyst"]
