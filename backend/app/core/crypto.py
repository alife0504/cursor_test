"""Phase 11 — Fernet 對稱加密工具。

依 PLAN.md 第 19.4 章 Secret 管理：
- LINE / Telegram token 加密儲存
- 使用 DATA_ENCRYPTION_KEY（與 SECRET_KEY 分離）
- Fernet 算法：AES-128-CBC + HMAC-SHA256 + base64 URL-safe

設計：
- 從 settings.DATA_ENCRYPTION_KEY（base64 編碼）建出 Fernet key（32 bytes urlsafe-b64）
- encrypt(plaintext) → token string；decrypt(token) → plaintext
- Decrypt 失敗 raise ValidationError（中文）
"""

from __future__ import annotations

import base64
import binascii
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.errors import ValidationError


def _derive_fernet_key(secret: str) -> bytes:
    """把 settings.DATA_ENCRYPTION_KEY（base64 ≥32 bytes）轉成 Fernet key。

    Fernet 規定 key 必須是 32 bytes 經 urlsafe_b64encode 的字串（44 字元）。
    我們的 ENV 是任意 base64 ≥ 32 bytes → 解碼取前 32 → 重新 urlsafe-b64encode。

    容忍：標準 / urlsafe 兩種 base64 都接受，padding 自動補齊。
    """
    s = secret.strip()
    # base64 padding：長度需 4 的倍數
    pad = (4 - len(s) % 4) % 4
    s_padded = s + ("=" * pad)
    try:
        raw = base64.urlsafe_b64decode(s_padded.encode("ascii"))
    except (binascii.Error, ValueError):
        # 退路：當作標準 base64 試一次
        raw = base64.b64decode(s_padded.encode("ascii"))
    if len(raw) < 32:
        raise ValueError("DATA_ENCRYPTION_KEY 解碼後須 ≥ 32 bytes")
    return base64.urlsafe_b64encode(raw[:32])


@lru_cache(maxsize=1)
def get_fernet() -> Fernet:
    """取得 process-level 共享 Fernet 實例（lazy + cached）。"""
    return Fernet(_derive_fernet_key(settings.DATA_ENCRYPTION_KEY))


def encrypt_str(plaintext: str) -> str:
    """加密一段字串（如 LINE token）→ 回 Fernet token 字串。"""
    if plaintext is None:
        raise ValueError("plaintext 不可為 None")
    return get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_str(token: str) -> str:
    """解密 Fernet token → 回原字串。

    失敗 raise ValidationError（中文）；caller 不應暴露原始錯誤訊息給 client。
    """
    if not token:
        raise ValidationError(message_zh="加密欄位為空")
    try:
        return get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as e:
        raise ValidationError(message_zh="加密欄位解密失敗（key 不符或內容已損壞）") from e


def mask_token(token: str | None) -> str | None:
    """回傳遮蔽過的 token，僅顯示前 4 後 4 字（log / response 用）。

    None / 空字串 → None；短於 8 字元 → 全 *。
    """
    if not token:
        return None
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}...{token[-4:]}"


__all__ = [
    "decrypt_str",
    "encrypt_str",
    "get_fernet",
    "mask_token",
]
