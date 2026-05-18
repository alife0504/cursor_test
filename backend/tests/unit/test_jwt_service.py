"""Phase 8 — JWTService 單元測試。

依 PLAN 第 19.1 章 + 第 19.4 章 雙 key rotation + 第二十七章 M 項。

不依賴 docker。
"""

from __future__ import annotations

import base64
import secrets
import time
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from jose import jwt

from app.core.errors import AuthError
from app.core.security import JWTService

pytestmark = pytest.mark.unit


def _make_key() -> str:
    """base64-encode 32 bytes 隨機 key（與 config 同格式）。"""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8")


def _settings(current: str | None = None, previous: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        SECRET_KEY=current or _make_key(),
        SECRET_KEY_PREVIOUS=previous,
    )


def test_create_access_token_includes_user_id_role() -> None:
    s = _settings()
    svc = JWTService(s)
    user_id = uuid4()
    token, jti = svc.create_access_token(user_id, "ADMIN")
    payload = svc.decode(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "ADMIN"
    assert payload["type"] == "access"
    assert payload["jti"] == jti


def test_create_refresh_token_returns_jti_and_exp() -> None:
    s = _settings()
    svc = JWTService(s)
    token, jti, exp = svc.create_refresh_token(uuid4())
    payload = svc.decode(token)
    assert payload["type"] == "refresh"
    assert payload["jti"] == jti
    assert exp.tzinfo is not None  # UTC aware


def test_decode_valid_token() -> None:
    s = _settings()
    svc = JWTService(s)
    token, _ = svc.create_access_token(uuid4(), "VIEWER")
    payload = svc.decode(token)
    assert payload["role"] == "VIEWER"


def test_decode_expired_raises() -> None:
    s = _settings()
    svc = JWTService(s)
    # 簽一個負 TTL 的 access token
    token, _ = svc.create_access_token(uuid4(), "VIEWER", ttl=timedelta(seconds=-10))
    with pytest.raises(AuthError) as exc:
        svc.decode(token)
    assert "過期" in exc.value.get_message()


def test_decode_invalid_signature_raises() -> None:
    s = _settings()
    svc = JWTService(s)
    token, _ = svc.create_access_token(uuid4(), "VIEWER")
    # 換掉最後幾個字元 → 簽章不符
    tampered = token[:-4] + "XXXX"
    with pytest.raises(AuthError):
        svc.decode(tampered)


def test_decode_empty_token_raises() -> None:
    s = _settings()
    svc = JWTService(s)
    with pytest.raises(AuthError):
        svc.decode("")


def test_dual_key_rotation_old_key_still_valid() -> None:
    """rotation 過渡期：用舊 key 簽的 token，新 key 為 current 時仍可 decode。"""
    old_key = _make_key()
    new_key = _make_key()

    # 「過渡前」svc：current=old，沒 previous
    svc_old = JWTService(_settings(current=old_key, previous=None))
    token_old, _ = svc_old.create_access_token(uuid4(), "ANALYST")

    # 「過渡後」svc：current=new，previous=old
    svc_new = JWTService(_settings(current=new_key, previous=old_key))
    payload = svc_new.decode(token_old)
    assert payload["role"] == "ANALYST"

    # 新 svc 簽的 token 仍可 decode
    token_new, _ = svc_new.create_access_token(uuid4(), "VIEWER")
    assert svc_new.decode(token_new)["role"] == "VIEWER"


def test_decode_with_no_previous_key_fails_for_other_key_signed_token() -> None:
    """如果沒有 SECRET_KEY_PREVIOUS，舊 key 簽的 token decode 應失敗。"""
    old_key = _make_key()
    new_key = _make_key()

    svc_old = JWTService(_settings(current=old_key, previous=None))
    token = svc_old.create_access_token(uuid4(), "VIEWER")[0]

    svc_new = JWTService(_settings(current=new_key, previous=None))
    with pytest.raises(AuthError):
        svc_new.decode(token)


def test_jwt_iat_exp_use_utc_epoch_seconds() -> None:
    """payload 的 iat / exp 應為 epoch second (int)。"""
    s = _settings()
    svc = JWTService(s)
    token, _ = svc.create_access_token(uuid4(), "VIEWER")
    payload = svc.decode(token)
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    # exp > iat + 14min（access ttl 是 15min）
    assert payload["exp"] - payload["iat"] >= 14 * 60


def test_token_blacklist_add_and_check() -> None:
    """TokenBlacklist：fakeredis 模擬。"""
    import asyncio

    import fakeredis.aioredis

    from app.core.security import TokenBlacklist

    async def _run():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        bl = TokenBlacklist(r)
        jti = str(uuid4())

        assert await bl.is_blacklisted(jti) is False
        await bl.add(jti, ttl_seconds=60)
        assert await bl.is_blacklisted(jti) is True

        # ttl ≤ 0 不加
        jti2 = str(uuid4())
        await bl.add(jti2, ttl_seconds=0)
        assert await bl.is_blacklisted(jti2) is False
        await r.aclose()

    asyncio.run(_run())


def test_ttl_seconds_from_exp() -> None:
    from app.core.security import ttl_seconds_from_exp

    now = int(time.time())
    assert ttl_seconds_from_exp(now + 100) >= 99
    assert ttl_seconds_from_exp(now - 100) == 0


def test_password_hash_and_verify_roundtrip() -> None:
    from app.core.security import hash_password, verify_password

    pwd = "MyP@ssw0rd2026!"
    h = hash_password(pwd)
    assert h != pwd  # 不是明文
    assert verify_password(pwd, h) is True
    assert verify_password("wrongpass", h) is False
    assert verify_password("", h) is False
    assert verify_password(pwd, "") is False


def test_jose_jwt_external_decode_does_not_validate() -> None:
    """直接用 jose 解 payload（不驗章）應該也能讀到 sub/role — 確保 token 結構穩定。"""
    s = _settings()
    svc = JWTService(s)
    user_id = uuid4()
    token, _ = svc.create_access_token(user_id, "ADMIN")
    # 不驗章 decode（jose 的方式）
    payload = jwt.get_unverified_claims(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "ADMIN"
