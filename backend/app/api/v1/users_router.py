"""Phase 10 — /api/v1/users/* router。

依 PLAN.md 第 19.1 章 RBAC：
- list / create / soft-delete / reset-password：admin only
- get / patch：admin or self
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import admin_only, get_current_user
from app.core.cursor import build_page_response
from app.core.database import get_rw_session
from app.core.errors import ForbiddenError
from app.core.response_envelope import envelope_success
from app.core.validators import validate_uuid
from app.schemas.users import (
    UserCreateRequest,
    UserDeleteResponse,
    UserPublic,
    UserResetPasswordRequest,
    UserResetPasswordResponse,
    UserUpdateRequest,
)
from app.services.quota_service import QuotaService
from app.services.user_service import UserService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


def _to_public(user) -> dict:
    return UserPublic(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,  # type: ignore[arg-type]
        preferred_timezone=user.preferred_timezone,
        preferred_language=user.preferred_language,
        onboarding_completed=user.onboarding_completed,
        must_change_password=user.must_change_password,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=getattr(user, "created_at", None),
    ).model_dump(mode="json")


@router.get("/me/quota", summary="目前登入者本月 LLM 月配額用量")
async def my_quota(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    """回傳當月已用 / 限額 / 百分比；dashboard LLM 月用量 progress bar 用。"""
    quota = QuotaService()
    allowed, used, limit = await quota.check_user_can_analyze(user.id, session=session)
    used_str = str(used)
    limit_str = str(limit)
    pct = float(used / limit) if limit and limit > 0 else 0.0
    return envelope_success(
        {
            "used_usd": used_str,
            "limit_usd": limit_str,
            "allowed": allowed,
            "percentage": round(min(pct, 1.0) * 100, 2),
        },
        trace_id=_trace_id(request),
    )


@router.get("", summary="列出使用者（admin only，cursor 分頁）")
async def list_users(
    request: Request,
    cursor: str | None = Query(default=None, max_length=2048),
    limit: int = Query(default=50, ge=1, le=100),
    include_deleted: bool = Query(default=False),
    _admin: User = Depends(admin_only),
    session: AsyncSession = Depends(get_rw_session),
):
    service = UserService(session)
    page = await service.list_users(cursor=cursor, limit=limit, include_deleted=include_deleted)
    items = [_to_public(u) for u in page.items]
    pagination = build_page_response(
        items, limit=page.limit, next_cursor_kwargs=page.next_cursor_kwargs
    )
    return envelope_success(items, trace_id=_trace_id(request), pagination=pagination)


@router.post("", status_code=201, summary="建立使用者（admin only）")
async def create_user(
    payload: UserCreateRequest,
    request: Request,
    _admin: User = Depends(admin_only),
    session: AsyncSession = Depends(get_rw_session),
):
    service = UserService(session)
    user = await service.create_user(
        email=str(payload.email),
        password=payload.password,
        full_name=payload.full_name,
        role=payload.role,
        preferred_timezone=payload.preferred_timezone,
        preferred_language=payload.preferred_language,
        must_change_password=payload.must_change_password,
    )
    return envelope_success(_to_public(user), trace_id=_trace_id(request))


@router.get("/{user_id}", summary="取使用者（admin or self）")
async def get_user(
    user_id: str,
    request: Request,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    uid = validate_uuid(user_id)
    # admin or self
    if actor.role.upper() != "ADMIN" and str(actor.id) != str(uid):
        raise ForbiddenError(message_zh="只能查自己；admin 才能查他人")
    service = UserService(session)
    user = await service.get_user(uid)
    return envelope_success(_to_public(user), trace_id=_trace_id(request))


@router.patch("/{user_id}", summary="更新使用者（admin 全欄位；self 只能改個人偏好）")
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    request: Request,
    actor: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    uid = validate_uuid(user_id)
    is_admin = actor.role.upper() == "ADMIN"
    is_self = str(actor.id) == str(uid)
    if not (is_admin or is_self):
        raise ForbiddenError(message_zh="只能改自己；admin 才能改他人")

    # self 不能改 role / is_active
    if not is_admin:
        if payload.role is not None:
            raise ForbiddenError(message_zh="不可自行改 role（admin 限定）", field="role")
        if payload.is_active is not None:
            raise ForbiddenError(message_zh="不可自行改 is_active（admin 限定）", field="is_active")

    service = UserService(session)
    updated = await service.update_user(
        uid,
        full_name=payload.full_name,
        role=payload.role,
        preferred_timezone=payload.preferred_timezone,
        preferred_language=payload.preferred_language,
        is_active=payload.is_active,
    )
    return envelope_success(_to_public(updated), trace_id=_trace_id(request))


@router.delete("/{user_id}", summary="軟刪除使用者（admin only）")
async def delete_user(
    user_id: str,
    request: Request,
    _admin: User = Depends(admin_only),
    session: AsyncSession = Depends(get_rw_session),
):
    uid = validate_uuid(user_id)
    service = UserService(session)
    await service.soft_delete_user(uid)
    return envelope_success(
        UserDeleteResponse().model_dump(mode="json"),
        trace_id=_trace_id(request),
    )


@router.post("/{user_id}/reset-password", summary="重設使用者密碼（admin only）")
async def reset_password(
    user_id: str,
    payload: UserResetPasswordRequest,
    request: Request,
    _admin: User = Depends(admin_only),
    session: AsyncSession = Depends(get_rw_session),
):
    uid = validate_uuid(user_id)
    service = UserService(session)
    await service.reset_password(
        uid,
        new_password=payload.new_password,
        must_change_password=payload.must_change_password,
    )
    return envelope_success(
        UserResetPasswordResponse().model_dump(mode="json"),
        trace_id=_trace_id(request),
    )


__all__ = ["router"]
