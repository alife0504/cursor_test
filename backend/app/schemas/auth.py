"""Phase 8 — Auth router 的 Pydantic schemas。

依 PLAN.md 第 19.1 章認證授權 + 第 13.4 章 onboarding next_action。

所有 schema 用 Pydantic v2。對 password 欄位設 `Field(min_length=12, max_length=128)`
做最外層 dumb validation（細節在 password_policy.validate_password 才校驗 4 類字元）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

NextAction = Literal["change_password", "onboarding", "dashboard"]
"""login 成功後前端下一步：強制改密碼 / onboarding / 進 dashboard。"""

Role = Literal["ADMIN", "ANALYST", "VIEWER"]


class UserPublic(BaseModel):
    """對外暴露的 user 公開欄位 — 不含 password_hash / failed_attempts 等敏感欄位。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str | None = None
    role: Role
    preferred_timezone: str
    preferred_language: str
    onboarding_completed: bool
    must_change_password: bool
    is_active: bool
    last_login_at: datetime | None = None


# ────────────────────────────────────────────────────────
# /auth/login
# ────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    """密碼長度限制較鬆 — 真正的強度檢查在 change-password 才做（避免 login 時把密碼洩漏在錯誤訊息）。"""


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = Field(description="access token 剩餘秒數")
    next_action: NextAction
    user: UserPublic


# ────────────────────────────────────────────────────────
# /auth/refresh
# ────────────────────────────────────────────────────────


class RefreshResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int


# ────────────────────────────────────────────────────────
# /auth/change-password
# ────────────────────────────────────────────────────────


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)


class ChangePasswordResponse(BaseModel):
    ok: Literal[True] = True
    message: str = "密碼已更新；其他裝置的 session 已撤銷"


# ────────────────────────────────────────────────────────
# /auth/password-reset (request + confirm)
# ────────────────────────────────────────────────────────


class PasswordResetRequestPayload(BaseModel):
    email: EmailStr


class PasswordResetRequestResponse(BaseModel):
    """為避免列舉 email，無論 email 是否存在一律回此 response。"""

    ok: Literal[True] = True
    message: str = "若帳號存在，已寄出重置連結（30 分鐘內有效）"


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=10, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)


class PasswordResetConfirmResponse(BaseModel):
    ok: Literal[True] = True
    message: str = "密碼已重置；所有舊 session 已失效，請重新登入"


# ────────────────────────────────────────────────────────
# /auth/ws-ticket
# ────────────────────────────────────────────────────────


class WSTicketResponse(BaseModel):
    ticket: str
    expires_in: int = Field(description="ticket TTL 秒數")
    subprotocol_hint: str = Field(
        description="提示前端 new WebSocket(url, ['tradingagents.v1', `ticket.${ticket}`])"
    )


# ────────────────────────────────────────────────────────
# /auth/me
# ────────────────────────────────────────────────────────


class MeResponse(UserPublic):
    """同 UserPublic，但語意上是「自己的資訊」。"""


# ────────────────────────────────────────────────────────
# /auth/logout
# ────────────────────────────────────────────────────────


class LogoutResponse(BaseModel):
    ok: Literal[True] = True
    message: str = "已登出"


__all__ = [
    "ChangePasswordRequest",
    "ChangePasswordResponse",
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    "MeResponse",
    "NextAction",
    "PasswordResetConfirmRequest",
    "PasswordResetConfirmResponse",
    "PasswordResetRequestPayload",
    "PasswordResetRequestResponse",
    "RefreshResponse",
    "Role",
    "UserPublic",
    "WSTicketResponse",
]
