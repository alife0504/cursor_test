"""Phase 11 — /api/v1/admin/* router。

全部 admin only。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import admin_only
from app.core.cursor import Cursor, build_page_response, clamp_limit
from app.core.database import get_rw_session
from app.core.response_envelope import envelope_success
from app.core.validators import validate_uuid
from app.schemas.admin import (
    AuditLogOut,
    DeadLetterOut,
    DLQResolveRequest,
    UserSessionOut,
)
from app.services.admin_service import AdminService

if TYPE_CHECKING:
    from app.models.user import User


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


# ════════════════ Audit ════════════════


@router.get("/audit", summary="列出 audit log（admin）")
async def list_audit(
    request: Request,
    actor: str | None = Query(default=None, max_length=64),
    action: str | None = Query(default=None, max_length=100),
    entity_type: str | None = Query(default=None, max_length=50, alias="entity"),
    from_ts: str | None = Query(default=None, max_length=40, alias="from"),
    to_ts: str | None = Query(default=None, max_length=40, alias="to"),
    cursor: str | None = Query(default=None, max_length=2048),
    limit: int = Query(default=50, ge=1, le=100),
    _admin: User = Depends(admin_only),
    session: AsyncSession = Depends(get_rw_session),
):
    service = AdminService(session)
    limit = clamp_limit(limit)
    before_timestamp = None
    if cursor:
        before_timestamp = Cursor.decode(cursor).get("before_timestamp")

    rows = await service.list_audit(
        actor=actor,
        action=action,
        entity_type=entity_type,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit + 1,
        before_timestamp=before_timestamp,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [AuditLogOut.model_validate(r).model_dump(mode="json") for r in rows]
    next_kwargs = None
    if has_more and rows:
        next_kwargs = {"before_timestamp": rows[-1].timestamp}
    pagination = build_page_response(items, limit=limit, next_cursor_kwargs=next_kwargs)
    return envelope_success(items, trace_id=_trace_id(request), pagination=pagination)


# ════════════════ System metrics（轉發給 /metrics）════════════════


@router.get("/system/metrics", summary="取得 /metrics 摘要（admin）")
async def system_metrics(
    request: Request,
    _admin: User = Depends(admin_only),
):
    """簡單包裝：直接告訴 caller 去 /metrics 拉 Prometheus format。"""
    return envelope_success(
        {
            "endpoint": "/metrics",
            "note": "請以 Authorization: Bearer <admin token> 取得 Prometheus 文字格式",
        },
        trace_id=_trace_id(request),
    )


@router.get("/system/info", summary="系統摘要：版本 / env / 啟動時間（admin）")
async def system_info(
    request: Request,
    _admin: User = Depends(admin_only),
):
    from app.core.config import settings

    return envelope_success(
        {
            "version": settings.APP_VERSION,
            "env": settings.APP_ENV,
            "log_format": settings.LOG_FORMAT,
        },
        trace_id=_trace_id(request),
    )


# ════════════════ DLQ ════════════════


@router.get("/pipeline/dlq", summary="列出 Celery DLQ")
async def list_dlq(
    request: Request,
    resolved: bool | None = Query(default=False),
    cursor: str | None = Query(default=None, max_length=2048),
    limit: int = Query(default=50, ge=1, le=100),
    _admin: User = Depends(admin_only),
    session: AsyncSession = Depends(get_rw_session),
):
    service = AdminService(session)
    limit = clamp_limit(limit)
    before_failed_at = None
    if cursor:
        before_failed_at = Cursor.decode(cursor).get("before_failed_at")

    rows = await service.list_dlq(
        resolved=resolved,
        limit=limit + 1,
        before_failed_at=before_failed_at,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [DeadLetterOut.model_validate(r).model_dump(mode="json") for r in rows]
    next_kwargs = None
    if has_more and rows:
        next_kwargs = {"before_failed_at": rows[-1].failed_at}
    pagination = build_page_response(items, limit=limit, next_cursor_kwargs=next_kwargs)
    return envelope_success(items, trace_id=_trace_id(request), pagination=pagination)


@router.post("/pipeline/dlq/{dlq_id}/resolve", summary="標記 DLQ 為已解決")
async def resolve_dlq(
    dlq_id: int,
    payload: DLQResolveRequest,
    request: Request,
    admin: User = Depends(admin_only),
    session: AsyncSession = Depends(get_rw_session),
):
    service = AdminService(session)
    row = await service.resolve_dlq(
        admin=admin,
        dlq_id=dlq_id,
        notes=payload.notes,
        request_id=_trace_id(request),
    )
    return envelope_success(
        DeadLetterOut.model_validate(row).model_dump(mode="json"),
        trace_id=_trace_id(request),
    )


@router.post("/pipeline/dlq/{dlq_id}/requeue", summary="重新派發 DLQ 任務（stub）")
async def requeue_dlq(
    dlq_id: int,
    request: Request,
    admin: User = Depends(admin_only),
    session: AsyncSession = Depends(get_rw_session),
):
    service = AdminService(session)
    row = await service.requeue_dlq(
        admin=admin,
        dlq_id=dlq_id,
        request_id=_trace_id(request),
    )
    return envelope_success(
        DeadLetterOut.model_validate(row).model_dump(mode="json"),
        trace_id=_trace_id(request),
    )


# ════════════════ User sessions（強制下線）════════════════


@router.get("/users/{user_id}/sessions", summary="列出指定 user 的 sessions")
async def list_user_sessions(
    user_id: str,
    request: Request,
    _admin: User = Depends(admin_only),
    session: AsyncSession = Depends(get_rw_session),
):
    service = AdminService(session)
    uid = validate_uuid(user_id)
    rows = await service.list_sessions(uid)
    items = [UserSessionOut.model_validate(r).model_dump(mode="json") for r in rows]
    return envelope_success(items, trace_id=_trace_id(request))


@router.delete("/users/{user_id}/sessions/{jti}", summary="強制下線（blacklist + revoke）")
async def revoke_user_session(
    user_id: str,
    jti: str = Path(min_length=8, max_length=64),
    *,
    request: Request,
    admin: User = Depends(admin_only),
    session: AsyncSession = Depends(get_rw_session),
):
    service = AdminService(session)
    uid = validate_uuid(user_id)
    row = await service.force_logout(
        admin=admin,
        user_id=uid,
        jti=jti,
        request_id=_trace_id(request),
    )
    return envelope_success(
        {
            "jti": jti,
            "user_id": str(uid),
            "revoked": True,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        },
        trace_id=_trace_id(request),
    )


__all__ = ["router"]
