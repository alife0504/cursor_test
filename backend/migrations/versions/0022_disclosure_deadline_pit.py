"""financial_statements / monthly_revenue 加 disclosure_deadline（PIT 正確性）。

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-16

背景：
- 實測 financial_statements（320,240 列）與 monthly_revenue（431,069 列）的 announced_at
  **100% 為 NULL** —— 上游 FinMind 根本不提供財報公告日（三張財報表只有期間日 date，
  月營收的 date 是「次月 1 日」的慣例、拿來當公告日會偷看未來 9 天）。
- 沒有公告日就沒有 point-in-time 正確性：Q1 期間 3/31 結束但法定 5/15 才公告，任何 4 月的
  分析若讀得到 Q1 財報就是**偷看未來**。與存活者偏誤同類：不會報錯，只會讓回測系統性高估。

設計（延續 0035ce6d8 disclosure_calendar 的決定）：
    announced_at        = 實際公告日（維持 NULL，待接 MOPS 公開資訊觀測站）
    disclosure_deadline = 法定期限（app.domain.disclosure_calendar 現在就能算）
    PIT 查詢 → COALESCE(announced_at, disclosure_deadline) <= as_of

**絕不把期限寫進 announced_at** —— 那會造出一個會說謊的欄位。用期限當 PIT 邊界是
correct-by-construction：永遠不會偷看未來，代價是低估「你多早知道」。保守會少賺、樂觀會爆炸。

本 migration 只加欄位與索引；既有列的回填由 scripts/backfill_disclosure_deadline.py 執行
（純計算，不需外部資料源）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("financial_statements", "monthly_revenue"):
        op.add_column(table, sa.Column("disclosure_deadline", sa.Date(), nullable=True))
        # PIT 查詢會以 COALESCE(announced_at, disclosure_deadline) 過濾 → 兩欄都要能走索引
        op.create_index(
            f"ix_{table}_disclosure_deadline",
            table,
            ["disclosure_deadline"],
        )


def downgrade() -> None:
    for table in ("financial_statements", "monthly_revenue"):
        op.drop_index(f"ix_{table}_disclosure_deadline", table_name=table)
        op.drop_column(table, "disclosure_deadline")
