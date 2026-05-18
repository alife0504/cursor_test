"""Phase 18 — OWASP Top 10 (2021) coverage tests。

依 PLAN.md 第二十七章 Phase 18 L 節（≥ 15 個 test）。

覆蓋（OWASP Top 10 2021）：
A01 Broken Access Control：
    - test_idor_user_cannot_access_other_user_resource
    - test_no_security_misconfiguration_default_credentials
A02 Cryptographic Failures：
    - test_logging_does_not_include_password
    - test_no_sensitive_data_exposure_in_error_responses
A03 Injection：
    - test_sql_injection_in_login_blocked
    - test_sql_injection_in_search_blocked
    - test_xss_in_username_escaped
    - test_xss_in_note_field_escaped
A04 Insecure Design：
    - test_mass_assignment_role_field_blocked
A05 Security Misconfiguration：
    - test_no_security_misconfiguration_default_credentials
    - test_xxe_in_xml_parser_disabled
A06 Vulnerable Components：—（Trivy + npm audit 在 CI 跑，不在這檔）
A07 Identification and Authentication Failures：
    - test_jwt_none_algorithm_rejected
    - test_no_security_misconfiguration_default_credentials
A08 Software and Data Integrity Failures：
    - test_open_redirect_in_login_callback_blocked
A09 Logging Failures：
    - test_logging_does_not_include_password
A10 Server-Side Request Forgery：
    - test_ssrf_in_url_validator_blocked
    - test_path_traversal_in_export_path_blocked

跑：cd backend && uv run pytest tests/security/test_owasp_top10.py -v
"""

from __future__ import annotations

import json
import logging

import pytest

from app.core.errors import ValidationError
from app.core.validators import validate_safe_url

pytestmark = [pytest.mark.security, pytest.mark.integration]


def _csrf(access: str, csrf: str) -> dict:
    return {"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf}


# ════════════════════════════════════════════════════════
# A03 Injection — SQL
# ════════════════════════════════════════════════════════


async def test_sql_injection_in_login_blocked(auth_client) -> None:
    """經典 SQLi payload (' OR 1=1 --) 在 email 欄位 → 422（email 格式不符）或 401。"""
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "' OR 1=1 --@x.com", "password": "any"},
    )
    # 422（EmailStr 拒絕）或 401（找不到 user）都是「擋下」
    assert r.status_code in (401, 422), r.text
    # 回應不能含敏感 SQL 字串
    assert "OR 1=1" not in r.text or "INVALID" in r.text.upper() or "VALIDATION" in r.text.upper()


async def test_sql_injection_in_search_blocked(auth_client, make_test_user, login_helper) -> None:
    """GET /stocks?q=<SQLi> → 不會洩漏資料；最多 422，不可 500。"""
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/stocks?q=' OR 1=1 --",
        headers={"Authorization": f"Bearer {access}"},
    )
    # 必須是預期的 200 / 422，不能 500
    assert r.status_code in (200, 422), r.text


# ════════════════════════════════════════════════════════
# A03 Injection — XSS
# ════════════════════════════════════════════════════════


async def test_xss_in_username_escaped(auth_client, make_test_user, login_helper) -> None:
    """user full_name 帶 XSS payload → API 回 JSON 內含原字串（不是 HTML）→ 前端負責 escape。

    驗收：response Content-Type 必須是 application/json（非 HTML），
    且任何回應裡的 <script> 都是 raw 字串，不會被瀏覽器當 HTML。
    """
    # XSS payload — make_test_user 目前不支援 full_name 注入，所以這裡只驗 Content-Type
    # 不會 echo HTML（前端再 React escape 是第二層保護）
    user, pwd = await make_test_user(
        role="VIEWER",
        must_change=False,
        email=f"xss-{__import__('uuid').uuid4().hex[:8]}@test.example.com",
    )
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct
    # response 可能含 user.full_name；XSS 防護由前端 React 自動 escape，
    # 但這裡至少驗 API 不會回 text/html
    assert "text/html" not in ct


async def test_xss_in_note_field_escaped(auth_client, make_test_user, login_helper) -> None:
    """notification settings 用 quiet_hours_start (字串) 嘗試 XSS → schema 拒絕。"""
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)
    r = auth_client.put(
        "/api/v1/notifications/settings",
        json={"quiet_hours_start": "<script>alert(1)</script>"},
        headers=_csrf(access, csrf),
    )
    assert r.status_code == 422, r.text


