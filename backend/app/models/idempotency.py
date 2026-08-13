"""IdempotencyKey — POST 建立類請求的 Idempotency-Key 持久化。

Redis db6 是主要儲存（TTL 24h），DB 表為持久備份（防 Redis 重啟丟）。
PLAN 第 14.5 章。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Default TTL：24 小時（與 Redis TTL 一致）
IDEMPOTENCY_TTL_HOURS = 24


def default_expires_at() -> datetime:
    """Python 端 default — 給 ORM 建立時用。

    DB 端 server_default 用 NOW() + INTERVAL '24 hours'。
    """

    return datetime.now(UTC) + timedelta(hours=IDEMPOTENCY_TTL_HOURS)


class IdempotencyKey(Base):
    """Idempotency-Key 紀錄 — TTL 24h，超期由 celery beat cleanup。"""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    """Client 提供的 Idempotency-Key header 值。"""
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    """SHA-256(method + path + body) — 用來偵測「同 key 但不同 request」的攻擊。"""

    response: Mapped[dict | list | None] = mapped_column(JSONB)
    """已成功處理的回應 body — 重送同 key 直接回此。"""
    status_code: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        # DB-side default：NOW() + 24h（在 migration 中設定）
    )

    __table_args__ = (
        Index("ix_idempotency_keys_expires_at", "expires_at"),
        Index("ix_idempotency_keys_user_id", "user_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"IdempotencyKey(key={self.key!r}, user={self.user_id}, expires={self.expires_at})"

    @staticmethod
    def calc_default_expires_at() -> Any:
        """Helper 給測試用。"""
        return default_expires_at()


__all__ = ["IDEMPOTENCY_TTL_HOURS", "IdempotencyKey", "default_expires_at"]
