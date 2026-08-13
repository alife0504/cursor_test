"""LINE Notify → Discord Webhook：notification_settings 換欄位 + channel CHECK 加 discord.

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-17

背景：LINE Notify 已於 2025/03 官方停止服務，改用 Discord Webhook。
- notification_settings：移除 line_token_encrypted、新增 discord_webhook_encrypted（Fernet 加密）
- notification_log.channel 的 CHECK constraint 加入 'discord'
  （保留 'line' 讓歷史 log 列不違反約束；short_enum 用 native_enum=False = VARCHAR + CHECK）
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 新舊 channel CHECK 內容（保留 line 給歷史 notification_log 列）
_CHANNEL_CHECK_NEW = "channel IN ('line', 'discord', 'telegram', 'email', 'webhook')"
_CHANNEL_CHECK_OLD = "channel IN ('line', 'telegram', 'email', 'webhook')"


def upgrade() -> None:
    # 1) notification_settings：新增 discord 欄、移除 line 欄
    op.add_column(
        "notification_settings",
        sa.Column("discord_webhook_encrypted", sa.Text, nullable=True),
    )
    op.drop_column("notification_settings", "line_token_encrypted")

    # 2) notification_log.channel CHECK 加入 'discord'
    op.drop_constraint("ck_notification_log_channel", "notification_log", type_="check")
    op.create_check_constraint(
        "ck_notification_log_channel", "notification_log", _CHANNEL_CHECK_NEW
    )


def downgrade() -> None:
    op.drop_constraint("ck_notification_log_channel", "notification_log", type_="check")
    # 歷史 log 可能已有 channel='discord' 的列（升級後實際發過通知），
    # 直接套舊 CHECK 會 CheckViolation → 先映射為語意最接近的 'webhook'。
    op.execute("UPDATE notification_log SET channel = 'webhook' WHERE channel = 'discord'")
    op.create_check_constraint(
        "ck_notification_log_channel", "notification_log", _CHANNEL_CHECK_OLD
    )
    op.add_column(
        "notification_settings",
        sa.Column("line_token_encrypted", sa.Text, nullable=True),
    )
    op.drop_column("notification_settings", "discord_webhook_encrypted")