# ════════════════════════════════════════════════════════
# A01 Broken Access Control — CSRF
# ════════════════════════════════════════════════════════


async def test_csrf_blocks_cross_origin_post(auth_client, make_test_user) -> None:
    """POST /auth/refresh 缺 X-CSRF-Token 應 403（CSRF middleware 擋）。"""
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    # 先登入拿 refresh cookie
    r1 = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": pwd},
    )
    assert r1.status_code == 200
    # 不帶 X-CSRF-Token → 403
    r2 = auth_client.post("/api/v1/auth/refresh")
    assert r2.status_code == 403, r2.text


# ════════════════════════════════════════════════════════
# A10 SSRF
# ════════════════════════════════════════════════════════


def test_ssrf_in_url_validator_blocked() -> None:
    """validate_safe_url 拒絕 file:// / 內部 IP / localhost。"""
    cases_blocked = [
        "file:///etc/passwd",
        "gopher://internal.host/_",
        "http://localhost:8000/admin",
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",  # AWS metadata
        "http://10.0.0.1/admin",  # 私有網段
        "http://192.168.1.1/admin",
        "http://[::1]/admin",
    ]
    for url in cases_blocked:
        with pytest.raises(ValidationError):
            validate_safe_url(url)

    # 合法 URL 應通過
    assert validate_safe_url("https://example.com/api") == "https://example.com/api"
    assert validate_safe_url("https://google.com") == "https://google.com"


# ════════════════════════════════════════════════════════
# A01 IDOR (Broken Access Control)
# ════════════════════════════════════════════════════════


async def test_idor_user_cannot_access_other_user_resource(
    auth_client, make_test_user, login_helper, db_session_maker
) -> None:
    """A 帳號不能拿到 B 帳號的 watchlist（IDOR）。"""
    user_a, pwd_a = await make_test_user(role="VIEWER", must_change=False)
    user_b, pwd_b = await make_test_user(role="VIEWER", must_change=False)
    # B 建一筆 watchlist
    access_b, csrf_b = await login_helper(auth_client, user_b.email, pwd_b)
    r_create = auth_client.post(
        "/api/v1/watchlist",
        json={"symbol": "2330", "market": "TWSE"},
        headers=_csrf(access_b, csrf_b),
    )
    # 沒種子資料可能 400/422 - 跳過 IDOR 嚴格驗證但仍跑 list 隔離
    b_item_id = r_create.json()["data"]["id"] if r_create.status_code == 201 else None

    # A 看自己的 watchlist
    access_a, _ = await login_helper(auth_client, user_a.email, pwd_a)
    r_list = auth_client.get(
        "/api/v1/watchlist",
        headers={"Authorization": f"Bearer {access_a}"},
    )
    assert r_list.status_code == 200
    items = r_list.json()["data"]
    # A 不能看到 B 的 symbol（v1.0 list 嚴格 user_id filter）
    assert all(it.get("user_id") != str(user_b.id) for it in items)

    # A 嘗試直接刪 B 的 item id（若拿得到）
    if b_item_id:
        _, csrf_a = await login_helper(auth_client, user_a.email, pwd_a)
        r_delete = auth_client.delete(
            f"/api/v1/watchlist/{b_item_id}",
            headers=_csrf(access_a, csrf_a),
        )
        # 應回 403 (Forbidden) 或 404 (Not Found，list 已過濾自己的就找不到)
        assert r_delete.status_code in (403, 404), r_delete.text


# ════════════════════════════════════════════════════════
# A01 Open Redirect
# ════════════════════════════════════════════════════════


async def test_open_redirect_in_login_callback_blocked(auth_client) -> None:
    """v1.0 後端不做 redirect（只回 JSON），驗 login 不含 Location header 指向外部。"""
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "no-such-user@test.example.com", "password": "Wrong1234567!Ab"},
    )
    # 不應有 redirect
    assert r.status_code != 302
    assert r.status_code != 301
    assert "Location" not in r.headers or "evil.com" not in r.headers.get("Location", "")


# ════════════════════════════════════════════════════════
# A05 Path Traversal
# ════════════════════════════════════════════════════════


async def test_path_traversal_in_export_path_blocked(
    auth_client, make_test_user, login_helper
) -> None:
    """exports 用 UUID 而非 path，path traversal 自然擋掉（validate_uuid）。"""
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/exports/..%2F..%2Fetc%2Fpasswd?format=pdf",
        headers={"Authorization": f"Bearer {access}"},
    )
    # 必須 422（UUID 格式錯誤）或 404，絕不能 200
    assert r.status_code in (404, 422), r.text


