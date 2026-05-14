"""Phase 8 — 暫時的 audit log 寫入 helper（P9 會改用完整 AuditRepository）。

依 PLAN 第二十七章 P8 audit log 寫入方式。本檔僅做最小寫入，hash chain
由 trigger（baseline 0012）自動填 prev_hash / entry_hash。

P9 會：
- 改用 AuditRepository（含 verify_chain / list 等）
- 加 IP / user-agent 自動填入
- 對齊 AuditMiddleware

P8 為了讓退出條件第 9 項
`SELECT count(*) FROM audit_logs WHERE action='auth.login' > 0` 通過。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.models.audit import AuditLog

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


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
    """最小 audit 寫入 — caller 負責 commit。

    trigger 會自動補 prev_hash / entry_hash（baseline 0012）。
    """
    record = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    session.add(record)
    await session.flush()
    return record


__all__ = ["append_audit"]
