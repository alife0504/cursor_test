"""Phase 8: password_history 表（最近 5 次密碼 hash）.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-14

設計（依 PLAN 第 19.1 章 + 第二十七章 Phase 8）：
- 紀錄 user 的歷史密碼 hash，change-password / reset-password 時比對前 5 次不可重複
- 結構：user_id + password_hash + created_at
- ondelete=CASCADE：user 軟刪除後 history 也清掉（避免 PII 漏出）
- 索引：(user_id, created_at DESC) — 查詢「該 user 最近 N 筆」用
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_password_history_user_id_users",
        ),
    )
    # 查詢「該 user 最近 N 筆」用 DESC 索引
    op.execute(
        "CREATE INDEX ix_password_history_user_id_created_at "
        "ON password_history (user_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_password_history_user_id_created_at")
    op.drop_table("password_history")
