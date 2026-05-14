"""Phase 8 — /api/v1/auth/change-password 整合測試。

依 PLAN 第二十七章 R 項：4 個必要測試。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.integration


async def _login_and_get_token(auth_client, email: str, password: str) -> str:
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


# ────────────────────────────────────────────────────────
# 1. 必須帶舊密碼
# ────────────────────────────────────────────────────────


async def test_change_password_requires_old(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    access = await _login_and_get_token(auth_client, user.email, password)

    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "WrongOld1!", "new_password": "BrandNewPwd2026!"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 401, r.text
    body = r.json()
    assert body["error"]["code"] == "AUTH_ERROR"


# ────────────────────────────────────────────────────────
# 2. 不可重複最近 5 次密碼
# ────────────────────────────────────────────────────────


async def test_change_password_blocks_recent_5(
    auth_client, make_test_user, db_session_maker
) -> None:
    user, p0 = await make_test_user(must_change=False)
    passwords = [
        p0,
        "PwdRoundTwo2!",
        "PwdRoundThree3!",
        "PwdRoundFour4!",
        "PwdRoundFive5!",
    ]

    # 先繞圈改 4 次（共 5 個不同密碼進 history）
    current_pwd = p0
    for new in passwords[1:]:
        access = await _login_and_get_token(auth_client, user.email, current_pwd)
        r = auth_client.post(
            "/api/v1/auth/change-password",
            json={"old_password": current_pwd, "new_password": new},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert r.status_code == 200, r.text
        current_pwd = new

    # 此時 history 有 p0 ~ p3（4 筆，因為當下用的 p4 還沒進 history）
    # 嘗試用 p0（最早的）回去 → 應被拒
    access = await _login_and_get_token(auth_client, user.email, current_pwd)
    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": current_pwd, "new_password": p0},
        headers={"Authorization": f"Bearer {access}"},
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
    access = await _login_and_get_token(auth_client, user.email, password)
    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": "BrandNewPwd2026!Z"},
        headers={"Authorization": f"Bearer {access}"},
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
    auth_client, make_test_user, db_session_maker
) -> None:
    user, password = await make_test_user(must_change=False)
    # login 2 次製造 2 個 session
    auth_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    auth_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})

    access = await _login_and_get_token(auth_client, user.email, password)
    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": "BrandNewPwd2026!Z"},
        headers={"Authorization": f"Bearer {access}"},
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
# 5. 弱密碼 → 422 (Pydantic) or 400 (policy)
# ────────────────────────────────────────────────────────


async def test_change_password_weak_password_rejected(auth_client, make_test_user) -> None:
    user, password = await make_test_user(must_change=False)
    access = await _login_and_get_token(auth_client, user.email, password)
    # 太短 → Pydantic 在 min_length=12 階段就擋掉
    r = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": "short"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 422, r.text

    # 12 字長但缺 4 類字元 → policy 擋
    r2 = auth_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": password, "new_password": "abcabcabcabc"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r2.status_code == 422, r2.text  # ValidationError → 422
