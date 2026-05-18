"""Phase 11 — /api/v1/orders/* router。

GET 任何 role 可看（自己的；admin 可看全部）；approve / reject 限 ADMIN / ANALYST。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.cursor import Cursor, build_page_response, clamp_limit
from app.core.database import get_rw_session
from app.core.logging_config import get_logger
from app.core.response_envelope import envelope_success
from app.core.validators import validate_uuid
from app.schemas.orders import OrderApproveRequest, OrderRejectRequest, OrderSummary
from app.services.order_service import OrderService

logger = get_logger(__name__)

if TYPE_CHECKING:
    from app.models.user import User


router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


def _to_item(order) -> dict:
    return OrderSummary.model_validate(order).model_dump(mode="json")


# ════════════════ GET / ════════════════


@router.get("", summary="列出訂單（依 status 過濾）")
async def list_orders(
    request: Request,
    status: str | None = Query(default=None, max_length=20),
    cursor: str | None = Query(default=None, max_length=2048),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = OrderService(session)
    limit = clamp_limit(limit)
    before_created_at = None
    if cursor:
        before_created_at = Cursor.decode(cursor).get("before_created_at")

    rows = await service.list_orders(
        user, status=status, limit=limit + 1, before_created_at=before_created_at
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_to_item(r) for r in rows]
    next_kwargs = None
    if has_more and rows:
        next_kwargs = {"before_created_at": rows[-1].created_at}
    pagination = build_page_response(items, limit=limit, next_cursor_kwargs=next_kwargs)
    return envelope_success(items, trace_id=_trace_id(request), pagination=pagination)


# ════════════════ GET /{id} ════════════════


@router.get("/{order_id}", summary="取得訂單詳情")
async def get_order(
    order_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = OrderService(session)
    uid = validate_uuid(order_id)
    order = await service.get_for_user(user, uid)
    return envelope_success(_to_item(order), trace_id=_trace_id(request))


# ════════════════ POST /{id}/approve ════════════════


@router.post("/{order_id}/approve", summary="核准訂單（並發保護）")
async def approve_order(
    order_id: str,
    request: Request,
    payload: OrderApproveRequest = OrderApproveRequest(),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = OrderService(session)
    uid = validate_uuid(order_id)
    order = await service.approve(
        reviewer=user,
        order_id=uid,
        expected_version=payload.expected_version,
        notes=payload.notes,
        request_id=_trace_id(request),
    )
    _dispatch_order_notification(order, "order.approved", reviewer=user, request=request)
    return envelope_success(_to_item(order), trace_id=_trace_id(request))


# ════════════════ POST /{id}/reject ════════════════


@router.post("/{order_id}/reject", summary="拒絕訂單")
async def reject_order(
    order_id: str,
    payload: OrderRejectRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = OrderService(session)
    uid = validate_uuid(order_id)
    order = await service.reject(
        reviewer=user,
        order_id=uid,
        reason=payload.reason,
        expected_version=payload.expected_version,
        request_id=_trace_id(request),
    )
    _dispatch_order_notification(
        order, "order.rejected", reviewer=user, request=request, reason=payload.reason
    )
    return envelope_success(_to_item(order), trace_id=_trace_id(request))


# ════════════════ P18：order 通知 dispatch ════════════════


def _dispatch_order_notification(
    order,
    event_type: str,
    *,
    reviewer,
    request: Request,
    reason: str | None = None,
) -> None:
    """P18：核准 / 拒絕後 fire-and-forget 通知下單者。

    異常吞下並 log，不影響 approve/reject 主流程。
    """
    try:
        from app.notifications import NotifyEvent, NotifyLevel, get_dispatcher

        approved = event_type == "order.approved"
        title = (
            f"訂單已核准 — {order.symbol} {order.side} {order.qty}"
            if approved
            else f"訂單已拒絕 — {order.symbol} {order.side} {order.qty}"
        )
        body_lines = [
            f"標的：{order.symbol}",
            f"方向：{order.side}  數量：{order.qty}",
            f"審核者：{reviewer.email if hasattr(reviewer, 'email') else reviewer.id}",
        ]
        if reason:
            body_lines.append(f"原因：{reason}")
        level = NotifyLevel.SUCCESS if approved else NotifyLevel.WARN
        get_dispatcher().dispatch_in_background(
            NotifyEvent(
                event_type=event_type,
                user_id=order.user_id,
                title=title,
                body="\n".join(body_lines),
                level=level,
                metadata={
                    "trace_id": _trace_id(request),
                    "order_id": str(order.id),
                    "symbol": order.symbol,
                },
            )
        )
    except Exception as exc:
        # 通知是 best-effort（不影響 approve/reject 主流程）
        logger.debug("order_notify.skipped", error=str(exc))


__all__ = ["router"]
