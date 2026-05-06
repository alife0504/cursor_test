"""structlog JSON output 測試 — Phase 1 階段標 skip，P3 才實作。

這是 v7.0 Phase 1 的測試雛形（依 PLAN.md 第 23.5.1 章）。
P3 會建立 backend/app/core/logging_config.py 後，這些測試會被啟用。
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.skip(reason="logging_config.py 在 P3 才建立")]


def test_log_outputs_json() -> None:
    """JSON format 必須是 valid JSON。"""


def test_log_includes_trace_id_when_set() -> None:
    """有 trace_id contextvar 時 log 必含。"""


def test_password_field_masked() -> None:
    """password 欄位必須遮蔽為 ***。"""


def test_api_key_field_masked() -> None:
    """api_key 欄位必須遮蔽。"""


def test_token_field_masked() -> None:
    """token / refresh_token / authorization 必須遮蔽。"""
