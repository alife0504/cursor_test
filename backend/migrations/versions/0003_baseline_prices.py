"""baseline: stock_prices（hypertable + retention policy 1 年）.

Phase 4 baseline part 3/13。

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-12

設計：
- 複合 PK (symbol, date) — hypertable 要求 time column 在 PK
- chunk_time_interval = 1 個月
- retention policy = 1 年
- TimescaleDB 限制：hypertable 一旦建立，PK 不可改 → 設計時請謹慎
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_prices",
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("open", sa.Numeric(20, 6), nullable=False),
        sa.Column("high", sa.Numeric(20, 6), nullable=False),
        sa.Column("low", sa.Numeric(20, 6), nullable=False),
        sa.Column("close", sa.Numeric(20, 6), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(20, 6)),
        sa.Column("volume", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("turnover", sa.Numeric(24, 2)),
        sa.Column("source", sa.String(30)),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("symbol", "date", name="pk_stock_prices"),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stock_list.symbol"],
            ondelete="CASCADE",
            name="fk_stock_prices_symbol_stock_list",
        ),
    )
    op.create_index("ix_stock_prices_date_desc", "stock_prices", ["date"])

    # ── TimescaleDB hypertable + retention ─────────────
    op.execute(
        "SELECT create_hypertable('stock_prices', 'date', "
        "chunk_time_interval => INTERVAL '1 month', "
        "if_not_exists => TRUE, migrate_data => TRUE)"
    )
    op.execute(
        "SELECT add_retention_policy('stock_prices', INTERVAL '1 year', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    # 退回先 remove retention policy（即使表 drop 也會卡）
    op.execute(
        "SELECT remove_retention_policy('stock_prices', if_exists => TRUE)"
    )
    op.drop_table("stock_prices")
