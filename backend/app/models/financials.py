"""FinancialStatement — 財務報表（季 / 年）。

依 PLAN.md 第 10.4 章「財報」(FinMind 主 / MOPS 備 / yfinance / Finnhub) + 第 20.2 章。

設計：
- 三大表（IS / BS / CF）合一表，statement_type 區分（VARCHAR + CHECK 取代 enum，與專案慣例一致）
- 年報 = quarter=0 ; 季報 = 1/2/3/4
- 常用欄位 explicit（revenue / net_income / eps / ...）
- 其他細項用 JSONB（payload）保留 source 原始
- 同 (symbol, fiscal_year, fiscal_quarter, statement_type) 唯一（PK 複合）
- 不是 hypertable（資料量小、按 fiscal_year 切沒意義）
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, short_enum

# IS = 損益表 ; BS = 資產負債表 ; CF = 現金流量表
STATEMENT_TYPE_VALUES = ("IS", "BS", "CF")


class FinancialStatement(Base):
    """財務報表（IS/BS/CF）。

    主鍵：(symbol, fiscal_year, fiscal_quarter, statement_type)
    - fiscal_quarter = 0 表示年報；1~4 表示季報
    """

    __tablename__ = "financial_statements"

    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stock_list.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, primary_key=True)
    fiscal_quarter: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    """0 = 年報 ; 1~4 = 季報。"""
    statement_type: Mapped[str] = mapped_column(
        short_enum(*STATEMENT_TYPE_VALUES, name="statement_type_enum"),
        primary_key=True,
    )

    # ── 常用聚合欄位（顯式存 column，方便查詢 / index）──
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """營收（IS only）"""
    gross_profit: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """毛利（IS only）"""
    operating_income: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """營業利益（IS only）"""
    net_income: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """稅後淨利（IS only）"""
    eps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    """每股盈餘（IS only）"""

    total_assets: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """總資產（BS only）"""
    total_liabilities: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """總負債（BS only）"""
    total_equity: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """股東權益總額（BS only）"""

    operating_cashflow: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """營運現金流（CF only）"""
    investing_cashflow: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """投資現金流（CF only）"""
    financing_cashflow: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """融資現金流（CF only）"""

    # ── 完整 payload（保留 source 原始細項）──
    payload: Mapped[dict | None] = mapped_column(JSONB)
    """完整 source response（如 FinMind 的 type / value 行對照）"""

    announced_at: Mapped[date_type | None] = mapped_column(Date)
    """財報公告日（CommonReturn 的填報日）。"""
    source: Mapped[str | None] = mapped_column(String(30))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_financial_statements_symbol_year",
            "symbol",
            "fiscal_year",
            "fiscal_quarter",
        ),
        Index("ix_financial_statements_announced", "announced_at"),
    )


__all__ = ["STATEMENT_TYPE_VALUES", "FinancialStatement"]
