"""Phase 9 — 輸入驗證工具集。

依 PLAN.md 第 19.2 章輸入驗證：
- Symbol（TW / US 雙正則）
- Date range（end >= start，跨度 ≤ max_days）
- UUID 字串
- URL 長度
- Sort field 白名單（ORDER BY 無法參數化 → 必須白名單）
- Content-Type 限制
- 字串 escape helper（XSS 防護）

設計：
- 全部 raise `ValidationError`（status 422）讓 exception handler 統一格式。
- 純函式 + Pydantic BaseModel（白名單）；沒有 IO，可 unit test。
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.core.errors import ValidationError

# ─────────────────────────────────────────────────────────
# Symbol patterns
# ─────────────────────────────────────────────────────────

TW_SYMBOL_PATTERN = re.compile(r"^[0-9]{4,6}[A-Z]?$")
"""TW 股票代號：
- 4-6 碼數字 + 可選後綴 1 個大寫英文。
- 4 碼：普通股（2330 / 0050）/ 短碼 ETF
- 5 碼：常見 ETF（00878 / 00713）
- 6 碼：較長代號（006208）
- 後綴：權證 / 特別股代碼（如 0050B / 2330A）
"""

US_SYMBOL_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")
"""US 股票代號：
- 1-5 碼大寫字母（AAPL / TSLA）
- 可選 `.X` 類別碼（BRK.A / BRK.B）
"""


def validate_symbol(symbol: str) -> str:
    """驗證並 normalize 股票代號（大寫化）。

    Raises:
        ValidationError(422): 格式錯誤
    """
    if not isinstance(symbol, str):
        raise ValidationError(message_zh="股票代號型別錯誤", field="symbol")
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise ValidationError(message_zh="股票代號不可為空", field="symbol")
    if not (TW_SYMBOL_PATTERN.match(cleaned) or US_SYMBOL_PATTERN.match(cleaned)):
        raise ValidationError(
            message_zh=f"股票代號格式錯誤：{symbol}",
            field="symbol",
            value=symbol,
        )
    return cleaned


# ─────────────────────────────────────────────────────────
# Date range
# ─────────────────────────────────────────────────────────

DEFAULT_MAX_DAYS = 3650  # 10 年


def validate_date_range(
    start: date,
    end: date,
    *,
    max_days: int = DEFAULT_MAX_DAYS,
    allow_future: bool = True,
) -> tuple[date, date]:
    """驗證日期區間。

    Raises:
        ValidationError(422):
            - end < start
            - (end - start) > max_days
            - allow_future=False 且 end > today
    """
    if not isinstance(start, date) or not isinstance(end, date):
        raise ValidationError(
            message_zh="日期型別錯誤",
            field="date_range",
        )
    if end < start:
        raise ValidationError(
            message_zh="結束日期不可早於開始日期",
            field="date_range",
            start=start.isoformat(),
            end=end.isoformat(),
        )
    span = (end - start).days
    if span > max_days:
        raise ValidationError(
            message_zh=f"日期跨度過大（最多 {max_days} 天），實際 {span} 天",
            field="date_range",
            max_days=max_days,
            actual_days=span,
        )
    if not allow_future:
        today = date.today()
        if end > today:
            raise ValidationError(
                message_zh="結束日期不可超過今日",
                field="date_range",
                today=today.isoformat(),
                end=end.isoformat(),
            )
    return start, end


# ─────────────────────────────────────────────────────────
# UUID
# ─────────────────────────────────────────────────────────


def validate_uuid(value: str) -> UUID:
    """轉換字串為 UUID；失敗 raise ValidationError。"""
    if not isinstance(value, str):
        raise ValidationError(message_zh="UUID 型別錯誤", field="uuid")
    try:
        return UUID(value)
    except (ValueError, TypeError) as e:
        raise ValidationError(
            message_zh=f"UUID 格式錯誤：{value}",
            field="uuid",
            value=value,
        ) from e


# ─────────────────────────────────────────────────────────
# URL
# ─────────────────────────────────────────────────────────

MAX_URL_LENGTH = 2048


def validate_url_length(url: str, *, max_length: int = MAX_URL_LENGTH) -> str:
    """限制 URL 長度（避免 path / query 攻擊）。"""
    if not isinstance(url, str):
        raise ValidationError(message_zh="URL 型別錯誤", field="url")
    if len(url) > max_length:
        raise ValidationError(
            message_zh=f"URL 過長（最多 {max_length} 字元）",
            field="url",
            max_length=max_length,
            actual_length=len(url),
        )
    return url


# ─────────────────────────────────────────────────────────
# Content-Type
# ─────────────────────────────────────────────────────────

ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/json",
        "application/json; charset=utf-8",
        "application/json;charset=utf-8",
    }
)


def validate_content_type(content_type: str | None) -> None:
    """限制 POST/PUT body 只接受 application/json（避免 form / XML 攻擊面）。

    GET / HEAD / DELETE / OPTIONS 不檢查（middleware 該 skip）。
    """
    if not content_type:
        raise ValidationError(
            message_zh="缺少 Content-Type header",
            field="content_type",
        )
    # 取主要 type，忽略 boundary 之類的 param
    main = content_type.split(";")[0].strip().lower()
    if main != "application/json":
        raise ValidationError(
            message_zh=f"Content-Type 必須為 application/json，實際 {content_type}",
            field="content_type",
            value=content_type,
        )


# ─────────────────────────────────────────────────────────
# Sort whitelist（防 ORDER BY SQL injection）
# ─────────────────────────────────────────────────────────


class SortField(BaseModel):
    """白名單 sort field 基類。

    子類設 `allowed = {"col_a", "col_b"}`。Pydantic 驗 value 必在 allowed。
    """

    allowed: ClassVar[set[str]] = set()
    value: str

    @field_validator("value")
    @classmethod
    def _check_in_allowed(cls, v: str) -> str:
        if v not in cls.allowed:
            raise ValueError(f"排序欄位 {v!r} 不在白名單；允許：{sorted(cls.allowed)}")
        return v


class StockSortField(SortField):
    """stock_list 的 sort 白名單。"""

    allowed: ClassVar[set[str]] = {"symbol", "name", "market_cap", "volume"}


class AnalysisSortField(SortField):
    """analysis_reports 的 sort 白名單。"""

    allowed: ClassVar[set[str]] = {"created_at", "completed_at", "status", "symbol"}


class AuditSortField(SortField):
    """audit_logs 的 sort 白名單。"""

    allowed: ClassVar[set[str]] = {"timestamp", "action", "actor_id"}


# 直接函式版（給 router 用，無需建 model）：
def validate_sort_field(value: str, *, allowed: set[str]) -> str:
    """檢查 sort field 是否在白名單。"""
    if value not in allowed:
        raise ValidationError(
            message_zh=f"排序欄位 {value!r} 不在白名單",
            field="sort",
            allowed=sorted(allowed),
            value=value,
        )
    return value


def validate_sort_order(value: str) -> str:
    """sort order 只能是 'asc' / 'desc'。"""
    cleaned = value.strip().lower()
    if cleaned not in {"asc", "desc"}:
        raise ValidationError(
            message_zh=f"排序方向必須是 asc 或 desc，實際 {value!r}",
            field="order",
            value=value,
        )
    return cleaned


# ─────────────────────────────────────────────────────────
# 字串 escape（給 log / 顯示用，不是給 DB）
# ─────────────────────────────────────────────────────────

_HTML_ESCAPE_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#x27;",
}


def html_escape(value: str) -> str:
    """HTML escape 字串（給未來顯示用；DB 走 ORM 不需要）。"""
    if not isinstance(value, str):
        return value
    return "".join(_HTML_ESCAPE_MAP.get(c, c) for c in value)


__all__ = [
    "ALLOWED_CONTENT_TYPES",
    "DEFAULT_MAX_DAYS",
    "MAX_URL_LENGTH",
    "TW_SYMBOL_PATTERN",
    "US_SYMBOL_PATTERN",
    "AnalysisSortField",
    "AuditSortField",
    "SortField",
    "StockSortField",
    "html_escape",
    "validate_content_type",
    "validate_date_range",
    "validate_sort_field",
    "validate_sort_order",
    "validate_symbol",
    "validate_url_length",
    "validate_uuid",
]


# 給 timedelta import 不被 ruff 砍：
_ = timedelta
