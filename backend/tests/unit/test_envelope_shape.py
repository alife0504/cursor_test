"""API Envelope 格式測試 — Phase 1 階段標 skip，P3 才實作。

這是 v7.0 Phase 1 的測試雛形（依 PLAN.md 第 17.3 章 + 第 23.5.1 章）。
P3 會建立 backend/app/core/response_envelope.py 後，這些測試會被啟用。
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.skip(reason="response_envelope.py 在 P3 才建立")]


def test_success_envelope_has_data_meta() -> None:
    """SuccessEnvelope 必須含 data + meta（trace_id, version, timestamp）。"""


def test_error_envelope_format() -> None:
    """ErrorEnvelope 必須含 error.code, error.message, error.trace_id。"""


def test_pagination_in_envelope() -> None:
    """Pagination 應在 envelope.pagination（非在 data 內）。"""


def test_envelope_serializes_decimal_as_string() -> None:
    """Decimal 欄位序列化為字串（依第 15.6 章）。"""


def test_envelope_serializes_datetime_as_iso() -> None:
    """datetime 序列化為 ISO 8601 UTC 字串。"""
