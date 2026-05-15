"""Phase 11 — OrderService：approve / reject 並發保護。

依 PLAN.md 第 15.1 章 transaction + 第 15.2 章樂觀鎖。

approve 流程：
1. `async with session.begin():` 開 transaction
2. `repo.get_for_update(order_id)` → row-level lock
3. 檢查 status == PENDING；不是 → ConflictError 中文
4. 檢查 expected_version（若 caller 提供）；不符 → ConflictError 中文
5. mark_status → APPROVED + version += 1
6. add_portfolio_from_order
7. audit_repo.append
8. commit
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.logging_config import get_logger
from app.core.metrics import ORDERS_APPROVED_TOTAL, ORDERS_REJECTED_TOTAL
from app.repos.audit_repo import AuditRepository
from app.repos.order_repo import OrderRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.order import PendingOrder
    from app.models.user import User

logger = get_logger(__name__)


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = OrderRepository(session)
        self.audit_repo = AuditRepository(session)

    # ── 查詢 ─────────────────────────────────────────
    async def list_orders(
        self,
        user: User,
        *,
        status: str | None = None,
        limit: int = 50,
        before_created_at=None,
    ) -> list[PendingOrder]:
        user_filter: UUID | None = None if user.role.upper() == "ADMIN" else user.id
        return await self.repo.list(
            user_id=user_filter,
            status=status,
            limit=limit,
            before_created_at=before_created_at,
        )

    async def get_for_user(self, user: User, order_id: UUID) -> PendingOrder:
        order = await self.repo.get_by_id(order_id)
        if order is None:
            raise NotFoundError(message_zh="訂單不存在", order_id=str(order_id))
        if user.role.upper() != "ADMIN" and order.user_id != user.id:
            raise ForbiddenError(message_zh="無權檢視他人的訂單")
        return order

    # ── approve（並發保護）──────────────────────────
    async def approve(
        self,
        *,
        reviewer: User,
        order_id: UUID,
        expected_version: int | None = None,
        notes: str | None = None,
        request_id: str | None = None,
    ) -> PendingOrder:
        if reviewer.role.upper() not in ("ADMIN", "ANALYST"):
            raise ForbiddenError(message_zh="僅 ADMIN/ANALYST 可核准訂單")

        # SQLAlchemy autobegin：execute() 第一次自動 begin transaction，
        # commit() / rollback() 結束。SELECT FOR UPDATE 在這個 transaction 中
        # 有效，直到 commit。失敗時必須 rollback 釋放 lock。
        try:
            order = await self.repo.get_for_update(order_id)
            if order is None:
                raise NotFoundError(message_zh="訂單不存在", order_id=str(order_id))
            if order.status != "PENDING":
                raise ConflictError(
                    message_zh="訂單已被其他人處理",
                    current_status=order.status,
                )
            if expected_version is not None and order.version != expected_version:
                raise ConflictError(
                    message_zh="訂單版本已變更，請重新查詢",
                    expected_version=expected_version,
                    actual_version=order.version,
                )

            exec_price = order.target_price if order.target_price is not None else Decimal("1.0")

            await self.repo.mark_status(
                order,
                new_status="APPROVED",
                reviewer_id=reviewer.id,
                review_notes=notes,
            )
            await self.repo.add_portfolio_from_order(order, price=exec_price)

            await self.audit_repo.append(
                actor_id=reviewer.id,
                action="order.approved",
                entity_type="pending_order",
                entity_id=str(order.id),
                details={
                    "symbol": order.symbol,
                    "qty": order.qty,
                    "side": order.side,
                    "exec_price": str(exec_price),
                    "new_version": order.version,
                },
                request_id=request_id,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        ORDERS_APPROVED_TOTAL.inc()
        logger.info(
            "order.approved",
            order_id=str(order.id),
            reviewer_id=str(reviewer.id),
            symbol=order.symbol,
        )
        refreshed = await self.repo.get_by_id(order_id)
        assert refreshed is not None
        return refreshed

    # ── reject ───────────────────────────────────────
    async def reject(
        self,
        *,
        reviewer: User,
        order_id: UUID,
        reason: str,
        expected_version: int | None = None,
        request_id: str | None = None,
    ) -> PendingOrder:
        if reviewer.role.upper() not in ("ADMIN", "ANALYST"):
            raise ForbiddenError(message_zh="僅 ADMIN/ANALYST 可拒絕訂單")

        try:
            order = await self.repo.get_for_update(order_id)
            if order is None:
                raise NotFoundError(message_zh="訂單不存在", order_id=str(order_id))
            if order.status != "PENDING":
                raise ConflictError(
                    message_zh="訂單已被其他人處理",
                    current_status=order.status,
                )
            if expected_version is not None and order.version != expected_version:
                raise ConflictError(
                    message_zh="訂單版本已變更，請重新查詢",
                    expected_version=expected_version,
                    actual_version=order.version,
                )

            await self.repo.mark_status(
                order,
                new_status="REJECTED",
                reviewer_id=reviewer.id,
                review_notes=reason,
            )

            await self.audit_repo.append(
                actor_id=reviewer.id,
                action="order.rejected",
                entity_type="pending_order",
                entity_id=str(order.id),
                details={
                    "symbol": order.symbol,
                    "qty": order.qty,
                    "reason": reason[:200],
                },
                request_id=request_id,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        ORDERS_REJECTED_TOTAL.inc()
        refreshed = await self.repo.get_by_id(order_id)
        assert refreshed is not None
        return refreshed


__all__ = ["OrderService"]
