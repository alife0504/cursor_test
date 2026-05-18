"""Phase 11 — /api/v1/notifications/* 整合測試。

涵蓋：
1. GET /settings：第一次無設定 → 回 default
2. PUT /settings 寫 line_token → 加密儲存，回應遮蔽
3. POST /test channel=line：先無 token → failed；設定後 → sent
4. GET /logs 回 envelope + pagination
5. unauthenticated → 401
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.crypto import decrypt_str
from app.models.notification import NotificationSetting

pytestmark = pytest.mark.integration


def _csrf(access: str, csrf: str) -> dict:
    return {"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf}


async def test_notifications_requires_auth(auth_client) -> None:
    r = auth_client.get("/api/v1/notifications/settings")
    assert r.status_code == 401


async def test_get_default_settings(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/notifications/settings",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["line_token_masked"] is None
    assert data["email_enabled"] is False


async def test_put_settings_encrypts_line_token(
    auth_client, make_test_user, login_helper, db_session_maker
) -> None:
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)
    r = auth_client.put(
        "/api/v1/notifications/settings",
        json={
            "line_token": "test-line-token-1234567890",
            "email_enabled": True,
            "enabled_channels": ["line", "email"],
            "enabled_events": ["analysis.completed"],
        },
        headers=_csrf(access, csrf),
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["line_token_masked"] is not None
    assert "test-line-token-1234567890" not in r.text  # 永遠不回明文

    # 驗 DB 存的是 ciphertext，且能解回原值
    async with db_session_maker() as s:
        row = (
            await s.execute(
                select(NotificationSetting).where(NotificationSetting.user_id == user.id)
            )
        ).scalar_one()
        assert row.line_token_encrypted is not None
        assert "test-line-token-1234567890" not in row.line_token_encrypted
        assert decrypt_str(row.line_token_encrypted) == "test-line-token-1234567890"


async def test_post_test_without_token_returns_failed_log(
    auth_client, make_test_user, login_helper
) -> None:
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)
    r = auth_client.post(
        "/api/v1/notifications/test",
        json={"channel": "line", "message": "Hello"},
        headers=_csrf(access, csrf),
    )
    assert r.status_code == 200, r.text
    log = r.json()["data"]
    assert log["status"] == "failed"
    assert "LINE" in (log.get("error_msg") or "")


async def test_post_test_with_token_returns_sent(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)

    auth_client.put(
        "/api/v1/notifications/settings",
        json={"line_token": "test-line-token-XXX-1234567890"},
        headers=_csrf(access, csrf),
    )

    r = auth_client.post(
        "/api/v1/notifications/test",
        json={"channel": "line", "message": "Hello"},
        headers=_csrf(access, csrf),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "sent"


async def test_get_logs_returns_envelope(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)

    # 先寫一筆 log（透過 /test）
    auth_client.post(
        "/api/v1/notifications/test",
        json={"channel": "line", "message": "Hi"},
        headers=_csrf(access, csrf),
    )

    r = auth_client.get(
        "/api/v1/notifications/logs?limit=10",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "pagination" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1
