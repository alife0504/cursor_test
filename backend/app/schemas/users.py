"""Phase 10 — /api/v1/users/* 的 Pydantic schemas。

依 PLAN.md 第 19.1 章認證授權（ADMIN/ANALYST/VIEWER）。

設計：
- UserPublic 直接 reuse auth.UserPublic 結構但獨立定義（解耦）
- UserCreateRequest 走 admin 建用戶流程：管理員設初始密碼 + 強制下次改密碼
- UserUpdateRequest 允許部分更新；密碼變更走 /auth/change-password，不在這
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.core.password_policy import (
    MIN_LENGTH as PASSWORD_MIN_LENGTH,
)
from app.core.password_policy import validate_password
from app.schemas.common import BaseSchema

Role = Literal["ADMIN", "ANALYST", "VIEWER"]


class UserCreateRequest(BaseSchema):
    """admin 建立新使用者。"""

    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)
    role: Role = "VIEWER"
    preferred_timezone: str = Field(default="Asia/Taipei", max_length=50)
    preferred_language: str = Field(default="zh-TW", max_length=10)
    must_change_password: bool = Field(
        default=True,
        description="預設 True：使用者下次登入必須改密碼（admin 初始建立行為）",
    )

    @field_validator("password")
    @classmethod
    def _check_complexity(cls, v: str) -> str:
        # 走全域 password policy：4 類字元 / 不在弱口令庫
        validate_password(v)
        return v


class UserUpdateRequest(BaseSchema):
    """部分更新（admin or self；admin 才能改 role / is_active）。"""

    full_name: str | None = Field(default=None, max_length=100)
    role: Role | None = None
    preferred_timezone: str | None = Field(default=None, max_length=50)
    preferred_language: str | None = Field(default=None, max_length=10)
    is_active: bool | None = None


class UserPublic(BaseSchema):
    """對外暴露的 user 公開欄位 — 不含 password_hash / failed_attempts 等敏感欄位。"""

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
    created_at: datetime | None = None


class UserDeleteResponse(BaseSchema):
    ok: Literal[True] = True
    message: str = "使用者已軟刪除（is_active=false）"


class UserResetPasswordRequest(BaseSchema):
    """admin 為使用者重設密碼。"""

    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)
    must_change_password: bool = Field(default=True, description="預設 True：強制下次登入改密碼")

    @field_validator("new_password")
    @classmethod
    def _check_complexity(cls, v: str) -> str:
        validate_password(v)
        return v


class UserResetPasswordResponse(BaseSchema):
    ok: Literal[True] = True
    message: str = "密碼已重設；該使用者所有 session 已撤銷"


__all__ = [
    "Role",
    "UserCreateRequest",
    "UserDeleteResponse",
    "UserPublic",
    "UserResetPasswordRequest",
    "UserResetPasswordResponse",
    "UserUpdateRequest",
]
