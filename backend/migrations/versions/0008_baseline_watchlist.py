"""baseline: user_watchlist。

Phase 4 baseline part 8/13。

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-12

設計：
- UNIQUE(user_id, symbol, market) — 同股不重複加入
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MARKET_CHECK = "market IN ('TWSE', 'TPEX', 'NYSE', 'NASDAQ', 'AMEX', 'OTHER')"


def upgrade() -> None:
    op.create_table(
        "user_watchlist",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("market", sa.String(50), nullable=False),
        sa.Column("tag", sa.String(50)),
        sa.Column("notes", sa.Text),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            ondelete="CASCADE",
            name="fk_user_watchlist_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stock_list.symbol"],
            ondelete="CASCADE",
            name="fk_user_watchlist_symbol_stock_list",
        ),
        sa.UniqueConstraint("user_id", "symbol", "market",
                            name="uq_user_watchlist_user_symbol_market"),
        sa.CheckConstraint(_MARKET_CHECK, name="ck_user_watchlist_market"),
    )
    op.create_index("ix_user_watchlist_user_sort", "user_watchlist",
                    ["user_id", "sort_order"])


def downgrade() -> None:
    op.drop_table("user_watchlist")
