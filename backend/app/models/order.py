"""Order / Portfolio / Trade models — 手動核准下單流程（PLAN ADR-007）。

依 PLAN.md 第 15.1 章 transaction 原則 + 第 20.2 章。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampedMixin, short_enum
from app.models.stock import MARKET_VALUES

ORDER_SIDE_VALUES = ("BUY", "SELL")
ORDER_STATUS_VALUES = (
    "PENDING",
    "APPROVED",
    "REJECTED",
    "EXPIRED",
    "EXECUTED",
    "CANCELLED",
)


class PendingOrder(Base, TimestampedMixin):
    """待核准訂單 — admin 透過 /admin/orders 頁手動核准。"""

    __tablename__ = "pending_orders"

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
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    """來源分析報告（可為 NULL 表用戶手動建立）。"""
    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stock_list.symbol", ondelete="RESTRICT"),
        nullable=False,
    )
    market: Mapped[str] = mapped_column(
        short_enum(*MARKET_VALUES, name="market_enum"),
        nullable=False,
    )

    side: Mapped[str] = mapped_column(
        short_enum(*ORDER_SIDE_VALUES, name="order_side_enum"),
        nullable=False,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    """數量（股）。"""
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))

    status: Mapped[str] = mapped_column(
        short_enum(*ORDER_STATUS_VALUES, name="order_status_enum"),
        nullable=False,
        server_default="PENDING",
    )

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """超過此時間自動 EXPIRED（PLAN 15.4 orphan cleanup）。"""

    # 樂觀鎖
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    __table_args__ = (
        Index("ix_pending_orders_status_created", "status", "created_at"),
        Index("ix_pending_orders_user_status", "user_id", "status"),
        Index("ix_pending_orders_analysis_id", "analysis_id"),
    )


class PortfolioPosition(Base, TimestampedMixin):
    """模擬持倉 — 由 APPROVED 訂單建立 / 更新。"""

    __tablename__ = "portfolio_positions"

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
        ForeignKey("stock_list.symbol", ondelete="RESTRICT"),
        nullable=False,
    )
    market: Mapped[str] = mapped_column(
        short_enum(*MARKET_VALUES, name="market_enum"),
        nullable=False,
    )

    qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(24, 6), nullable=False, server_default="0"
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_portfolio_positions_user_symbol", "user_id", "symbol", unique=False),
        Index("ix_portfolio_positions_user_open", "user_id", "closed_at"),
    )


class TradeHistory(Base):
    """交易紀錄 — APPROVED 訂單真正執行（模擬）後寫入。"""

    __tablename__ = "trade_history"

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
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    position_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stock_list.symbol", ondelete="RESTRICT"),
        nullable=False,
    )
    market: Mapped[str] = mapped_column(
        short_enum(*MARKET_VALUES, name="market_enum"),
        nullable=False,
    )
    side: Mapped[str] = mapped_column(
        short_enum(*ORDER_SIDE_VALUES, name="order_side_enum"),
        nullable=False,
    )

    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, server_default="0")
    tax: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, server_default="0")
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_trade_history_user_executed", "user_id", "executed_at"),
        Index("ix_trade_history_symbol_executed", "symbol", "executed_at"),
        Index("ix_trade_history_order_id", "order_id"),
    )


__all__ = [
    "ORDER_SIDE_VALUES",
    "ORDER_STATUS_VALUES",
    "PendingOrder",
    "PortfolioPosition",
    "TradeHistory",
]
