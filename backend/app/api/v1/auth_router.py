"""Phase 8 — /api/v1/auth/* 路由。

包含：login / refresh / logout / me / change-password / password-reset[/confirm] / ws-ticket。

Cookie 設計（依 PLAN 第 19.1 章）：
- refresh_token：httpOnly + Secure（prod）+ SameSite (Lax dev / Strict prod) + path=/api/v1/auth
- csrf_token：非 httpOnly（前端 JS 要讀來放 X-CSRF-Token header）+ Secure (prod) + SameSite=Lax

回應：統一走 envelope_success / 例外由 register_exception_handlers 接管。
"""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response

from app.api.dependencies import (
    get_auth_service,
    get_current_user,
    get_ws_ticket_service,
)
from app.core.config import settings
from app.core.csrf import CSRF_TOKEN_BYTES
from app.core.response_envelope import envelope_success
from app.core.ws_ticket import TICKET_TTL_SECONDS
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    PasswordResetRequestPayload,
    PasswordResetRequestResponse,
    RefreshResponse,
    UserPublic,
    WSTicketResponse,
)

if TYPE_CHECKING:
    from app.models.user import User
    from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
CSRF_COOKIE_NAME = "csrf_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _cookie_kwargs_refresh(max_age: int) -> dict:
    """refresh cookie：httpOnly + 走 /api/v1/auth path。

    dev: SameSite=Lax + Secure=False（http localhost）
    prod: SameSite=Strict + Secure=True
    """
    is_prod = settings.APP_ENV == "prod"
    return {
        "httponly": True,
        "secure": is_prod,
        "samesite": "strict" if is_prod else "lax",
        "max_age": max_age,
        "path": REFRESH_COOKIE_PATH,
    }


def _cookie_kwargs_csrf(max_age: int) -> dict:
    """csrf cookie：非 httpOnly（讓 JS 讀）。"""
    is_prod = settings.APP_ENV == "prod"
    return {
        "httponly": False,
        "secure": is_prod,
        "samesite": "strict" if is_prod else "lax",
        "max_age": max_age,
        "path": "/",
    }


def _client_ip(request: Request) -> str | None:
    """回有效 IP 字串或 None。

    Starlette TestClient 會傳 host='testclient'，這不是合法 IP，會炸 INET 欄位 →
    驗證後不合法一律回 None。
    Reverse proxy 後可改讀 X-Forwarded-For（P18 加 trusted proxy 設定）。
    """
    import ipaddress

    if request.client is None:
        return None
    host = request.client.host
    if not host:
        return None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return None
    return host


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "trace_id", None)


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _user_public(user: User) -> UserPublic:
    return UserPublic(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        preferred_timezone=user.preferred_timezone,
        preferred_language=user.preferred_language,
        onboarding_completed=user.onboarding_completed,
        must_change_password=user.must_change_password,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
    )


# ════════════════ /login ════════════════


@router.post("/login", summary="登入（取 access + refresh + CSRF cookie）")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    result = await service.login(
        email=str(payload.email),
        password=payload.password,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
        request_id=_request_id(request),
    )

    from datetime import datetime

    refresh_max_age = max(
        0,
        int((result.refresh_expires_at - datetime.now(UTC)).total_seconds()),
    )

    response.set_cookie(
        REFRESH_COOKIE_NAME,
        result.refresh_token,
        **_cookie_kwargs_refresh(refresh_max_age),
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        result.csrf_token,
        **_cookie_kwargs_csrf(refresh_max_age),
    )

    body = LoginResponse(
        access_token=result.access_token,
        expires_in=result.access_ttl_seconds,
        next_action=result.next_action,  # type: ignore[arg-type]
        user=_user_public(result.user),
    )
    return envelope_success(body.model_dump(mode="json"), trace_id=request.state.trace_id)


# ════════════════ /refresh ════════════════


