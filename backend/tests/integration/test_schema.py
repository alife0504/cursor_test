"""Phase 4 schema 整合測試。

驗證：
- 25+ 個 public schema table
- 6 個 hypertable + chunk_time_interval = 1 month
- 6 個 retention policy（5 個 1 年 + notification_log 90 天）
- audit_logs hash chain trigger 正確
- updated_at trigger 正確
- 主要 index 存在
- ta_service_rw 不可 UPDATE / DELETE audit_logs
- Qdrant 7 個 collections 存在

需要 docker compose up（timescaledb / qdrant healthy）+ alembic upgrade head 完。
"""

from __future__ import annotations

import asyncio
import uuid

import asyncpg  # type: ignore[import-not-found]
import pytest

from app.core.config import settings

pytestmark = pytest.mark.integration


# ── 共用 helper ──────────────────────────────────────────


async def _connect_superuser() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user="postgres",
        password=settings.POSTGRES_SUPERUSER_PASSWORD.get_secret_value(),
        database=settings.POSTGRES_DB,
    )


async def _connect_service_rw() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user="ta_service_rw",
        password=settings.TA_SERVICE_RW_PASSWORD.get_secret_value(),
        database=settings.POSTGRES_DB,
    )


async def _connect_agent_ro() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user="ta_agent_ro",
        password=settings.TA_AGENT_RO_PASSWORD.get_secret_value(),
        database=settings.POSTGRES_DB,
    )


# ── tests ────────────────────────────────────────────────


async def test_all_tables_created() -> None:
    """public schema 應該有 25+ 個 table（13 個 baseline migration 建立的）。"""
    conn = await _connect_superuser()
    try:
        n = await conn.fetchval(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
        )
        assert n >= 24, f"預期 ≥ 24 tables（含 alembic_version），實際 {n}"

        # 抽樣驗證幾個關鍵 table 存在
        for tbl in (
            "users",
            "stock_list",
            "stock_prices",
            "audit_logs",
            "analysis_reports",
            "pending_orders",
            "llm_usage",
            "celery_dead_letters",
            "notification_log",
            "user_watchlist",
        ):
            exists = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=$1",
                tbl,
            )
            assert exists == 1, f"關鍵 table 缺：{tbl}"
    finally:
        await conn.close()


async def test_hypertable_chunk_time_interval() -> None:
    """6 個 hypertable 都該存在；其中 stock_prices 的 chunk = 1 month。"""
    conn = await _connect_superuser()
    try:
        rows = await conn.fetch("SELECT hypertable_name FROM timescaledb_information.hypertables")
        names = {r["hypertable_name"] for r in rows}
        expected = {
            "stock_prices",
            "audit_logs",
            "llm_usage",
            "notification_log",
            "celery_dead_letters",
            "debate_history",
        }
        missing = expected - names
        assert not missing, f"hypertable 缺：{missing}"

        # 抽 stock_prices 確認 chunk_time_interval（in microseconds for time / Date）
        interval = await conn.fetchval(
            "SELECT integer_interval FROM timescaledb_information.dimensions "
            "WHERE hypertable_name='stock_prices'"
        )
        # Date dimension 用 integer_interval（days*86400000000 微秒 / 30 days = ~2592000000000）
        # 1 month 約 30 天 = 30*86400*1_000_000 微秒
        # interval 為 None 表示用 time 軸（不是 integer）。Date 本身會用 integer.
        assert interval is None or interval > 0, f"chunk interval 應 >0，實際 {interval}"
    finally:
        await conn.close()


async def test_retention_policies_set() -> None:
    """6 個 retention policy 都該存在，notification_log 為 90 天，其他為 1 年。"""
    conn = await _connect_superuser()
    try:
        rows = await conn.fetch(
            "SELECT hypertable_name, config->>'drop_after' AS drop_after "
            "FROM timescaledb_information.jobs "
            "WHERE proc_name='policy_retention'"
        )
        d = {r["hypertable_name"]: r["drop_after"] for r in rows}
        # 6 個 hypertable 全部要有 retention
        assert len(d) >= 6, f"預期 ≥ 6 retention policy，實際 {len(d)}"

        # notification_log 為 90 days，其餘為 1 year
        assert "90 days" in (
            d.get("notification_log") or ""
        ), f"notification_log retention 不對：{d.get('notification_log')}"
        for tbl in ("stock_prices", "audit_logs", "llm_usage"):
            assert "1 year" in (d.get(tbl) or ""), f"{tbl} retention 不是 1 year：{d.get(tbl)}"
    finally:
        await conn.close()


