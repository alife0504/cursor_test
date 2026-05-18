"""Phase 18 — Secret handling tests（PLAN 19.4 + 第二十七章 P18 N 節）。

驗證：
1. 密碼不出現在 log
2. JWT secret 不出現在 response
3. API key 在 log 中遮蔽
4. token 不放 URL query
5. CSRF token 不被 log
6. Telegram bot token 加密儲存

跑：cd backend && uv run pytest tests/security/test_secret_handling.py -v
"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.crypto import decrypt_str, encrypt_str
from app.models.notification import NotificationSetting

pytestmark = pytest.mark.security


def _csrf(access: str, csrf: str) -> dict:
    return {"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf}


# ════════════════════════════════════════════════════════
# 1. 密碼不出現在 log
# ════════════════════════════════════════════════════════


async def test_password_never_in_logs(auth_client, make_test_user, caplog) -> None:
    user, _ = await make_test_user(role="VIEWER", must_change=False)
    secret_pwd = "PlaintextSecret123!Ab_unique_marker_xyz"
    with caplog.at_level(logging.DEBUG):  # 收最詳細的 log
        r = auth_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": secret_pwd},
        )
        assert r.status_code in (401, 422)
        for rec in caplog.records:
            msg = rec.getMessage()
            if secret_pwd in msg:
                pytest.fail(f"密碼明文洩漏在 log: {msg!r}")


# ════════════════════════════════════════════════════════
# 2. JWT secret 不出現在 response
# ════════════════════════════════════════════════════════


async def test_jwt_secret_never_in_response(auth_client) -> None:
    """任何 API endpoint 的 response 都不能含 SECRET_KEY 明文。"""
    secret = settings.SECRET_KEY  # 真實 SECRET_KEY 字串
    for path in ("/api/v1/auth/login", "/api/v1/auth/me", "/health/live"):
        r = auth_client.get(path) if path.startswith("/health") else auth_client.post(path, json={})
        if secret in r.text:
            pytest.fail(f"SECRET_KEY 洩漏於 {path}: {r.text[:200]!r}")


# ════════════════════════════════════════════════════════
# 3. API key 在 log 中遮蔽
# ════════════════════════════════════════════════════════


async def test_api_key_masked_in_log(caplog) -> None:
    """app.core.logging_config 應遮蔽 api_key / token / authorization 等欄位。"""
    import structlog

    logger = structlog.get_logger("test.secret_handling")
    sensitive = "sk-google-FAKE-API-KEY-1234567890ABCDEFGHIJ"
    with caplog.at_level(logging.INFO):
        logger.info(
            "test.event",
            api_key=sensitive,
            google_api_key=sensitive,
            authorization=f"Bearer {sensitive}",
        )

    all_logs = " ".join(rec.getMessage() for rec in caplog.records)
    # structlog mask processor 應該擋下
    if sensitive in all_logs:
        pytest.fail(f"API key 未遮蔽：{all_logs!r}")


# ════════════════════════════════════════════════════════
# 4. token 不放 URL query
# ════════════════════════════════════════════════════════


async def test_token_not_in_url_query(auth_client, make_test_user, login_helper) -> None:
    """所有 endpoint：token 必須走 Authorization header，不能用 ?token= query。"""
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    # 嘗試用 query 傳 token → 應 401（沒走 header）
    r = auth_client.get(f"/api/v1/auth/me?token={access}")
    assert r.status_code == 401, r.text


# ════════════════════════════════════════════════════════
# 5. CSRF token 不被 log
# ════════════════════════════════════════════════════════


async def test_csrf_token_not_logged(auth_client, make_test_user, login_helper, caplog) -> None:
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    with caplog.at_level(logging.DEBUG):
        access, csrf = await login_helper(auth_client, user.email, pwd)
        # 帶 csrf token 訪問 /me（會走 audit middleware log）
        auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf},
        )
        # csrf cookie + header 不應出現在 log 完整字串
        all_logs = " ".join(rec.getMessage() for rec in caplog.records)
        if csrf and csrf in all_logs:
            pytest.fail(f"CSRF token 洩漏在 log: {all_logs!r}")


# ════════════════════════════════════════════════════════
# 6. Telegram bot token 加密儲存
# ════════════════════════════════════════════════════════


async def test_telegram_token_encrypted_at_rest(
    auth_client, make_test_user, login_helper, db_session_maker
) -> None:
    """PUT settings 把 telegram_bot_token 加密寫 DB；明文不該出現在 row。"""
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)

    plaintext_bot_token = "9876543210:ABCdef_FAKE_telegram_bot_token_xyz"
    r = auth_client.put(
        "/api/v1/notifications/settings",
        json={
            "telegram_bot_token": plaintext_bot_token,
            "telegram_chat_id": "-1001234567890",
        },
        headers=_csrf(access, csrf),
    )
    assert r.status_code == 200, r.text
    # response 不可含明文
    assert plaintext_bot_token not in r.text

    async with db_session_maker() as s:
        row = (
            await s.execute(
                select(NotificationSetting).where(NotificationSetting.user_id == user.id)
            )
        ).scalar_one()
        assert row.telegram_bot_token_encrypted is not None
        assert plaintext_bot_token not in row.telegram_bot_token_encrypted, "DB 仍存明文！"
        assert decrypt_str(row.telegram_bot_token_encrypted) == plaintext_bot_token


# ════════════════════════════════════════════════════════
# bonus: encrypt/decrypt round-trip 不洩漏
# ════════════════════════════════════════════════════════


def test_encrypt_decrypt_roundtrip_for_short_secret() -> None:
    """Fernet encrypt/decrypt 短 secret 也 round-trip OK。"""
    secret = "short_token"
    ct = encrypt_str(secret)
    # ciphertext 應該不含明文
    assert secret not in ct
    assert decrypt_str(ct) == secret
