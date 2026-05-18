"""UserWatchlist — 自選股清單。

UNIQUE(user_id, symbol, market) 保證一支股不會重複加入。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, short_enum
from app.models.stock import MARKET_VALUES


class UserWatchlist(Base):
    """自選股 — UNIQUE(user_id, symbol, market)。"""

    __tablename__ = "user_watchlist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stock_list.symbol", ondelete="CASCADE"),
        nullable=False,
    )
    market: Mapped[str] = mapped_column(
        short_enum(*MARKET_VALUES, name="market_enum"),
        nullable=False,
    )
    tag: Mapped[str | None] = mapped_column(String(50))
    """用戶自訂分組標籤（如：核心、觀察、短線）。"""
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "symbol", "market", name="uq_user_watchlist_user_symbol_market"
        ),
        Index("ix_user_watchlist_user_sort", "user_id", "sort_order"),
    )


__all__ = ["UserWatchlist"]
