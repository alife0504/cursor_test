"""Phase 11 — /api/v1/admin/* schemas。"""

from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


class AuditLogOut(BaseSchema):
    id: int
    timestamp: datetime
    actor_id: UUID | None = None
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    details: dict[str, Any] | list[Any] | None = None
    ip: str | None = None
    request_id: str | None = None
    prev_hash: str | None = None
    entry_hash: str | None = None

    @field_validator("ip", mode="before")
    @classmethod
    def _coerce_ip(cls, v: Any) -> Any:
        """SQLAlchemy INET column 解出 IPv4Address/IPv6Address；str() 化以利序列化。"""
        if isinstance(v, IPv4Address | IPv6Address):
            return str(v)
        return v


class DeadLetterOut(BaseSchema):
    id: int
    failed_at: datetime
    task_name: str
    task_id: UUID | None = None
    args: list[Any] | dict[str, Any] | None = None
    kwargs: dict[str, Any] | None = None
    exception_type: str | None = None
    exception: str | None = None
    retry_count: int
    resolved: bool
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    resolution_notes: str | None = None


class DLQResolveRequest(BaseSchema):
    notes: str = Field(min_length=1, max_length=500)


class UserSessionOut(BaseSchema):
    id: UUID
    jti: str
    user_id: UUID
    issued_at: datetime
    expires_at: datetime
    revoked: bool
    revoked_at: datetime | None = None
    ip: str | None = None
    user_agent: str | None = None

    @field_validator("ip", mode="before")
    @classmethod
    def _coerce_ip(cls, v: Any) -> Any:
        if isinstance(v, IPv4Address | IPv6Address):
            return str(v)
        return v


__all__ = [
    "AuditLogOut",
    "DLQResolveRequest",
    "DeadLetterOut",
    "UserSessionOut",
]
