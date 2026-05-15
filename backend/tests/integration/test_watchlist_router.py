"""Phase 10 — /api/v1/watchlist/* 整合測試。

涵蓋：CRUD + UNIQUE 衝突 + CSRF + 越權 + auth。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _csrf_headers(access: str, csrf: str) -> dict:
    return {"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf}


# ────────────────────────────────────────────────────────
# 1. 沒登入 → 401
# ────────────────────────────────────────────────────────


async def test_watchlist_requires_auth(auth_client) -> None:
    r = auth_client.get("/api/v1/watchlist")
    assert r.status_code == 401, r.text


# ────────────────────────────────────────────────────────
# 2. 新增成功 + envelope
# ────────────────────────────────────────────────────────


async def test_watchlist_add_success(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks([{"symbol": "98001", "market": "TWSE", "name": "watchlist測試A"}])
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)

    r = auth_client.post(
        "/api/v1/watchlist",
        json={"symbol": "98001", "market": "TWSE", "notes": "test"},
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["symbol"] == "98001"
    assert data["market"] == "TWSE"
    assert data["user_id"] == str(user.id)


# ────────────────────────────────────────────────────────
# 3. 重複加同一支 → 409
# ────────────────────────────────────────────────────────


async def test_watchlist_duplicate_returns_409(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks([{"symbol": "98002", "market": "TWSE", "name": "重複測試"}])
    user, pwd = await make_test_user(must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)

    payload = {"symbol": "98002", "market": "TWSE"}
    r1 = auth_client.post(
        "/api/v1/watchlist",
        json=payload,
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r1.status_code == 201, r1.text

    r2 = auth_client.post(
        "/api/v1/watchlist",
        json=payload,
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] == "CONFLICT"


# ────────────────────────────────────────────────────────
# 4. 缺 CSRF → 403
# ────────────────────────────────────────────────────────


async def test_watchlist_csrf_missing_returns_403(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks([{"symbol": "98003", "market": "TWSE", "name": "CSRF測試"}])
    user, pwd = await make_test_user(must_change=False)
    access, _csrf = await login_helper(auth_client, user.email, pwd)

    r = auth_client.post(
        "/api/v1/watchlist",
        json={"symbol": "98003", "market": "TWSE"},
        headers={"Authorization": f"Bearer {access}"},  # 沒帶 X-CSRF-Token
    )
    assert r.status_code == 403, r.text


# ────────────────────────────────────────────────────────
# 5. 列出我的 watchlist
# ────────────────────────────────────────────────────────


async def test_watchlist_list_returns_added_items(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks(
        [
            {"symbol": "98010", "market": "TWSE", "name": "列表A"},
            {"symbol": "98011", "market": "TWSE", "name": "列表B"},
        ]
    )
    user, pwd = await make_test_user(must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)
    for sym in ("98010", "98011"):
        r = auth_client.post(
            "/api/v1/watchlist",
            json={"symbol": sym, "market": "TWSE"},
            headers=_csrf_headers(access, csrf),
            cookies={"csrf_token": csrf},
        )
        assert r.status_code == 201, r.text

    r = auth_client.get(
        "/api/v1/watchlist",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    syms = {row["symbol"] for row in r.json()["data"]}
    assert {"98010", "98011"}.issubset(syms)


# ────────────────────────────────────────────────────────
# 6. PATCH 更新欄位
# ────────────────────────────────────────────────────────


async def test_watchlist_patch_updates_fields(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks([{"symbol": "98020", "market": "TWSE", "name": "patch測試"}])
    user, pwd = await make_test_user(must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)
    r1 = auth_client.post(
        "/api/v1/watchlist",
        json={"symbol": "98020", "market": "TWSE"},
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    wid = r1.json()["data"]["id"]

    r2 = auth_client.patch(
        f"/api/v1/watchlist/{wid}",
        json={"tag": "短線", "sort_order": 99},
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["tag"] == "短線"
    assert r2.json()["data"]["sort_order"] == 99


# ────────────────────────────────────────────────────────
# 7. DELETE 成功 + 再列已不存在
# ────────────────────────────────────────────────────────


async def test_watchlist_delete_removes_item(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks([{"symbol": "98030", "market": "TWSE", "name": "刪除測試"}])
    user, pwd = await make_test_user(must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)
    r1 = auth_client.post(
        "/api/v1/watchlist",
        json={"symbol": "98030", "market": "TWSE"},
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    wid = r1.json()["data"]["id"]

    r2 = auth_client.delete(
        f"/api/v1/watchlist/{wid}",
        headers=_csrf_headers(access, csrf),
        cookies={"csrf_token": csrf},
    )
    assert r2.status_code == 200, r2.text

    r3 = auth_client.get(
        "/api/v1/watchlist",
        headers={"Authorization": f"Bearer {access}"},
    )
    syms = {row["symbol"] for row in r3.json()["data"]}
    assert "98030" not in syms


# ────────────────────────────────────────────────────────
# 8. 不能刪別人的 watchlist
# ────────────────────────────────────────────────────────


async def test_watchlist_cannot_delete_others(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks([{"symbol": "98040", "market": "TWSE", "name": "越權測試"}])
    user_a, pwd_a = await make_test_user(must_change=False)
    user_b, pwd_b = await make_test_user(must_change=False)

    access_a, csrf_a = await login_helper(auth_client, user_a.email, pwd_a)
    r1 = auth_client.post(
        "/api/v1/watchlist",
        json={"symbol": "98040", "market": "TWSE"},
        headers=_csrf_headers(access_a, csrf_a),
        cookies={"csrf_token": csrf_a},
    )
    assert r1.status_code == 201
    wid = r1.json()["data"]["id"]

    access_b, csrf_b = await login_helper(auth_client, user_b.email, pwd_b)
    r2 = auth_client.delete(
        f"/api/v1/watchlist/{wid}",
        headers=_csrf_headers(access_b, csrf_b),
        cookies={"csrf_token": csrf_b},
    )
    assert r2.status_code == 404, r2.text
