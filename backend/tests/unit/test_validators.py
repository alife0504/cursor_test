"""Phase 9 — validators 單元測試。

依 PLAN 第 19.2 章 + 第二十八章 K 項。
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.errors import ValidationError
from app.core.validators import (
    StockSortField,
    html_escape,
    validate_content_type,
    validate_date_range,
    validate_sort_field,
    validate_sort_order,
    validate_symbol,
    validate_url_length,
    validate_uuid,
)

pytestmark = pytest.mark.unit


# ────────────────────────────────────────────────────────
# 1. Symbol
# ────────────────────────────────────────────────────────


def test_validate_symbol_tw_normal() -> None:
    """4 碼數字 TW 普通股。"""
    assert validate_symbol("2330") == "2330"
    assert validate_symbol("0050") == "0050"


def test_validate_symbol_tw_etf_5digit() -> None:
    """4+1 ETF 格式。"""
    assert validate_symbol("00878B") == "00878B"
    assert validate_symbol("0050T") == "0050T"


def test_validate_symbol_tw_etf_6digit() -> None:
    """6 碼數字（內部 ETF 編碼）。"""
    assert validate_symbol("123456") == "123456"
    assert validate_symbol("123456A") == "123456A"


def test_validate_symbol_us_normal() -> None:
    assert validate_symbol("AAPL") == "AAPL"
    assert validate_symbol("aapl") == "AAPL"  # 自動大寫


def test_validate_symbol_us_class_share() -> None:
    assert validate_symbol("BRK.A") == "BRK.A"
    assert validate_symbol("brk.b") == "BRK.B"


def test_validate_symbol_invalid_raises() -> None:
    with pytest.raises(ValidationError) as e:
        validate_symbol("INVALID!@")
    assert "股票代號" in e.value.get_message()


def test_validate_symbol_empty_raises() -> None:
    with pytest.raises(ValidationError):
        validate_symbol("")


def test_validate_symbol_non_string_raises() -> None:
    with pytest.raises(ValidationError):
        validate_symbol(2330)  # type: ignore[arg-type]


# ────────────────────────────────────────────────────────
# 2. Date range
# ────────────────────────────────────────────────────────


def test_validate_date_range_normal() -> None:
    s = date(2024, 1, 1)
    e = date(2024, 12, 31)
    rs, re_ = validate_date_range(s, e)
    assert rs == s
    assert re_ == e


def test_validate_date_range_end_before_start_raises() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_date_range(date(2024, 5, 1), date(2024, 1, 1))
    assert "結束日期" in exc.value.get_message()


def test_validate_date_range_too_long_raises() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_date_range(date(2010, 1, 1), date(2024, 1, 1), max_days=3650)
    assert "跨度過大" in exc.value.get_message()


def test_validate_date_range_no_future_raises() -> None:
    future = date.today() + timedelta(days=30)
    with pytest.raises(ValidationError):
        validate_date_range(date.today(), future, allow_future=False)


# ────────────────────────────────────────────────────────
# 3. UUID
# ────────────────────────────────────────────────────────


def test_validate_uuid_valid() -> None:
    u = uuid4()
    parsed = validate_uuid(str(u))
    assert isinstance(parsed, UUID)
    assert parsed == u


def test_validate_uuid_invalid_raises() -> None:
    with pytest.raises(ValidationError):
        validate_uuid("not-a-uuid")


def test_validate_uuid_path_traversal_blocked() -> None:
    """嘗試 path traversal style payload。"""
    with pytest.raises(ValidationError):
        validate_uuid("../../etc/passwd")


# ────────────────────────────────────────────────────────
# 4. URL
# ────────────────────────────────────────────────────────


def test_validate_url_length_ok() -> None:
    validate_url_length("https://example.com/path?q=1")


def test_validate_url_length_too_long_raises() -> None:
    with pytest.raises(ValidationError):
        validate_url_length("a" * 3000)


# ────────────────────────────────────────────────────────
# 5. Content-Type
# ────────────────────────────────────────────────────────


def test_validate_content_type_application_json_ok() -> None:
    validate_content_type("application/json")
    validate_content_type("application/json; charset=utf-8")


def test_validate_content_type_form_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_content_type("application/x-www-form-urlencoded")


def test_validate_content_type_missing_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_content_type(None)


# ────────────────────────────────────────────────────────
# 6. Sort whitelist
# ────────────────────────────────────────────────────────


def test_sort_field_whitelist_blocks_unknown() -> None:
    """非白名單 field 應 raise ValidationError。"""
    with pytest.raises(ValidationError) as exc:
        validate_sort_field("password_hash", allowed={"symbol", "name"})
    assert "白名單" in exc.value.get_message()


def test_sort_field_whitelist_allows_known() -> None:
    assert validate_sort_field("symbol", allowed={"symbol", "name"}) == "symbol"


def test_stock_sort_field_pydantic_class() -> None:
    """Pydantic 版檢查（給 schema 用）。"""
    obj = StockSortField(value="symbol")
    assert obj.value == "symbol"

    with pytest.raises(ValueError):
        StockSortField(value="password_hash")


def test_validate_sort_order() -> None:
    assert validate_sort_order("ASC") == "asc"
    assert validate_sort_order("desc") == "desc"
    with pytest.raises(ValidationError):
        validate_sort_order("random")


# ────────────────────────────────────────────────────────
# 7. html_escape
# ────────────────────────────────────────────────────────


def test_html_escape_basic() -> None:
    assert html_escape("<script>alert(1)</script>") == ("&lt;script&gt;alert(1)&lt;/script&gt;")


def test_html_escape_no_change_for_safe_string() -> None:
    assert html_escape("hello world") == "hello world"
