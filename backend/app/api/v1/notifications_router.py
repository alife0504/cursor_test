"""Phase 11 — /api/v1/notifications/* router。

GET / PUT /settings：個人；POST /test：個人；GET /logs：個人（admin 可看全部）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.cursor import Cursor, build_page_response, clamp_limit
from app.core.database import get_rw_session
from app.core.response_envelope import envelope_success
from app.schemas.notifications import (
    NotificationLogOut,
    NotificationSettingsUpdate,
    NotificationTestRequest,
)
from app.services.notification_service import NotificationService

if TYPE_CHECKING:
    from app.models.user import User


router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


# ════════════════ Settings ════════════════


@router.get("/settings", summary="取得個人通知設定")
async def get_settings(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = NotificationService(session)
    row = await service.get_settings(user)
    body = service.serialize_settings(row, user.id)
    return envelope_success(body, trace_id=_trace_id(request))


@router.put("/settings", summary="更新個人通知設定")
async def update_settings(
    payload: NotificationSettingsUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = NotificationService(session)
    patch = payload.model_dump(exclude_unset=True)
    row = await service.update_settings(user, patch=patch, request_id=_trace_id(request))
    body = service.serialize_settings(row, user.id)
    return envelope_success(body, trace_id=_trace_id(request))


# ════════════════ Test ════════════════


@router.post("/test", summary="送一則測試通知（不真打外部）")
async def send_test(
    payload: NotificationTestRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = NotificationService(session)
    log = await service.send_test(
        user,
        channel=payload.channel,
        message=payload.message,
        request_id=_trace_id(request),
    )
    return envelope_success(
        NotificationLogOut.model_validate(log).model_dump(mode="json"),
        trace_id=_trace_id(request),
    )


# ════════════════ Logs ════════════════


@router.get("/logs", summary="列出通知 log")
async def list_logs(
    request: Request,
    cursor: str | None = Query(default=None, max_length=2048),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = NotificationService(session)
    limit = clamp_limit(limit)
    before_sent_at = None
    if cursor:
        before_sent_at = Cursor.decode(cursor).get("before_sent_at")

    rows = await service.list_logs(user, limit=limit + 1, before_sent_at=before_sent_at)
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [NotificationLogOut.model_validate(r).model_dump(mode="json") for r in rows]
    next_kwargs = None
    if has_more and rows:
        next_kwargs = {"before_sent_at": rows[-1].sent_at}
    pagination = build_page_response(items, limit=limit, next_cursor_kwargs=next_kwargs)
    return envelope_success(items, trace_id=_trace_id(request), pagination=pagination)


__all__ = ["router"]
