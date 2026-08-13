"""Phase 11 — NotificationRepository（settings + log）。

依 PLAN.md 第 20.2 章 schema + 第 19.4 章 token 加密。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from app.models.notification import NotificationLog, NotificationSetting
from app.repos.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class NotificationRepository(BaseRepository):
    """notification_settings + notification_log 的 CRUD wrapper。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── Settings ─────────────────────────────────────
    async def get_settings(self, user_id: UUID) -> NotificationSetting | None:
        stmt = select(NotificationSetting).where(NotificationSetting.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert_settings(
        self,
        user_id: UUID,
        *,
        patch: dict[str, Any],
    ) -> NotificationSetting:
        """部分更新；不存在則新建（caller 負責 commit）。"""
        existing = await self.get_settings(user_id)
        if existing is None:
            existing = NotificationSetting(user_id=user_id)
            self.session.add(existing)
        for k, v in patch.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
        await self.session.flush()
        return existing

    # ── Log ──────────────────────────────────────────
    async def add_log(
        self,
        *,
        user_id: UUID | None,
        channel: str,
        event_type: str,
        payload: dict[str, Any],
        status: str = "queued",
        error_msg: str | None = None,
    ) -> NotificationLog:
        log = NotificationLog(
            user_id=user_id,
            channel=channel,
            event_type=event_type,
            payload=payload,
            status=status,
            error_msg=error_msg,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_logs(
        self,
        *,
        user_id: UUID | None = None,
        limit: int = 50,
        before_sent_at: Any | None = None,
    ) -> list[NotificationLog]:
        stmt = select(NotificationLog)
        if user_id is not None:
            stmt = stmt.where(NotificationLog.user_id == user_id)
        if before_sent_at is not None:
            stmt = stmt.where(NotificationLog.sent_at < before_sent_at)
        stmt = stmt.order_by(NotificationLog.sent_at.desc(), NotificationLog.id.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["NotificationRepository"]