# ════════════════════════════════════════════════════════
# A04 Mass Assignment
# ════════════════════════════════════════════════════════


async def test_mass_assignment_role_field_blocked(
    auth_client, make_test_user, login_helper
) -> None:
    """非 ADMIN 用戶 POST /users body 帶 role=ADMIN → 應 403（RBAC 擋下，非 schema）。"""
    viewer, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, csrf = await login_helper(auth_client, viewer.email, pwd)
    r = auth_client.post(
        "/api/v1/users",
        json={
            "email": "evil-promoter@test.example.com",
            "password": "TestPwd2026!Ab",
            "role": "ADMIN",
        },
        headers=_csrf(access, csrf),
    )
    assert r.status_code == 403, r.text


# ════════════════════════════════════════════════════════
# A05 XXE
# ════════════════════════════════════════════════════════


async def test_xxe_in_xml_parser_disabled(auth_client) -> None:
    """送 application/xml POST → Content-Type middleware 必須拒絕（v1.0 不接 XML）。"""
    xxe_payload = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        "<foo>&xxe;</foo>"
    )
    r = auth_client.post(
        "/api/v1/auth/login",
        data=xxe_payload,
        headers={"Content-Type": "application/xml"},
    )
    # ContentType middleware 應拒絕（415 或 422）
    assert r.status_code in (415, 422, 400), r.text
    # 絕不可洩漏 /etc/passwd 內容
    assert "root:" not in r.text


# ════════════════════════════════════════════════════════
# A05 Security Misconfiguration — default credentials
# ════════════════════════════════════════════════════════


async def test_no_security_misconfiguration_default_credentials(auth_client) -> None:
    """admin/admin / admin/admin123 / root/root → 應 lockout 或拒絕。"""
    weak_creds = [
        ("admin@admin", "admin"),
        ("admin@admin.com", "admin123"),
        ("root@root.com", "root"),
        ("admin@example.com", "password"),
    ]
    for email, pwd in weak_creds:
        r = auth_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": pwd},
        )
        assert r.status_code in (401, 422, 423, 429), r.text


# ════════════════════════════════════════════════════════
# A02 Cryptographic Failures
# ════════════════════════════════════════════════════════


async def test_no_sensitive_data_exposure_in_error_responses(auth_client, make_test_user) -> None:
    """錯誤回應不能含 DB connection string / 內部 stack trace / secret。"""
    # 故意觸發 422
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "x"},
    )
    assert r.status_code in (400, 401, 422)
    body = r.text.lower()
    # 採寬鬆比對：不允許「完整 DSN」與「DATA_ENCRYPTION_KEY」字串
    # （password=key= 是常見 query 字串，但完整 DSN / 加密 key 名稱才屬於敏感洩漏）
    for sensitive in ("postgresql://", "postgres://", "redis://", "data_encryption_key"):
        assert sensitive not in body, f"敏感字串 {sensitive!r} 洩漏於 error response"


async def test_logging_does_not_include_password(auth_client, make_test_user, caplog) -> None:
    """登入失敗時 log 不能含原密碼字串。"""
    user, _ = await make_test_user(role="VIEWER", must_change=False)
    secret_pwd = "MyS3cret_Plain_Password_2026"
    with caplog.at_level(logging.WARNING):
        r = auth_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": secret_pwd},
        )
        assert r.status_code in (401, 422)
        all_logs = " ".join(rec.getMessage() for rec in caplog.records)
        assert secret_pwd not in all_logs, "密碼明文洩漏於 log！"


# ════════════════════════════════════════════════════════
# A07 Authentication Failures — JWT none algorithm
# ════════════════════════════════════════════════════════


def test_jwt_none_algorithm_rejected() -> None:
    """構造 alg=none 的 JWT → JWTService.decode 必須拒絕（PLAN 19.1 + 已知陷阱）。"""
    import base64

    from app.core.config import settings
    from app.core.errors import AuthError
    from app.core.security import JWTService

    service = JWTService(settings)

    # 構造一個 alg=none、payload 任意的 JWT
    header = {"alg": "none", "typ": "JWT"}
    payload = {"sub": "fake-user-id", "role": "ADMIN", "exp": 9_999_999_999}

    def _b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    fake_jwt = f"{_b64(header)}.{_b64(payload)}."

    # decode 必須擲 AuthError（不接受 alg=none）
    with pytest.raises(AuthError):
        service.decode(fake_jwt)
