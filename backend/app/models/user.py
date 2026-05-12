"""User-related models: User, UserSession, PasswordResetToken。

依 PLAN.md 第 13.4 章 onboarding + 第 19.1 章認證授權 + 第 15.4 章 orphan cleanup。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampedMixin, short_enum


class UserRole(str):
    """角色常數（不用 Python Enum，因 PG enum 已在 DB 層強制）。"""

    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class User(Base, TimestampedMixin):
    """使用者主表。v1.0 不開放註冊，由 admin 建立。"""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(
        short_enum("ADMIN", "ANALYST", "VIEWER", name="user_role_enum"),
        nullable=False,
        server_default="VIEWER",
    )
    preferred_timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="Asia/Taipei"
    )
    preferred_language: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="zh-TW"
    )

    # Onboarding（第 13.4 章）
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # Lockout（第 19.1 章 5 次失敗 → 15 分鐘鎖）
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_ip: Mapped[str | None] = mapped_column(INET)

    # 軟刪除
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # LLM monthly budget override（None 表用全域預設）
    # 改放 llm_monthly_quota 表的 per-user override；這裡不放

    __table_args__ = (
        Index("ix_users_email_lower", func.lower(email), unique=True),
        Index("ix_users_role", "role"),
        Index("ix_users_is_active", "is_active"),
    )


class UserSession(Base):
    """JWT refresh session — per user 5 個上限（第 19.1 章）。"""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    """JWT ID — JWT 黑名單比對用。"""
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_user_sessions_user_id_expires", "user_id", "expires_at"),
        Index("ix_user_sessions_expires_at", "expires_at"),
    )


class PasswordResetToken(Base):
    """密碼重置 token — 一次性 + 限速 3/hr/IP（第 19.1 章）。"""

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ip: Mapped[str | None] = mapped_column(INET)

    __table_args__ = (
        Index("ix_password_reset_tokens_user_id", "user_id"),
        Index("ix_password_reset_tokens_expires_at", "expires_at"),
    )


__all__ = ["PasswordResetToken", "User", "UserRole", "UserSession"]
