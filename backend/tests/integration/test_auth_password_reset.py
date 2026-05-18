"""Phase 8 — /api/v1/auth/password-reset[/confirm] 整合測試。

依 PLAN 第二十七章 Q 項：5 個必要測試 + 限速。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.integration


# ────────────────────────────────────────────────────────
# 1. request 會寫一筆 token（dev 直接回 dev_token）
# ────────────────────────────────────────────────────────


async def test_password_reset_request_returns_envelope(
    auth_client, make_test_user, db_session_maker
) -> None:
    user, _ = await make_test_user(must_change=False)
    r = auth_client.post(
        "/api/v1/auth/password-reset",
        json={"email": user.email},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["ok"] is True
    # dev 環境會回 dev_token
    assert "dev_token" in data
    assert isinstance(data["dev_token"], str) and len(data["dev_token"]) > 20

    # DB 應該有對應 row
    from app.models.user import PasswordResetToken

    async with db_session_maker() as s:
        rows = await s.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
        items = list(rows.scalars().all())
    assert len(items) == 1
    # 存的是 hash，不是 plaintext
    assert items[0].token_hash != data["dev_token"]


# ────────────────────────────────────────────────────────
# 2. 限速 3/hr/IP
# ────────────────────────────────────────────────────────


async def test_password_reset_request_rate_limit_3_per_hour(auth_client, make_test_user) -> None:
    user, _ = await make_test_user(must_change=False)
    # 用同一個 client（同 IP）發 3 次成功
    for _ in range(3):
        r = auth_client.post("/api/v1/auth/password-reset", json={"email": user.email})
        assert r.status_code == 200, r.text
    # 第 4 次應 429
    r4 = auth_client.post("/api/v1/auth/password-reset", json={"email": user.email})
    assert r4.status_code == 429, r4.text
    assert r4.json()["error"]["code"] == "RATE_LIMITED"


# ────────────────────────────────────────────────────────
# 3. confirm 用 token 更新密碼 + 撤銷所有 session
# ────────────────────────────────────────────────────────


async def test_password_reset_confirm_with_valid_token(
    auth_client, make_test_user, db_session_maker
) -> None:
    user, old_password = await make_test_user(must_change=False)
    # 先 login 製造一個 session
    auth_client.post("/api/v1/auth/login", json={"email": user.email, "password": old_password})
    # request reset
    r = auth_client.post("/api/v1/auth/password-reset", json={"email": user.email})
    dev_token = r.json()["data"]["dev_token"]
    new_password = "BrandNewPwd2026!Z"

    cr = auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": dev_token, "new_password": new_password},
    )
    assert cr.status_code == 200, cr.text

    # 新密碼可登入
    login_r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": new_password},
    )
    assert login_r.status_code == 200, login_r.text

    # 舊密碼不可
    fail_r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": old_password},
    )
    assert fail_r.status_code == 401, fail_r.text


async def test_password_reset_revokes_all_sessions(
    auth_client, make_test_user, db_session_maker
) -> None:
    user, password = await make_test_user(must_change=False)
    # login 2 次製造 2 個 session
    auth_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    auth_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})

    r = auth_client.post("/api/v1/auth/password-reset", json={"email": user.email})
    dev_token = r.json()["data"]["dev_token"]
    new_password = "BrandNewPwd2026!Z"

    cr = auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": dev_token, "new_password": new_password},
    )
    assert cr.status_code == 200, cr.text

    from app.models.user import UserSession

    async with db_session_maker() as s:
        rows = await s.execute(select(UserSession).where(UserSession.user_id == user.id))
        sessions = list(rows.scalars().all())
    assert len(sessions) >= 2
    assert all(x.revoked for x in sessions), "全部舊 session 應被撤銷"


# ────────────────────────────────────────────────────────
# 4. 一次性：用過再用 → 失敗
# ────────────────────────────────────────────────────────


async def test_password_reset_token_one_use_only(auth_client, make_test_user) -> None:
    user, _ = await make_test_user(must_change=False)
    r = auth_client.post("/api/v1/auth/password-reset", json={"email": user.email})
    dev_token = r.json()["data"]["dev_token"]
    new_password = "BrandNewPwd2026!Z"

    cr1 = auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": dev_token, "new_password": new_password},
    )
    assert cr1.status_code == 200

    cr2 = auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": dev_token, "new_password": "AnotherTotallyNew99!"},
    )
    assert cr2.status_code == 401, cr2.text


# ────────────────────────────────────────────────────────
# 5. 不存在的 email → 仍回 200（不洩漏存在性）
# ────────────────────────────────────────────────────────


async def test_password_reset_unknown_email_returns_200(auth_client) -> None:
    r = auth_client.post(
        "/api/v1/auth/password-reset",
        json={"email": "nonexistent-99999@test.example.com"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["ok"] is True
    # 不應有 dev_token（因為沒這個 user）
    assert "dev_token" not in data
