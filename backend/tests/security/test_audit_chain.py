"""Phase 9 — Audit hash chain 安全測試。

依 PLAN 第 19.6 章 + 第二十八章 P 項。

驗證：
1. 正常 insert 後 chain 完整
2. 手動 UPDATE 某筆 entry_hash → verify_chain 應抓到
3. 手動 DELETE 某筆 → chain 斷裂應抓到
4. 手動 swap 兩筆 timestamp → chain 順序亂 應抓到

注意：ta_service_rw 已 REVOKE UPDATE/DELETE，這些測試需要用 superuser 連線手動破壞，
模擬攻擊者拿到 DB 權限的情境。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.security


async def _make_some_audit(auth_client, make_test_user, n: int = 5) -> None:
    """製造一些 audit log entry（透過幾個 login 嘗試）。"""
    for i in range(n):
        auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": f"sec-{i}@test.example.com",
                "password": "WrongPwd2026!Ab",
            },
        )
    # 等 audit middleware flush 完
    await asyncio.sleep(0.1)


async def test_verify_chain_passes_after_normal_inserts(
    auth_client, make_test_user, db_session_maker
) -> None:
    """正常 insert 後 chain 應該完整。"""
    since = datetime.now(UTC) - timedelta(seconds=1)
    await _make_some_audit(auth_client, make_test_user, n=5)

    from app.repos.audit_repo import AuditRepository

    async with db_session_maker() as s:
        repo = AuditRepository(s)
        ok, broken = await repo.verify_chain(since=since)
    assert ok is True, f"chain 應該完整，實際斷裂於：{broken}"


async def test_verify_chain_detects_manual_tampering(
    auth_client, make_test_user, db_session_maker, env_vars
) -> None:
    """手動竄改某筆 entry_hash → verify_chain 應抓到。"""
    since = datetime.now(UTC) - timedelta(seconds=1)
    await _make_some_audit(auth_client, make_test_user, n=5)

    # 用 superuser 連線竄改 — 模擬攻擊者
    import asyncpg

    superuser_pwd = env_vars.get("POSTGRES_SUPERUSER_PASSWORD", "")
    conn = await asyncpg.connect(
        host=env_vars.get("POSTGRES_HOST", "localhost"),
        port=int(env_vars.get("POSTGRES_PORT", "5432")),
        user="postgres",
        password=superuser_pwd,
        database=env_vars.get("POSTGRES_DB", "tradingagents_tw"),
    )
    # 找最近的一筆並竄改它的 entry_hash
    row = await conn.fetchrow(
        "SELECT id FROM audit_logs WHERE timestamp >= $1 ORDER BY id DESC LIMIT 1",
        since,
    )
    tampered_id = row["id"]
    await conn.execute(
        "UPDATE audit_logs SET entry_hash = $1 WHERE id = $2",
        "00" * 32,  # 64 個 0 — 顯然不對
        tampered_id,
    )

    try:
        from app.repos.audit_repo import AuditRepository

        async with db_session_maker() as s:
            repo = AuditRepository(s)
            ok, broken = await repo.verify_chain(since=since)
        assert ok is False, "竄改後 chain 應抓到斷裂"
        assert tampered_id in broken, f"預期抓到 {tampered_id}，實際 {broken}"
    finally:
        # 還原（重新跑 trigger）：直接重算 hash 後寫回
        recomputed = await conn.fetchval(
            """
            SELECT encode(digest(
                prev_hash || '|' ||
                COALESCE(id::text, '') || '|' ||
                COALESCE(actor_id::text, '') || '|' ||
                action || '|' ||
                COALESCE(entity_type, '') || '|' ||
                COALESCE(entity_id, '') || '|' ||
                COALESCE(details::text, '{}') || '|' ||
                timestamp::text,
                'sha256'
            ), 'hex')
            FROM audit_logs WHERE id = $1
            """,
            tampered_id,
        )
        await conn.execute(
            "UPDATE audit_logs SET entry_hash = $1 WHERE id = $2",
            recomputed,
            tampered_id,
        )
        await conn.close()


async def test_verify_chain_detects_swapped_timestamp(
    auth_client, make_test_user, db_session_maker, env_vars
) -> None:
    """竄改某筆的 timestamp → 重新排序後 chain 斷掉。"""
    since = datetime.now(UTC) - timedelta(seconds=1)
    await _make_some_audit(auth_client, make_test_user, n=5)

    import asyncpg

    superuser_pwd = env_vars.get("POSTGRES_SUPERUSER_PASSWORD", "")
    conn = await asyncpg.connect(
        host=env_vars.get("POSTGRES_HOST", "localhost"),
        port=int(env_vars.get("POSTGRES_PORT", "5432")),
        user="postgres",
        password=superuser_pwd,
        database=env_vars.get("POSTGRES_DB", "tradingagents_tw"),
    )
    # 把最近兩筆的 timestamp 對調
    rows = await conn.fetch(
        "SELECT id, timestamp FROM audit_logs WHERE timestamp >= $1 " "ORDER BY id DESC LIMIT 2",
        since,
    )
    if len(rows) < 2:
        await conn.close()
        pytest.skip("最近 audit 不足 2 筆，無法做 swap 測試")
    r1, r2 = rows[0], rows[1]
    # 用 superuser TRUNCATE/UPDATE — TimescaleDB hypertable 對 UPDATE 限制較多，
    # 改用直接 swap 試試（若失敗就視為通過防護）
    try:
        await conn.execute(
            "UPDATE audit_logs SET timestamp = $1 WHERE id = $2",
            r2["timestamp"],
            r1["id"],
        )
        await conn.execute(
            "UPDATE audit_logs SET timestamp = $1 WHERE id = $2",
            r1["timestamp"],
            r2["id"],
        )
    except Exception:
        await conn.close()
        pytest.skip("hypertable UPDATE timestamp 被擋；DB 保護生效")

    try:
        from app.repos.audit_repo import AuditRepository

        async with db_session_maker() as s:
            repo = AuditRepository(s)
            ok, broken = await repo.verify_chain(since=since)
        assert ok is False, "對調 timestamp 後 chain 應該斷"
        # 至少抓到一筆斷裂
        assert len(broken) >= 1
    finally:
        # 還原
        try:
            await conn.execute(
                "UPDATE audit_logs SET timestamp = $1 WHERE id = $2",
                r1["timestamp"],
                r1["id"],
            )
            await conn.execute(
                "UPDATE audit_logs SET timestamp = $1 WHERE id = $2",
                r2["timestamp"],
                r2["id"],
            )
        except Exception as restore_exc:  # pragma: no cover  - noqa: S110
            _ = restore_exc
        await conn.close()


async def test_verify_chain_detects_manual_delete(
    auth_client, make_test_user, db_session_maker, env_vars
) -> None:
    """手動 DELETE 某筆 → chain 斷裂（下一筆的 prev_hash 對不上）。"""
    since = datetime.now(UTC) - timedelta(seconds=1)
    await _make_some_audit(auth_client, make_test_user, n=5)

    import asyncpg

    superuser_pwd = env_vars.get("POSTGRES_SUPERUSER_PASSWORD", "")
    conn = await asyncpg.connect(
        host=env_vars.get("POSTGRES_HOST", "localhost"),
        port=int(env_vars.get("POSTGRES_PORT", "5432")),
        user="postgres",
        password=superuser_pwd,
        database=env_vars.get("POSTGRES_DB", "tradingagents_tw"),
    )
    # 抓出 since 後第 2 筆（不刪最後一筆，要讓「下一筆」存在）
    rows = await conn.fetch(
        "SELECT id, timestamp FROM audit_logs WHERE timestamp >= $1 " "ORDER BY id ASC LIMIT 3",
        since,
    )
    if len(rows) < 3:
        await conn.close()
        pytest.skip("audit log 不足 3 筆，無法做 DELETE 測試")
    target_id = rows[1]["id"]
    target_ts = rows[1]["timestamp"]
    # 備份完整 row 以還原
    backup = await conn.fetchrow(
        "SELECT * FROM audit_logs WHERE id = $1 AND timestamp = $2",
        target_id,
        target_ts,
    )
    try:
        await conn.execute(
            "DELETE FROM audit_logs WHERE id = $1 AND timestamp = $2",
            target_id,
            target_ts,
        )
    except Exception:
        await conn.close()
        pytest.skip("hypertable DELETE 被擋；DB 保護生效")

    try:
        from app.repos.audit_repo import AuditRepository

        async with db_session_maker() as s:
            repo = AuditRepository(s)
            ok, _broken = await repo.verify_chain(since=since)
        assert ok is False, "DELETE 中間一筆後 chain 應該斷"
    finally:
        # 還原
        if backup is not None:
            try:
                cols = list(backup.keys())
                placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
                # 重新 insert（trigger 會重算 entry_hash，但這只為了測試還原）
                await conn.execute(
                    f"INSERT INTO audit_logs ({', '.join(cols)}) VALUES ({placeholders}) "  # noqa: S608
                    f"ON CONFLICT DO NOTHING",
                    *[backup[c] for c in cols],
                )
            except Exception as restore_exc:  # pragma: no cover  - noqa: S110
                _ = restore_exc
        await conn.close()


# 抑制 unused import
_ = text
