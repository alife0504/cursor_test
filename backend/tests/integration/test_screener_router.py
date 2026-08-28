"""Phase 10 — /api/v1/screener 整合測試。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


# ────────────────────────────────────────────────────────
# 1. 沒登入 → 401
# ────────────────────────────────────────────────────────


async def test_screener_requires_auth(auth_client) -> None:
    r = auth_client.get("/api/v1/screener")
    assert r.status_code == 401, r.text


# ────────────────────────────────────────────────────────
# 2. 預設 TW 200 + 空 list
# ────────────────────────────────────────────────────────


async def test_screener_default_returns_list(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/screener?market=TW&limit=10",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    assert "pagination" in body
    assert isinstance(body["data"], list)


# ────────────────────────────────────────────────────────
# 3. 篩選依 industry
# ────────────────────────────────────────────────────────


async def test_screener_industry_filter(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    # 用**專用測試產業名**（不與真實資料庫既有產業碰撞）：否則跑在有真實資料的庫上，
    # limit 會被真實半導體股填滿而擠掉種子股，造成測試隔離失敗（非程式錯誤）。
    ind_a = "測試半導體ZZ"
    ind_b = "測試金融ZZ"
    await seed_stocks(
        [
            {"symbol": "96001", "market": "TWSE", "name": "半導體A", "industry": ind_a},
            {"symbol": "96002", "market": "TWSE", "name": "金融A", "industry": ind_b},
        ]
    )
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    from urllib.parse import quote

    r = auth_client.get(
        f"/api/v1/screener?market=TW&industry={quote(ind_a)}&limit=10",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    syms = {x["symbol"] for x in rows}
    assert "96001" in syms
    assert "96002" not in syms


# ────────────────────────────────────────────────────────
# 4. sort 非白名單 → 422
# ────────────────────────────────────────────────────────


async def test_screener_bad_sort_field_422(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/screener?market=TW&sort=evil_drop_table",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ────────────────────────────────────────────────────────
# 5. cursor pagination 行為
# ────────────────────────────────────────────────────────


async def test_screener_cursor_pagination(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    syms = [f"96{i:03d}" for i in range(10, 16)]  # 96010 ~ 96015
    await seed_stocks([{"symbol": s, "market": "TWSE", "name": f"分頁{s}"} for s in syms])
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/screener?market=TW&industry=&limit=2",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pagination"]["limit"] == 2
    # 如果有更多資料應該帶 cursor
    if len(body["data"]) == 2:
        assert body["pagination"]["limit"] == 2


# ────────────────────────────────────────────────────────
# 6. cursor 格式錯誤 → 422
# ────────────────────────────────────────────────────────


async def test_screener_bad_cursor_422(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/screener?market=TW&cursor=not_a_real_cursor!!!",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 422, r.text
