"""v1.0.1: analysis_reports 加 metadata 欄位 (analyst_outputs / analyst_types / debate_rounds / risk_tolerance).

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-02

依 v1.0.1 改善計劃 Batch 4：
- 前端原本拿不到 analyst raw output（無法在 AnalystResultCard 展示）
- 前端無法拿到原始 analyst_types/debate_rounds 來建 AgentFlowGraph 節點
- 所有欄位 nullable，不破壞既有資料、不影響 audit hash chain

欄位設計：
- analyst_outputs: JSONB — 每個 analyst 的結構化結果（type → {score/key_points/report_md/...}）
- analyst_types: ARRAY(TEXT) — 建立時的請求參數，重新打開分析詳情頁也能還原節點
- debate_rounds: INTEGER — 建立時的請求參數
- risk_tolerance: VARCHAR(20) — 建立時的請求參數（保留欄位，v1.1 可用）
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_reports",
        sa.Column("analyst_outputs", JSONB, nullable=True),
    )
    op.add_column(
        "analysis_reports",
        sa.Column("analyst_types", ARRAY(sa.Text), nullable=True),
    )
    op.add_column(
        "analysis_reports",
        sa.Column("debate_rounds", sa.Integer, nullable=True),
    )
    op.add_column(
        "analysis_reports",
        sa.Column("risk_tolerance", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_reports", "risk_tolerance")
    op.drop_column("analysis_reports", "debate_rounds")
    op.drop_column("analysis_reports", "analyst_types")
    op.drop_column("analysis_reports", "analyst_outputs")
