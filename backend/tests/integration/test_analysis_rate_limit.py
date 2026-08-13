"""L5 分析建立限流整合測試（PLAN 19.3 L5：10/hr/user）。

涵蓋：
1. 超過 L5 限制 → POST /analysis 回 429 RATE_LIMITED
2. Idempotent replay 不扣 L5 次數（replay 在限流檢查之前短路）
"""

from __future__ import annotations

import uuid

import pytest

import app.core.rate_limit as rate_limit_module
from app.core.rate_limit import RateRule

pytestmark = pytest.mark.integration


def _csrf(access: str, csrf: str) -> dict:
    return {"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf}


def _payload(symbol: str = "2330") -> dict:
    return {
        "symbol": symbol,
        "analyst_types": ["market"],
        "llm_model": "gemini-2.0-flash",
        "debate_rounds": 0,
    }


async def test_l5_rate_limit_blocks_burst_create(
    auth_client, make_test_user, login_helper, seed_stocks, monkeypatch
) -> None:
    """壓低 L5 limit=2 → 第 3 次建立回 429（防突發爆量繞過月配額 TOCTOU）。"""
    monkeypatch.setattr(
        rate_limit_module,
        "L5_ANALYSIS",
        RateRule(layer="L5", key_prefix="rate:analysis:", limit=2, window_sec=3600),
    )

    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    user, pwd = await make_test_user(role="ANALYST", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)

    for _ in range(2):
        headers = _csrf(access, csrf) | {"Idempotency-Key": str(uuid.uuid4())}
        r = auth_client.post("/api/v1/analysis", json=_payload(), headers=headers)
        assert r.status_code == 201, r.text

    headers = _csrf(access, csrf) | {"Idempotency-Key": str(uuid.uuid4())}
    r = auth_client.post("/api/v1/analysis", json=_payload(), headers=headers)
    assert r.status_code == 429, r.text
    assert r.json()["error"]["code"] == "RATE_LIMITED"


async def test_l5_idempotent_replay_does_not_consume_quota(
    auth_client, make_test_user, login_helper, seed_stocks, monkeypatch
) -> None:
    """同一 Idempotency-Key replay N 次不扣 L5 次數（limit=1 仍全部 200）。"""
    monkeypatch.setattr(
        rate_limit_module,
        "L5_ANALYSIS",
        RateRule(layer="L5", key_prefix="rate:analysis:", limit=1, window_sec=3600),
    )

    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    user, pwd = await make_test_user(role="ANALYST", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)

    headers = _csrf(access, csrf) | {"Idempotency-Key": str(uuid.uuid4())}
    r1 = auth_client.post("/api/v1/analysis", json=_payload(), headers=headers)
    assert r1.status_code == 201, r1.text

    # 同 key replay：走 idempotency cache（200），不應觸發 429
    r2 = auth_client.post("/api/v1/analysis", json=_payload(), headers=headers)
    assert r2.status_code == 200, r2.text
    r3 = auth_client.post("/api/v1/analysis", json=_payload(), headers=headers)
    assert r3.status_code == 200, r3.text
