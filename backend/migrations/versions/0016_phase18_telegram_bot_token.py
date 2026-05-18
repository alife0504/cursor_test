"""Phase 18: notification_settings 加 telegram_bot_token_encrypted.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-18

依 PLAN.md 第 19.4 章 + 第二十七章 Phase 18：
- LINE token 已有 line_token_encrypted (P11)
- Telegram chat_id 是公開資訊（非機敏）已在 telegram_chat_id 欄
- 本 phase 加 telegram_bot_token_encrypted 存「Telegram Bot Token」（機敏，必須加密）
- 同步加 enabled_notifiers 欄（與 enabled_channels 並列；channel 是 events.line/email；notifier 是
  實際發送目標 ID）
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_settings",
        sa.Column("telegram_bot_token_encrypted", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_settings", "telegram_bot_token_encrypted")
