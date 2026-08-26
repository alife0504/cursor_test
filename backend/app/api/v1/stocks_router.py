"""Phase 10 — /api/v1/stocks/* router。

所有 endpoint 要求登入（任何 role 都可讀）；無 admin-only 限制。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.cursor import build_page_response
from app.core.database import get_rw_session
from app.core.response_envelope import envelope_success
from app.core.validators import validate_symbol
from app.models.tw_specific import StockMetrics
from app.schemas.stocks import (
    AnnouncementItem,
    FinancialStatementItem,
    IndicatorPoint,
    NewsItem,
    OHLCVPoint,
    StockDetail,
    StockSummary,
)
from app.services.stock_service import StockService

if TYPE_CHECKING:
    from app.models.user import User


router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


# ════════════════ GET /stocks ════════════════


@router.get("", summary="列出股票（cursor 分頁；可選 market / q 過濾）")
async def list_stocks(
    request: Request,
    market: str | None = Query(default=None, max_length=10),
    q: str | None = Query(default=None, max_length=100),
    cursor: str | None = Query(default=None, max_length=2048),
    limit: int = Query(default=50, ge=1, le=100),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = StockService(session)
    page = await service.list_stocks(market=market, q=q, cursor=cursor, limit=limit)
    items = [StockSummary.model_validate(s).model_dump(mode="json") for s in page.items]
    pagination = build_page_response(
        items, limit=page.limit, next_cursor_kwargs=page.next_cursor_kwargs
    )
    return envelope_success(items, trace_id=_trace_id(request), pagination=pagination)


# ════════════════ GET /stocks/{symbol} ════════════════


@router.get("/{symbol}", summary="股票詳情（含 stock_info）")
async def get_stock(
    request: Request,
    symbol: str,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = StockService(session)
    sym = validate_symbol(symbol)
    stock, info = await service.get_stock(sym)
    detail = StockDetail(
        symbol=stock.symbol,
        market=stock.market,
        name=stock.name,
        short_name=stock.short_name,
        industry=stock.industry,
        listed_at=stock.listed_at,
        is_active=stock.is_active,
        full_name=info.full_name if info else None,
        sector=info.sector if info else None,
        sub_industry=info.sub_industry if info else None,
        description=info.description if info else None,
        website=info.website if info else None,
        capital=info.capital if info else None,
        employees=info.employees if info else None,
        fiscal_year_end=info.fiscal_year_end if info else None,
    )
    return envelope_success(detail.model_dump(mode="json"), trace_id=_trace_id(request))


@router.get("/{symbol}/metrics", summary="個股關鍵指標（PE/PBR/殖利率/EPS成長/RSI/市值）")
async def get_stock_metrics(
    request: Request,
    symbol: str,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
) -> dict:
    """多股比較用：回傳 stock_metrics（由每日 sync_stock_metrics_tw 物化）。

    無資料欄位回 null（前端顯示 -）；不硬湊。
    """
    symbol = validate_symbol(symbol)
    row = await session.get(StockMetrics, symbol)

    def _f(v: object) -> float | None:
        return float(v) if v is not None else None  # type: ignore[arg-type]

    data = {
        "symbol": symbol,
        "as_of_date": row.as_of_date.isoformat() if row and row.as_of_date else None,
        "pe_ratio": _f(row.pe_ratio) if row else None,
        "pbr": _f(row.pbr) if row else None,
        "dividend_yield": _f(row.dividend_yield) if row else None,
        "market_cap": (row.market_cap if row else None),
        "rsi14": _f(row.rsi14) if row else None,
        "eps_growth": _f(row.eps_growth) if row else None,
    }
    return envelope_success(data, trace_id=_trace_id(request))


# ════════════════ GET /stocks/{symbol}/ohlcv ════════════════


@router.get("/{symbol}/ohlcv", summary="OHLCV 區間")
async def get_ohlcv(
    request: Request,
    symbol: str,
    start: date = Query(...),
    end: date = Query(...),
    interval: str = Query(default="daily", max_length=10),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = StockService(session)
    rows = await service.get_ohlcv(symbol, start=start, end=end, interval=interval)
    items = [OHLCVPoint.model_validate(r).model_dump(mode="json") for r in rows]
    return envelope_success(items, trace_id=_trace_id(request))


# ════════════════ GET /stocks/{symbol}/indicators ════════════════


@router.get("/{symbol}/indicators", summary="技術指標（RSI / MACD / KD / BBANDS）")
async def get_indicators(
    request: Request,
    symbol: str,
    period: int = Query(default=14, ge=2, le=200),
    type: str = Query(default="RSI,MACD,KD,BBANDS", max_length=64),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = StockService(session)
    types = [t.strip() for t in type.split(",") if t.strip()]
    rows = await service.get_indicators(symbol, period=period, types=types, start=start, end=end)
    items = [IndicatorPoint(**r).model_dump(mode="json") for r in rows]
    return envelope_success(items, trace_id=_trace_id(request))


# ════════════════ GET /stocks/{symbol}/financial ════════════════


@router.get("/{symbol}/financial", summary="財務報表（IS / BS / CF）")
async def get_financial(
    request: Request,
    symbol: str,
    year: int | None = Query(default=None, ge=1900, le=2100),
    quarter: int | None = Query(default=None, ge=0, le=4),
    statement_type: str | None = Query(default=None, max_length=5),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = StockService(session)
    rows = await service.list_financial(
        symbol, year=year, quarter=quarter, statement_type=statement_type
    )
    items = [FinancialStatementItem.model_validate(r).model_dump(mode="json") for r in rows]
    return envelope_success(items, trace_id=_trace_id(request))


# ════════════════ GET /stocks/{symbol}/news ════════════════


@router.get("/{symbol}/news", summary="新聞清單（依 published_at desc）")
async def get_news(
    request: Request,
    symbol: str,
    since: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = StockService(session)
    rows = await service.list_news(symbol, since=since, limit=limit)
    items = [
        NewsItem(
            id=str(r.id),
            symbol=r.symbol,
            market=r.market,
            title=r.title,
            summary=r.summary,
            source=r.source,
            url=r.url,
            author=r.author,
            published_at=r.published_at,
            sentiment=r.sentiment,
            sentiment_score=r.sentiment_score,
        ).model_dump(mode="json")
        for r in rows
    ]
    return envelope_success(items, trace_id=_trace_id(request))


# ════════════════ GET /stocks/{symbol}/announcements ════════════════


@router.get("/{symbol}/announcements", summary="重大訊息／公告")
async def get_announcements(
    request: Request,
    symbol: str,
    since: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = StockService(session)
    rows = await service.list_announcements(symbol, since=since, limit=limit)
    items = [
        AnnouncementItem(
            id=str(r.id),
            symbol=r.symbol,
            market=r.market,
            announcement_type=r.announcement_type,
            title=r.title,
            url=r.url,
            published_at=r.published_at,
        ).model_dump(mode="json")
        for r in rows
    ]
    return envelope_success(items, trace_id=_trace_id(request))


__all__ = ["router"]
