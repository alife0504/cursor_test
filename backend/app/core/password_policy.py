"""Phase 8 — 密碼策略 + 歷史比對。

依 PLAN.md 第 19.1 章：
- 12+ 字元、4 類字元（大寫、小寫、數字、特殊字元）
- 不可包含 email local part
- 不可與最近 5 次密碼重複（PasswordHistory 表）

策略統一在這裡實作；register / change / reset 都呼叫 validate_password()。
"""

from __future__ import annotations

import re
import string
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.core.security import verify_password
from app.models.user import PasswordHistory

if TYPE_CHECKING:
    from uuid import UUID

MIN_LENGTH = 12
MAX_LENGTH = 128
RECENT_HISTORY_LIMIT = 5

# 特殊字元 = 除 ASCII letter/digit 之外的所有 printable
_SPECIAL_CHARS = set(string.punctuation)
_UPPER_RE = re.compile(r"[A-Z]")
_LOWER_RE = re.compile(r"[a-z]")
_DIGIT_RE = re.compile(r"\d")


def validate_password(password: str, user_email: str | None = None) -> None:
    """驗證密碼強度。失敗 raise ValidationError；通過回 None。

    Args:
        password: 明文密碼
        user_email: 若有提供，會檢查密碼不包含 email 的 local part（@ 前面）
    """
    if not isinstance(password, str):
        raise ValidationError(message_zh="密碼格式錯誤", field="password")

    if len(password) < MIN_LENGTH:
        raise ValidationError(
            message_zh=f"密碼長度需 ≥ {MIN_LENGTH} 字元",
            field="password",
            min_length=MIN_LENGTH,
        )
    if len(password) > MAX_LENGTH:
        raise ValidationError(
            message_zh=f"密碼長度需 ≤ {MAX_LENGTH} 字元",
            field="password",
            max_length=MAX_LENGTH,
        )

    missing: list[str] = []
    if not _UPPER_RE.search(password):
        missing.append("大寫字母")
    if not _LOWER_RE.search(password):
        missing.append("小寫字母")
    if not _DIGIT_RE.search(password):
        missing.append("數字")
    if not any(c in _SPECIAL_CHARS for c in password):
        missing.append("特殊字元")

    if missing:
        raise ValidationError(
            message_zh=f"密碼需含 4 類字元（缺：{', '.join(missing)}）",
            field="password",
            missing_categories=missing,
        )

    # 不可包含 email local part（@ 前面），不分大小寫
    if user_email and "@" in user_email:
        local = user_email.split("@", 1)[0].strip()
        if local and len(local) >= 3 and local.lower() in password.lower():
            raise ValidationError(
                message_zh="密碼不可包含 email 帳號",
                field="password",
            )


# ─────────────────────────────────────────────────────────
# PasswordHistory — 持久化在 password_history 表
# ─────────────────────────────────────────────────────────


class PasswordHistoryService:
    """密碼歷史比對：取最近 N 筆 hash，逐筆 bcrypt verify。"""

    def __init__(self, session: AsyncSession, *, limit: int = RECENT_HISTORY_LIMIT) -> None:
        self.session = session
        self.limit = limit

    async def is_recent(self, user_id: UUID, plain_password: str) -> bool:
        """檢查 plain_password 是否與最近 N 筆歷史密碼任一相同。

        Args:
            user_id: 使用者 ID
            plain_password: 明文密碼（會逐筆 bcrypt.checkpw）

        Returns:
            True = 與最近 N 筆重複（應拒絕）
            False = 不重複（可以用）
        """
        if not plain_password:
            return False
        stmt = (
            select(PasswordHistory.password_hash)
            .where(PasswordHistory.user_id == user_id)
            .order_by(PasswordHistory.created_at.desc())
            .limit(self.limit)
        )
        result = await self.session.execute(stmt)
        return any(verify_password(plain_password, hashed) for (hashed,) in result.all())

    async def add(self, user_id: UUID, hashed: str) -> PasswordHistory:
        """寫入一筆歷史。caller 負責 commit。"""
        record = PasswordHistory(user_id=user_id, password_hash=hashed)
        self.session.add(record)
        return record


__all__ = [
    "MAX_LENGTH",
    "MIN_LENGTH",
    "RECENT_HISTORY_LIMIT",
    "PasswordHistoryService",
    "validate_password",
]
