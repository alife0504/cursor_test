"""Phase 10 — /api/v1/stocks/* 的 Pydantic schemas。

依 PLAN.md 第 17.3 章 envelope + 第 17.4 章分頁 + 第 17.5 章 Decimal as str。

Endpoints：
- GET /stocks?market=&q=&cursor=&limit=
- GET /stocks/{symbol}
- GET /stocks/{symbol}/ohlcv?start=&end=
- GET /stocks/{symbol}/indicators?period=14&type=RSI,MACD,KD,BBANDS
- GET /stocks/{symbol}/financial
- GET /stocks/{symbol}/news?since=&limit=
- GET /stocks/{symbol}/announcements
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.common import BaseSchema

MarketLiteral = Literal["TW", "US", "TWSE", "TPEX", "NYSE", "NASDAQ", "AMEX"]


# ════════════════ /stocks 列表 / 詳情 ════════════════


class StockSummary(BaseSchema):
    """list 列表的單筆，不含 financial / detail。"""

    symbol: str
    market: str
    name: str
    short_name: str | None = None
    industry: str | None = None
    is_active: bool


class StockListResponse(BaseSchema):
    """GET /stocks 回傳的 data 區段（pagination 走 envelope.pagination）。"""

    items: list[StockSummary]


class StockDetail(BaseSchema):
    """GET /stocks/{symbol} 回傳的 data；含 stock_info 細節。"""

    symbol: str
    market: str
    name: str
    short_name: str | None = None
    industry: str | None = None
    listed_at: date | None = None
    is_active: bool

    # ── 來自 stock_info（1:1）──
    full_name: str | None = None
    sector: str | None = None
    sub_industry: str | None = None
    description: str | None = None
    website: str | None = None
    capital: Decimal | None = None
    employees: int | None = None
    fiscal_year_end: str | None = None


# ════════════════ /stocks/{symbol}/ohlcv ════════════════


class OHLCVPoint(BaseSchema):
    """單一交易日的 OHLCV。"""

    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None = None
    volume: int
    turnover: Decimal | None = None
    source: str | None = None


# ════════════════ /stocks/{symbol}/indicators ════════════════


class IndicatorPoint(BaseSchema):
    """單一交易日的技術指標值（依 type 動態欄位）。"""

    date: date
    rsi: Decimal | None = None
    macd: Decimal | None = None
    macd_signal: Decimal | None = None
    macd_hist: Decimal | None = None
    k: Decimal | None = None
    d: Decimal | None = None
    bb_upper: Decimal | None = None
    bb_middle: Decimal | None = None
    bb_lower: Decimal | None = None


# ════════════════ /stocks/{symbol}/financial ════════════════


class FinancialStatementItem(BaseSchema):
    """單張財報（IS/BS/CF）的摘要。"""

    symbol: str
    fiscal_year: int
    fiscal_quarter: int = Field(description="0=年報；1~4=季報")
    statement_type: Literal["IS", "BS", "CF"]
    revenue: Decimal | None = None
    gross_profit: Decimal | None = None
    operating_income: Decimal | None = None
    net_income: Decimal | None = None
    eps: Decimal | None = None
    total_assets: Decimal | None = None
    total_liabilities: Decimal | None = None
    total_equity: Decimal | None = None
    operating_cashflow: Decimal | None = None
    investing_cashflow: Decimal | None = None
    financing_cashflow: Decimal | None = None
    announced_at: date | None = None
    source: str | None = None


# ════════════════ /stocks/{symbol}/news ════════════════


class NewsItem(BaseSchema):
    id: str
    symbol: str | None = None
    market: str | None = None
    title: str
    summary: str | None = None
    source: str | None = None
    url: str | None = None
    author: str | None = None
    published_at: datetime
    sentiment: str
    sentiment_score: Decimal | None = None


# ════════════════ /stocks/{symbol}/announcements ════════════════


class AnnouncementItem(BaseSchema):
    id: str
    symbol: str | None = None
    market: str | None = None
    announcement_type: str | None = None
    title: str
    url: str | None = None
    published_at: datetime


__all__ = [
    "AnnouncementItem",
    "FinancialStatementItem",
    "IndicatorPoint",
    "MarketLiteral",
    "NewsItem",
    "OHLCVPoint",
    "StockDetail",
    "StockListResponse",
    "StockSummary",
]
