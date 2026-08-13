"""Phase 8 — /api/v1/auth/change-password 整合測試（P9 之後加 CSRF + rate limit 處理）。

依 PLAN 第二十七章 R 項：4 個必要測試。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.integration


async def _login_get_access_and_csrf(auth_client, email: str, password: str) -> tuple[str, str]:
    """登入並回 (access_token, csrf_cookie)。"""
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    csrf = r.cookies.get("csrf_token") or ""
    return r.json()["data"]["access_token"], csrf


def _change_password_headers(access: str, csrf: str) -> dict:
    return {
        "Authorization": f"Bearer {access}",
        "X-CSRF-Token": csrf,
    }


# ────────────────────────────────────────────────────────
# 1. 必須帶舊密碼
# ────────────────────────────────────────────────────────


async def test_change_password_requires_old(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    access, csrf = await _login_get_access_and_csrf(auth_client, user.email, password)

    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "WrongOld1!", "new_password": "BrandNewPwd2026!"},
        headers=_change_password_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r.status_code == 401, r.text
    body = r.json()
    assert body["error"]["code"] == "AUTH_ERROR"


# ────────────────────────────────────────────────────────
# 2. 不可重複最近 5 次密碼
# ────────────────────────────────────────────────────────


async def test_change_password_blocks_recent_5(
    auth_client, make_test_user, db_session_maker, flush_rate_limit
) -> None:
    user, p0 = await make_test_user(must_change=False)
    passwords = [
        p0,
        "PwdRoundTwo2!",
        "PwdRoundThree3!",
        "PwdRoundFour4!",
        "PwdRoundFive5!",
    ]

    current_pwd = p0
    for new in passwords[1:]:
        flush_rate_limit()
        access, csrf = await _login_get_access_and_csrf(auth_client, user.email, current_pwd)
        r = auth_client.post(
            "/api/v1/auth/change-password",
            json={"old_password": current_pwd, "new_password": new},
            headers=_change_password_headers(access, csrf),
            cookies={"csrf_token": csrf},
        )
        assert r.status_code == 200, r.text
        current_pwd = new

    # 此時 history 有 p0 ~ p3
    flush_rate_limit()
    access, csrf = await _login_get_access_and_csrf(auth_client, user.email, current_pwd)
    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": current_pwd, "new_password": p0},
        headers=_change_password_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r.status_code == 401, r.text
    assert "最近 5 次" in r.json()["error"]["message"]


# ────────────────────────────────────────────────────────
# 3. 改密碼後 must_change_password 應變 false
# ────────────────────────────────────────────────────────


async def test_change_password_clears_must_change_flag(
    auth_client, make_test_user, db_session_maker
) -> None:
    user, password = await make_test_user(must_change=True)
    access, csrf = await _login_get_access_and_csrf(auth_client, user.email, password)
    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": "BrandNewPwd2026!Z"},
        headers=_change_password_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r.status_code == 200, r.text

    from app.models.user import User

    async with db_session_maker() as s:
        rows = await s.execute(select(User).where(User.id == user.id))
        u = rows.scalar_one()
    assert u.must_change_password is False


# ────────────────────────────────────────────────────────
# 4. 改密碼後其他 active session 全部撤銷
# ────────────────────────────────────────────────────────


async def test_change_password_revokes_other_sessions(
    auth_client, make_test_user, db_session_maker, flush_rate_limit
) -> None:
    user, password = await make_test_user(must_change=False)
    # login 2 次製造 2 個 session
    flush_rate_limit()
    auth_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    flush_rate_limit()
    auth_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})

    flush_rate_limit()
    access, csrf = await _login_get_access_and_csrf(auth_client, user.email, password)
    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": "BrandNewPwd2026!Z"},
        headers=_change_password_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r.status_code == 200, r.text

    from app.models.user import UserSession

    async with db_session_maker() as s:
        rows = await s.execute(select(UserSession).where(UserSession.user_id == user.id))
        sessions = list(rows.scalars().all())
    # 全部都會被撤銷（current_refresh_jti=None policy）
    assert all(x.revoked for x in sessions)
    assert len(sessions) >= 3  # 至少 3 個 session（2 多開 + 1 拿 token）


# ────────────────────────────────────────────────────────
# 5. 弱密碼 → 422
# ────────────────────────────────────────────────────────


async def test_change_password_weak_password_rejected(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    access, csrf = await _login_get_access_and_csrf(auth_client, user.email, password)
    # 太短
    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": "short"},
        headers=_change_password_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r.status_code == 422, r.text

    # 12 字長但缺 4 類字元
    r2 = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": "abcabcabcabc"},
        headers=_change_password_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r2.status_code == 422, r2.text
