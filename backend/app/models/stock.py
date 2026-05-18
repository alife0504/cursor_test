"""Stock master data: StockList, StockInfo。

依 PLAN.md 第 10 章跨市場架構 + 第 20.2 章資料表。

stock_list：所有支援的股票（TWSE / TPEX / NYSE / NASDAQ ...）— 前端搜尋必需。
stock_info：補強資料（產業、capital、website 等）— 由 seeders 慢更新。
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, short_enum

# Market enum — TWSE/TPEX/NYSE/NASDAQ/AMEX 全支援
MARKET_VALUES = ("TWSE", "TPEX", "NYSE", "NASDAQ", "AMEX", "OTHER")


class StockList(Base):
    """股票基本資料 — symbol 為 PK。seeders 維護。"""

    __tablename__ = "stock_list"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    market: Mapped[str] = mapped_column(
        short_enum(*MARKET_VALUES, name="market_enum"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """中文 / 英文名稱。GIN(name gin_trgm_ops) 用於模糊搜尋。"""
    short_name: Mapped[str | None] = mapped_column(String(50))
    industry: Mapped[str | None] = mapped_column(String(100))
    listed_at: Mapped[date_type | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_stock_list_market", "market"),
        Index("ix_stock_list_industry", "industry"),
        Index("ix_stock_list_is_active", "is_active"),
        # GIN(name gin_trgm_ops) 在 migration 用 op.execute() 顯式建（autogenerate 不支援）
    )


class StockInfo(Base):
    """股票補強資料 — sector / capital / website / employees 等。

    與 stock_list 1:1，但分表避免主表過寬影響搜尋效能。
    """

    __tablename__ = "stock_info"

    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stock_list.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    full_name: Mapped[str | None] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(100))
    sub_industry: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    capital: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    """資本額（元）。"""
    employees: Mapped[int | None] = mapped_column()
    fiscal_year_end: Mapped[str | None] = mapped_column(String(5))
    """財報年度結算月日（如 12-31）。"""
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_stock_info_sector", "sector"),)


__all__ = ["MARKET_VALUES", "StockInfo", "StockList"]
