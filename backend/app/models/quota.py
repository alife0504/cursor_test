"""LLM Usage + Monthly Quota — PLAN 第 19.3 章 L6 + 第 20.2 章。

llm_usage：每次呼叫 LLM 的成本紀錄（hypertable on created_at）。
llm_monthly_quota：每用戶每月預算 + 已使用累計（普通表）。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LLMUsage(Base):
    """每次 LLM 呼叫紀錄 — hypertable on created_at（chunk 1 month，retention 1 年）。"""

    __tablename__ = "llm_usage"

    # 複合 PK — (id, created_at)：hypertable 要求
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        server_default=func.now(),
        nullable=False,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    """google / openai / anthropic / ollama-local"""
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    """gemini-2.0-flash / gpt-4o-mini / claude-haiku-..."""
    purpose: Mapped[str | None] = mapped_column(String(50))
    """analyst / debate / summary / embedding"""

    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
    """精度 (12, 6)：足以表達單筆 ~$1,000,000.000001 等微小金額。"""

    latency_ms: Mapped[int | None] = mapped_column(Integer)
    succeeded: Mapped[bool | None] = mapped_column()
    error_msg: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index("ix_llm_usage_user_created", "user_id", "created_at"),
        Index("ix_llm_usage_analysis_id", "analysis_id"),
        Index("ix_llm_usage_provider_model", "provider", "model"),
    )


class LLMMonthlyQuota(Base):
    """每用戶每月預算與已使用（PLAN 19.3 L6: $50/user）。"""

    __tablename__ = "llm_monthly_quota"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    used_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "year", "month", name="uq_llm_monthly_quota_user_year_month"),
        Index("ix_llm_monthly_quota_year_month", "year", "month"),
    )


__all__ = ["LLMMonthlyQuota", "LLMUsage"]
