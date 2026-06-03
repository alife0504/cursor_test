"""Phase 9 — AuditMiddleware 整合測試。

依 PLAN 第 19.6 章 + 第二十八章 M 項。
"""

from __future__ import annotations

from datetime import UTC

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


# ────────────────────────────────────────────────────────
# 1. /me 請求 → audit_logs 寫一筆
# ────────────────────────────────────────────────────────


async def test_request_writes_audit_log(auth_client, make_test_user, db_session_maker) -> None:
    user, password = await make_test_user(must_change=False)
    # login 取 token
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = r.json()["data"]["access_token"]

    # 取 /me — 該路徑應被 audit
    me_r = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_r.status_code == 200
    trace_id = me_r.json()["meta"]["trace_id"]

    async with db_session_maker() as s:
        count = (
            await s.execute(
                text(
                    "SELECT count(*) FROM audit_logs "
                    "WHERE action='http.get' AND entity_id='/api/v1/auth/me' "
                    "AND request_id=:tid"
                ),
                {"tid": trace_id},
            )
        ).scalar()
    assert count and count >= 1


# ────────────────────────────────────────────────────────
# 2. /health/live 不該被 audit
# ────────────────────────────────────────────────────────


async def test_health_excluded_from_audit(auth_client, db_session_maker) -> None:
    r = auth_client.get("/health/live")
    assert r.status_code == 200
    trace_id = r.json()["meta"]["trace_id"]

    async with db_session_maker() as s:
        count = (
            await s.execute(
                text("SELECT count(*) FROM audit_logs WHERE request_id=:tid"),
                {"tid": trace_id},
            )
        ).scalar()
    assert count == 0, f"/health/live 不該寫 audit，實際 {count} 筆"


# ────────────────────────────────────────────────────────
# 3. audit log 含 trace_id
# ────────────────────────────────────────────────────────


async def test_audit_includes_trace_id(auth_client, make_test_user, db_session_maker) -> None:
    user, _ = await make_test_user()
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "WrongPwd1!Abcd"},
    )
    trace_id = r.json()["error"]["trace_id"]

    # http.post audit
    async with db_session_maker() as s:
        row = (
            await s.execute(
                text(
                    "SELECT request_id, action, entity_id FROM audit_logs "
                    "WHERE request_id=:tid AND action='http.post'"
                ),
                {"tid": trace_id},
            )
        ).first()
    assert row is not None
    assert row.request_id == trace_id
    assert row.entity_id == "/api/v1/auth/login"


# ────────────────────────────────────────────────────────
# 4. authenticated request actor_id 應該填上
# ────────────────────────────────────────────────────────


async def test_audit_includes_user_when_authenticated(
    auth_client, make_test_user, db_session_maker
) -> None:
    user, password = await make_test_user(must_change=False)
    login_r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_r.json()["data"]["access_token"]
    me_r = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    trace_id = me_r.json()["meta"]["trace_id"]

    async with db_session_maker() as s:
        row = (
            await s.execute(
                text("SELECT actor_id FROM audit_logs WHERE request_id=:tid AND action='http.get'"),
                {"tid": trace_id},
            )
        ).first()
    assert row is not None
    assert row.actor_id == user.id


# ────────────────────────────────────────────────────────
# 5. 100 個 request 後 chain 仍完整
# ────────────────────────────────────────────────────────


async def test_audit_chain_unbroken_after_many_requests(auth_client, db_session_maker) -> None:
    """連 30 個 audit-able 請求後 chain 仍完整。"""
    from datetime import datetime, timedelta

    since = datetime.now(UTC) - timedelta(seconds=5)

    # 觸發一些 audit
    for _ in range(30):
        r = auth_client.post(
            "/api/v1/auth/login",
            json={"email": "noexist@test.example.com", "password": "Abc12345678!"},
        )
        # 預期都 401（user 不存在），但仍寫 audit
        assert r.status_code in (401, 429)

    from app.repos.audit_repo import AuditRepository

    async with db_session_maker() as s:
        repo = AuditRepository(s)
        ok, broken = await repo.verify_chain(since=since)
    assert ok is True, f"chain 斷裂於 ids: {broken}"