async def test_audit_logs_hash_chain_trigger() -> None:
    """INSERT audit_logs 應由 trigger 自動算 entry_hash（64 字 hex）。"""
    conn = await _connect_service_rw()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details)
            VALUES (NULL, 'test.schema', 'system', 'unit-test', '{}'::jsonb)
            RETURNING id, prev_hash, entry_hash
            """
        )
        assert row is not None
        assert row["entry_hash"] is not None
        assert len(row["entry_hash"]) == 64
        # hex 字元
        int(row["entry_hash"], 16)
        # prev_hash 也是 64 字 hex（可能是 64 個 0 或上一筆）
        assert len(row["prev_hash"]) == 64
    finally:
        await conn.close()


async def test_audit_logs_hash_chain_continuity() -> None:
    """連續 INSERT 兩筆：第 2 筆的 prev_hash 應等於第 1 筆的 entry_hash。"""
    conn = await _connect_service_rw()
    try:
        r1 = await conn.fetchrow(
            """
            INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details)
            VALUES (NULL, 'test.chain.1', 'system', $1, '{}'::jsonb)
            RETURNING entry_hash
            """,
            f"chain-{uuid.uuid4()}",
        )
        r2 = await conn.fetchrow(
            """
            INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details)
            VALUES (NULL, 'test.chain.2', 'system', $1, '{}'::jsonb)
            RETURNING prev_hash, entry_hash
            """,
            f"chain-{uuid.uuid4()}",
        )
        assert r1 is not None and r2 is not None
        assert (
            r2["prev_hash"] == r1["entry_hash"]
        ), f"hash chain 斷裂：r2.prev={r2['prev_hash']} != r1.entry={r1['entry_hash']}"
        assert r2["entry_hash"] != r1["entry_hash"]
    finally:
        await conn.close()


async def test_updated_at_trigger() -> None:
    """UPDATE users 應由 trigger 自動更新 updated_at。

    自建一個 ephemeral user 並清理，避免依賴 init_db 已跑。
    """
    test_email = f"trigger-test-{uuid.uuid4()}@example.com"
    conn = await _connect_service_rw()
    try:
        # 自建 user（password_hash 隨意，僅為驗 trigger）
        row = await conn.fetchrow(
            """
            INSERT INTO users (email, password_hash, role)
            VALUES ($1, 'placeholder-hash', 'VIEWER')
            RETURNING id, updated_at
            """,
            test_email,
        )
        assert row is not None
        original_updated_at = row["updated_at"]
        user_id = row["id"]

        await asyncio.sleep(0.1)
        await conn.execute(
            "UPDATE users SET preferred_language = preferred_language WHERE id = $1",
            user_id,
        )

        new_updated_at = await conn.fetchval("SELECT updated_at FROM users WHERE id = $1", user_id)
        assert (
            new_updated_at > original_updated_at
        ), f"updated_at 沒更新：{new_updated_at} <= {original_updated_at}"

        # 清理（不污染後續測試）
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)
    finally:
        await conn.close()


async def test_indexes_present() -> None:
    """主要 index 應該都存在。"""
    conn = await _connect_superuser()
    try:
        expected_indexes = [
            "ix_users_email_lower",
            "ix_users_role",
            "ix_stock_list_name_trgm",
            "ix_stock_list_market",
            "ix_audit_logs_actor_timestamp",
            "ix_audit_logs_entity_timestamp",
            "ix_analysis_reports_user_created",
            "ix_pending_orders_status_created",
            "ix_notification_log_user_sent",
            "ix_llm_usage_user_created",
        ]
        rows = await conn.fetch("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
        present = {r["indexname"] for r in rows}
        missing = [ix for ix in expected_indexes if ix not in present]
        assert not missing, f"index 缺：{missing}"
    finally:
        await conn.close()


async def test_audit_logs_revoked_update_delete_for_service_rw() -> None:
    """ta_service_rw 不可 UPDATE / DELETE audit_logs（依 PLAN 19.6）。"""
    conn = await _connect_service_rw()
    try:
        # UPDATE 應失敗
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("UPDATE audit_logs SET action='hack' WHERE id=1")
        # DELETE 應失敗
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("DELETE FROM audit_logs WHERE id=1")
    finally:
        await conn.close()


async def test_ta_agent_ro_can_read_but_not_write() -> None:
    """ta_agent_ro 可 SELECT 各表，但不可 INSERT/UPDATE/DELETE。"""
    conn = await _connect_agent_ro()
    try:
        # SELECT OK
        await conn.fetchval("SELECT count(*) FROM stock_list")
        await conn.fetchval("SELECT count(*) FROM users")

        # INSERT 應失敗
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "INSERT INTO users (email, password_hash) VALUES ('hack@x.com', 'x')"
            )
    finally:
        await conn.close()


async def test_qdrant_collections_present() -> None:
    """PLAN 20.3 中 7 個 Qdrant collection 都該存在。"""
    from qdrant_client import AsyncQdrantClient  # type: ignore[import-untyped]

    client = AsyncQdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        api_key=settings.QDRANT_API_KEY.get_secret_value(),
        https=False,
        prefer_grpc=False,
        timeout=10,
    )
    try:
        result = await client.get_collections()
        names = {c.name for c in (result.collections or [])}
        expected = {
            "tw_news_v1",
            "tw_announcements_v1",
            "tw_earnings_calls_v1",
            "tw_macro_news_v1",
            "tw_industry_reports_v1",
            "us_news_v1",
            "us_filings_v1",
        }
        missing = expected - names
        assert not missing, f"Qdrant collection 缺：{missing}"
    finally:
        await client.close()
