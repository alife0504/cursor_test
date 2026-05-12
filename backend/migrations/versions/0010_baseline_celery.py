"""baseline: celery_dead_letters（hypertable）+ idempotency_keys.

Phase 4 baseline part 10/13。

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-12

設計：
- celery_dead_letters：(id, failed_at) 複合 PK；hypertable（chunk 1 month）
  retention 1 年 — Phase 4 設定全表 retention；應用層 cleanup 只刪 resolved=true 的舊紀錄
- idempotency_keys：TEXT PK；DB-side default 24h TTL
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── celery_dead_letters ───────────────────────────
    op.create_table(
        "celery_dead_letters",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True)),
        sa.Column("args", postgresql.JSONB),
        sa.Column("kwargs", postgresql.JSONB),
        sa.Column("exception_type", sa.String(255)),
        sa.Column("exception", sa.Text),
        sa.Column("traceback", sa.Text),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("resolved", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True)),
        sa.Column("resolution_notes", sa.Text),
        sa.PrimaryKeyConstraint("id", "failed_at", name="pk_celery_dead_letters"),
    )
    op.create_index("ix_celery_dead_letters_resolved_failed", "celery_dead_letters",
                    ["resolved", "failed_at"])
    op.create_index("ix_celery_dead_letters_task_name", "celery_dead_letters",
                    ["task_name"])

    op.execute(
        "SELECT create_hypertable('celery_dead_letters', 'failed_at', "
        "chunk_time_interval => INTERVAL '1 month', "
        "if_not_exists => TRUE, migrate_data => TRUE)"
    )
    op.execute(
        "SELECT add_retention_policy('celery_dead_letters', INTERVAL '1 year', "
        "if_not_exists => TRUE)"
    )

    # ── idempotency_keys ──────────────────────────────
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", postgresql.JSONB),
        sa.Column("status_code", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW() + INTERVAL '24 hours'"),
        ),
    )
    op.create_index("ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"])
    op.create_index("ix_idempotency_keys_user_id", "idempotency_keys", ["user_id"])


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.execute("SELECT remove_retention_policy('celery_dead_letters', if_exists => TRUE)")
    op.drop_table("celery_dead_letters")
