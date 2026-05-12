"""StockPrice — OHLCV，TimescaleDB hypertable。

依 PLAN.md 第 20.2 章 + 第 14.10 章 retention（1 年）。

注意：
- TimescaleDB hypertable 要求 time column 在 PK；本表 PK = (symbol, date)
- chunk_time_interval = 1 month（在 alembic migration 用 op.execute）
- retention policy = 1 year
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StockPrice(Base):
    """OHLCV 行情 — hypertable on `date`（chunk 1 month）。"""

    __tablename__ = "stock_prices"

    # 複合 PK — (symbol, date)；hypertable 要求 time column 在 PK
    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stock_list.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    date: Mapped[date_type] = mapped_column(Date, primary_key=True)

    open: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    """成交股數（股）。"""
    turnover: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """成交金額（元）。"""

    # 來源追蹤
    source: Mapped[str | None] = mapped_column(String(30))
    """資料來源：FinMind / TWSE / yfinance / AlphaVantage。"""

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # (symbol, date DESC) 是 PK 自帶，但 explicit index for date-only queries
        Index("ix_stock_prices_date_desc", "date"),
    )


__all__ = ["StockPrice"]
