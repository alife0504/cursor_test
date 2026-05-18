"""QuotaService 整合測試 — 月配額 ($50/user/month, PLAN 19.3 L6)。

QuotaService 接受 session injection（session=...）避免跨 event loop pool 衝突。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.services.quota_service import QuotaService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_user_under_limit_allowed(db_session_maker, make_test_user) -> None:
    user, _ = await make_test_user()
    svc = QuotaService()
    async with db_session_maker() as s:
        allowed, used, limit = await svc.check_user_can_analyze(user.id, session=s)
    assert allowed is True
    assert used == Decimal("0")
    assert limit > Decimal("0")


@pytest.mark.asyncio
async def test_user_at_limit_blocked(db_session_maker, make_test_user) -> None:
    """寫一筆 cost 超預算 → allowed = False。"""
    from sqlalchemy import delete

    from app.models.quota import LLMMonthlyQuota, LLMUsage

    user, _ = await make_test_user()
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
                purpose="test",
                prompt_tokens=1000,
                completion_tokens=500,
                total_tokens=1500,
                cost_usd=Decimal("0.01"),
            )
        )
        await s.commit()

    svc = QuotaService()
    async with db_session_maker() as s:
        allowed, used, limit = await svc.check_user_can_analyze(user.id, session=s)
    assert allowed is False
    assert used >= Decimal("0.01")
    assert limit == Decimal("0.001")

    async with db_session_maker() as s:
        await s.execute(delete(LLMUsage).where(LLMUsage.user_id == user.id))
        await s.execute(delete(LLMMonthlyQuota).where(LLMMonthlyQuota.user_id == user.id))
        await s.commit()


@pytest.mark.asyncio
async def test_user_uses_default_limit(db_session_maker, make_test_user) -> None:
    """無 per-user override → 用 settings.LLM_MONTHLY_BUDGET_USD_DEFAULT。"""
    from app.core.config import settings

    user, _ = await make_test_user()
    svc = QuotaService()
    async with db_session_maker() as s:
        _, _, limit = await svc.check_user_can_analyze(user.id, session=s)
    assert limit == Decimal(settings.LLM_MONTHLY_BUDGET_USD_DEFAULT)


@pytest.mark.asyncio
async def test_record_usage_writes_db(db_session_maker, make_test_user) -> None:
    """record_usage 用注入 session 寫一筆 LLMUsage。"""
    from sqlalchemy import delete, select

    from app.models.quota import LLMUsage

    user, _ = await make_test_user()
    svc = QuotaService()
    async with db_session_maker() as s:
        await svc.record_usage(
            user_id=user.id,
            analysis_id=None,
            provider="google",
            model="gemini-2.0-flash",
            input_tokens=100,
            output_tokens=50,
            cost_usd=Decimal("0.0001"),
            purpose="unit_test",
            session=s,
        )
        await s.commit()

    async with db_session_maker() as s:
        rows = (
            (await s.execute(select(LLMUsage).where(LLMUsage.user_id == user.id))).scalars().all()
        )
        assert len(rows) == 1
        assert rows[0].provider == "google"
        assert rows[0].total_tokens == 150
        await s.execute(delete(LLMUsage).where(LLMUsage.user_id == user.id))
        await s.commit()


@pytest.mark.asyncio
async def test_quota_isolated_to_current_month(db_session_maker, make_test_user) -> None:
    """跨月：寫一筆 created_at 是上月的 cost → 不該計入本月 used。"""
    from sqlalchemy import delete

    from app.models.quota import LLMUsage

    user, _ = await make_test_user()
    now = datetime.now(tz=UTC)
    if now.month == 1:
        last_month = now.replace(year=now.year - 1, month=12, day=15)
    else:
        last_month = now.replace(month=now.month - 1, day=15)
    async with db_session_maker() as s:
        s.add(
            LLMUsage(
                user_id=user.id,
                provider="openai",
                model="gpt-4o-mini",
                purpose="old",
                prompt_tokens=10000,
                completion_tokens=5000,
                total_tokens=15000,
                cost_usd=Decimal("99.99"),
                created_at=last_month,
            )
        )
        await s.commit()
    svc = QuotaService()
    async with db_session_maker() as s:
        _, used_now, _ = await svc.check_user_can_analyze(user.id, session=s)
    assert used_now < Decimal("99.99")

    async with db_session_maker() as s:
        await s.execute(delete(LLMUsage).where(LLMUsage.user_id == user.id))
        await s.commit()
