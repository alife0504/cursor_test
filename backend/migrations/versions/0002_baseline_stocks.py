"""baseline: stock_list + stock_info.

Phase 4 baseline part 2/13。

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-12

設計：
- market：CHECK constraint
- stock_list.name：GIN(name gin_trgm_ops) for 模糊搜尋（PLAN 20.2）
- stock_info：1:1 與 stock_list，FK CASCADE
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MARKET_CHECK = "market IN ('TWSE', 'TPEX', 'NYSE', 'NASDAQ', 'AMEX', 'OTHER')"


def upgrade() -> None:
    # ── stock_list ────────────────────────────────────
    op.create_table(
        "stock_list",
        sa.Column("symbol", sa.String(20), primary_key=True),
        sa.Column("market", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("short_name", sa.String(50)),
        sa.Column("industry", sa.String(100)),
        sa.Column("listed_at", sa.Date),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.CheckConstraint(_MARKET_CHECK, name="ck_stock_list_market"),
    )
    op.create_index("ix_stock_list_market", "stock_list", ["market"])
    op.create_index("ix_stock_list_industry", "stock_list", ["industry"])
    op.create_index("ix_stock_list_is_active", "stock_list", ["is_active"])
    # GIN(name gin_trgm_ops)：模糊搜尋（pg_trgm 已在 init.sql.template 啟用）
    op.execute(
        "CREATE INDEX ix_stock_list_name_trgm ON stock_list USING gin (name gin_trgm_ops)"
    )

    # ── stock_info ────────────────────────────────────
    op.create_table(
        "stock_info",
        sa.Column("symbol", sa.String(20), primary_key=True),
        sa.Column("full_name", sa.String(255)),
        sa.Column("sector", sa.String(100)),
        sa.Column("sub_industry", sa.String(100)),
        sa.Column("description", sa.Text),
        sa.Column("address", sa.Text),
        sa.Column("website", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("capital", sa.Numeric(24, 2)),
        sa.Column("employees", sa.Integer),
        sa.Column("fiscal_year_end", sa.String(5)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stock_list.symbol"],
            ondelete="CASCADE",
            name="fk_stock_info_symbol_stock_list",
        ),
    )
    op.create_index("ix_stock_info_sector", "stock_info", ["sector"])


def downgrade() -> None:
    op.drop_table("stock_info")
    op.execute("DROP INDEX IF EXISTS ix_stock_list_name_trgm")
    op.drop_table("stock_list")
