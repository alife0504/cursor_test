"""Phase 10 — 統一 Cursor-based pagination 工具。

依 PLAN.md 第 17.4 章「分頁」：
- 統一 cursor-based：`?limit=50&cursor=base64(json)`
- max limit=100

設計：
- 任意 dict → urlsafe base64(JSON) → 字串（可塞進 URL query）
- 解碼失敗 → ValidationError(422, 中文)
- UUID / datetime / Decimal 走 _serialize 統一字串化（避免 JSON 序列化失敗）
- 提供 build_next_cursor / build_page_response 兩個高階 helper，把 router 重複碼壓平
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.errors import ValidationError

DEFAULT_LIMIT = 50
MAX_LIMIT = 100
MIN_LIMIT = 1


def _serialize(v: Any) -> Any:
    """把 UUID / datetime / Decimal 轉成 JSON-safe 字串。"""
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, datetime | date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, dict):
        return {k: _serialize(val) for k, val in v.items()}
    if isinstance(v, list | tuple):
        return [_serialize(x) for x in v]
    return v


class Cursor:
    """Cursor pagination — base64(JSON) 編碼/解碼。

    用法：
        cursor = Cursor.encode(last_id="2330", last_date="2026-04-30")
        kwargs = Cursor.decode(cursor)  # {"last_id": "2330", "last_date": "2026-04-30"}

    Decode 失敗（非 base64 / 非 JSON / 結構錯誤）統一 raise ValidationError。
    """

    @classmethod
    def encode(cls, **kwargs: Any) -> str:
        """把任意 keyword args 編碼為 cursor 字串。"""
        payload = json.dumps(_serialize(kwargs), separators=(",", ":"), ensure_ascii=False)
        return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")

    @classmethod
    def decode(cls, cursor: str | None) -> dict[str, Any]:
        """解碼 cursor 字串 → dict。"""
        if cursor is None or cursor == "":
            return {}
        # 補齊 base64 padding
        s = cursor.strip()
        padding = (4 - len(s) % 4) % 4
        s = s + ("=" * padding)
        try:
            raw = base64.urlsafe_b64decode(s.encode("ascii"))
        except (binascii.Error, ValueError) as e:
            raise ValidationError(
                message_zh="cursor 格式錯誤（非合法 base64）",
                field="cursor",
            ) from e
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValidationError(
                message_zh="cursor 格式錯誤（非合法 JSON）",
                field="cursor",
            ) from e
        if not isinstance(data, dict):
            raise ValidationError(
                message_zh="cursor 格式錯誤（payload 必須是 object）",
                field="cursor",
            )
        return data


def clamp_limit(limit: int | None, *, default: int = DEFAULT_LIMIT) -> int:
    """把 limit 夾到 [MIN_LIMIT, MAX_LIMIT]，並提供預設值。"""
    if limit is None:
        return default
    if not isinstance(limit, int):
        raise ValidationError(
            message_zh="limit 必須是整數",
            field="limit",
        )
    if limit < MIN_LIMIT:
        return MIN_LIMIT
    if limit > MAX_LIMIT:
        return MAX_LIMIT
    return limit


def build_page_response(
    items: list[Any],
    *,
    limit: int,
    next_cursor_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """產生 pagination 區段 dict（給 envelope_success 的 pagination 參數）。

    Args:
        items: 已截斷至 limit 的當頁資料
        limit: 本頁要求的最大筆數
        next_cursor_kwargs: 下一頁 cursor 的 payload；None → 沒有下一頁

    Returns:
        {"next_cursor": ..., "limit": ..., "has_more": ...}
    """
    if next_cursor_kwargs is None:
        return {
            "next_cursor": None,
            "limit": limit,
            "has_more": False,
        }
    return {
        "next_cursor": Cursor.encode(**next_cursor_kwargs),
        "limit": limit,
        "has_more": True,
    }


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MIN_LIMIT",
    "Cursor",
    "build_page_response",
    "clamp_limit",
]
