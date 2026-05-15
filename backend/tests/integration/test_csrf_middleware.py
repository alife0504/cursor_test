"""Phase 9 — CSRFMiddleware 整合測試。

依 PLAN 第 19.1 章 + 第二十八章 N 項。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


# ────────────────────────────────────────────────────────
# 1. GET 不需要 CSRF
# ────────────────────────────────────────────────────────


async def test_get_no_csrf_required(auth_client) -> None:
    r = auth_client.get("/health/live")
    assert r.status_code == 200


async def test_get_protected_no_csrf_required(auth_client, make_test_user) -> None:
    """GET /me 不需要 CSRF（只 POST/PUT/DELETE 才需要）。"""
    user, password = await make_test_user(must_change=False)
    login_r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_r.json()["data"]["access_token"]

    r = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        # 不帶 X-CSRF-Token
    )
    assert r.status_code == 200


# ────────────────────────────────────────────────────────
# 2. POST 沒 CSRF token 被擋（非豁免路徑）
# ────────────────────────────────────────────────────────


async def test_post_without_csrf_blocked(auth_client, make_test_user) -> None:
    """登入後對 change-password 發 POST 但不帶 X-CSRF-Token → 403。"""
    user, password = await make_test_user(must_change=False)
    login_r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_r.json()["data"]["access_token"]

    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": "AnotherStrong2026!"},
        headers={"Authorization": f"Bearer {token}"},
        # 故意不帶 X-CSRF-Token；也清掉 cookie
        cookies={},
    )
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["error"]["code"] == "FORBIDDEN"


# ────────────────────────────────────────────────────────
# 3. CSRF mismatch → 403
# ────────────────────────────────────────────────────────


async def test_post_csrf_mismatch_blocked(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    login_r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_r.json()["data"]["access_token"]
    csrf_cookie = login_r.cookies.get("csrf_token")

    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": "AnotherStrong2026!"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": "WRONG-CSRF-VALUE",
        },
        cookies={"csrf_token": csrf_cookie},
    )
    assert r.status_code == 403, r.text


# ────────────────────────────────────────────────────────
# 4. CSRF match → 通過
# ────────────────────────────────────────────────────────


async def test_post_csrf_match_allowed(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    login_r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_r.json()["data"]["access_token"]
    csrf_cookie = login_r.cookies.get("csrf_token")

    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": "AnotherStrong2026!"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": csrf_cookie,
        },
        cookies={"csrf_token": csrf_cookie},
    )
    assert r.status_code == 200, r.text


# ────────────────────────────────────────────────────────
# 5. /auth/login 豁免（沒 cookie 還是能 login）
# ────────────────────────────────────────────────────────


async def test_login_endpoint_csrf_exempt(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
        # 完全不帶 CSRF；login 該成功
    )
    assert r.status_code == 200, r.text


async def test_password_reset_csrf_exempt(auth_client, make_test_user) -> None:
    user, _ = await make_test_user(must_change=False)
    r = auth_client.post(
        "/api/v1/auth/password-reset",
        json={"email": user.email},
        # 不帶 CSRF
    )
    assert r.status_code in (200, 429), r.text
