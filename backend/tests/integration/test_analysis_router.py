"""Phase 11 — /api/v1/analysis/* 整合測試。

涵蓋：
1. 未登入 → 401
2. POST 建立 → 201 + envelope
3. GET 列表（cursor 分頁）
4. GET /{id}：自己 ok / 他人 → 403
5. POST /{id}/cancel
6. DELETE /{id} viewer → 403；admin ok
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


def _csrf(access: str, csrf: str) -> dict:
    return {"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf}


async def test_analysis_requires_auth(auth_client) -> None:
    r = auth_client.get("/api/v1/analysis")
    assert r.status_code == 401


async def test_analysis_create_and_get(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    user, pwd = await make_test_user(role="ANALYST", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)
    headers = _csrf(access, csrf) | {"Idempotency-Key": str(uuid.uuid4())}

    r = auth_client.post(
        "/api/v1/analysis",
        json={
            "symbol": "2330",
            "analyst_types": ["market"],
            "llm_model": "gemini-2.0-flash",
            "debate_rounds": 0,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "data" in body and "meta" in body
    analysis_id = body["data"]["analysis_id"]

    r2 = auth_client.get(
        f"/api/v1/analysis/{analysis_id}",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["symbol"] == "2330"


async def test_analysis_list_returns_envelope(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    await seed_analysis(user_id=user.id, symbol="2330", status="completed")

    r = auth_client.get(
        "/api/v1/analysis?limit=10",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    assert "pagination" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1


async def test_analysis_get_others_forbidden(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    """B 嘗試讀 A 的 analysis → 403。"""
    user_a, _ = await make_test_user(role="VIEWER", must_change=False)
    user_b, pwd_b = await make_test_user(role="VIEWER", must_change=False)
    a_id = await seed_analysis(user_id=user_a.id, symbol="2330")
    access_b, _ = await login_helper(auth_client, user_b.email, pwd_b)

    r = auth_client.get(
        f"/api/v1/analysis/{a_id}",
        headers={"Authorization": f"Bearer {access_b}"},
    )
    assert r.status_code == 403, r.text


async def test_analysis_cancel(auth_client, make_test_user, login_helper, seed_analysis) -> None:
    user, pwd = await make_test_user(role="ANALYST", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)
    a_id = await seed_analysis(user_id=user.id, symbol="2330", status="queued")

    r = auth_client.post(
        f"/api/v1/analysis/{a_id}/cancel",
        headers=_csrf(access, csrf),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"


async def test_analysis_delete_admin_only(
    auth_client, make_test_user, login_helper, seed_analysis
) -> None:
    owner, _ = await make_test_user(role="VIEWER", must_change=False)
    viewer, vpwd = await make_test_user(role="VIEWER", must_change=False)
    admin, apwd = await make_test_user(role="ADMIN", must_change=False)
    a_id = await seed_analysis(user_id=owner.id, symbol="2330")

    # viewer 自己看別人的 → 403
    v_access, v_csrf = await login_helper(auth_client, viewer.email, vpwd)
    rv = auth_client.delete(
        f"/api/v1/analysis/{a_id}",
        headers=_csrf(v_access, v_csrf),
    )
    assert rv.status_code == 403, rv.text

    # admin → 200
    a_access, a_csrf = await login_helper(auth_client, admin.email, apwd)
    ra = auth_client.delete(
        f"/api/v1/analysis/{a_id}",
        headers=_csrf(a_access, a_csrf),
    )
    assert ra.status_code == 200, ra.text
    assert ra.json()["data"]["deleted"] is True
