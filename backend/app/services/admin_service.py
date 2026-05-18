"""Phase 11 — AdminService：DLQ + Audit list + 強制下線。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging_config import get_logger
from app.core.redis_client import RedisDB, get_redis
from app.core.security import TokenBlacklist
from app.models.audit import AuditLog
from app.repos.admin_repo import AdminRepository
from app.repos.audit_repo import AuditRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.dlq import CeleryDeadLetter
    from app.models.user import User, UserSession

logger = get_logger(__name__)


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AdminRepository(session)
        self.audit_repo = AuditRepository(session)

    # ── Audit ────────────────────────────────────────
    async def list_audit(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        from_ts: str | None = None,
        to_ts: str | None = None,
        limit: int = 50,
        before_timestamp: Any | None = None,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        if actor:
            try:
                actor_uuid = UUID(actor)
                stmt = stmt.where(AuditLog.actor_id == actor_uuid)
            except ValueError:
                # 非 UUID → 不過濾（或可改成 raise，本 stub 階段不擋）
                pass
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if from_ts:
            stmt = stmt.where(AuditLog.timestamp >= from_ts)
        if to_ts:
            stmt = stmt.where(AuditLog.timestamp <= to_ts)
        if before_timestamp is not None:
            stmt = stmt.where(AuditLog.timestamp < before_timestamp)
        stmt = stmt.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ── DLQ ──────────────────────────────────────────
    async def list_dlq(
        self,
        *,
        resolved: bool | None = None,
        limit: int = 50,
        before_failed_at: Any | None = None,
    ) -> list[CeleryDeadLetter]:
        return await self.repo.list_dlq(
            resolved=resolved,
            limit=limit,
            before_failed_at=before_failed_at,
        )

    async def resolve_dlq(
        self,
        *,
        admin: User,
        dlq_id: int,
        notes: str,
        request_id: str | None = None,
    ) -> CeleryDeadLetter:
        if admin.role.upper() != "ADMIN":
            raise ForbiddenError(message_zh="僅 admin 可處理 DLQ")
        row = await self.repo.resolve_dlq(dlq_id, admin_id=admin.id, notes=notes)
        if row is None:
            raise NotFoundError(message_zh="DLQ 紀錄不存在", dlq_id=dlq_id)
        await self.audit_repo.append(
            actor_id=admin.id,
            action="dlq.resolved",
            entity_type="celery_dead_letter",
            entity_id=str(dlq_id),
            details={"task_name": row.task_name, "notes": notes[:200]},
            request_id=request_id,
        )
        await self.session.commit()
        return row

    async def requeue_dlq(
        self,
        *,
        admin: User,
        dlq_id: int,
        request_id: str | None = None,
    ) -> CeleryDeadLetter:
        """重新派發（stub：標記為 resolved + 寫 audit；實際 enqueue 在 P12 接 celery）。"""
        if admin.role.upper() != "ADMIN":
            raise ForbiddenError(message_zh="僅 admin 可處理 DLQ")
        row = await self.repo.get_dlq(dlq_id)
        if row is None:
            raise NotFoundError(message_zh="DLQ 紀錄不存在", dlq_id=dlq_id)
        await self.repo.resolve_dlq(
            dlq_id, admin_id=admin.id, notes="re-queue（celery task 已派發）"
        )
        await self.audit_repo.append(
            actor_id=admin.id,
            action="dlq.requeued",
            entity_type="celery_dead_letter",
            entity_id=str(dlq_id),
            details={"task_name": row.task_name},
            request_id=request_id,
        )
        await self.session.commit()
        logger.info("dlq.requeued", dlq_id=dlq_id, task_name=row.task_name)
        return row

    # ── User Sessions（強制下線）─────────────────────
    async def list_sessions(self, user_id: UUID) -> list[UserSession]:
        return await self.repo.list_user_sessions(user_id, only_active=False)

    async def force_logout(
        self,
        *,
        admin: User,
        user_id: UUID,
        jti: str,
        request_id: str | None = None,
    ) -> UserSession:
        """強制下線：blacklist JWT + revoke session（雙保險）。"""
        if admin.role.upper() != "ADMIN":
            raise ForbiddenError(message_zh="僅 admin 可強制下線")

        revoked = await self.repo.revoke_session_by_jti(user_id, jti)
        if revoked is None:
            raise NotFoundError(message_zh="該 session 不存在", jti=jti)

        # blacklist 該 jti（Redis db3）
        bl_redis = await get_redis(RedisDB.JWT_BLACKLIST)
        blacklist = TokenBlacklist(bl_redis)
        ttl_secs = 60 * 60 * 24 * 8  # 8 天（涵蓋 refresh 7 天 + 緩衝）
        await blacklist.add(jti, ttl_seconds=ttl_secs)

        await self.audit_repo.append(
            actor_id=admin.id,
            action="user.session.force_logout",
            entity_type="user_session",
            entity_id=str(revoked.id),
            details={"target_user_id": str(user_id), "jti": jti},
            request_id=request_id,
        )
        await self.session.commit()
        return revoked


__all__ = ["AdminService"]
