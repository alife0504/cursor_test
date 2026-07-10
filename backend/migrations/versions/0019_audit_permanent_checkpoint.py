"""稽核鏈永久保存 + 尾端錨定 checkpoint（H4 / #36 深度審計修補）。

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-10

背景（深度審計發現）：
- audit_logs 原設 1 年 retention（0009），但 audit 設計是「不可竄改證據鏈」。TimescaleDB 的
  retention 背景 job 以 table owner 執行 drop_chunks，繞過 0013 對 ta_service_rw 的 REVOKE，
  會靜默刪掉超過 1 年的最舊 chunk → 破壞鏈，且每日 verify_chain 會誤報 CRITICAL 竄改告警。
- verify_chain 原本「prev_hash 只要能在全表任一列找到」是與順序無關的檢查，且無外部錨定 → 刪除
  鏈尾最新數筆（湮滅最新稽核）偵測不到。

本 migration（使用者裁示：稽核鏈永久保存、真正不可竄改）：
1. 移除 audit_logs 的 retention policy（改永久保存，不再 drop 舊 chunk）。
2. 新增 audit_checkpoints（append-only）：週期性記錄鏈尾（row_count / last_id / last_entry_hash），
   讓 verify 能偵測「列數回退（尾端截斷）」與「錨定列被刪改」。
3. 比照 audit_logs（0013）對 ta_service_rw REVOKE UPDATE/DELETE/TRUNCATE，checkpoint 僅可 append。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) 稽核鏈永久保存：移除 audit_logs 的 1 年 retention（避免背景 job drop 舊 chunk 破壞鏈）
    op.execute("SELECT remove_retention_policy('audit_logs', if_exists => TRUE)")

    # 2) 尾端錨定 checkpoint 表（append-only）
    op.create_table(
        "audit_checkpoints",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), primary_key=True),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("row_count", sa.BigInteger, nullable=False),
        sa.Column("last_id", sa.BigInteger),
        sa.Column("last_entry_hash", sa.String(64)),
    )
    op.create_index("ix_audit_checkpoints_checked_at", "audit_checkpoints", ["checked_at"])

    # 3) append-only：撤銷 ta_service_rw 的 UPDATE/DELETE/TRUNCATE（比照 audit_logs 0013）
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_checkpoints FROM ta_service_rw")


def downgrade() -> None:
    # 還原權限後刪表；並把 audit_logs retention 加回（僅為 alembic 完整性，實務不應 downgrade）
    op.execute("GRANT UPDATE, DELETE, TRUNCATE ON audit_checkpoints TO ta_service_rw")
    op.drop_index("ix_audit_checkpoints_checked_at", table_name="audit_checkpoints")
    op.drop_table("audit_checkpoints")
    op.execute(
        "SELECT add_retention_policy('audit_logs', INTERVAL '1 year', if_not_exists => TRUE)"
    )
