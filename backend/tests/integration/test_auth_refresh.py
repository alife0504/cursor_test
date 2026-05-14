"""Phase 8 — /api/v1/auth/refresh 整合測試。

依 PLAN 第二十七章 P 項：5 個必要測試。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _login(auth_client, email: str, password: str):
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return r


# ────────────────────────────────────────────────────────
# 1. valid refresh → rotation
# ────────────────────────────────────────────────────────


async def test_refresh_with_valid_token_rotates(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    login_r = await _login(auth_client, user.email, password)
    refresh_cookie = login_r.cookies.get("refresh_token")
    csrf_cookie = login_r.cookies.get("csrf_token")
    assert refresh_cookie and csrf_cookie

    r = auth_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_cookie, "csrf_token": csrf_cookie},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["access_token"]
    assert data["token_type"] == "Bearer"
    # 新 refresh_token cookie 應該換掉舊的
    new_refresh = r.cookies.get("refresh_token")
    assert new_refresh and new_refresh != refresh_cookie


# ────────────────────────────────────────────────────────
# 2. refresh 後舊 jti 應該被 blacklist
# ────────────────────────────────────────────────────────


async def test_refresh_blacklists_old_jti(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    login_r = await _login(auth_client, user.email, password)
    refresh_cookie = login_r.cookies.get("refresh_token")
    csrf_cookie = login_r.cookies.get("csrf_token")

    # 第一次 refresh 成功
    r1 = auth_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_cookie, "csrf_token": csrf_cookie},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert r1.status_code == 200

    # 用「舊」refresh token 再 refresh 一次 → 應該失敗（jti 已被 blacklist）
    r2 = auth_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_cookie, "csrf_token": csrf_cookie},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert r2.status_code == 401, r2.text


# ────────────────────────────────────────────────────────
# 3. 沒 CSRF header → 403
# ────────────────────────────────────────────────────────


async def test_refresh_without_csrf_rejected(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    login_r = await _login(auth_client, user.email, password)
    refresh_cookie = login_r.cookies.get("refresh_token")
    csrf_cookie = login_r.cookies.get("csrf_token")

    r = auth_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_cookie, "csrf_token": csrf_cookie},
        # 故意不帶 X-CSRF-Token
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "FORBIDDEN"


# ────────────────────────────────────────────────────────
# 4. CSRF header 與 cookie 不符 → 403
# ────────────────────────────────────────────────────────


async def test_refresh_csrf_mismatch_rejected(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    login_r = await _login(auth_client, user.email, password)
    refresh_cookie = login_r.cookies.get("refresh_token")
    csrf_cookie = login_r.cookies.get("csrf_token")

    r = auth_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_cookie, "csrf_token": csrf_cookie},
        headers={"X-CSRF-Token": "TAMPERED-csrf-token-value"},
    )
    assert r.status_code == 403, r.text


# ────────────────────────────────────────────────────────
# 5. logout 之後 refresh 應失敗
# ────────────────────────────────────────────────────────


async def test_refresh_after_logout_rejected(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    login_r = await _login(auth_client, user.email, password)
    refresh_cookie = login_r.cookies.get("refresh_token")
    csrf_cookie = login_r.cookies.get("csrf_token")

    # logout
    auth_client.post(
        "/api/v1/auth/logout",
        cookies={"refresh_token": refresh_cookie},
    )

    # 用舊 cookie 再 refresh → 應失敗
    r = auth_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_cookie, "csrf_token": csrf_cookie},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert r.status_code == 401, r.text


# ────────────────────────────────────────────────────────
# 6. 缺 refresh cookie → 401
# ────────────────────────────────────────────────────────


async def test_refresh_without_cookie_returns_401(auth_client) -> None:
    r = auth_client.post(
        "/api/v1/auth/refresh",
        cookies={"csrf_token": "abc"},
        headers={"X-CSRF-Token": "abc"},
    )
    # CSRF check 先過（值相符）但 refresh token 缺失 → 401
    assert r.status_code == 401, r.text
