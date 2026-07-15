"""Phase 10 — /api/v1/market/* router。

所有 endpoint 要求登入。
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_rw_session
from app.core.response_envelope import envelope_success
from app.schemas.market import InstitutionalRow, MoverRow
from app.services.market_service import MarketService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/api/v1/market", tags=["market"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


@router.get("/overview", summary="大盤總覽（指數 + 漲跌家數 + 成交量）")
async def get_overview(
    request: Request,
    market: str = Query(default="TW", max_length=10),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = MarketService(session)
    payload = await service.get_overview(market)
    return envelope_success(payload, trace_id=_trace_id(request))


@router.get("/institutional", summary="三大法人買賣超（TW only）")
async def get_institutional(
    request: Request,
    market: str = Query(default="TW", max_length=10),
    target_date: date | None = Query(default=None, alias="date"),
    limit: int = Query(default=100, ge=1, le=500),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = MarketService(session)
    used_date, rows = await service.get_institutional(
        target_date=target_date, market=market, limit=limit
    )
    items = [
        InstitutionalRow(
            symbol=r.symbol,
            date=r.date,
            foreign_buy=r.foreign_buy,
            foreign_sell=r.foreign_sell,
            foreign_net=r.foreign_net,
            trust_buy=r.trust_buy,
            trust_sell=r.trust_sell,
            trust_net=r.trust_net,
            dealer_buy=r.dealer_buy,
            dealer_sell=r.dealer_sell,
            dealer_net=r.dealer_net,
        ).model_dump(mode="json")
        for r in rows
    ]
    return envelope_success(
        {"date": used_date.isoformat() if used_date else None, "rows": items},
        trace_id=_trace_id(request),
    )


@router.get("/movers", summary="漲跌幅 / 成交量排行")
async def get_movers(
    request: Request,
    market: str = Query(default="TW", max_length=10),
    type: str = Query(default="gainers", max_length=10),
    limit: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = MarketService(session)
    rows = await service.get_movers(market=market, mover_type=type, limit=limit)
    items = [
        MoverRow(
            symbol=r["symbol"],
            name=r.get("name"),
            close=r.get("close"),
            change_pct=r.get("change_pct"),
            volume=r.get("volume"),
        ).model_dump(mode="json")
        for r in rows
    ]
    return envelope_success(items, trace_id=_trace_id(request))


@router.get("/calendar", summary="財報日曆（mock；P17 完整）")
async def get_calendar(
    request: Request,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    market: str = Query(default="TW", max_length=10),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = MarketService(session)
    items = await service.get_calendar(from_date=from_date, to_date=to_date, market=market)
    return envelope_success(items, trace_id=_trace_id(request))


def _split_ids(raw: str, *, limit: int = 50) -> list[str]:
    """把逗號分隔的代號字串切成 list（去空白 / 去空項 / 上限保護）。"""
    ids = [s.strip() for s in raw.split(",") if s.strip()]
    return ids[:limit]


@router.get("/realtime/stock", summary="台股個股即時報價（需 FinMind Sponsor 等級）")
async def get_realtime_stock(
    request: Request,
    symbols: str = Query(..., max_length=500, description="逗號分隔股票代號，如 2330,2317"),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    """即時 snapshot；未開通 Sponsor 等級時回 available=false + reason（優雅降級）。"""
    service = MarketService(session)
    payload = await service.get_realtime_stock(_split_ids(symbols))
    return envelope_success(payload, trace_id=_trace_id(request))


@router.get("/realtime/futures", summary="台股期貨即時報價（需 FinMind Sponsor 等級）")
async def get_realtime_futures(
    request: Request,
    ids: str = Query(default="TX", max_length=200, description="逗號分隔期貨代號，如 TX,MTX"),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = MarketService(session)
    payload = await service.get_realtime_futures(_split_ids(ids))
    return envelope_success(payload, trace_id=_trace_id(request))


__all__ = ["router"]
