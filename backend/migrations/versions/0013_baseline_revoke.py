"""baseline: REVOKE UPDATE/DELETE on audit_logs from ta_service_rw.

Phase 4 baseline part 13/13。

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-12

設計（依 PLAN 第 19.6 章）：
- audit_logs 一旦寫入不可修改／刪除（hash chain 形成證據鏈）
- ta_service_rw 帳號只能 SELECT / INSERT
- 系統管理員（postgres superuser）仍可（緊急情況下手動）

注意：
- ta_migration 帳號跑此 migration，REVOKE 對其他帳號生效，自身 DDL 權限不受影響
- 若 ta_service_rw 帳號因任何原因不存在（init.sql 還沒跑完），
  op.execute() 會拋錯 — 此時應先 docker compose up 等 init.sh 跑完再 migrate
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 撤銷 UPDATE / DELETE — audit_logs 不可竄改
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM ta_service_rw")

    # 雙保險：也 REVOKE TRUNCATE
    op.execute("REVOKE TRUNCATE ON audit_logs FROM ta_service_rw")

    # ALTER DEFAULT PRIVILEGES 是後續 ta_migration 建新表時用的；
    # 此處針對「現有 audit_logs」明確撤銷。後續 migration 若 ALTER audit_logs，
    # 仍保留 SELECT / INSERT 給 ta_service_rw（不會自動還回 UPDATE/DELETE）。


def downgrade() -> None:
    # 還原權限（讓 ta_service_rw 重新可 UPDATE/DELETE/TRUNCATE）
    # 但實務上 audit 表權限不應 downgrade，這裡僅為 alembic 完整性。
    op.execute("GRANT UPDATE, DELETE, TRUNCATE ON audit_logs TO ta_service_rw")
