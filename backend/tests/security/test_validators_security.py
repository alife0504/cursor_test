"""Phase 9 — Validators 安全測試。

依 PLAN 第 19.2 章 + 第二十八章 Q 項。

驗證攻擊路徑被阻擋：
- SQL injection in symbol
- XSS in search query（html_escape）
- Path traversal in UUID
- Oversized body → 413
- Unknown sort field → 422
"""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.core.validators import (
    html_escape,
    validate_sort_field,
    validate_symbol,
    validate_uuid,
)

pytestmark = pytest.mark.security


# ────────────────────────────────────────────────────────
# 1. SQL injection in symbol
# ────────────────────────────────────────────────────────


SQL_INJECTION_PAYLOADS = [
    "2330'; DROP TABLE users;--",
    "2330 OR 1=1",
    "2330' UNION SELECT password_hash FROM users--",
    "0050; DELETE FROM stock_list",
    "2330" + chr(0) + "EXTRA",  # null byte attempt
    "../../etc/passwd",
]


@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_sql_injection_in_symbol_blocked(payload: str) -> None:
    with pytest.raises(ValidationError):
        validate_symbol(payload)


# ────────────────────────────────────────────────────────
# 2. XSS in search query (html_escape)
# ────────────────────────────────────────────────────────


def test_xss_script_tag_escaped() -> None:
    escaped = html_escape("<script>alert('xss')</script>")
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped


def test_xss_img_onerror_escaped() -> None:
    payload = '<img src="x" onerror="alert(1)">'
    escaped = html_escape(payload)
    assert "<" not in escaped
    assert ">" not in escaped


def test_xss_unicode_payload_escaped() -> None:
    payload = "<svg/onload=alert(1)>"
    escaped = html_escape(payload)
    assert "<" not in escaped


# ────────────────────────────────────────────────────────
# 3. Path traversal in UUID
# ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "payload",
    [
        "../../etc/passwd",
        "../../../root/.ssh/id_rsa",
        "..\\..\\windows\\system32",
        "/etc/shadow",
        "00000000-0000-0000-0000-000000000000/../",
    ],
)
def test_path_traversal_in_uuid_blocked(payload: str) -> None:
    with pytest.raises(ValidationError):
        validate_uuid(payload)


# ────────────────────────────────────────────────────────
# 4. Body size → 413（integration via auth_client）
# ────────────────────────────────────────────────────────


def test_oversized_body_returns_413(auth_client) -> None:
    """送 > 1MB body 應回 413。"""
    huge = "a" * (2 * 1024 * 1024)  # 2 MB
    r = auth_client.post(
        "/api/v1/auth/login",
        headers={"Content-Type": "application/json", "Content-Length": str(len(huge))},
        content=huge,
    )
    assert r.status_code == 413, r.text
    body = r.json()
    assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"


# ────────────────────────────────────────────────────────
# 5. Unknown sort field → ValidationError (→ 422)
# ────────────────────────────────────────────────────────


def test_unknown_sort_field_blocked() -> None:
    with pytest.raises(ValidationError):
        validate_sort_field("password_hash", allowed={"symbol", "name", "market_cap"})


@pytest.mark.parametrize(
    "payload",
    [
        "password_hash",
        "1; DELETE FROM users",
        "symbol; DROP TABLE",
        "*",
        "ALL",
    ],
)
def test_sort_field_sql_injection_blocked(payload: str) -> None:
    with pytest.raises(ValidationError):
        validate_sort_field(payload, allowed={"symbol", "name"})
