"""Phase 10 — /api/v1/stocks/* 整合測試。

需 docker compose up（DB + Redis）。每個 test 建獨立 stock + user 並自動清理。
"""

from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.integration


# ────────────────────────────────────────────────────────
# 1. 未登入 → 401
# ────────────────────────────────────────────────────────


async def test_stocks_requires_auth(auth_client) -> None:
    r = auth_client.get("/api/v1/stocks?market=TW")
    assert r.status_code == 401, r.text
    assert r.json()["error"]["code"] == "AUTH_ERROR"


# ────────────────────────────────────────────────────────
# 2. 列表 200 + envelope（空 stock_list 也回 200）
# ────────────────────────────────────────────────────────


async def test_stocks_list_returns_envelope(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks(
        [
            {"symbol": "99001", "market": "TWSE", "name": "測試A"},
            {"symbol": "99002", "market": "TWSE", "name": "測試B"},
        ]
    )
    user, pwd = await make_test_user(role="VIEWER", must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)

    r = auth_client.get(
        "/api/v1/stocks?market=TW&q=99&limit=5",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    assert "meta" in body
    assert "pagination" in body
    assert isinstance(body["data"], list)
    syms = [r["symbol"] for r in body["data"]]
    assert "99001" in syms or "99002" in syms


# ────────────────────────────────────────────────────────
# 3. 列表 q 過濾
# ────────────────────────────────────────────────────────


async def test_stocks_list_keyword_filter(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks(
        [
            {"symbol": "99010", "market": "TWSE", "name": "ABC"},
            {"symbol": "99011", "market": "TWSE", "name": "XYZ"},
        ]
    )
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/stocks?market=TW&q=ABC&limit=10",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    syms = {row["symbol"] for row in r.json()["data"]}
    assert "99010" in syms
    assert "99011" not in syms


# ────────────────────────────────────────────────────────
# 4. cursor pagination：取兩頁
# ────────────────────────────────────────────────────────


async def test_stocks_cursor_pagination(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    syms = [f"9911{i}" for i in range(5)]  # 99110~99114
    await seed_stocks([{"symbol": s, "market": "TWSE", "name": s} for s in syms])
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)

    r1 = auth_client.get(
        "/api/v1/stocks?market=TW&q=9911&limit=2",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert len(body1["data"]) == 2
    assert body1["pagination"]["has_more"] is True
    assert body1["pagination"]["next_cursor"] is not None

    cursor = body1["pagination"]["next_cursor"]
    r2 = auth_client.get(
        f"/api/v1/stocks?market=TW&q=9911&limit=2&cursor={cursor}",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    # 兩頁不應重複
    first_syms = {x["symbol"] for x in body1["data"]}
    second_syms = {x["symbol"] for x in body2["data"]}
    assert first_syms.isdisjoint(second_syms)


# ────────────────────────────────────────────────────────
# 5. 詳情 200
# ────────────────────────────────────────────────────────


async def test_stocks_detail_returns_data(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks([{"symbol": "99201", "market": "TWSE", "name": "測試詳情"}])
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/stocks/99201",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["symbol"] == "99201"
    assert data["market"] == "TWSE"


# ────────────────────────────────────────────────────────
# 6. 詳情 404
# ────────────────────────────────────────────────────────


async def test_stocks_detail_not_found(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/stocks/9999",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ────────────────────────────────────────────────────────
# 7. OHLCV — Decimal 為字串 + 範圍正確
# ────────────────────────────────────────────────────────


async def test_stocks_ohlcv_decimal_as_string(
    auth_client, make_test_user, login_helper, seed_stocks, seed_ohlcv
) -> None:
    await seed_stocks([{"symbol": "99301", "market": "TWSE", "name": "測試OHLCV"}])
    await seed_ohlcv(
        [
            {
                "symbol": "99301",
                "date": date(2026, 4, 1),
                "open": "100.0",
                "high": "110.0",
                "low": "95.0",
                "close": "105.5",
                "volume": 1000,
            },
            {
                "symbol": "99301",
                "date": date(2026, 4, 2),
                "open": "105.0",
                "high": "115.0",
                "low": "100.0",
                "close": "112.0",
                "volume": 2000,
            },
        ]
    )
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/stocks/99301/ohlcv?start=2026-04-01&end=2026-04-30",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data) == 2
    # Decimal 應為字串
    assert isinstance(data[0]["close"], str)
    assert data[0]["close"] == "105.500000" or data[0]["close"].startswith("105.5")


# ────────────────────────────────────────────────────────
# 8. OHLCV 起迄反向 → 422
# ────────────────────────────────────────────────────────


async def test_stocks_ohlcv_invalid_range_422(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks([{"symbol": "99302", "market": "TWSE", "name": "範圍測試"}])
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/stocks/99302/ohlcv?start=2026-04-30&end=2026-04-01",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ────────────────────────────────────────────────────────
# 9. Symbol 格式錯誤 → 422
# ────────────────────────────────────────────────────────


async def test_stocks_symbol_bad_format_422(auth_client, make_test_user, login_helper) -> None:
    user, pwd = await make_test_user(must_change=False)
    access, _ = await login_helper(auth_client, user.email, pwd)
    r = auth_client.get(
        "/api/v1/stocks/NOT_A_SYMBOL!!!",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
