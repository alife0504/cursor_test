"""Phase 10 — /api/v1/screener/* 的 Pydantic schemas。

依 PLAN.md 第 17.3 章 envelope + 第 19.2 章輸入驗證 + 排序白名單。

設計：
- ScreenerFilters：所有過濾條件
- 動態 SQL 由 screener_repo 用 SQLAlchemy expression 組裝（非字串拼接）
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.common import BaseSchema

MarketCode = Literal["TW", "US"]

# Whitelist 給 router 跟 repo 共用（防 SQL injection）
SCREENER_SORT_FIELDS: frozenset[str] = frozenset(
    {
        "symbol",
        "pe_ratio",
        "dividend_yield",
        "eps_growth",
        "rsi",
        "market_cap",
    }
)


class ScreenerFilters(BaseSchema):
    """Screener 多條件過濾（每個欄位都是可選）。

    note：所有 Decimal min/max 都允許為 None；router 把 None 跳過不 join 條件。
    """

    market: MarketCode = Field(default="TW")
    pe_min: Decimal | None = Field(default=None, ge=0)
    pe_max: Decimal | None = Field(default=None, ge=0)
    dividend_yield_min: Decimal | None = Field(default=None, ge=0, le=100)
    eps_growth_min: Decimal | None = Field(default=None)
    rsi_min: Decimal | None = Field(default=None, ge=0, le=100)
    rsi_max: Decimal | None = Field(default=None, ge=0, le=100)
    market_cap_min: Decimal | None = Field(default=None, ge=0)
    industry: str | None = Field(default=None, max_length=100)


class ScreenerRow(BaseSchema):
    """Screener 結果單筆（聚合多個欄位 ）。"""

    symbol: str
    market: str
    name: str
    industry: str | None = None
    pe_ratio: Decimal | None = None
    dividend_yield: Decimal | None = None
    eps_growth: Decimal | None = None
    rsi: Decimal | None = None
    market_cap: Decimal | None = None
    close: Decimal | None = None


__all__ = [
    "SCREENER_SORT_FIELDS",
    "MarketCode",
    "ScreenerFilters",
    "ScreenerRow",
]
