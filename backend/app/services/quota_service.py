"""LLM 月配額服務 — PLAN 第 19.3 章 L6 ($50/user/month)。

依據：
- 主成本表：`llm_usage`（每次 LLM 呼叫）
- 用戶月預算：`llm_monthly_quota` 表（per-user override；無 row → 用全域 default）
- 全域 default：`settings.LLM_MONTHLY_BUDGET_USD_DEFAULT`（預設 Decimal('50.00')）

設計重點：
- `check_user_can_analyze(user_id)`：查當月累計 cost vs limit，回 (allowed, used, limit)。
  - 累計來源：sum(llm_usage.cost_usd) WHERE user_id=? AND created_at >= 當月 1 號 00:00 UTC。
  - 不依賴 `llm_monthly_quota.used_usd`（該欄位是 cache，可能落後）。
- `record_usage(...)`：寫一筆 llm_usage（caller 控制 transaction）。
- race condition：兩個 request 同時通過 check 是已知陷阱（PLAN 14）；不嚴格鎖。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import ro_session, rw_session
from app.core.logging_config import get_logger
from app.models.quota import LLMMonthlyQuota, LLMUsage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class QuotaService:
    """LLM 月配額 service（每月 1 號 00:00 UTC reset）。"""

    @staticmethod
    def _current_month_start() -> datetime:
        """當月 1 號 00:00 UTC。"""
        now = datetime.now(tz=UTC)
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async def get_user_budget(
        self, user_id: UUID, *, session: AsyncSession | None = None
    ) -> Decimal:
        """取得用戶當月預算（per-user override 優先；無 → 全域 default）。

        Args:
            session: 若給則用注入的 session（測試用，避免跨 loop）；None → 開 ro_session。
        """
        now = self._current_month_start()
        if session is not None:
            row = (
                await session.execute(
                    select(LLMMonthlyQuota.budget_usd).where(
                        LLMMonthlyQuota.user_id == user_id,
                        LLMMonthlyQuota.year == now.year,
                        LLMMonthlyQuota.month == now.month,
                    )
                )
            ).scalar_one_or_none()
        else:
            async with ro_session() as s:
                row = (
                    await s.execute(
                        select(LLMMonthlyQuota.budget_usd).where(
                            LLMMonthlyQuota.user_id == user_id,
                            LLMMonthlyQuota.year == now.year,
                            LLMMonthlyQuota.month == now.month,
                        )
                    )
                ).scalar_one_or_none()
        if row is not None:
            return Decimal(row)
        return Decimal(settings.LLM_MONTHLY_BUDGET_USD_DEFAULT)

    async def get_user_used(self, user_id: UUID, *, session: AsyncSession | None = None) -> Decimal:
        """取得用戶當月已使用 cost (USD)。"""
        month_start = self._current_month_start()
        if session is not None:
            used = await session.scalar(
                select(func.coalesce(func.sum(LLMUsage.cost_usd), 0)).where(
                    LLMUsage.user_id == user_id,
                    LLMUsage.created_at >= month_start,
                )
            )
        else:
            async with ro_session() as s:
                used = await s.scalar(
                    select(func.coalesce(func.sum(LLMUsage.cost_usd), 0)).where(
                        LLMUsage.user_id == user_id,
                        LLMUsage.created_at >= month_start,
                    )
                )
        return Decimal(used or 0)

    async def check_user_can_analyze(
        self, user_id: UUID, *, session: AsyncSession | None = None
    ) -> tuple[bool, Decimal, Decimal]:
        """檢查用戶當月配額是否還夠。

        Args:
            session: 給則用該 session；None → 開 ro_session。
                router 場景應該傳入；celery / standalone 場景可不傳。

        Returns:
            (allowed, used_usd, limit_usd)：allowed = used < limit。
        """
        used = await self.get_user_used(user_id, session=session)
        limit = await self.get_user_budget(user_id, session=session)
        allowed = used < limit

        if not allowed:
            logger.warning(
                "quota.exceeded",
                user_id=str(user_id),
                used=str(used),
                limit=str(limit),
            )
        elif limit > 0 and (used / limit) >= Decimal("0.8"):
            logger.warning(
                "quota.warning_80pct",
                user_id=str(user_id),
                used=str(used),
                limit=str(limit),
                used_pct=str((used / limit * Decimal("100")).quantize(Decimal("0.1"))),
            )
        return allowed, used, limit

    async def record_usage(
        self,
        *,
        user_id: UUID | str | None,
        analysis_id: UUID | str | None,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal,
        purpose: str | None = None,
        latency_ms: int | None = None,
        succeeded: bool = True,
        error_msg: str | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        """寫一筆 LLMUsage。

        Args:
            session: 若給 → 用該 session（不 commit；caller 控制）；
                若 None → 自己開 rw_session 並 commit。
        """
        row = LLMUsage(
            user_id=_uuid_or_none(user_id),
            analysis_id=_uuid_or_none(analysis_id),
            provider=provider[:30],
            model=model[:100],
            purpose=purpose[:50] if purpose else None,
            prompt_tokens=int(input_tokens),
            completion_tokens=int(output_tokens),
            total_tokens=int(input_tokens) + int(output_tokens),
            cost_usd=Decimal(cost_usd),
            latency_ms=latency_ms,
            succeeded=succeeded,
            error_msg=error_msg[:500] if error_msg else None,
        )
        if session is not None:
            session.add(row)
            await session.flush()
            logger.info(
                "quota.record_usage",
                provider=provider,
                model=model,
                cost_usd=str(cost_usd),
                in_session=True,
            )
            return
        async with rw_session() as s:
            s.add(row)
            await s.commit()
        logger.info(
            "quota.record_usage",
            provider=provider,
            model=model,
            cost_usd=str(cost_usd),
            in_session=False,
        )


def _uuid_or_none(v: UUID | str | None) -> UUID | None:
    if v is None:
        return None
    if isinstance(v, UUID):
        return v
    try:
        return UUID(str(v))
    except (ValueError, TypeError):
        return None


__all__ = ["QuotaService"]
