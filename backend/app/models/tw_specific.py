"""台股獨有資料表：三大法人 / 融資融券 / 月營收。

依 PLAN.md 第 10.5 章 + 第 20.2 章。
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
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InstitutionalTrading(Base):
    """三大法人買賣超（台股 only）。"""

    __tablename__ = "institutional_trading"

    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stock_list.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    date: Mapped[date_type] = mapped_column(Date, primary_key=True)

    # 外資（含外資自營商）
    foreign_buy: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    foreign_sell: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    foreign_net: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")

    # 投信
    trust_buy: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    trust_sell: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    trust_net: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")

    # 自營商
    dealer_buy: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    dealer_sell: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    dealer_net: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")

    source: Mapped[str | None] = mapped_column(String(30))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_institutional_trading_date", "date"),)


class MarginTrading(Base):
    """融資融券（台股 only）。"""

    __tablename__ = "margin_trading"

    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stock_list.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    date: Mapped[date_type] = mapped_column(Date, primary_key=True)

    margin_balance: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    """融資餘額（張）。"""
    margin_quota: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    margin_buy: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    margin_sell: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")

    short_balance: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    """融券餘額（張）。"""
    short_quota: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    short_buy: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    short_sell: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")

    source: Mapped[str | None] = mapped_column(String(30))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_margin_trading_date", "date"),)


class MonthlyRevenue(Base):
    """每月營收（台股 only） — 第 10 號公報，台股早於財報 1.5 月發布。"""

    __tablename__ = "monthly_revenue"

    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stock_list.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[int] = mapped_column(SmallInteger, primary_key=True)

    revenue: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    """當月營收（元）。"""
    revenue_mom: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    """月增率 (%)。"""
    revenue_yoy: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    """年增率 (%)。"""
    ytd_revenue: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    ytd_yoy: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    announced_at: Mapped[date_type | None] = mapped_column(Date)
    """**實際**公告日。FinMind 不提供 → 目前全為 NULL，待接 MOPS。

    ⚠️ 不可拿 FinMind 的 date（次月 1 日的慣例）充當公告日——法定是次月 10 日前，
    那會偷看未來 9 天。期限請用 disclosure_deadline。
    """
    disclosure_deadline: Mapped[date_type | None] = mapped_column(Date)
    """**法定**最晚公告期限（app.domain.disclosure_calendar，證交法 §36：次月 10 日前）。

    PIT 邊界：`COALESCE(announced_at, disclosure_deadline) <= as_of`。
    """
    source: Mapped[str | None] = mapped_column(String(30))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_monthly_revenue_year_month", "year", "month"),
        Index("ix_monthly_revenue_disclosure_deadline", "disclosure_deadline"),
    )


class StockMetrics(Base):
    """每檔最新指標快照（選股篩選器用）。

    每檔一列（symbol PK），由每日排程 sync_stock_metrics 刷新為「最新」快照，非時序。
    PE/PBR/殖利率 來自 FinMind TaiwanStockPER、市值 來自 TaiwanStockMarketValue、
    rsi14 由 stock_prices 算、eps_growth 由 financial_statements EPS YoY 算。
    """

    __tablename__ = "stock_metrics"

    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stock_list.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    as_of_date: Mapped[date_type | None] = mapped_column(Date)
    """指標對應資料日（PER/市值 as-of；RSI 用最新收盤日）。"""

    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    pbr: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    """殖利率 (%)，如 0.9 = 0.9%。"""
    market_cap: Mapped[int | None] = mapped_column(BigInteger)
    """市值 (TWD)。"""
    rsi14: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    eps_growth: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    """最新一季 EPS 對去年同季 YoY (%)，如 15.5 = +15.5%。"""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_stock_metrics_pe_ratio", "pe_ratio"),
        Index("ix_stock_metrics_market_cap", "market_cap"),
        Index("ix_stock_metrics_dividend_yield", "dividend_yield"),
    )


__all__ = ["InstitutionalTrading", "MarginTrading", "MonthlyRevenue", "StockMetrics"]
