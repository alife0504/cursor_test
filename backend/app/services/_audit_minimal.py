"""Phase 8 → 9：thin wrapper 維持向後相容，內部呼叫 P9 AuditRepository。

P8 originally 直接 add AuditLog；P9 整合到 AuditRepository.append。
保留此 module 以避免 P8 既有 import 全部改。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.repos.audit_repo import AuditRepository

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.audit import AuditLog


async def append_audit(
    session: AsyncSession,
    *,
    actor_id: UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> AuditLog:
    """thin wrapper — caller 仍負責 commit。"""
    return await AuditRepository(session).append(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )


__all__ = ["append_audit"]