@router.post("/refresh", summary="用 refresh cookie 換新 access（需 X-CSRF-Token）")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    service: AuthService = Depends(get_auth_service),
):
    from datetime import datetime

    result = await service.refresh(
        refresh_token=refresh_token or "",
        csrf_header=x_csrf_token,
        csrf_cookie=csrf_cookie,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
        request_id=_request_id(request),
    )
    refresh_max_age = max(
        0,
        int((result.refresh_expires_at - datetime.now(UTC)).total_seconds()),
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        result.refresh_token,
        **_cookie_kwargs_refresh(refresh_max_age),
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        result.csrf_token,
        **_cookie_kwargs_csrf(refresh_max_age),
    )
    body = RefreshResponse(
        access_token=result.access_token,
        expires_in=result.access_ttl_seconds,
    )
    return envelope_success(body.model_dump(mode="json"), trace_id=request.state.trace_id)


# ════════════════ /logout ════════════════


@router.post("/logout", summary="登出（撤銷 refresh session + access blacklist）")
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    service: AuthService = Depends(get_auth_service),
):
    await service.logout(
        refresh_token=refresh_token,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
        request_id=_request_id(request),
    )
    # 清 cookie
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    return envelope_success(
        LogoutResponse().model_dump(mode="json"),
        trace_id=request.state.trace_id,
    )


# ════════════════ /me ════════════════


@router.get("/me", summary="目前登入的使用者資訊")
async def me(request: Request, user: User = Depends(get_current_user)):
    body = MeResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        preferred_timezone=user.preferred_timezone,
        preferred_language=user.preferred_language,
        onboarding_completed=user.onboarding_completed,
        must_change_password=user.must_change_password,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
    )
    return envelope_success(body.model_dump(mode="json"), trace_id=request.state.trace_id)


# ════════════════ /change-password ════════════════


@router.post("/change-password", summary="改密碼（需登入 + 提供舊密碼）")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    await service.change_password(
        user_id=user.id,
        old_password=payload.old_password,
        new_password=payload.new_password,
        current_refresh_jti=None,  # 改密碼一律撤銷全部 session（最安全做法）
        ip=_client_ip(request),
        user_agent=_user_agent(request),
        request_id=_request_id(request),
    )
    return envelope_success(
        ChangePasswordResponse().model_dump(mode="json"),
        trace_id=request.state.trace_id,
    )


# ════════════════ /password-reset (request) ════════════════


@router.post("/password-reset", summary="發起密碼重置（限速 3/hr/IP）")
async def password_reset_request(
    payload: PasswordResetRequestPayload,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ip = _client_ip(request) or "0.0.0.0"  # noqa: S104 — fallback IP，僅供 audit log + rate limit key
    token = await service.password_reset_request(
        email=str(payload.email),
        ip=ip,
        user_agent=_user_agent(request),
        request_id=_request_id(request),
    )
    # dev / test 環境直接回 token 方便手測；prod 由 P18 寄信
    body: dict = PasswordResetRequestResponse().model_dump(mode="json")
    if settings.APP_ENV != "prod" and token is not None:
        body["dev_token"] = token
    return envelope_success(body, trace_id=request.state.trace_id)


# ════════════════ /password-reset/confirm ════════════════


@router.post("/password-reset/confirm", summary="確認重置密碼（用 dev_token 或 email link）")
async def password_reset_confirm(
    payload: PasswordResetConfirmRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    await service.password_reset_confirm(
        token=payload.token,
        new_password=payload.new_password,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
        request_id=_request_id(request),
    )
    return envelope_success(
        PasswordResetConfirmResponse().model_dump(mode="json"),
        trace_id=request.state.trace_id,
    )


# ════════════════ /ws-ticket ════════════════


@router.post("/ws-ticket", summary="取一次性 WebSocket ticket（60s TTL）")
async def issue_ws_ticket(
    request: Request,
    user: User = Depends(get_current_user),
    svc=Depends(get_ws_ticket_service),
):
    ticket = await svc.issue(user.id)
    body = WSTicketResponse(
        ticket=ticket,
        expires_in=TICKET_TTL_SECONDS,
        subprotocol_hint=("new WebSocket(url, ['tradingagents.v1', `ticket.${ticket}`])"),
    )
    return envelope_success(body.model_dump(mode="json"), trace_id=request.state.trace_id)


__all__ = ["CSRF_COOKIE_NAME", "REFRESH_COOKIE_NAME", "REFRESH_COOKIE_PATH", "router"]

# csrf token bytes 用於 swagger 顯示（避免 import 後 ruff 認為 unused）
_ = CSRF_TOKEN_BYTES
