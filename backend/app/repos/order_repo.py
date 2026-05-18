"""Phase 11 — OrderRepository（pending_orders + portfolio_positions）。

依 PLAN.md 第 15.1 章 transaction 原則 + 第 15.2 章樂觀鎖。

關鍵：
- approve / reject 必須在 caller 的 transaction 內呼叫 `get_for_update`
- version 比對由 service 決定（並發核准用 expected_version 比對）
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from app.models.order import PendingOrder, PortfolioPosition
from app.repos.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OrderRepository(BaseRepository):
    """pending_orders 的 CRUD + 並發保護 + portfolio 同步。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── 查詢 ─────────────────────────────────────────
    async def get_by_id(self, order_id: UUID) -> PendingOrder | None:
        stmt = select(PendingOrder).where(PendingOrder.id == order_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_for_update(self, order_id: UUID) -> PendingOrder | None:
        """row-level lock（必須在 transaction 內呼叫）。"""
        stmt = select(PendingOrder).where(PendingOrder.id == order_id).with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        *,
        user_id: UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        before_created_at: Any | None = None,
    ) -> list[PendingOrder]:
        stmt = select(PendingOrder)
        if user_id is not None:
            stmt = stmt.where(PendingOrder.user_id == user_id)
        if status:
            stmt = stmt.where(PendingOrder.status == status)
        if before_created_at is not None:
            stmt = stmt.where(PendingOrder.created_at < before_created_at)
        stmt = stmt.order_by(PendingOrder.created_at.desc(), PendingOrder.id.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ── 寫入 ─────────────────────────────────────────
    async def mark_status(
        self,
        order: PendingOrder,
        *,
        new_status: str,
        reviewer_id: UUID,
        review_notes: str | None = None,
    ) -> PendingOrder:
        """更新 status + reviewer + version += 1（caller 確保在 transaction）。"""
        order.status = new_status
        order.reviewed_by = reviewer_id
        order.reviewed_at = datetime.now(UTC)
        if review_notes is not None:
            order.review_notes = review_notes
        order.version = (order.version or 0) + 1
        await self.session.flush()
        return order

    async def add_portfolio_from_order(
        self, order: PendingOrder, *, price: Decimal
    ) -> PortfolioPosition:
        """從一個 APPROVED 訂單建一筆 portfolio_positions（同一 transaction）。"""
        pos = PortfolioPosition(
            user_id=order.user_id,
            symbol=order.symbol,
            market=order.market,
            qty=order.qty if order.side == "BUY" else -order.qty,
            avg_cost=price,
        )
        self.session.add(pos)
        await self.session.flush()
        return pos


__all__ = ["OrderRepository"]
