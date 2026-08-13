"""baseline: users + user_sessions + password_reset_tokens.

Phase 4 baseline part 1/13。

Revision ID: 0001
Revises:
Create Date: 2026-05-12

設計：
- email lowercase 唯一（functional index）
- role：CHECK constraint（VARCHAR + IN），避免 PG enum 跨 table 衝突
- onboarding_completed / must_change_password — PLAN 13.4
- failed_attempts / locked_until — PLAN 19.1 lockout
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100)),
        sa.Column("role", sa.String(50), nullable=False, server_default="VIEWER"),
        sa.Column("preferred_timezone", sa.String(50), nullable=False,
                  server_default="Asia/Taipei"),
        sa.Column("preferred_language", sa.String(10), nullable=False,
                  server_default="zh-TW"),
        sa.Column("onboarding_completed", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("must_change_password", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        sa.Column("failed_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_ip", postgresql.INET),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'ANALYST', 'VIEWER')",
            name="ck_users_role",
        ),
    )
    # 大小寫不敏感的唯一 email（functional index）
    op.execute("CREATE UNIQUE INDEX ix_users_email_lower ON users (LOWER(email))")
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    # ── user_sessions ──────────────────────────────────
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jti", sa.String(64), nullable=False),
        sa.Column("refresh_token_hash", sa.String(255), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("ip", postgresql.INET),
        sa.Column("user_agent", sa.Text),
        sa.UniqueConstraint("jti", name="uq_user_sessions_jti"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            ondelete="CASCADE",
            name="fk_user_sessions_user_id_users",
        ),
    )
    op.create_index("ix_user_sessions_user_id_expires", "user_sessions", ["user_id", "expires_at"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    # ── password_reset_tokens ─────────────────────────
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("ip", postgresql.INET),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            ondelete="CASCADE",
            name="fk_password_reset_tokens_user_id_users",
        ),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_expires_at",
                    "password_reset_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
    op.drop_table("user_sessions")
    op.execute("DROP INDEX IF EXISTS ix_users_email_lower")
    op.drop_table("users")
