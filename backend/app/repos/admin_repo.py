"""Phase 11 — AdminRepository：DLQ + UserSession 強制下線。

依 PLAN.md 第 14.10 章 DLQ + 第 19.1 章 session 強制下線。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from app.models.dlq import CeleryDeadLetter
from app.models.user import UserSession
from app.repos.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AdminRepository(BaseRepository):
    """admin 專屬操作：DLQ 列表 / resolve / requeue；session 列表 / revoke。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── DLQ ──────────────────────────────────────────
    async def list_dlq(
        self,
        *,
        resolved: bool | None = None,
        limit: int = 50,
        before_failed_at: Any | None = None,
    ) -> list[CeleryDeadLetter]:
        stmt = select(CeleryDeadLetter)
        if resolved is not None:
            stmt = stmt.where(CeleryDeadLetter.resolved == resolved)
        if before_failed_at is not None:
            stmt = stmt.where(CeleryDeadLetter.failed_at < before_failed_at)
        stmt = stmt.order_by(CeleryDeadLetter.failed_at.desc(), CeleryDeadLetter.id.desc()).limit(
            limit
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_dlq(self, dlq_id: int) -> CeleryDeadLetter | None:
        stmt = select(CeleryDeadLetter).where(CeleryDeadLetter.id == dlq_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def resolve_dlq(
        self,
        dlq_id: int,
        *,
        admin_id: UUID,
        notes: str,
    ) -> CeleryDeadLetter | None:
        row = await self.get_dlq(dlq_id)
        if row is None:
            return None
        row.resolved = True
        row.resolved_at = datetime.now(UTC)
        row.resolved_by = admin_id
        row.resolution_notes = notes
        await self.session.flush()
        return row

    # ── User Session ─────────────────────────────────
    async def list_user_sessions(
        self,
        user_id: UUID,
        *,
        only_active: bool = True,
        limit: int = 50,
    ) -> list[UserSession]:
        stmt = select(UserSession).where(UserSession.user_id == user_id)
        if only_active:
            stmt = stmt.where(UserSession.revoked.is_(False))
        stmt = stmt.order_by(UserSession.issued_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def revoke_session_by_jti(self, user_id: UUID, jti: str) -> UserSession | None:
        stmt = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.jti == jti,
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        row.revoked = True
        row.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return row


__all__ = ["AdminRepository"]
