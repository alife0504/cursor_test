"""audit_logs.entry_hash 索引（配合永久保存，避免 verify_chain 全表 O(N²)）。

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-10

背景（第二輪審計）：
- 0019 移除 audit_logs 的 retention（永久保存）後，表會隨時間無上限成長。
- verify_chain 對每一列都跑相關子查詢 `EXISTS(SELECT 1 FROM audit_logs al2 WHERE al2.entry_hash
  = al.prev_hash)`；entry_hash 原無索引 → 每列 O(N)、全表驗證 O(N²)，長期每日校驗會逐漸變慢
  以致超時。加 entry_hash 索引後每次探測 O(log N)、全表 O(N log N)。
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_audit_logs_entry_hash", "audit_logs", ["entry_hash"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_entry_hash", table_name="audit_logs")
