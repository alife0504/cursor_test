"""Phase 10 — /api/v1/watchlist/* router。

所有 endpoint 要求登入；CSRF 由 middleware 處理（POST/PATCH/DELETE 都會檢）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_rw_session
from app.core.response_envelope import envelope_success
from app.core.validators import validate_uuid
from app.schemas.watchlist import (
    WatchlistDeleteResponse,
    WatchlistItem,
    WatchlistItemCreate,
    WatchlistItemUpdate,
)
from app.services.watchlist_service import WatchlistService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


def _to_item(row) -> dict:
    return WatchlistItem(
        id=str(row.id),
        user_id=str(row.user_id),
        symbol=row.symbol,
        market=row.market,
        tag=row.tag,
        notes=row.notes,
        sort_order=row.sort_order,
        created_at=row.created_at,
    ).model_dump(mode="json")


@router.get("", summary="列出我的自選股")
async def list_watchlist(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = WatchlistService(session)
    rows = await service.list(user.id)
    items = [_to_item(r) for r in rows]
    return envelope_success(items, trace_id=_trace_id(request))


@router.post("", status_code=201, summary="新增自選股")
async def add_watchlist(
    payload: WatchlistItemCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = WatchlistService(session)
    entry = await service.add(
        user_id=user.id,
        symbol=payload.symbol,
        market=payload.market,
        tag=payload.tag,
        notes=payload.notes,
    )
    return envelope_success(_to_item(entry), trace_id=_trace_id(request))


@router.patch("/{watchlist_id}", summary="更新自選股欄位（tag / notes / sort_order）")
async def update_watchlist(
    watchlist_id: str,
    payload: WatchlistItemUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = WatchlistService(session)
    wl_uuid = validate_uuid(watchlist_id)
    updated = await service.update(
        user_id=user.id,
        watchlist_id=wl_uuid,
        tag=payload.tag,
        notes=payload.notes,
        sort_order=payload.sort_order,
    )
    return envelope_success(_to_item(updated), trace_id=_trace_id(request))


@router.delete("/{watchlist_id}", summary="刪除自選股")
async def delete_watchlist(
    watchlist_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = WatchlistService(session)
    wl_uuid = validate_uuid(watchlist_id)
    await service.delete(user_id=user.id, watchlist_id=wl_uuid)
    return envelope_success(
        WatchlistDeleteResponse().model_dump(mode="json"),
        trace_id=_trace_id(request),
    )


__all__ = ["router"]
