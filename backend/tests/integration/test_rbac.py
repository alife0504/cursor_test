"""Phase 8 — RBAC（admin_only / require_role）整合測試。

依 PLAN 第二十七章 S 項：5 個必要測試。
test 用的 admin-only probe endpoint 由 conftest 的 `auth_app` fixture 動態 mount。
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


async def _login_get_token(auth_client, email: str, password: str) -> str:
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


# ────────────────────────────────────────────────────────
# 1. ADMIN 可進 admin-only endpoint
# ────────────────────────────────────────────────────────


async def test_admin_can_access_admin_endpoint(auth_client, make_test_user) -> None:
    user, password = await make_test_user(role="ADMIN", must_change=False)
    access = await _login_get_token(auth_client, user.email, password)
    r = auth_client.get(
        "/_test/admin-only",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "ADMIN"


# ────────────────────────────────────────────────────────
# 2. VIEWER 進 admin-only → 403
# ────────────────────────────────────────────────────────


async def test_viewer_cannot_access_admin_endpoint_403(auth_client, make_test_user) -> None:
    user, password = await make_test_user(role="VIEWER", must_change=False)
    access = await _login_get_token(auth_client, user.email, password)
    r = auth_client.get(
        "/_test/admin-only",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "FORBIDDEN"


# ────────────────────────────────────────────────────────
# 3. ANALYST 進 admin-only → 403
# ────────────────────────────────────────────────────────


async def test_analyst_cannot_access_admin_endpoint_403(auth_client, make_test_user) -> None:
    user, password = await make_test_user(role="ANALYST", must_change=False)
    access = await _login_get_token(auth_client, user.email, password)
    r = auth_client.get(
        "/_test/admin-only",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 403, r.text


# ────────────────────────────────────────────────────────
# 4. 完全沒 Authorization header → 401
# ────────────────────────────────────────────────────────


async def test_no_token_returns_401(auth_client) -> None:
    r = auth_client.get("/_test/admin-only")
    assert r.status_code == 401, r.text
    assert r.json()["error"]["code"] == "AUTH_ERROR"


# ────────────────────────────────────────────────────────
# 5. 亂寫的 token → 401
# ────────────────────────────────────────────────────────


async def test_invalid_token_returns_401(auth_client) -> None:
    r = auth_client.get(
        "/_test/admin-only",
        headers={"Authorization": "Bearer this.is.not.a.real.jwt"},
    )
    assert r.status_code == 401, r.text


async def test_missing_bearer_prefix_returns_401(auth_client) -> None:
    r = auth_client.get(
        "/_test/admin-only",
        headers={"Authorization": "abc-token"},  # 沒 Bearer
    )
    assert r.status_code == 401, r.text


# ────────────────────────────────────────────────────────
# 6. 過期 token → 401（自簽一張 ttl=-10 的）
# ────────────────────────────────────────────────────────


async def test_expired_token_returns_401(auth_client, make_test_user) -> None:
    user, _ = await make_test_user(role="ADMIN", must_change=False)
    # 直接用 JWTService 簽一張過期 token
    from app.core.config import settings
    from app.core.security import JWTService

    jwt_svc = JWTService(settings)
    token, _ = jwt_svc.create_access_token(user.id, user.role, ttl=timedelta(seconds=-10))
    r = auth_client.get(
        "/_test/admin-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401, r.text


# ────────────────────────────────────────────────────────
# 7. /me 任何登入角色都可以
# ────────────────────────────────────────────────────────


async def test_me_endpoint_works_for_any_authenticated(auth_client, make_test_user) -> None:
    user, password = await make_test_user(role="VIEWER", must_change=False)
    access = await _login_get_token(auth_client, user.email, password)
    r = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # 確認不洩漏 password_hash
    assert "password_hash" not in data
    assert data["email"].lower() == user.email.lower()


# 抑制 unused import
_ = uuid4
