"""Phase 11 — /api/v1/notifications/* schemas。

Discord webhook URL 用 Fernet 加密儲存；response 永遠遮蔽（不回傳明文）。
（LINE Notify 已停服，改 Discord Webhook。）
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema

ALLOWED_CHANNELS = {"discord", "telegram", "email", "webhook"}
ALLOWED_EVENTS = {
    "analysis.completed",
    "analysis.failed",
    "order.approved",
    "order.rejected",
    "system.alert",
    "test",
}


class NotificationSettingsOut(BaseSchema):
    """GET /api/v1/notifications/settings 回應。

    P18：discord_webhook / telegram_bot_token 永遠遮蔽（只回 is_set / masked）。
    """

    user_id: UUID
    discord_webhook_masked: str | None = None
    discord_webhook_set: bool = False
    telegram_bot_token_set: bool = False
    telegram_chat_id: str | None = None
    email_enabled: bool = False
    enabled_channels: list[str] | None = None
    enabled_events: list[str] | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    updated_at: datetime


class NotificationSettingsUpdate(BaseSchema):
    """PUT /api/v1/notifications/settings 的 body。

    discord_webhook / telegram_bot_token / telegram_chat_id 為 None → 不變；
    為空字串 → 清空；
    其他值 → 加密寫入（token 類）或直接寫入（chat_id）。
    """

    discord_webhook: str | None = Field(default=None, max_length=500)
    telegram_bot_token: str | None = Field(default=None, max_length=500)
    telegram_chat_id: str | None = Field(default=None, max_length=50)
    email_enabled: bool | None = None
    enabled_channels: list[str] | None = Field(default=None, max_length=8)
    enabled_events: list[str] | None = Field(default=None, max_length=32)
    quiet_hours_start: str | None = Field(default=None, max_length=5)
    quiet_hours_end: str | None = Field(default=None, max_length=5)

    @field_validator("enabled_channels")
    @classmethod
    def validate_channels(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        bad = [c for c in v if c not in ALLOWED_CHANNELS]
        if bad:
            raise ValueError(f"channel 不支援：{bad}；允許：{sorted(ALLOWED_CHANNELS)}")
        return list(dict.fromkeys(v))

    @field_validator("enabled_events")
    @classmethod
    def validate_events(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        bad = [e for e in v if e not in ALLOWED_EVENTS]
        if bad:
            raise ValueError(f"event 不支援：{bad}")
        return list(dict.fromkeys(v))

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def validate_hhmm(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        # HH:MM
        if len(v) != 5 or v[2] != ":":
            raise ValueError("時間格式必須是 HH:MM")
        try:
            hh, mm = int(v[:2]), int(v[3:])
        except ValueError as e:
            raise ValueError("時間格式必須是 HH:MM（純數字）") from e
        if not (0 <= hh < 24 and 0 <= mm < 60):
            raise ValueError("時、分必須在合法範圍")
        return v


class NotificationTestRequest(BaseSchema):
    """POST /api/v1/notifications/test。

    P18：dry_run=True（預設）→ 寫 NotificationLog 但不真打外部；
    dry_run=False → 真打 Discord/Telegram（需 webhook/token 已設）。
    """

    channel: str = Field(default="discord", max_length=20)
    message: str = Field(default="TradingAgents-TW 測試通知", max_length=500)
    dry_run: bool = Field(default=True)

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        if v not in ALLOWED_CHANNELS:
            raise ValueError(f"channel 必須為：{sorted(ALLOWED_CHANNELS)}")
        return v


class NotificationLogOut(BaseSchema):
    """GET /api/v1/notifications/logs 元素。"""

    id: int
    user_id: UUID | None = None
    channel: str
    event_type: str
    payload: dict[str, Any] | list[Any]
    status: str
    error_msg: str | None = None
    retry_count: int
    sent_at: datetime


__all__ = [
    "ALLOWED_CHANNELS",
    "ALLOWED_EVENTS",
    "NotificationLogOut",
    "NotificationSettingsOut",
    "NotificationSettingsUpdate",
    "NotificationTestRequest",
]
