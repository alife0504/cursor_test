"""Phase 8 — FastAPI dependencies：取 current user、檢查 role、開 service。

依 PLAN.md 第 19.1 章認證授權（RBAC: ADMIN / ANALYST / VIEWER）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_rw_session
from app.core.errors import AuthError, ForbiddenError
from app.core.redis_client import RedisDB, get_redis
from app.core.security import JWTService, TokenBlacklist
from app.core.ws_ticket import WSTicketService
from app.repos.user_repo import UserRepository
from app.services.auth_service import AuthService

if TYPE_CHECKING:
    from app.models.user import User


# ─────────────────────────────────────────────────────────
# Service factories
# ─────────────────────────────────────────────────────────


def get_jwt_service(request: Request) -> JWTService:
    """從 app.state 拿 lifespan 啟動時建好的 JWTService 單例。"""
    svc: JWTService | None = getattr(request.app.state, "jwt_service", None)
    if svc is None:
        # 退路：lazy 建
        from app.core.config import settings as _settings

        svc = JWTService(_settings)
        request.app.state.jwt_service = svc
    return svc


async def get_token_blacklist() -> TokenBlacklist:
    redis = await get_redis(RedisDB.JWT_BLACKLIST)
    return TokenBlacklist(redis)


async def get_ws_ticket_service(request: Request) -> WSTicketService:
    """先試 app.state；沒有則 lazy 建。"""
    svc: WSTicketService | None = getattr(request.app.state, "ws_ticket_service", None)
    if svc is None:
        redis = await get_redis(RedisDB.WS_TICKET)
        svc = WSTicketService(redis)
        request.app.state.ws_ticket_service = svc
    return svc


async def get_auth_service(
    session: AsyncSession = Depends(get_rw_session),
    jwt_service: JWTService = Depends(get_jwt_service),
    blacklist: TokenBlacklist = Depends(get_token_blacklist),
) -> AuthService:
    return AuthService(session=session, jwt_service=jwt_service, blacklist=blacklist)


# ─────────────────────────────────────────────────────────
# Current user / role check
# ─────────────────────────────────────────────────────────


def _parse_bearer(authorization: str | None) -> str:
    """從 'Authorization: Bearer xxx' header 抽出 token。"""
    if not authorization:
        raise AuthError(message_zh="缺少 Authorization header")
    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError(message_zh="Authorization header 格式錯誤（應為 Bearer <token>）")
    return parts[1]


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_rw_session),
    jwt_service: JWTService = Depends(get_jwt_service),
    blacklist: TokenBlacklist = Depends(get_token_blacklist),
) -> User:
    """從 access token 解出 user。失敗 raise AuthError（exception handler 回 401）。"""
    token = _parse_bearer(authorization)
    payload = jwt_service.decode(token)
    if payload.get("type") != "access":
        raise AuthError(message_zh="Token 類型錯誤（不是 access token）")

    jti = str(payload.get("jti") or "")
    if jti and await blacklist.is_blacklisted(jti):
        raise AuthError(message_zh="Token 已被撤銷")

    sub = payload.get("sub")
    if not sub:
        raise AuthError(message_zh="Token 內容不完整")

    try:
        user_id = UUID(str(sub))
    except (ValueError, TypeError) as e:
        raise AuthError(message_zh="Token 內容無效") from e

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise AuthError(message_zh="帳號不存在或已停用")

    # 把 payload 帶到 request.state 方便其他層讀
    request.state.access_jti = jti
    request.state.actor_id = str(user.id)
    return user


def require_role(*roles: str):
    """產生一個 dependency：檢查 current user 的 role 在指定範圍內。"""
    allowed = {r.upper() for r in roles}

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role.upper() not in allowed:
            raise ForbiddenError(
                message_zh="權限不足",
                allowed_roles=sorted(allowed),
                actual_role=user.role,
            )
        return user

    return _checker


# 常用 shortcut（每個 Phase 都會 import）
admin_only = require_role("ADMIN")
analyst_or_admin = require_role("ADMIN", "ANALYST")
any_authenticated = get_current_user


__all__ = [
    "admin_only",
    "analyst_or_admin",
    "any_authenticated",
    "get_auth_service",
    "get_current_user",
    "get_jwt_service",
    "get_token_blacklist",
    "get_ws_ticket_service",
    "require_role",
]
