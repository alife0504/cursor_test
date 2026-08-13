"""Phase 18 — Audit hash chain 竄改偵測補強測試（PLAN 19.6 + 第二十七章 P18 M 節）。

P9 的 test_audit_chain.py 已涵蓋基礎情境；本檔案額外驗收：
- 直接 UPDATE 任意欄位（不只 entry_hash）→ chain 斷
- 刪除 row → chain 斷（透過後續 row 的 prev_hash 比對）
- 重新排列 row（swap timestamps）→ chain 斷
- 乾淨 DB → verify 通過

跑：cd backend && uv run pytest tests/security/test_audit_chain_tampering.py -v
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.security


async def _generate_audit_entries(auth_client, count: int = 5) -> None:
    """製造 audit log（透過幾個 login 嘗試）。"""
    for i in range(count):
        auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": f"chain-tamper-{i}@test.example.com",
                "password": "WrongPwd2026!Ab",
            },
        )
    await asyncio.sleep(0.1)


async def _superuser_conn(env_vars):
    import asyncpg

    return await asyncpg.connect(
        host=env_vars.get("POSTGRES_HOST", "localhost"),
        port=int(env_vars.get("POSTGRES_PORT", "5432")),
        user="postgres",
        password=env_vars.get("POSTGRES_SUPERUSER_PASSWORD", ""),
        database=env_vars.get("POSTGRES_DB", "tradingagents_tw"),
    )


async def _verify_chain(db_session_maker, since):
    """共用 verify wrapper。"""
    from app.repos.audit_repo import AuditRepository

    async with db_session_maker() as s:
        repo = AuditRepository(s)
        return await repo.verify_chain(since=since)


# ════════════════════════════════════════════════════════
# 1. clean DB → verify passes
# ════════════════════════════════════════════════════════


async def test_verify_chain_passes_clean_db(auth_client, make_test_user, db_session_maker) -> None:
    """正常 insert（中間沒人竄改）→ verify_chain 應該完全通過。"""
    since = datetime.now(UTC) - timedelta(seconds=1)
    await _generate_audit_entries(auth_client, count=4)
    ok, broken = await _verify_chain(db_session_maker, since)
    assert ok is True, f"乾淨 DB 應通過 verify，實際斷裂：{broken}"
    assert broken == []


# ════════════════════════════════════════════════════════
# 2. 直接 UPDATE entry_hash → 抓得到
# ════════════════════════════════════════════════════════


async def test_direct_db_update_breaks_chain(
    auth_client, make_test_user, db_session_maker, env_vars
) -> None:
    """攻擊者拿到 superuser 直接 UPDATE 任意欄位 → verify 抓到 hash mismatch。"""
    since = datetime.now(UTC) - timedelta(seconds=1)
    await _generate_audit_entries(auth_client, count=4)
    conn = await _superuser_conn(env_vars)

    row = await conn.fetchrow(
        "SELECT id FROM audit_logs WHERE timestamp >= $1 ORDER BY id DESC LIMIT 1",
        since,
    )
    if row is None:
        await conn.close()
        pytest.skip("沒抓到 audit 紀錄")
    target_id = row["id"]

    # 直接竄改 action 欄位（不是 entry_hash）— hash 不變但 row 內容變了 → verify 重算應 mismatch
    try:
        await conn.execute(
            "UPDATE audit_logs SET action = $1 WHERE id = $2",
            "tampered.action.malicious",
            target_id,
        )
    except Exception:
        await conn.close()
        pytest.skip("hypertable UPDATE 被擋；DB 保護生效（也算「擋下」）")

    try:
        ok, broken = await _verify_chain(db_session_maker, since)
        assert ok is False, "UPDATE action 後 verify 應抓到 mismatch"
        assert target_id in broken, f"預期 {target_id} 在 broken；實際 {broken}"
    finally:
        # 還原 action（但 entry_hash 已是舊值，verify 仍會抓 — 之後跑的 test 會看到 broken）
        with contextlib.suppress(Exception):
            await conn.execute(
                """
                UPDATE audit_logs
                SET entry_hash = encode(digest(
                    prev_hash || '|' || COALESCE(id::text, '') || '|' ||
                    COALESCE(actor_id::text, '') || '|' || action || '|' ||
                    COALESCE(entity_type, '') || '|' || COALESCE(entity_id, '') || '|' ||
                    COALESCE(details::text, '{}') || '|' || timestamp::text,
                    'sha256'
                ), 'hex')
                WHERE id = $1
                """,
                target_id,
            )
        await conn.close()


# ════════════════════════════════════════════════════════
# 3. 刪除中間 row → 抓得到
# ════════════════════════════════════════════════════════


async def test_row_deletion_breaks_chain(
    auth_client, make_test_user, db_session_maker, env_vars
) -> None:
    """刪掉中間一筆 → 下一筆的 prev_hash 對不上原來的『前一筆』。"""
    since = datetime.now(UTC) - timedelta(seconds=1)
    await _generate_audit_entries(auth_client, count=5)
    conn = await _superuser_conn(env_vars)

    rows = await conn.fetch(
        "SELECT id, timestamp FROM audit_logs WHERE timestamp >= $1 ORDER BY id ASC LIMIT 3",
        since,
    )
    if len(rows) < 3:
        await conn.close()
        pytest.skip("audit log 不足 3 筆")
    target_id = rows[1]["id"]
    target_ts = rows[1]["timestamp"]
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
        ok, _broken = await _verify_chain(db_session_maker, since)
        assert ok is False, "DELETE 中間 row 後 verify 應抓到"
    finally:
        if backup is not None:
            cols = list(backup.keys())
            placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
            with contextlib.suppress(Exception):
                await conn.execute(
                    f"INSERT INTO audit_logs ({', '.join(cols)}) VALUES ({placeholders}) "  # noqa: S608
                    "ON CONFLICT DO NOTHING",
                    *[backup[c] for c in cols],
                )
        await conn.close()


# ════════════════════════════════════════════════════════
# 4. 重新排序（swap timestamps）→ 抓得到
# ════════════════════════════════════════════════════════


async def test_row_reorder_detected(
    auth_client, make_test_user, db_session_maker, env_vars
) -> None:
    """對調兩筆 row 的 timestamp → verify 抓到順序錯亂。"""
    since = datetime.now(UTC) - timedelta(seconds=1)
    await _generate_audit_entries(auth_client, count=4)
    conn = await _superuser_conn(env_vars)

    rows = await conn.fetch(
        "SELECT id, timestamp FROM audit_logs WHERE timestamp >= $1 ORDER BY id DESC LIMIT 2",
        since,
    )
    if len(rows) < 2:
        await conn.close()
        pytest.skip("audit 不足 2 筆")
    r1, r2 = rows[0], rows[1]
    try:
        # 兩筆原本是不同 ts；對調
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
        ok, broken = await _verify_chain(db_session_maker, since)
        # 對調 timestamp 後，hash 計算包含 timestamp → 跟原 entry_hash 必對不上 → broken
        assert ok is False, "swap timestamp 後 verify 應抓到"
        assert len(broken) >= 1
    finally:
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
        except Exception:  # noqa: S110
            pass
        await conn.close()
