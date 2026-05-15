"""Phase 10 — /api/v1/users/* 整合測試（admin RBAC + self update）。"""

from __future__ import annotations

import uuid as _uuid

import pytest

pytestmark = pytest.mark.integration


def _csrf_headers(access: str, csrf: str) -> dict:
    return {"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf}


# ────────────────────────────────────────────────────────
# 1. ADMIN 列表 200
# ────────────────────────────────────────────────────────


async def test_users_admin_can_list(auth_client, make_test_user, login_helper) -> None:
    admin, pwd = await make_test_user(role="ADMIN", must_change=False)
    access, _ = await login_helper(auth_client, admin.email, pwd)
    r = auth_client.get(
        "/api/v1/users?limit=10",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body and isinstance(body["data"], list)


# ────────────────────────────────────────────────────────
# 2. VIEWER 列表 → 403
# ────────────────────────────────────────────────────────


async def test_users_viewer_list_403(auth_client, make_test_user, login_helper) -> None:
    viewer, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, _ = await login_helper(auth_client, viewer.email, pwd)
    r = auth_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 403, r.text


# ────────────────────────────────────────────────────────
# 3. ADMIN 建立使用者
# ────────────────────────────────────────────────────────


async def test_users_admin_can_create(auth_client, make_test_user, login_helper) -> None:
    admin, pwd = await make_test_user(role="ADMIN", must_change=False)
    access, csrf = await login_helper(auth_client, admin.email, pwd)
    fake_email = f"p10-{_uuid.uuid4().hex[:8]}@test.example.com"
    r = auth_client.post(
        "/api/v1/users",
        json={
            "email": fake_email,
            "password": "TestPwd2026!Ab",
            "role": "ANALYST",
            "full_name": "新分析師",
        },
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["email"].lower() == fake_email.lower()
    assert data["role"] == "ANALYST"
    # 不能洩漏 password_hash
    assert "password_hash" not in data
    # cleanup: 軟刪掉這個 user（避免亂留）
    new_id = data["id"]
    auth_client.delete(
        f"/api/v1/users/{new_id}",
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )


# ────────────────────────────────────────────────────────
# 4. VIEWER POST → 403
# ────────────────────────────────────────────────────────


async def test_users_viewer_cannot_create(auth_client, make_test_user, login_helper) -> None:
    viewer, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, csrf = await login_helper(auth_client, viewer.email, pwd)
    r = auth_client.post(
        "/api/v1/users",
        json={
            "email": f"viewer-{_uuid.uuid4().hex[:6]}@test.example.com",
            "password": "TestPwd2026!Ab",
            "role": "VIEWER",
        },
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r.status_code == 403, r.text


# ────────────────────────────────────────────────────────
# 5. self 取自己 200；他人 → 403
# ────────────────────────────────────────────────────────


async def test_users_self_can_get_others_forbidden(
    auth_client, make_test_user, login_helper
) -> None:
    user_a, pwd_a = await make_test_user(role="VIEWER", must_change=False)
    user_b, _pwd_b = await make_test_user(role="VIEWER", must_change=False)
    access_a, _ = await login_helper(auth_client, user_a.email, pwd_a)

    # 取自己 OK
    r1 = auth_client.get(
        f"/api/v1/users/{user_a.id}",
        headers={"Authorization": f"Bearer {access_a}"},
    )
    assert r1.status_code == 200, r1.text

    # 取他人 → 403
    r2 = auth_client.get(
        f"/api/v1/users/{user_b.id}",
        headers={"Authorization": f"Bearer {access_a}"},
    )
    assert r2.status_code == 403, r2.text


# ────────────────────────────────────────────────────────
# 6. self PATCH 不能改 role
# ────────────────────────────────────────────────────────


async def test_users_self_cannot_patch_role(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)
    r = auth_client.patch(
        f"/api/v1/users/{user.id}",
        json={"role": "ADMIN"},
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r.status_code == 403, r.text


# ────────────────────────────────────────────────────────
# 7. ADMIN 軟刪除使用者
# ────────────────────────────────────────────────────────


async def test_users_admin_can_soft_delete(auth_client, make_test_user, login_helper) -> None:
    admin, pwd = await make_test_user(role="ADMIN", must_change=False)
    target, _ = await make_test_user(role="VIEWER", must_change=False)
    access, csrf = await login_helper(auth_client, admin.email, pwd)

    r = auth_client.delete(
        f"/api/v1/users/{target.id}",
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r.status_code == 200, r.text

    # 再列表（不含 deleted）應該看不到
    r2 = auth_client.get(
        "/api/v1/users?limit=100",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r2.status_code == 200, r2.text
    ids = {row["id"] for row in r2.json()["data"]}
    assert str(target.id) not in ids
