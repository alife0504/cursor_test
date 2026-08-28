"""LangGraph Analysis Reports + Debate History。

依 PLAN.md 第 14.9 章 LangGraph State + 第 15.2 章樂觀鎖（version）+ 第 20.2 章。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, short_enum
from app.models.stock import MARKET_VALUES

ANALYSIS_STATUS_VALUES = ("queued", "running", "completed", "failed", "cancelled")
SIGNAL_VALUES = ("BUY", "SELL", "HOLD", "STRONG_BUY", "STRONG_SELL")


class AnalysisReport(Base):
    """分析報告 — LangGraph workflow 的最終產出。

    version 欄位是樂觀鎖（PLAN 15.2）：寫入時 WHERE version = expected。
    """

    __tablename__ = "analysis_reports"

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
    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stock_list.symbol", ondelete="RESTRICT"),
        nullable=False,
    )
    market: Mapped[str] = mapped_column(
        short_enum(*MARKET_VALUES, name="market_enum"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        short_enum(*ANALYSIS_STATUS_VALUES, name="analysis_status_enum"),
        nullable=False,
        server_default="queued",
    )
    signal: Mapped[str | None] = mapped_column(short_enum(*SIGNAL_VALUES, name="signal_enum"))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    """0.0 ~ 1.0"""
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))

    # LLM 使用
    llm_provider: Mapped[str | None] = mapped_column(String(30))
    llm_model: Mapped[str | None] = mapped_column(String(100))
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, server_default="0"
    )

    report_md: Mapped[str | None] = mapped_column(Text)
    """最終 Markdown 報告（繁中）。"""
    error_msg: Mapped[str | None] = mapped_column(Text)

    # v1.0.1：保留 analyst 結構化輸出（前端 AnalystResultCard 用）+ 還原建立參數
    analyst_outputs: Mapped[dict | None] = mapped_column(JSONB)
    """每個 analyst 結構化結果：{type → {score / key_points / report_md / metrics}}"""
    analyst_types: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    """建立時的請求參數，給前端 AgentFlowGraph 還原節點用。"""
    debate_rounds: Mapped[int | None] = mapped_column(Integer)
    """建立時的請求參數。"""
    risk_tolerance: Mapped[str | None] = mapped_column(String(20))
    """建立時的請求參數（保留欄位，v1.1 由 Agent 邏輯使用）。"""
    # v1.1.1：持久化派發參數，供 orphan 自癒忠實還原（否則重派會硬編 risk_rounds=0、
    # 遺失 agent_models → 完整風險架構分析被靜默降級重跑，見 cleanup.cleanup_orphans）。
    risk_rounds: Mapped[int | None] = mapped_column(Integer)
    """建立時的風險辯論輪數（>0 才接完整風險層 trader+verifier）；孤兒重派需忠實還原。"""
    agent_models: Mapped[dict | None] = mapped_column(JSONB)
    """建立時各 agent 的自訂模型 {agent→model}；孤兒重派需忠實還原。"""

    # 樂觀鎖（PLAN 15.2）
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    # 時間戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_analysis_reports_user_created", "user_id", "created_at"),
        Index("ix_analysis_reports_symbol_created", "symbol", "created_at"),
        Index("ix_analysis_reports_status", "status"),
    )


class DebateMessage(Base):
    """LangGraph debate 過程的單則訊息 — hypertable on created_at。

    用於：
    - 還原分析過程（前端「辯論詳情」頁）
    - trim/summary 後仍可回放原始記錄
    """

    __tablename__ = "debate_history"

    # 複合 PK — (id, created_at)；hypertable 要求 time column 在 PK
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        server_default=func.now(),
        nullable=False,
    )

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    """注意：因 analysis_reports 是普通表，本 FK 在普通 schema 可以建；
    但若未來 analysis_reports 改成 hypertable，FK 要拿掉。
    暫先不加 FK constraint，僅靠 index 維持查詢。"""

    round_num: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    """bull / bear / risk / trader / manager / summary"""
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    """訊息內容（含 structured output 完整 JSON）。"""

    tokens_used: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_debate_history_analysis_round", "analysis_id", "round_num"),
        Index("ix_debate_history_created_desc", "created_at"),
    )


__all__ = [
    "ANALYSIS_STATUS_VALUES",
    "SIGNAL_VALUES",
    "AnalysisReport",
    "DebateMessage",
]
