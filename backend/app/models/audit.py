"""AuditLog — hash chain + 不可竄改（PLAN 第 19.6 章）。

設計：
- BIGSERIAL id（時序順序保證）
- prev_hash / entry_hash 形成 hash chain
- 表為 hypertable on timestamp（chunk 1 month，retention 1 年）
- ta_service_rw 帳號 REVOKE UPDATE/DELETE（baseline 0013 處理）
- BEFORE INSERT trigger 自動計算 prev_hash + entry_hash（baseline 0012）

hash 公式：
  sha256(prev_hash || row_id || actor_id || action || entity_type ||
         entity_id || details::text || timestamp)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """審計日誌 — 不可 UPDATE / DELETE（PG 權限 + hash chain 雙保險）。"""

    __tablename__ = "audit_logs"

    # 複合 PK — (id, timestamp)：hypertable 要求 time column 在 PK；
    # BIGSERIAL id 仍保證唯一插入順序，方便 hash chain trigger 用 lag()。
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        server_default=func.now(),
        nullable=False,
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    """誰做的（NULL = 系統 / 匿名）。"""
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    """如 auth.login / order.approve / data.export。"""
    entity_type: Mapped[str | None] = mapped_column(String(50))
    """如 user / analysis / order / system。"""
    entity_id: Mapped[str | None] = mapped_column(String(100))
    """被操作對象 ID（字串相容 UUID / 整數 / 自訂 key）。"""

    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    """請求 body / 變更前後 diff / 其他 context。敏感欄位需在寫入前遮蔽。"""

    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))
    """X-Request-ID（追蹤一次請求的所有 audit）。"""

    # Hash chain — trigger 自動填
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    entry_hash: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_audit_logs_actor_timestamp", "actor_id", "timestamp"),
        Index("ix_audit_logs_entity_timestamp", "entity_type", "entity_id", "timestamp"),
        Index("ix_audit_logs_action_timestamp", "action", "timestamp"),
        Index("ix_audit_logs_request_id", "request_id"),
    )


__all__ = ["AuditLog"]
