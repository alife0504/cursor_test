"""baseline: 共用 trigger（updated_at 自動更新、audit_logs hash chain）.

Phase 4 baseline part 12/13。

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-12

設計：
- update_updated_at_column()：通用 BEFORE UPDATE，設 NEW.updated_at = NOW()
- audit_logs_hash_chain()：BEFORE INSERT，依 PLAN 19.6 章
    sha256(prev_hash || row_id || actor_id || action || entity_type ||
           entity_id || details::text || timestamp)
- 同時用 pg_advisory_xact_lock 避免 race（並發 INSERT 拿到相同 prev_hash）

注意：
- 不掛 updated_at trigger 到 hypertable（避免 TimescaleDB chunk 相容性問題）
- updated_at trigger 涵蓋：users, stock_list, stock_info, analysis_reports,
  pending_orders, portfolio_positions, llm_monthly_quota, notification_settings
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES_WITH_UPDATED_AT = (
    "users",
    "stock_list",
    "stock_info",
    "analysis_reports",
    "pending_orders",
    "portfolio_positions",
    "llm_monthly_quota",
    "notification_settings",
)


# ── update_updated_at_column trigger function ─────────────
_UPDATED_AT_FN = """
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;
"""

# ── audit_logs hash chain trigger function ─────────────────
# 依 PLAN 19.6：sha256(prev || id || actor_id || action || entity_type ||
#                       entity_id || details::text || timestamp)
# 用 pg_advisory_xact_lock 避免 concurrent INSERT race
_AUDIT_HASH_FN = """
CREATE OR REPLACE FUNCTION audit_logs_hash_chain()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    last_hash TEXT;
    payload TEXT;
BEGIN
    -- 全表 advisory lock，序列化 INSERT 計算（事務結束自動釋放）
    PERFORM pg_advisory_xact_lock(hashtext('audit_logs_hash_chain'));

    -- 取上一筆 entry_hash（依 timestamp、id 最新者）
    SELECT entry_hash INTO last_hash
    FROM audit_logs
    ORDER BY timestamp DESC, id DESC
    LIMIT 1;

    NEW.prev_hash := COALESCE(last_hash, repeat('0', 64));

    -- 組合 payload
    payload := NEW.prev_hash
            || '|' || COALESCE(NEW.id::text, '')
            || '|' || COALESCE(NEW.actor_id::text, '')
            || '|' || NEW.action
            || '|' || COALESCE(NEW.entity_type, '')
            || '|' || COALESCE(NEW.entity_id, '')
            || '|' || COALESCE(NEW.details::text, '{}')
            || '|' || NEW.timestamp::text;

    -- pgcrypto digest（sha256） + encode hex（64 字元）
    NEW.entry_hash := encode(digest(payload, 'sha256'), 'hex');

    RETURN NEW;
END;
$$;
"""


def upgrade() -> None:
    # 1. updated_at function + triggers
    op.execute(_UPDATED_AT_FN)
    for tbl in TABLES_WITH_UPDATED_AT:
        op.execute(
            f"""
            CREATE TRIGGER trg_{tbl}_updated_at
            BEFORE UPDATE ON {tbl}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )

    # 2. audit_logs hash chain
    op.execute(_AUDIT_HASH_FN)
    op.execute(
        """
        CREATE TRIGGER trg_audit_logs_hash_chain
        BEFORE INSERT ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION audit_logs_hash_chain();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_hash_chain ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_hash_chain()")

    for tbl in TABLES_WITH_UPDATED_AT:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tbl}_updated_at ON {tbl}")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
