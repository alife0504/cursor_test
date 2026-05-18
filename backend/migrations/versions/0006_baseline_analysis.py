"""baseline: analysis_reports（含 version 樂觀鎖）+ debate_history（hypertable）.

Phase 4 baseline part 6/13。

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-12

設計：
- analysis_reports：version 欄位（PLAN 15.2 樂觀鎖）
- debate_history：hypertable on created_at（chunk 1 month，retention 1 年）
- analysis_id 不設 FK（避免 hypertable 限制；用 index 維持查詢性能）
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MARKET_CHECK = "market IN ('TWSE', 'TPEX', 'NYSE', 'NASDAQ', 'AMEX', 'OTHER')"
_STATUS_CHECK = "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"
_SIGNAL_CHECK = (
    "signal IS NULL OR signal IN "
    "('BUY', 'SELL', 'HOLD', 'STRONG_BUY', 'STRONG_SELL')"
)


def upgrade() -> None:
    # ── analysis_reports ──────────────────────────────
    op.create_table(
        "analysis_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("market", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("signal", sa.String(50)),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("target_price", sa.Numeric(20, 6)),
        sa.Column("stop_loss", sa.Numeric(20, 6)),
        sa.Column("take_profit", sa.Numeric(20, 6)),
        sa.Column("llm_provider", sa.String(30)),
        sa.Column("llm_model", sa.String(100)),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("report_md", sa.Text),
        sa.Column("error_msg", sa.Text),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            ondelete="CASCADE",
            name="fk_analysis_reports_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stock_list.symbol"],
            ondelete="RESTRICT",
            name="fk_analysis_reports_symbol_stock_list",
        ),
        sa.CheckConstraint(_MARKET_CHECK, name="ck_analysis_reports_market"),
        sa.CheckConstraint(_STATUS_CHECK, name="ck_analysis_reports_status"),
        sa.CheckConstraint(_SIGNAL_CHECK, name="ck_analysis_reports_signal"),
    )
    op.create_index("ix_analysis_reports_user_created", "analysis_reports",
                    ["user_id", "created_at"])
    op.create_index("ix_analysis_reports_symbol_created", "analysis_reports",
                    ["symbol", "created_at"])
    op.create_index("ix_analysis_reports_status", "analysis_reports", ["status"])

    # ── debate_history ──────────────────────────────────
    op.create_table(
        "debate_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_num", sa.Integer, nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column("tokens_used", sa.Integer),
        sa.PrimaryKeyConstraint("id", "created_at", name="pk_debate_history"),
    )
    op.create_index("ix_debate_history_analysis_round", "debate_history",
                    ["analysis_id", "round_num"])
    op.create_index("ix_debate_history_created_desc", "debate_history", ["created_at"])

    # ── hypertable + retention ─────────────────────────
    op.execute(
        "SELECT create_hypertable('debate_history', 'created_at', "
        "chunk_time_interval => INTERVAL '1 month', "
        "if_not_exists => TRUE, migrate_data => TRUE)"
    )
    op.execute(
        "SELECT add_retention_policy('debate_history', INTERVAL '1 year', "
        "if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.execute("SELECT remove_retention_policy('debate_history', if_exists => TRUE)")
    op.drop_table("debate_history")
    op.drop_table("analysis_reports")
