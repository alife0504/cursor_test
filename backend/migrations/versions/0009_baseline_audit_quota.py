"""baseline: audit_logs（hypertable）+ llm_usage（hypertable）+ llm_monthly_quota.

Phase 4 baseline part 9/13。

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-12

設計：
- audit_logs：(id, timestamp) 複合 PK；hypertable on timestamp（chunk 1 month，retention 1 年）
- llm_usage：(id, created_at) 複合 PK；hypertable（chunk 1 month，retention 1 年）
- llm_monthly_quota：普通表，UNIQUE(user_id, year, month)
- hash chain trigger 在 0012 統一建
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── audit_logs ─────────────────────────────────────
    op.create_table(
        "audit_logs",
        # BIGSERIAL — alembic 用 BigInteger + Identity 來建 PG SERIAL
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", sa.String(100)),
        sa.Column("details", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip", postgresql.INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("request_id", sa.String(64)),
        sa.Column("prev_hash", sa.String(64)),
        sa.Column("entry_hash", sa.String(64)),
        sa.PrimaryKeyConstraint("id", "timestamp", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_actor_timestamp", "audit_logs",
                    ["actor_id", "timestamp"])
    op.create_index("ix_audit_logs_entity_timestamp", "audit_logs",
                    ["entity_type", "entity_id", "timestamp"])
    op.create_index("ix_audit_logs_action_timestamp", "audit_logs",
                    ["action", "timestamp"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])

    op.execute(
        "SELECT create_hypertable('audit_logs', 'timestamp', "
        "chunk_time_interval => INTERVAL '1 month', "
        "if_not_exists => TRUE, migrate_data => TRUE)"
    )
    op.execute(
        "SELECT add_retention_policy('audit_logs', INTERVAL '1 year', if_not_exists => TRUE)"
    )

    # ── llm_usage ──────────────────────────────────────
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True)),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("purpose", sa.String(50)),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("succeeded", sa.Boolean),
        sa.Column("error_msg", sa.String(500)),
        sa.PrimaryKeyConstraint("id", "created_at", name="pk_llm_usage"),
    )
    op.create_index("ix_llm_usage_user_created", "llm_usage", ["user_id", "created_at"])
    op.create_index("ix_llm_usage_analysis_id", "llm_usage", ["analysis_id"])
    op.create_index("ix_llm_usage_provider_model", "llm_usage", ["provider", "model"])

    op.execute(
        "SELECT create_hypertable('llm_usage', 'created_at', "
        "chunk_time_interval => INTERVAL '1 month', "
        "if_not_exists => TRUE, migrate_data => TRUE)"
    )
    op.execute(
        "SELECT add_retention_policy('llm_usage', INTERVAL '1 year', if_not_exists => TRUE)"
    )

    # ── llm_monthly_quota ──────────────────────────────
    op.create_table(
        "llm_monthly_quota",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.SmallInteger, nullable=False),
        sa.Column("budget_usd", sa.Numeric(12, 4), nullable=False),
        sa.Column("used_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("request_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            ondelete="CASCADE",
            name="fk_llm_monthly_quota_user_id_users",
        ),
        sa.UniqueConstraint("user_id", "year", "month",
                            name="uq_llm_monthly_quota_user_year_month"),
        sa.CheckConstraint("month BETWEEN 1 AND 12",
                           name="ck_llm_monthly_quota_month_range"),
    )
    op.create_index("ix_llm_monthly_quota_year_month", "llm_monthly_quota",
                    ["year", "month"])


def downgrade() -> None:
    op.drop_table("llm_monthly_quota")
    op.execute("SELECT remove_retention_policy('llm_usage', if_exists => TRUE)")
    op.drop_table("llm_usage")
    op.execute("SELECT remove_retention_policy('audit_logs', if_exists => TRUE)")
    op.drop_table("audit_logs")
