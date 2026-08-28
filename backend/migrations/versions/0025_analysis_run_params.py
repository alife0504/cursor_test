"""analysis_reports 增 risk_rounds / agent_models —— orphan 自癒忠實還原派發參數。

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-28

背景：
- run_analysis 的派發參數 risk_rounds（>0 才接完整風險層 trader+risk team+verifier）與
  agent_models（各 agent 自訂模型）原本**只透過 celery task kwargs 傳遞、DB 未持久化**。
- cleanup_orphans 對 worker 被殺/redeploy 留下的 running 孤兒會重設 queued + 重派 run_analysis，
  但只能從 DB 撈回 (analyst_types, debate_rounds)，硬編 risk_rounds=0 且完全不帶 agent_models
  → 使用者原以「完整風險架構 + 自訂模型」送出的分析，被靜默改以「無風險層、預設模型」重跑，
  最後仍標 completed。使用者拿到的是與請求不同且能力降級的報告（且據以產生的 signal 也可能不同）。
- 修法：持久化這兩個派發參數，讓 cleanup 重派時忠實還原。

新增兩個 nullable 欄位（舊列為 NULL；cleanup 對 NULL 退回保守行為）。
analysis_reports 既有表，ALTER ADD COLUMN 沿用既有權限，不需額外 GRANT。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_reports",
        sa.Column("risk_rounds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "analysis_reports",
        sa.Column("agent_models", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_reports", "agent_models")
    op.drop_column("analysis_reports", "risk_rounds")
