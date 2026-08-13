"""RequestID middleware 單元測試（依 PLAN 第 P3 章節 U）。

驗證：
- 沒帶 X-Request-ID 時自動生成 UUID
- 帶合法 UUID 時被沿用
- response 必含 X-Request-ID header
- 非法 UUID 會被替換成新生成的
- contextvars 內含 trace_id（可給 structlog 用）
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.core.request_id import REQUEST_ID_HEADER, RequestIDMiddleware

pytestmark = pytest.mark.unit


_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@pytest.fixture
def app_with_middleware() -> FastAPI:
    """建立最小 FastAPI app 含 RequestIDMiddleware。"""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/echo")
    async def echo() -> dict[str, str]:  # type: ignore[no-redef]
        from app.core.request_id import get_current_trace_id

        return {"trace_id": get_current_trace_id()}

    return app


def test_request_id_generated_when_no_header(app_with_middleware: FastAPI) -> None:
    """沒帶 header 時自動生成 UUID v4。"""
    client = TestClient(app_with_middleware)
    r = client.get("/echo")
    assert r.status_code == 200
    rid = r.headers.get(REQUEST_ID_HEADER)
    assert rid, "response 必含 X-Request-ID header"
    assert _UUID_PATTERN.match(rid), f"應為 UUID 格式：{rid}"


def test_request_id_propagated_from_header(app_with_middleware: FastAPI) -> None:
    """帶合法 UUID 時 response 沿用同一個。"""
    client = TestClient(app_with_middleware)
    rid = "12345678-1234-1234-1234-123456789abc"
    r = client.get("/echo", headers={REQUEST_ID_HEADER: rid})
    assert r.headers[REQUEST_ID_HEADER] == rid
    assert r.json()["trace_id"] == rid


def test_request_id_in_response_header(app_with_middleware: FastAPI) -> None:
    """每個 response 都必有 X-Request-ID header（基本 contract）。"""
    client = TestClient(app_with_middleware)
    for _ in range(3):
        r = client.get("/echo")
        assert REQUEST_ID_HEADER in r.headers


def test_request_id_in_log_context(app_with_middleware: FastAPI) -> None:
    """trace_id 進 contextvars，router 內 get_current_trace_id() 可取。"""
    client = TestClient(app_with_middleware)
    custom_id = "abc-123-test"
    r = client.get("/echo", headers={REQUEST_ID_HEADER: custom_id})
    # /echo router 從 contextvars 讀 trace_id
    assert r.json()["trace_id"] == custom_id


def test_request_id_format_is_uuid_when_invalid_input(app_with_middleware: FastAPI) -> None:
    """非法字符（如 SQL injection 字串）應被替換為新 UUID。"""
    client = TestClient(app_with_middleware)
    bad = "'; DROP TABLE users; --"
    r = client.get("/echo", headers={REQUEST_ID_HEADER: bad})
    rid = r.headers[REQUEST_ID_HEADER]
    assert rid != bad
    assert _UUID_PATTERN.match(rid)


def test_request_id_too_long_replaced(app_with_middleware: FastAPI) -> None:
    """過長字串（> 64 chars）應被替換。"""
    client = TestClient(app_with_middleware)
    too_long = "x" * 200
    r = client.get("/echo", headers={REQUEST_ID_HEADER: too_long})
    rid = r.headers[REQUEST_ID_HEADER]
    assert rid != too_long
    assert len(rid) <= 64


def test_request_id_alphanumeric_with_dash_accepted(app_with_middleware: FastAPI) -> None:
    """alphanumeric + - + _ 是 OK（非 UUID 也接受，給其他 client）。"""
    client = TestClient(app_with_middleware)
    custom = "service-A_request-42"
    r = client.get("/echo", headers={REQUEST_ID_HEADER: custom})
    assert r.headers[REQUEST_ID_HEADER] == custom
