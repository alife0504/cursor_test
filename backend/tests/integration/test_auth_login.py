"""Phase 8 — /api/v1/auth/login 整合測試。

需 docker compose up（DB + Redis）。每個 test 建立獨立 test user 並自動清理。

依 PLAN 第二十七章 O 項：8 個必要測試。
"""

from __future__ import annotations

from datetime import UTC

import pytest
from sqlalchemy import select, text

pytestmark = pytest.mark.integration


# ────────────────────────────────────────────────────────
# 1. 成功登入
# ────────────────────────────────────────────────────────


async def test_login_success(auth_client, make_test_user) -> None:
    user, password = await make_test_user(
        role="ADMIN", must_change=False, onboarding_completed=True
    )
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    assert "meta" in body
    data = body["data"]
    assert isinstance(data["access_token"], str) and len(data["access_token"]) > 20
    assert data["token_type"] == "Bearer"
    assert data["next_action"] == "dashboard"
    assert data["user"]["email"].lower() == user.email.lower()
    assert data["user"]["role"] == "ADMIN"
    # cookies 應有 refresh_token + csrf_token
    cookie_names = {c.name for c in r.cookies.jar}
    assert "refresh_token" in cookie_names
    assert "csrf_token" in cookie_names


# ────────────────────────────────────────────────────────
# 2. 錯誤密碼 → 401 + 累計 failed_attempts
# ────────────────────────────────────────────────────────


async def test_login_wrong_password_increments_attempts(
    auth_client, make_test_user, db_session_maker
) -> None:
    user, _ = await make_test_user(role="VIEWER")
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "WrongPassword1!"},
    )
    assert r.status_code == 401, r.text
    body = r.json()
    assert body["error"]["code"] == "AUTH_ERROR"

    from app.models.user import User

    async with db_session_maker() as s:
        refreshed = await s.execute(select(User).where(User.id == user.id))
        u = refreshed.scalar_one()
        assert u.failed_attempts == 1


# ────────────────────────────────────────────────────────
# 3. 連 5 次失敗 → 鎖
# ────────────────────────────────────────────────────────


async def test_login_5_failures_locks_account(
    auth_client, make_test_user, db_session_maker
) -> None:
    user, _ = await make_test_user(role="VIEWER")
    for _ in range(4):
        auth_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "WrongPassword1!"},
        )
    # 第 5 次：應 423（鎖定）
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "WrongPassword1!"},
    )
    assert r.status_code == 423, r.text
    body = r.json()
    assert body["error"]["code"] == "LOCKED"

    from app.models.user import User

    async with db_session_maker() as s:
        refreshed = await s.execute(select(User).where(User.id == user.id))
        u = refreshed.scalar_one()
        assert u.locked_until is not None


# ────────────────────────────────────────────────────────
# 4. 已鎖的帳號就算正確密碼也 423
# ────────────────────────────────────────────────────────


async def test_login_locked_account_returns_423(
    auth_client, make_test_user, db_session_maker
) -> None:
    from datetime import datetime, timedelta

    from sqlalchemy import update

    from app.models.user import User

    user, password = await make_test_user(role="VIEWER")
    # 直接把這個 user 鎖到 15 分鐘後
    async with db_session_maker() as s:
        await s.execute(
            update(User)
            .where(User.id == user.id)
            .values(locked_until=datetime.now(UTC) + timedelta(minutes=15))
        )
        await s.commit()
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert r.status_code == 423, r.text


# ────────────────────────────────────────────────────────
# 5. must_change_password=true → next_action=change_password
# ────────────────────────────────────────────────────────


async def test_login_returns_next_action_change_password_for_new_user(
    auth_client, make_test_user
) -> None:
    user, password = await make_test_user(
        role="ANALYST", must_change=True, onboarding_completed=False
    )
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["next_action"] == "change_password"


async def test_login_returns_next_action_onboarding(auth_client, make_test_user) -> None:
    user, password = await make_test_user(
        role="VIEWER", must_change=False, onboarding_completed=False
    )
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["next_action"] == "onboarding"


# ────────────────────────────────────────────────────────
# 6. 第 6 次 login → 撤銷最舊 session
# ────────────────────────────────────────────────────────


async def test_login_6_sessions_revokes_oldest(
    auth_client, make_test_user, db_session_maker, flush_rate_limit
) -> None:
    user, password = await make_test_user(role="VIEWER", must_change=False)

    # login 6 次（5 次到上限，第 6 次應撤舊）
    # 每次 login 前清 rate limit（避開 L2 5/min 限制）
    for _ in range(6):
        flush_rate_limit()
        r = auth_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert r.status_code == 200, r.text

    from app.models.user import UserSession

    async with db_session_maker() as s:
        rows = await s.execute(select(UserSession).where(UserSession.user_id == user.id))
        sessions = list(rows.scalars().all())
    assert len(sessions) == 6, "user_sessions 共 6 筆"
    revoked = [x for x in sessions if x.revoked]
    assert len(revoked) >= 1, "至少 1 筆被撤銷"
    active = [x for x in sessions if not x.revoked]
    assert len(active) == 5, "active 應收斂到 5"


# ────────────────────────────────────────────────────────
# 7. login 成功會寫 audit log
# ────────────────────────────────────────────────────────


async def test_login_audit_log_written(auth_client, make_test_user, db_session_maker) -> None:
    user, password = await make_test_user(role="VIEWER", must_change=False)
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert r.status_code == 200, r.text

    async with db_session_maker() as s:
        count = (
            await s.execute(
                text(
                    "SELECT count(*) FROM audit_logs "
                    "WHERE action='auth.login' AND actor_id = :uid"
                ),
                {"uid": user.id},
            )
        ).scalar()
    assert count and count >= 1


# ────────────────────────────────────────────────────────
# 8. envelope 格式
# ────────────────────────────────────────────────────────


async def test_login_response_envelope_format(auth_client, make_test_user) -> None:
    user, password = await make_test_user(role="VIEWER", must_change=False)
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    body = r.json()
    assert set(body.keys()) >= {"data", "meta"}
    assert set(body["meta"].keys()) >= {"trace_id", "version", "timestamp"}


async def test_login_failed_response_envelope_format(auth_client, make_test_user) -> None:
    user, _ = await make_test_user(role="VIEWER")
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Wrong1234567!"},
    )
    assert r.status_code == 401
    body = r.json()
    assert "error" in body
    assert {"code", "message", "trace_id"} <= set(body["error"].keys())


# ────────────────────────────────────────────────────────
# 9. 不存在的 email → 401（不洩漏存在性，且 timing-safe）
# ────────────────────────────────────────────────────────


async def test_login_unknown_email_returns_401(auth_client) -> None:
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent-99999@test.example.com", "password": "Anything12345!"},
    )
    assert r.status_code == 401, r.text
    body = r.json()
    assert body["error"]["code"] == "AUTH_ERROR"
    # 訊息不應透露「使用者不存在」
    assert "不存在" not in body["error"]["message"]
