"""Phase 10 — /api/v1/screener/* router。

依 PLAN.md 第 17.4 章 cursor + 第 19.2 章 sort whitelist + 19.2 動態 SQL（SQLAlchemy expression）。
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.cursor import build_page_response
from app.core.database import get_rw_session
from app.core.response_envelope import envelope_success
from app.schemas.screener import ScreenerFilters, ScreenerRow
from app.services.screener_service import ScreenerService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/api/v1/screener", tags=["screener"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


@router.get("", summary="條件篩選（PE / yield / EPS / RSI / industry）")
async def screen(
    request: Request,
    market: str = Query(default="TW", max_length=10),
    PE_min: Decimal | None = Query(default=None, alias="PE_min"),
    PE_max: Decimal | None = Query(default=None, alias="PE_max"),
    dividend_yield_min: Decimal | None = Query(default=None),
    eps_growth_min: Decimal | None = Query(default=None),
    RSI_min: Decimal | None = Query(default=None, alias="RSI_min"),
    RSI_max: Decimal | None = Query(default=None, alias="RSI_max"),
    market_cap_min: Decimal | None = Query(default=None),
    industry: str | None = Query(default=None, max_length=100),
    sort: str = Query(default="symbol", max_length=32),
    order: str = Query(default="asc", max_length=8),
    cursor: str | None = Query(default=None, max_length=2048),
    limit: int = Query(default=50, ge=1, le=100),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    filters = ScreenerFilters(
        market=market.upper(),  # type: ignore[arg-type]
        pe_min=PE_min,
        pe_max=PE_max,
        dividend_yield_min=dividend_yield_min,
        eps_growth_min=eps_growth_min,
        rsi_min=RSI_min,
        rsi_max=RSI_max,
        market_cap_min=market_cap_min,
        industry=industry,
    )
    service = ScreenerService(session)
    page = await service.screen(filters, sort_by=sort, sort_order=order, limit=limit, cursor=cursor)
    items = [ScreenerRow(**r).model_dump(mode="json") for r in page.items]
    pagination = build_page_response(
        items, limit=page.limit, next_cursor_kwargs=page.next_cursor_kwargs
    )
    return envelope_success(items, trace_id=_trace_id(request), pagination=pagination)


__all__ = ["router"]
