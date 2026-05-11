"""Response envelope 測試（依 PLAN 第 P3 章節 T）。

P3 已實作 response_envelope.py，本檔升級為實際測試（取代 P1 skip stub）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.response_envelope import envelope_error, envelope_success

pytestmark = pytest.mark.unit


def test_success_envelope_has_data_meta() -> None:
    """SuccessEnvelope 必含 data + meta（trace_id / version / timestamp）。"""
    body = envelope_success({"key": "value"}, trace_id="trace-1")
    assert "data" in body
    assert body["data"] == {"key": "value"}
    assert "meta" in body
    assert body["meta"]["trace_id"] == "trace-1"
    assert body["meta"]["version"] == "v1"
    assert "timestamp" in body["meta"]


def test_error_envelope_format() -> None:
    """ErrorEnvelope 必含 error.code / message / trace_id。"""
    body = envelope_error(
        code="NOT_FOUND",
        message="用戶不存在",
        trace_id="trace-2",
    )
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "用戶不存在"
    assert body["error"]["trace_id"] == "trace-2"


def test_pagination_in_envelope() -> None:
    """Pagination 應在 envelope.pagination（非在 data 內）。"""
    pagination = {"next_cursor": "abc", "limit": 50, "has_more": True}
    body = envelope_success([1, 2, 3], trace_id="t", pagination=pagination)
    assert body["pagination"] == pagination
    # pagination 不該污染 data
    assert body["data"] == [1, 2, 3]


def test_envelope_serializes_decimal_as_string() -> None:
    """Decimal 欄位應序列化為字串（依 PLAN 15.6 章）。"""
    body = envelope_success({"price": Decimal("12.34")}, trace_id="t")
    assert body["data"]["price"] == "12.34"
    assert isinstance(body["data"]["price"], str)


def test_envelope_serializes_decimal_in_nested_dict() -> None:
    """巢狀 dict 中的 Decimal 也要序列化。"""
    data = {"order": {"price": Decimal("100.50"), "qty": 10}}
    body = envelope_success(data, trace_id="t")
    assert body["data"]["order"]["price"] == "100.50"


def test_envelope_serializes_decimal_in_list() -> None:
    """List 中的 Decimal 也要序列化。"""
    body = envelope_success([Decimal("1.1"), Decimal("2.2")], trace_id="t")
    assert body["data"] == ["1.1", "2.2"]


def test_envelope_serializes_datetime_as_iso() -> None:
    """datetime 序列化為 ISO 8601 UTC 字串。"""
    dt_aware = datetime(2026, 5, 6, 10, 0, 0, tzinfo=UTC)
    body = envelope_success({"created_at": dt_aware}, trace_id="t")
    # ISO 格式應含 'T' 分隔 + Z 或 +00:00
    iso = body["data"]["created_at"]
    assert "2026-05-06T10:00:00" in iso


def test_envelope_naive_datetime_assumed_utc() -> None:
    """timezone-naive datetime 應被假定為 UTC。"""
    dt_naive = datetime(2026, 5, 6, 10, 0, 0)
    body = envelope_success({"ts": dt_naive}, trace_id="t")
    iso = body["data"]["ts"]
    assert "2026-05-06T10:00:00" in iso
    assert "+00:00" in iso or "Z" in iso


def test_error_envelope_with_details() -> None:
    """ErrorEnvelope 帶 details 應正確序列化。"""
    body = envelope_error(
        code="VALIDATION_ERROR",
        message="輸入錯誤",
        trace_id="t",
        details={"field": "email", "reason": "format"},
    )
    assert body["error"]["details"] == {"field": "email", "reason": "format"}


def test_error_envelope_without_details() -> None:
    """ErrorEnvelope 不帶 details 時不應有 details key。"""
    body = envelope_error(code="X", message="msg", trace_id="t")
    assert "details" not in body["error"]
