"""Notification models — LINE / Telegram / Email 通知（PLAN 第 20.2 章）。

notification_log：hypertable on sent_at（retention 90 天）。
notification_settings：普通表，1:1 user。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, short_enum

NOTIFICATION_CHANNEL_VALUES = ("line", "telegram", "email", "webhook")
NOTIFICATION_STATUS_VALUES = ("queued", "sent", "failed", "retry")


class NotificationLog(Base):
    """通知發送紀錄 — hypertable on sent_at。"""

    __tablename__ = "notification_log"

    # 複合 PK — (id, sent_at)：hypertable 要求
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        server_default=func.now(),
        nullable=False,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    channel: Mapped[str] = mapped_column(
        short_enum(*NOTIFICATION_CHANNEL_VALUES, name="notification_channel_enum"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    """analysis.completed / order.approved / system.alert ..."""

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    """通知內容（標題、訊息、deep link）。"""

    status: Mapped[str] = mapped_column(
        short_enum(*NOTIFICATION_STATUS_VALUES, name="notification_status_enum"),
        nullable=False,
        server_default="queued",
    )
    error_msg: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")

    __table_args__ = (
        Index("ix_notification_log_user_sent", "user_id", "sent_at"),
        Index("ix_notification_log_status", "status"),
        Index("ix_notification_log_event_type", "event_type"),
    )


class NotificationSetting(Base):
    """每用戶通知偏好（1:1 與 users）。LINE token 用 Fernet 加密儲存。"""

    __tablename__ = "notification_settings"

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

    line_token_encrypted: Mapped[str | None] = mapped_column(Text)
    """Fernet 加密後的 LINE Notify token（PLAN 19.4）。"""
    telegram_bot_token_encrypted: Mapped[str | None] = mapped_column(Text)
    """Phase 18 加：Fernet 加密的 Telegram Bot Token（機敏；與 chat_id 分開）。"""
    telegram_chat_id: Mapped[str | None] = mapped_column(String(50))
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    enabled_channels: Mapped[list | None] = mapped_column(JSONB)
    """如 ["line", "email"] — 啟用的 channel 清單。"""
    enabled_events: Mapped[list | None] = mapped_column(JSONB)
    """如 ["analysis.completed", "order.approved"] — 接收的事件類型。"""

    quiet_hours_start: Mapped[str | None] = mapped_column(String(5))
    """如 22:00 — 此時段內僅 CRITICAL 才送。"""
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", name="uq_notification_settings_user_id"),)


__all__ = [
    "NOTIFICATION_CHANNEL_VALUES",
    "NOTIFICATION_STATUS_VALUES",
    "NotificationLog",
    "NotificationSetting",
]
