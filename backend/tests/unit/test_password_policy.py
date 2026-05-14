"""Phase 8 — password policy 單元測試。

依 PLAN 第 19.1 章 + 第二十七章 L 項。

不依賴 docker：純函式測試 + Pasword history 用 sqlite in-memory（或 mock）。
"""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.core.password_policy import (
    MAX_LENGTH,
    MIN_LENGTH,
    validate_password,
)

pytestmark = pytest.mark.unit


# ────────────────────────────────────────────────────────
# 1. 字元類別 & 長度
# ────────────────────────────────────────────────────────


def test_password_too_short() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_password("Aa1!short")  # 9 字
    assert "≥ 12" in exc.value.get_message() or f"≥ {MIN_LENGTH}" in exc.value.get_message()


def test_password_too_long() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_password("A" + "a1!" * 50)  # > 128
    assert f"≤ {MAX_LENGTH}" in exc.value.get_message()


def test_password_lacks_uppercase() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_password("abc123def!ghi")
    assert "大寫字母" in exc.value.get_message()


def test_password_lacks_lowercase() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_password("ABC123DEF!GHI")
    assert "小寫字母" in exc.value.get_message()


def test_password_lacks_digit() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_password("AbcDef!GhiJkl")
    assert "數字" in exc.value.get_message()


def test_password_lacks_special() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_password("AbcDef123Ghi4")
    assert "特殊字元" in exc.value.get_message()


def test_password_valid_minimum() -> None:
    """12 字元 + 4 類字元 → 通過。"""
    validate_password("Abcdef123!gh")  # exactly 12 chars
    # 不 raise = 通過


def test_password_valid_complex() -> None:
    validate_password("My$ecureP@ss2026")


# ────────────────────────────────────────────────────────
# 2. 不可包含 email
# ────────────────────────────────────────────────────────


def test_password_contains_email_local_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_password("AdminUser1234!", user_email="admin@example.com")
    assert "email" in exc.value.get_message()


def test_password_contains_email_case_insensitive() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_password("WuHsiang2026!a", user_email="wuhsiang@gmail.com")
    assert "email" in exc.value.get_message()


def test_password_no_email_local_ok() -> None:
    # 密碼中沒有 email local
    validate_password("Strong$Pass2026", user_email="admin@example.com")


def test_password_email_local_too_short_skipped() -> None:
    """若 email local 太短（< 3 字元），不檢查避免太多誤判。"""
    validate_password("My$ecureP@ss2026", user_email="aa@example.com")


# ────────────────────────────────────────────────────────
# 3. 非字串 / 空字串
# ────────────────────────────────────────────────────────


def test_password_non_string_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_password(12345678901234)  # type: ignore[arg-type]


def test_password_empty_string_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_password("")


# ────────────────────────────────────────────────────────
# 4. PasswordHistoryService — 用 stubbed session 測 is_recent / add
# ────────────────────────────────────────────────────────


class _FakeSession:
    """最小 stub：模擬 session.execute(stmt) 回 result.all() 拿 hash list。"""

    def __init__(self, hashes: list[str]):
        self._hashes = hashes
        self.added: list = []

    async def execute(self, _stmt):
        class _Result:
            def __init__(self, h):
                self.h = h

            def all(self):
                return [(x,) for x in self.h]

        return _Result(self._hashes)

    def add(self, obj):
        self.added.append(obj)


@pytest.mark.asyncio
async def test_password_history_blocks_recent_5() -> None:
    """is_recent 應對最近 5 次 hash 任一相符回 True。"""
    from uuid import uuid4

    from app.core.password_policy import PasswordHistoryService
    from app.core.security import hash_password

    user_id = uuid4()
    pwd_old = "MyOldPwd2024!"
    pwd_new = "DifferentPwd2026!"

    hashed_list = [hash_password(pwd_old), hash_password("Other$Pass2025")]
    fake_session = _FakeSession(hashed_list)

    history = PasswordHistoryService(fake_session)  # type: ignore[arg-type]
    assert await history.is_recent(user_id, pwd_old) is True
    assert await history.is_recent(user_id, pwd_new) is False


@pytest.mark.asyncio
async def test_password_history_add_appends() -> None:
    from uuid import uuid4

    from app.core.password_policy import PasswordHistoryService

    fake_session = _FakeSession([])
    history = PasswordHistoryService(fake_session)  # type: ignore[arg-type]
    await history.add(uuid4(), "$2b$12$some.hash")
    assert len(fake_session.added) == 1
