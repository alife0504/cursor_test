"""Phase 10 — /api/v1/market/* 整合測試。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.integration


# ────────────────────────────────────────────────────────
# 1. 沒登入 → 401
# ────────────────────────────────────────────────────────


async def test_market_overview_requires_auth(auth_client) -> None:
    r = auth_client.get("/api/v1/market/overview")
    assert r.status_code == 401, r.text


# ────────────────────────────────────────────────────────
# 2. /overview 200 + indices
# ────────────────────────────────────────────────────────


async def test_market_overview_returns_envelope(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/market/overview?market=TW",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["market"] == "TW"
    assert "indices" in data
    assert isinstance(data["indices"], list)


# ────────────────────────────────────────────────────────
# 3. /overview 不支援 market → 422
# ────────────────────────────────────────────────────────


async def test_market_overview_bad_market_422(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/market/overview?market=JP",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 422, r.text


# ────────────────────────────────────────────────────────
# 4. /movers 200
# ────────────────────────────────────────────────────────


async def test_market_movers_returns_list(
    auth_client, make_test_user, login_helper, seed_stocks, seed_ohlcv
) -> None:
    # 即使沒資料也要回 200 + []
    await seed_stocks(
        [
            {"symbol": "97001", "market": "TWSE", "name": "movers測試"},
        ]
    )
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/market/movers?market=TW&type=gainers&limit=5",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["data"], list)


# ────────────────────────────────────────────────────────
# 5. /movers 不支援 type → 422
# ────────────────────────────────────────────────────────


async def test_market_movers_bad_type_422(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/market/movers?market=TW&type=invalid",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 422, r.text


# ────────────────────────────────────────────────────────
# 6. /institutional 美股 → 422
# ────────────────────────────────────────────────────────


async def test_market_institutional_us_returns_422(
    auth_client, make_test_user, login_helper
) -> None:
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/market/institutional?market=US",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 422, r.text


# ────────────────────────────────────────────────────────
# 7. /calendar 200 mock event
# ────────────────────────────────────────────────────────


async def test_market_calendar_returns_events(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    today = date(2026, 4, 1)
    later = today + timedelta(days=5)
    r = auth_client.get(
        f"/api/v1/market/calendar?from={today.isoformat()}&to={later.isoformat()}&market=TW",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # 月初的 1 日該有 mock event
    assert any(e["event_date"].startswith("2026-04-01") for e in data)
