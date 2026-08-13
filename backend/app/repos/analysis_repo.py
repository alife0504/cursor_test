"""Phase 11 — AnalysisRepository。

依 PLAN.md 第 15.2 章樂觀鎖 + 第 14.9 章 LangGraph state。

職責：
- 列表 / 取單筆 / 更新 status / 寫 debate_history
- list_for_user：viewer 看自己；admin 看全部
- get_by_id 永遠帶 row（router 自己做 IDOR check）
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from app.models.analysis import AnalysisReport, DebateMessage
from app.repos.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AnalysisRepository(BaseRepository):
    """analysis_reports + debate_history 的 CRUD wrapper。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── 寫入 ─────────────────────────────────────────
    async def create(
        self,
        *,
        user_id: UUID,
        symbol: str,
        market: str,
        llm_model: str | None = None,
        analyst_types: list[str] | None = None,
        debate_rounds: int | None = None,
        risk_tolerance: str | None = None,
    ) -> AnalysisReport:
        """建立一筆 queued 分析（caller 負責 commit）。

        v1.0.1：保留 analyst_types / debate_rounds / risk_tolerance 給前端還原節點圖。
        """
        report = AnalysisReport(
            user_id=user_id,
            symbol=symbol,
            market=market,
            status="queued",
            llm_model=llm_model,
            analyst_types=analyst_types,
            debate_rounds=debate_rounds,
            risk_tolerance=risk_tolerance,
        )
        self.session.add(report)
        await self.session.flush()
        return report

    async def update_status(
        self,
        analysis_id: UUID,
        *,
        status: str,
        error_msg: str | None = None,
    ) -> AnalysisReport | None:
        """更新 status（caller 負責 commit）。"""
        row = await self.get_by_id(analysis_id)
        if row is None:
            return None
        row.status = status
        if error_msg is not None:
            row.error_msg = error_msg
        await self.session.flush()
        return row

    # ── 查詢 ─────────────────────────────────────────
    async def get_by_id(self, analysis_id: UUID) -> AnalysisReport | None:
        stmt = select(AnalysisReport).where(AnalysisReport.id == analysis_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_recent(
        self,
        *,
        user_id: UUID | None = None,
        status: str | None = None,
        symbol: str | None = None,
        limit: int = 50,
        before_created_at: Any | None = None,
    ) -> list[AnalysisReport]:
        """列表（cursor 用 before_created_at）。

        user_id=None → 不過濾（給 admin 用）。
        """
        stmt = select(AnalysisReport)
        if user_id is not None:
            stmt = stmt.where(AnalysisReport.user_id == user_id)
        if status:
            stmt = stmt.where(AnalysisReport.status == status)
        if symbol:
            stmt = stmt.where(AnalysisReport.symbol == symbol)
        if before_created_at is not None:
            stmt = stmt.where(AnalysisReport.created_at < before_created_at)
        stmt = stmt.order_by(AnalysisReport.created_at.desc(), AnalysisReport.id.desc()).limit(
            limit
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_debate(self, analysis_id: UUID, *, limit: int = 100) -> list[DebateMessage]:
        stmt = (
            select(DebateMessage)
            .where(DebateMessage.analysis_id == analysis_id)
            .order_by(DebateMessage.round_num.asc(), DebateMessage.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, analysis_id: UUID) -> bool:
        row = await self.get_by_id(analysis_id)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        return True


__all__ = ["AnalysisRepository"]
