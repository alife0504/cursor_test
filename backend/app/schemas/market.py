"""Phase 10 — /api/v1/market/* 的 Pydantic schemas。

依 PLAN.md 第 17.3 章 envelope + 第 17.5 章 cache。

Endpoints：
- GET /market/overview?market=TW|US
- GET /market/institutional?market=TW&date=
- GET /market/movers?market=TW&type=gainers|losers|volume
- GET /market/calendar?from=&to=
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.common import BaseSchema

MarketCode = Literal["TW", "US"]
MoverType = Literal["gainers", "losers", "volume"]


class IndexQuote(BaseSchema):
    """單一指數（TAIEX / S&P500 ...）。"""

    name: str
    symbol: str
    close: Decimal | None = None
    change: Decimal | None = None
    change_pct: Decimal | None = None
    volume: int | None = None
    as_of: date | None = None


class MarketOverview(BaseSchema):
    """GET /market/overview 回傳。"""

    market: MarketCode
    as_of: date
    indices: list[IndexQuote]
    advance_count: int = Field(default=0, description="上漲家數")
    decline_count: int = Field(default=0, description="下跌家數")
    unchanged_count: int = Field(default=0, description="平盤家數")
    total_volume: int = Field(default=0, description="市場總成交量")


class InstitutionalRow(BaseSchema):
    """單一股票的三大法人。"""

    symbol: str
    name: str | None = None
    date: date
    foreign_buy: int
    foreign_sell: int
    foreign_net: int
    trust_buy: int
    trust_sell: int
    trust_net: int
    dealer_buy: int
    dealer_sell: int
    dealer_net: int


class MoverRow(BaseSchema):
    """漲跌幅 / 成交量排行的單筆。"""

    symbol: str
    name: str | None = None
    close: Decimal | None = None
    change_pct: Decimal | None = None
    volume: int | None = None


class CalendarItem(BaseSchema):
    """財報日曆／重大事件單筆。"""

    symbol: str
    market: MarketCode
    event_type: str
    event_date: date
    title: str
    extra: dict | None = None


__all__ = [
    "CalendarItem",
    "IndexQuote",
    "InstitutionalRow",
    "MarketCode",
    "MarketOverview",
    "MoverRow",
    "MoverType",
]
