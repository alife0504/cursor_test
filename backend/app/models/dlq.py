"""CeleryDeadLetter — 失敗任務 DLQ（PLAN 第 14.10 章）。

hypertable on failed_at（chunk 1 month，retention 1 年 only when resolved）。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CeleryDeadLetter(Base):
    """Celery 任務失敗後寫入 — admin /admin/pipeline 頁手動 resolve / re-queue。"""

    __tablename__ = "celery_dead_letters"

    # 複合 PK — (id, failed_at)：hypertable 要求 time column 在 PK
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        server_default=func.now(),
        nullable=False,
    )

    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    args: Mapped[dict | list | None] = mapped_column(JSONB)
    kwargs: Mapped[dict | None] = mapped_column(JSONB)

    exception_type: Mapped[str | None] = mapped_column(String(255))
    exception: Mapped[str | None] = mapped_column(Text)
    traceback: Mapped[str | None] = mapped_column(Text)

    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resolution_notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_celery_dead_letters_resolved_failed", "resolved", "failed_at"),
        Index("ix_celery_dead_letters_task_name", "task_name"),
    )


__all__ = ["CeleryDeadLetter"]
