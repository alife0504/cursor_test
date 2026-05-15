"""Phase 10 — cursor 單元測試（pytest，不需 docker）。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.core.cursor import Cursor, build_page_response, clamp_limit
from app.core.errors import ValidationError


def test_cursor_roundtrip_simple_dict() -> None:
    encoded = Cursor.encode(after_symbol="2330", page=2)
    assert isinstance(encoded, str)
    decoded = Cursor.decode(encoded)
    assert decoded == {"after_symbol": "2330", "page": 2}


def test_cursor_handles_uuid_and_datetime() -> None:
    uid = UUID("11111111-2222-3333-4444-555555555555")
    when = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    encoded = Cursor.encode(user_id=uid, since=when, price=Decimal("123.45"))
    decoded = Cursor.decode(encoded)
    assert decoded["user_id"] == str(uid)
    assert decoded["since"].startswith("2026-01-01")
    assert decoded["price"] == "123.45"


def test_cursor_handles_date() -> None:
    encoded = Cursor.encode(d=date(2026, 4, 30))
    decoded = Cursor.decode(encoded)
    assert decoded["d"] == "2026-04-30"


def test_cursor_decode_empty_returns_empty_dict() -> None:
    assert Cursor.decode(None) == {}
    assert Cursor.decode("") == {}


def test_cursor_decode_invalid_base64_raises() -> None:
    with pytest.raises(ValidationError) as exc:
        Cursor.decode("not_base64!!!")
    assert "cursor" in exc.value.get_message()


def test_cursor_decode_invalid_json_raises() -> None:
    # 一個合法 base64 但解碼出來不是 JSON
    import base64

    bad = base64.urlsafe_b64encode(b"not-json{").decode("ascii").rstrip("=")
    with pytest.raises(ValidationError):
        Cursor.decode(bad)


def test_cursor_decode_non_dict_raises() -> None:
    """合法 base64 + 合法 JSON 但 payload 是 list → 應拒絕。"""
    encoded = Cursor.encode  # placeholder to silence linter
    _ = encoded
    import base64
    import json

    bad = base64.urlsafe_b64encode(json.dumps([1, 2, 3]).encode()).decode("ascii").rstrip("=")
    with pytest.raises(ValidationError):
        Cursor.decode(bad)


def test_clamp_limit_default_and_bounds() -> None:
    assert clamp_limit(None) == 50
    assert clamp_limit(None, default=10) == 10
    assert clamp_limit(0) == 1
    assert clamp_limit(101) == 100
    assert clamp_limit(50) == 50


def test_build_page_response_no_more() -> None:
    page = build_page_response([1, 2, 3], limit=50, next_cursor_kwargs=None)
    assert page == {"next_cursor": None, "limit": 50, "has_more": False}


def test_build_page_response_has_more_encodes_cursor() -> None:
    page = build_page_response(
        [{"symbol": "2330"}, {"symbol": "2454"}],
        limit=2,
        next_cursor_kwargs={"after_symbol": "2454"},
    )
    assert page["limit"] == 2
    assert page["has_more"] is True
    assert isinstance(page["next_cursor"], str)
    # 解回去應得到相同 kwargs
    assert Cursor.decode(page["next_cursor"]) == {"after_symbol": "2454"}
