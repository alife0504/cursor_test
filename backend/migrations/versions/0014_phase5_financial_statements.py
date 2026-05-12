"""Phase 5: financial_statements 表.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-12

新增 financial_statements 表用於存放 IS/BS/CF（季 / 年）報表：
- PK (symbol, fiscal_year, fiscal_quarter, statement_type)
- statement_type CHECK in ('IS','BS','CF')
- fiscal_quarter = 0 = 年報；1~4 = 季報
- 常用欄位 explicit + payload JSONB 保留 source 原始
- 不是 hypertable（資料量小、隨 fiscal_year 切無意義）
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STMT_CHECK = "statement_type IN ('IS', 'BS', 'CF')"


def upgrade() -> None:
    op.create_table(
        "financial_statements",
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("fiscal_year", sa.Integer, nullable=False),
        sa.Column("fiscal_quarter", sa.SmallInteger, nullable=False),
        sa.Column("statement_type", sa.String(50), nullable=False),
        # 損益表常用欄位
        sa.Column("revenue", sa.Numeric(24, 2)),
        sa.Column("gross_profit", sa.Numeric(24, 2)),
        sa.Column("operating_income", sa.Numeric(24, 2)),
        sa.Column("net_income", sa.Numeric(24, 2)),
        sa.Column("eps", sa.Numeric(10, 4)),
        # 資產負債表常用欄位
        sa.Column("total_assets", sa.Numeric(24, 2)),
        sa.Column("total_liabilities", sa.Numeric(24, 2)),
        sa.Column("total_equity", sa.Numeric(24, 2)),
        # 現金流量表常用欄位
        sa.Column("operating_cashflow", sa.Numeric(24, 2)),
        sa.Column("investing_cashflow", sa.Numeric(24, 2)),
        sa.Column("financing_cashflow", sa.Numeric(24, 2)),
        # JSONB payload + meta
        sa.Column("payload", postgresql.JSONB),
        sa.Column("announced_at", sa.Date),
        sa.Column("source", sa.String(30)),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint(
            "symbol",
            "fiscal_year",
            "fiscal_quarter",
            "statement_type",
            name="pk_financial_statements",
        ),
        sa.ForeignKeyConstraint(
            ["symbol"],
            ["stock_list.symbol"],
            ondelete="CASCADE",
            name="fk_financial_statements_symbol_stock_list",
        ),
        sa.CheckConstraint(_STMT_CHECK, name="ck_financial_statements_statement_type"),
        sa.CheckConstraint(
            "fiscal_quarter BETWEEN 0 AND 4",
            name="ck_financial_statements_fiscal_quarter",
        ),
    )
    op.create_index(
        "ix_financial_statements_symbol_year",
        "financial_statements",
        ["symbol", "fiscal_year", "fiscal_quarter"],
    )
    op.create_index(
        "ix_financial_statements_announced",
        "financial_statements",
        ["announced_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_financial_statements_announced", table_name="financial_statements")
    op.drop_index("ix_financial_statements_symbol_year", table_name="financial_statements")
    op.drop_table("financial_statements")
