"""News + Announcement metadata — vector 存 Qdrant，元資料 + qdrant_point_id 存 PG。

依 PLAN.md 第 20.2 章 + 第 ADR-002 章（向量分離儲存）。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, short_enum
from app.models.stock import MARKET_VALUES

SENTIMENT_VALUES = ("positive", "neutral", "negative", "unknown")


class NewsMetadata(Base):
    """新聞元資料 — 向量在 Qdrant `tw_news_v1` / `us_news_v1`。"""

    __tablename__ = "news_metadata"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    symbol: Mapped[str | None] = mapped_column(String(20))
    """關聯股票（可為空，macro 新聞無 symbol）。不設 FK 因 macro 新聞不對應 stock_list。"""
    market: Mapped[str | None] = mapped_column(short_enum(*MARKET_VALUES, name="market_enum"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(50))
    """cnyes / Bloomberg / Reuters / 經濟日報 ..."""
    url: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(100))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sentiment: Mapped[str] = mapped_column(
        short_enum(*SENTIMENT_VALUES, name="sentiment_enum"),
        nullable=False,
        server_default="unknown",
    )
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    """-1.0 ~ 1.0"""
    qdrant_collection: Mapped[str | None] = mapped_column(String(50))
    qdrant_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    word_count: Mapped[int | None] = mapped_column(Integer)
    extra_meta: Mapped[dict | None] = mapped_column(JSONB)
    """關鍵字、entity、其他 metadata。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_news_metadata_symbol_published", "symbol", "published_at"),
        Index("ix_news_metadata_published_desc", "published_at"),
        Index("ix_news_metadata_sentiment", "sentiment"),
    )


class Announcement(Base):
    """重大訊息 / 公司公告。"""

    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    symbol: Mapped[str | None] = mapped_column(String(20))
    market: Mapped[str | None] = mapped_column(short_enum(*MARKET_VALUES, name="market_enum"))
    announcement_type: Mapped[str | None] = mapped_column(String(100))
    """重大訊息 / 法說會 / 股利 / 股東會 / 8-K / 10-K ..."""
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    qdrant_collection: Mapped[str | None] = mapped_column(String(50))
    qdrant_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    extra_meta: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_announcements_symbol_published", "symbol", "published_at"),
        Index("ix_announcements_published_desc", "published_at"),
        Index("ix_announcements_type", "announcement_type"),
    )


__all__ = ["SENTIMENT_VALUES", "Announcement", "NewsMetadata"]
