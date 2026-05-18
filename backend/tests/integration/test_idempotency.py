"""Phase 11 — Idempotency-Key 整合測試。

涵蓋：
1. 缺 Idempotency-Key → 422
2. 同 key + 同 body → 第二次回相同 analysis_id（不建第二筆）
3. 同 key + 不同 body → 409 IDEMPOTENCY_CONFLICT
4. 不同 user 用同 key → 各建一筆（per-user namespace）
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


def _payload(symbol: str = "2330") -> dict:
    return {
        "symbol": symbol,
        "analyst_types": ["market"],
        "llm_model": "gemini-2.0-flash",
        "debate_rounds": 0,
    }


async def test_idempotency_missing_header_422(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    user, pwd = await make_test_user(role="ADMIN", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)

    r = auth_client.post(
        "/api/v1/analysis",
        json=_payload(),
        headers={"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf},
    )
    assert r.status_code == 422, r.text
    assert "Idempotency-Key" in r.text or "VALIDATION" in r.text.upper()


async def test_idempotency_same_key_returns_same_id(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    user, pwd = await make_test_user(role="ADMIN", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)

    key = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {access}",
        "X-CSRF-Token": csrf,
        "Idempotency-Key": key,
    }
    r1 = auth_client.post("/api/v1/analysis", json=_payload(), headers=headers)
    assert r1.status_code == 201, r1.text
    id1 = r1.json()["data"]["analysis_id"]

    r2 = auth_client.post("/api/v1/analysis", json=_payload(), headers=headers)
    assert r2.status_code == 200, r2.text
    id2 = r2.json()["data"]["analysis_id"]
    assert id1 == id2


async def test_idempotency_same_key_diff_body_conflict(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    await seed_stocks(
        [
            {"symbol": "2330", "market": "TWSE", "name": "台積電"},
            {"symbol": "2317", "market": "TWSE", "name": "鴻海"},
        ]
    )
    user, pwd = await make_test_user(role="ADMIN", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)

    key = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {access}",
        "X-CSRF-Token": csrf,
        "Idempotency-Key": key,
    }
    r1 = auth_client.post("/api/v1/analysis", json=_payload("2330"), headers=headers)
    assert r1.status_code == 201, r1.text

    r2 = auth_client.post("/api/v1/analysis", json=_payload("2317"), headers=headers)
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


async def test_idempotency_per_user_namespace(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    """同一個 key 不同 user 互不干擾。

    注意：TestClient cookie jar 共用，第二次 login 會蓋掉第一次的 csrf cookie。
    所以兩次 POST 之間順序：u1 login → u1 POST → u2 login → u2 POST。
    """
    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    u1, p1 = await make_test_user(role="ADMIN", must_change=False)
    u2, p2 = await make_test_user(role="ADMIN", must_change=False)

    key = str(uuid.uuid4())

    a1, c1 = await login_helper(auth_client, u1.email, p1)
    r1 = auth_client.post(
        "/api/v1/analysis",
        json=_payload(),
        headers={"Authorization": f"Bearer {a1}", "X-CSRF-Token": c1, "Idempotency-Key": key},
    )
    assert r1.status_code == 201, r1.text

    # 清掉 cookie 並重新 login u2
    auth_client.cookies.clear()
    a2, c2 = await login_helper(auth_client, u2.email, p2)
    r2 = auth_client.post(
        "/api/v1/analysis",
        json=_payload(),
        headers={"Authorization": f"Bearer {a2}", "X-CSRF-Token": c2, "Idempotency-Key": key},
    )
    assert r2.status_code == 201, r2.text
    assert r1.json()["data"]["analysis_id"] != r2.json()["data"]["analysis_id"]
