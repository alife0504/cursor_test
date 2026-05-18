"""Phase 11 — /api/v1/admin/* 整合測試。

涵蓋：
1. 非 admin → 403
2. GET /admin/audit
3. GET /admin/system/info
4. GET /admin/pipeline/dlq + POST resolve
5. POST /admin/pipeline/dlq/{id}/requeue
6. GET /admin/users/{id}/sessions
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _csrf(access: str, csrf: str) -> dict:
    return {"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf}


async def test_admin_routes_forbid_viewer(auth_client, make_test_user, login_helper) -> None:
    viewer, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, _ = await login_helper(auth_client, viewer.email, pwd)
    r = auth_client.get(
        "/api/v1/admin/audit?limit=5",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 403, r.text


async def test_admin_audit_list(auth_client, make_test_user, login_helper) -> None:
    admin, pwd = await make_test_user(role="ADMIN", must_change=False)
    access, _ = await login_helper(auth_client, admin.email, pwd)
    r = auth_client.get(
        "/api/v1/admin/audit?limit=5",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    assert isinstance(body["data"], list)


async def test_admin_system_info(auth_client, make_test_user, login_helper) -> None:
    admin, pwd = await make_test_user(role="ADMIN", must_change=False)
    access, _ = await login_helper(auth_client, admin.email, pwd)
    r = auth_client.get(
        "/api/v1/admin/system/info",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    assert "version" in r.json()["data"]


async def test_admin_dlq_list_and_resolve(
    auth_client, make_test_user, login_helper, seed_dlq
) -> None:
    admin, pwd = await make_test_user(role="ADMIN", must_change=False)
    access, csrf = await login_helper(auth_client, admin.email, pwd)

    dlq_id = await seed_dlq(task_name="data_pipeline.sync_ohlcv_one")

    r1 = auth_client.get(
        "/api/v1/admin/pipeline/dlq?resolved=false&limit=10",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r1.status_code == 200, r1.text
    ids = [row["id"] for row in r1.json()["data"]]
    assert dlq_id in ids

    r2 = auth_client.post(
        f"/api/v1/admin/pipeline/dlq/{dlq_id}/resolve",
        json={"notes": "已修復 root cause"},
        headers=_csrf(access, csrf),
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["resolved"] is True


async def test_admin_dlq_requeue(auth_client, make_test_user, login_helper, seed_dlq) -> None:
    admin, pwd = await make_test_user(role="ADMIN", must_change=False)
    access, csrf = await login_helper(auth_client, admin.email, pwd)

    dlq_id = await seed_dlq(task_name="data_pipeline.news_ingest")
    r = auth_client.post(
        f"/api/v1/admin/pipeline/dlq/{dlq_id}/requeue",
        json={},
        headers=_csrf(access, csrf),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["resolved"] is True


async def test_admin_list_user_sessions(auth_client, make_test_user, login_helper) -> None:
    """登入後產生 session，admin 應該看得到。"""
    admin, apwd = await make_test_user(role="ADMIN", must_change=False)
    target, tpwd = await make_test_user(role="VIEWER", must_change=False)
    # target 先登入產生 session
    await login_helper(auth_client, target.email, tpwd)

    a_access, _ = await login_helper(auth_client, admin.email, apwd)
    r = auth_client.get(
        f"/api/v1/admin/users/{target.id}/sessions",
        headers={"Authorization": f"Bearer {a_access}"},
    )
    assert r.status_code == 200, r.text
    sessions = r.json()["data"]
    assert isinstance(sessions, list)
