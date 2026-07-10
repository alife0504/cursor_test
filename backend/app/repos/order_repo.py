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


_Q = Decimal("0.000001")


def net_position(
    *,
    old_qty: int,
    old_avg: Decimal,
    old_realized: Decimal,
    delta: int,
    price: Decimal,
) -> tuple[int, Decimal, Decimal, bool]:
    """把一筆成交（delta 股 @ price）套到既有部位，回 (new_qty, new_avg, new_realized, closed)。

    純函式（無 DB），供 add_portfolio_from_order 與單元測試共用：
    - 同向加碼 → 加權平均成本、realized 不變。
    - 反向沖銷 → 對已平倉部分計 realized_pnl（平多＝賣價−成本；平空＝成本−買價）；
      歸零 → closed=True；部分平倉 → 沿用原均價；翻倉 → 超出部分以本次價為新均價。
    """
    new_qty = old_qty + delta
    same_direction = old_qty == 0 or (old_qty > 0) == (delta > 0)
    if same_direction:
        total_abs = abs(old_qty) + abs(delta)
        new_avg = (
            (
                (Decimal(abs(old_qty)) * old_avg + Decimal(abs(delta)) * price) / Decimal(total_abs)
            ).quantize(_Q)
            if total_abs > 0
            else old_avg
        )
        return new_qty, new_avg, old_realized, False

    closing = min(abs(old_qty), abs(delta))
    pnl = (
        Decimal(closing) * (price - old_avg)  # 平多：賣出價 − 成本
        if old_qty > 0
        else Decimal(closing) * (old_avg - price)  # 平空：成本 − 買回價
    )
    new_realized = (old_realized + pnl).quantize(_Q)
    if new_qty == 0:
        return 0, old_avg, new_realized, True
    if (new_qty > 0) != (old_qty > 0):
        return new_qty, price, new_realized, False  # 翻倉：超出部分以本次價為新均價
    return new_qty, old_avg, new_realized, False  # 部分平倉：剩餘沿用原均價


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
        """把一個 APPROVED 訂單套用到 portfolio_positions（淨額合併，同一 transaction）。

        修正原本「每次核准都 INSERT 新列、從不淨額、realized_pnl/closed_at 永不計算、SELL 憑空
        造出負股數幻影部位」的問題：
        - 同向加碼 → 加權平均成本、股數累加。
        - 反向沖銷 → 對已平倉部分計 realized_pnl（平多＝賣價−成本；平空＝成本−買價）；
          歸零則設 closed_at；部分平倉沿用原均價；翻倉則超出部分以本次價為新均價。
        - 無既有未平倉部位才新建（BUY 為多、SELL 為開空）。
        """
        delta = order.qty if order.side == "BUY" else -order.qty

        stmt = (
            select(PortfolioPosition)
            .where(
                PortfolioPosition.user_id == order.user_id,
                PortfolioPosition.symbol == order.symbol,
                PortfolioPosition.closed_at.is_(None),
            )
            .order_by(PortfolioPosition.opened_at.asc())
            .with_for_update()
        )
        existing = (await self.session.execute(stmt)).scalars().first()

        if existing is None:
            pos = PortfolioPosition(
                user_id=order.user_id,
                symbol=order.symbol,
                market=order.market,
                qty=delta,
                avg_cost=price,
            )
            self.session.add(pos)
            await self.session.flush()
            return pos

        new_qty, new_avg, new_realized, closed = net_position(
            old_qty=int(existing.qty),
            old_avg=Decimal(existing.avg_cost),
            old_realized=Decimal(existing.realized_pnl),
            delta=delta,
            price=price,
        )
        existing.qty = new_qty
        existing.avg_cost = new_avg
        existing.realized_pnl = new_realized
        if closed:
            existing.closed_at = datetime.now(UTC)

        await self.session.flush()
        return existing

    # ── portfolio 讀取 ───────────────────────────────
    async def list_open_positions(self, user_id: UUID) -> list[PortfolioPosition]:
        """列出使用者目前未平倉且淨額非零的持倉（權威來源，已由核准時淨額合併）。"""
        stmt = (
            select(PortfolioPosition)
            .where(
                PortfolioPosition.user_id == user_id,
                PortfolioPosition.closed_at.is_(None),
                PortfolioPosition.qty != 0,
            )
            .order_by(PortfolioPosition.symbol.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


__all__ = ["OrderRepository"]
