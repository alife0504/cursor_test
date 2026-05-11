"""structlog JSON output + 敏感欄位遮蔽（依 PLAN 第 P3 章節 S）。

P3 已實作 logging_config.py，本檔升級為實際測試（取代 P1 skip stub）。
"""

from __future__ import annotations

import io
import json
import logging
from contextlib import redirect_stdout

import pytest
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.logging_config import _mask_sensitive_processor, configure_logging, get_logger

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_contextvars():
    """每個 test 開始前清 contextvars。"""
    clear_contextvars()
    yield
    clear_contextvars()


def test_log_outputs_json() -> None:
    """LOG_FORMAT=json 時 output 是合法 JSON。"""
    configure_logging()
    log = get_logger("test")
    buf = io.StringIO()
    with redirect_stdout(buf):
        log.info("test.event", user_id="user-123", amount=42)
    output = buf.getvalue().strip()
    assert output, "log 應有輸出"
    last_line = output.splitlines()[-1]
    parsed = json.loads(last_line)
    assert parsed["event"] == "test.event"
    assert parsed["user_id"] == "user-123"
    assert parsed["amount"] == 42


def test_log_includes_trace_id_when_set() -> None:
    """有 contextvars trace_id 時 log 自動帶。"""
    configure_logging()
    bind_contextvars(trace_id="trace-abc-123")
    log = get_logger("test")
    buf = io.StringIO()
    with redirect_stdout(buf):
        log.info("with.trace")
    parsed = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert parsed["trace_id"] == "trace-abc-123"


def test_password_field_masked() -> None:
    """password 欄位被遮蔽。"""
    event_dict = {"event": "login", "password": "supersecret"}
    out = _mask_sensitive_processor(None, "info", event_dict)
    assert out["password"] == "***REDACTED***"


def test_api_key_field_masked() -> None:
    """api_key / google_api_key 等欄位被遮蔽。"""
    event_dict = {
        "event": "test",
        "api_key": "sk-xxxx",
        "google_api_key": "AIzaXXXX",
        "openai_api_key": "sk-yyyy",
    }
    out = _mask_sensitive_processor(None, "info", event_dict)
    assert out["api_key"] == "***REDACTED***"
    assert out["google_api_key"] == "***REDACTED***"
    assert out["openai_api_key"] == "***REDACTED***"


def test_token_field_masked() -> None:
    """token / refresh_token / authorization 全部遮蔽。"""
    event_dict = {
        "event": "auth",
        "token": "jwt-xxx",
        "refresh_token": "rt-yyy",
        "authorization": "Bearer abc",
        "user_password": "should-also-mask",
    }
    out = _mask_sensitive_processor(None, "info", event_dict)
    assert out["token"] == "***REDACTED***"
    assert out["refresh_token"] == "***REDACTED***"
    assert out["authorization"] == "***REDACTED***"
    # 含 "password" 子字串的也要遮
    assert out["user_password"] == "***REDACTED***"


def test_normal_field_not_masked() -> None:
    """非敏感欄位（user_id / event / amount）不該遮。"""
    event_dict = {"event": "test", "user_id": "u1", "amount": 100}
    out = _mask_sensitive_processor(None, "info", event_dict)
    assert out["user_id"] == "u1"
    assert out["amount"] == 100
    assert out["event"] == "test"


def test_log_level_filter() -> None:
    """LOG_LEVEL=INFO 時 DEBUG 不會輸出。"""
    configure_logging()
    log = get_logger("test")
    buf = io.StringIO()
    with redirect_stdout(buf):
        log.debug("debug.event")
        log.info("info.event")
    output = buf.getvalue()
    # debug.event 不該出現（INFO level）
    assert "debug.event" not in output
    assert "info.event" in output


def test_get_logger_returns_bound_logger() -> None:
    """get_logger() 應回 BoundLogger（可 chain bind/info/etc）。"""
    log = get_logger()
    assert hasattr(log, "info")
    assert hasattr(log, "warning")
    assert hasattr(log, "bind")


# 抑制 unused import warning（用於 isolation）
_ = (logging, structlog)
