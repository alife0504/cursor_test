"""baseline: notification_log（hypertable）+ notification_settings.

Phase 4 baseline part 11/13。

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-12

設計：
- notification_log：(id, sent_at) 複合 PK；hypertable（chunk 1 month，retention 90 天）
- notification_settings：1:1 與 users；LINE token Fernet 加密儲存
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHANNEL_CHECK = "channel IN ('line', 'telegram', 'email', 'webhook')"
_NOTIF_STATUS_CHECK = "status IN ('queued', 'sent', 'failed', 'retry')"


def upgrade() -> None:
    # ── notification_log ──────────────────────────────
    op.create_table(
        "notification_log",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("error_msg", sa.Text),
        sa.Column("retry_count", sa.BigInteger, nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", "sent_at", name="pk_notification_log"),
        sa.CheckConstraint(_CHANNEL_CHECK, name="ck_notification_log_channel"),
        sa.CheckConstraint(_NOTIF_STATUS_CHECK, name="ck_notification_log_status"),
    )
    op.create_index("ix_notification_log_user_sent", "notification_log",
                    ["user_id", "sent_at"])
    op.create_index("ix_notification_log_status", "notification_log", ["status"])
    op.create_index("ix_notification_log_event_type", "notification_log", ["event_type"])

    op.execute(
        "SELECT create_hypertable('notification_log', 'sent_at', "
        "chunk_time_interval => INTERVAL '1 month', "
        "if_not_exists => TRUE, migrate_data => TRUE)"
    )
    # retention 90 days
    op.execute(
        "SELECT add_retention_policy('notification_log', INTERVAL '90 days', "
        "if_not_exists => TRUE)"
    )

    # ── notification_settings ─────────────────────────
    op.create_table(
        "notification_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_token_encrypted", sa.Text),
        sa.Column("telegram_chat_id", sa.String(50)),
        sa.Column("email_enabled", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("enabled_channels", postgresql.JSONB),
        sa.Column("enabled_events", postgresql.JSONB),
        sa.Column("quiet_hours_start", sa.String(5)),
        sa.Column("quiet_hours_end", sa.String(5)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            ondelete="CASCADE",
            name="fk_notification_settings_user_id_users",
        ),
        sa.UniqueConstraint("user_id", name="uq_notification_settings_user_id"),
    )


def downgrade() -> None:
    op.drop_table("notification_settings")
    op.execute("SELECT remove_retention_policy('notification_log', if_exists => TRUE)")
    op.drop_table("notification_log")
