"""baseline: institutional_trading + margin_trading + monthly_revenue（TW only）.

Phase 4 baseline part 4/13。

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-12

設計：
- 三大法人、融資融券、月營收，僅 TWSE/TPEX 用
- 不轉 hypertable（每日一筆，總量可控）
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── institutional_trading ─────────────────────────
    op.create_table(
        "institutional_trading",
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("foreign_buy", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("foreign_sell", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("foreign_net", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("trust_buy", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("trust_sell", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("trust_net", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("dealer_buy", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("dealer_sell", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("dealer_net", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("source", sa.String(30)),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("symbol", "date", name="pk_institutional_trading"),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stock_list.symbol"],
            ondelete="CASCADE",
            name="fk_institutional_trading_symbol_stock_list",
        ),
    )
    op.create_index("ix_institutional_trading_date", "institutional_trading", ["date"])

    # ── margin_trading ────────────────────────────────
    op.create_table(
        "margin_trading",
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("margin_balance", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("margin_quota", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("margin_buy", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("margin_sell", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("short_balance", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("short_quota", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("short_buy", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("short_sell", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("source", sa.String(30)),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("symbol", "date", name="pk_margin_trading"),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stock_list.symbol"],
            ondelete="CASCADE",
            name="fk_margin_trading_symbol_stock_list",
        ),
    )
    op.create_index("ix_margin_trading_date", "margin_trading", ["date"])

    # ── monthly_revenue ───────────────────────────────
    op.create_table(
        "monthly_revenue",
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.SmallInteger, nullable=False),
        sa.Column("revenue", sa.Numeric(24, 2), nullable=False),
        sa.Column("revenue_mom", sa.Numeric(10, 4)),
        sa.Column("revenue_yoy", sa.Numeric(10, 4)),
        sa.Column("ytd_revenue", sa.Numeric(24, 2)),
        sa.Column("ytd_yoy", sa.Numeric(10, 4)),
        sa.Column("announced_at", sa.Date),
        sa.Column("source", sa.String(30)),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("symbol", "year", "month", name="pk_monthly_revenue"),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stock_list.symbol"],
            ondelete="CASCADE",
            name="fk_monthly_revenue_symbol_stock_list",
        ),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_monthly_revenue_month_range"),
    )
    op.create_index("ix_monthly_revenue_year_month", "monthly_revenue", ["year", "month"])


def downgrade() -> None:
    op.drop_table("monthly_revenue")
    op.drop_table("margin_trading")
    op.drop_table("institutional_trading")
