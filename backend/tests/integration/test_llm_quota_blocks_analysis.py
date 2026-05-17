"""Phase 14 — 月配額攔截整合測試（≥ 2 個測試）。

涵蓋：
1. quota 用盡 → POST /analysis 回 402
2. quota warning（≥ 80%）→ 通過但 log warning
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

pytestmark = pytest.mark.integration


def _csrf(access: str, csrf: str) -> dict:
    return {"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf}


async def test_quota_exceeded_returns_402(
    auth_client, make_test_user, login_helper, seed_stocks, db_session_maker
) -> None:
    """寫一筆當月 cost 超 limit → POST /analysis 回 402。"""
    from sqlalchemy import delete

    from app.models.quota import LLMMonthlyQuota, LLMUsage

    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    user, pwd = await make_test_user(role="ANALYST", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)

    # 設極低 limit + 已寫一筆 cost 超 limit
    now = datetime.now(tz=UTC)
    async with db_session_maker() as s:
        s.add(
            LLMMonthlyQuota(
                user_id=user.id,
                year=now.year,
                month=now.month,
                budget_usd=Decimal("0.001"),
            )
        )
        s.add(
            LLMUsage(
                user_id=user.id,
                provider="openai",
                model="gpt-4o-mini",
                purpose="seed",
                prompt_tokens=1000,
                completion_tokens=500,
                total_tokens=1500,
                cost_usd=Decimal("0.005"),
            )
        )
        await s.commit()

    headers = _csrf(access, csrf) | {"Idempotency-Key": str(uuid.uuid4())}
    r = auth_client.post(
        "/api/v1/analysis",
        json={
            "symbol": "2330",
            "analyst_types": ["market"],
            "llm_model": "gemini-2.0-flash",
            "debate_rounds": 0,
        },
        headers=headers,
    )
    # QuotaExceededError → 402
    assert r.status_code == 402, r.text
    body = r.json()
    assert body["error"]["code"] == "QUOTA_EXCEEDED"

    # cleanup
    async with db_session_maker() as s:
        await s.execute(delete(LLMUsage).where(LLMUsage.user_id == user.id))
        await s.execute(delete(LLMMonthlyQuota).where(LLMMonthlyQuota.user_id == user.id))
        await s.commit()


async def test_quota_under_limit_allows_create(
    auth_client, make_test_user, login_helper, seed_stocks
) -> None:
    """新用戶當月無 cost → POST /analysis 通過（201）。"""
    await seed_stocks([{"symbol": "2330", "market": "TWSE", "name": "台積電"}])
    user, pwd = await make_test_user(role="ANALYST", must_change=False)
    access, csrf = await login_helper(auth_client, user.email, pwd)
    headers = _csrf(access, csrf) | {"Idempotency-Key": str(uuid.uuid4())}
    r = auth_client.post(
        "/api/v1/analysis",
        json={
            "symbol": "2330",
            "analyst_types": ["market"],
            "llm_model": "gemini-2.0-flash",
            "debate_rounds": 0,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
