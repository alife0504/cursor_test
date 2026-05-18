"""Phase 10 — /api/v1/watchlist/* 的 Pydantic schemas。

依 PLAN.md 第 17.3 章 envelope + 第 19.2 章輸入驗證 + 第 20.2 章 UNIQUE(user_id, symbol, market)。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.core.validators import validate_symbol
from app.schemas.common import BaseSchema

MarketLiteral = Literal["TWSE", "TPEX", "NYSE", "NASDAQ", "AMEX", "OTHER"]


class WatchlistItemCreate(BaseSchema):
    """POST /watchlist body。"""

    symbol: str = Field(min_length=1, max_length=20)
    market: MarketLiteral
    tag: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, v: str) -> str:
        return validate_symbol(v)


class WatchlistItemUpdate(BaseSchema):
    """PATCH /watchlist/{id} body — 部分更新。"""

    tag: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)
    sort_order: int | None = Field(default=None, ge=0, le=10000)


class WatchlistItem(BaseSchema):
    """單筆 watchlist 紀錄（回傳）。"""

    id: str
    user_id: str
    symbol: str
    market: str
    tag: str | None = None
    notes: str | None = None
    sort_order: int
    created_at: datetime


class WatchlistDeleteResponse(BaseSchema):
    ok: Literal[True] = True
    message: str = "已刪除"


__all__ = [
    "MarketLiteral",
    "WatchlistDeleteResponse",
    "WatchlistItem",
    "WatchlistItemCreate",
    "WatchlistItemUpdate",
]
