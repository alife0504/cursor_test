"""baseline: pending_orders + portfolio_positions + trade_history.

Phase 4 baseline part 7/13。

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-12

設計：
- 手動核准下單流程（PLAN ADR-007）
- pending_orders 有 version 樂觀鎖
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MARKET_CHECK = "market IN ('TWSE', 'TPEX', 'NYSE', 'NASDAQ', 'AMEX', 'OTHER')"
_SIDE_CHECK = "side IN ('BUY', 'SELL')"
_STATUS_CHECK = (
    "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', 'EXECUTED', 'CANCELLED')"
)


def upgrade() -> None:
    # ── pending_orders ────────────────────────────────
    op.create_table(
        "pending_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True)),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("market", sa.String(50), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("target_price", sa.Numeric(20, 6)),
        sa.Column("stop_loss", sa.Numeric(20, 6)),
        sa.Column("take_profit", sa.Numeric(20, 6)),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_notes", sa.Text),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            ondelete="CASCADE",
            name="fk_pending_orders_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stock_list.symbol"],
            ondelete="RESTRICT",
            name="fk_pending_orders_symbol_stock_list",
        ),
        sa.CheckConstraint(_MARKET_CHECK, name="ck_pending_orders_market"),
        sa.CheckConstraint(_SIDE_CHECK, name="ck_pending_orders_side"),
        sa.CheckConstraint(_STATUS_CHECK, name="ck_pending_orders_status"),
        sa.CheckConstraint("qty > 0", name="ck_pending_orders_qty_positive"),
    )
    op.create_index("ix_pending_orders_status_created", "pending_orders",
                    ["status", "created_at"])
    op.create_index("ix_pending_orders_user_status", "pending_orders",
                    ["user_id", "status"])
    op.create_index("ix_pending_orders_analysis_id", "pending_orders", ["analysis_id"])

    # ── portfolio_positions ───────────────────────────
    op.create_table(
        "portfolio_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("market", sa.String(50), nullable=False),
        sa.Column("qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_cost", sa.Numeric(20, 6), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(24, 6), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            ondelete="CASCADE",
            name="fk_portfolio_positions_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stock_list.symbol"],
            ondelete="RESTRICT",
            name="fk_portfolio_positions_symbol_stock_list",
        ),
        sa.CheckConstraint(_MARKET_CHECK, name="ck_portfolio_positions_market"),
    )
    op.create_index("ix_portfolio_positions_user_symbol", "portfolio_positions",
                    ["user_id", "symbol"])
    op.create_index("ix_portfolio_positions_user_open", "portfolio_positions",
                    ["user_id", "closed_at"])

    # ── trade_history ─────────────────────────────────
    op.create_table(
        "trade_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True)),
        sa.Column("position_id", postgresql.UUID(as_uuid=True)),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("market", sa.String(50), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(20, 6), nullable=False),
        sa.Column("fee", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("pnl", sa.Numeric(24, 6)),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("notes", sa.Text),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            ondelete="CASCADE",
            name="fk_trade_history_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stock_list.symbol"],
            ondelete="RESTRICT",
            name="fk_trade_history_symbol_stock_list",
        ),
        sa.CheckConstraint(_MARKET_CHECK, name="ck_trade_history_market"),
        sa.CheckConstraint(_SIDE_CHECK, name="ck_trade_history_side"),
    )
    op.create_index("ix_trade_history_user_executed", "trade_history",
                    ["user_id", "executed_at"])
    op.create_index("ix_trade_history_symbol_executed", "trade_history",
                    ["symbol", "executed_at"])
    op.create_index("ix_trade_history_order_id", "trade_history", ["order_id"])


def downgrade() -> None:
    op.drop_table("trade_history")
    op.drop_table("portfolio_positions")
    op.drop_table("pending_orders")
