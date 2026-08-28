"""Phase 11 — AnalysisService：建立分析、列表、取得、取消。

依 PLAN.md 第 14.5 章 Idempotency + 第 20.x。

注意：run_analysis 是 stub（LangGraph 在 P12+ 才真正跑），
本 service 只負責 DB 寫入 + audit + 模擬 enqueue。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.logging_config import get_logger
from app.core.market_dispatcher import MarketDispatcher, detect_region
from app.core.metrics import ANALYSIS_TOTAL
from app.models.stock import StockList
from app.repos.analysis_repo import AnalysisRepository
from app.repos.audit_repo import AuditRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.analysis import AnalysisReport, DebateMessage
    from app.models.user import User

logger = get_logger(__name__)


class AnalysisService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        dispatcher: MarketDispatcher | None = None,
    ) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.repo = AnalysisRepository(session)
        self.audit_repo = AuditRepository(session)

    async def create_analysis(
        self,
        *,
        user: User,
        symbol: str,
        analyst_types: list[str],
        llm_model: str,
        debate_rounds: int,
        risk_tolerance: str | None = None,
        risk_rounds: int = 0,
        agent_models: dict[str, str] | None = None,
        request_id: str | None = None,
    ) -> AnalysisReport:
        """新建一筆 queued 分析。寫 DB + audit；推 celery task 是 stub。

        v1.0.1：保留 analyst_types / debate_rounds / risk_tolerance 給前端還原。
        v1.1.1：持久化 risk_rounds / agent_models，供 orphan 自癒忠實還原（否則重派會靜默降級）。
        """
        market = await self._infer_market(symbol)
        report = await self.repo.create(
            user_id=user.id,
            symbol=symbol,
            market=market,
            llm_model=llm_model,
            analyst_types=analyst_types,
            debate_rounds=debate_rounds,
            risk_tolerance=risk_tolerance,
            risk_rounds=risk_rounds,
            agent_models=agent_models,
        )
        await self.audit_repo.append(
            actor_id=user.id,
            action="analysis.created",
            entity_type="analysis_report",
            entity_id=str(report.id),
            details={
                "symbol": symbol,
                "market": market,
                "analyst_types": analyst_types,
                "llm_model": llm_model,
                "debate_rounds": debate_rounds,
            },
            request_id=request_id,
        )
        await self.session.commit()

        ANALYSIS_TOTAL.labels(status="queued").inc()
        # 真正 enqueue celery 在 P12+ 才接，這裡只 log
        logger.info(
            "analysis.queued",
            analysis_id=str(report.id),
            user_id=str(user.id),
            symbol=symbol,
        )
        return report

    async def list_for_user(
        self,
        user: User,
        *,
        status: str | None = None,
        symbol: str | None = None,
        limit: int = 50,
        before_created_at: Any | None = None,
    ) -> list[AnalysisReport]:
        """role=ADMIN 看全部，其他僅看自己。"""
        user_filter: UUID | None = None if user.role.upper() == "ADMIN" else user.id
        return await self.repo.list_recent(
            user_id=user_filter,
            status=status,
            symbol=symbol,
            limit=limit,
            before_created_at=before_created_at,
        )

    async def get_for_user(self, user: User, analysis_id: UUID) -> AnalysisReport:
        row = await self.repo.get_by_id(analysis_id)
        if row is None:
            raise NotFoundError(message_zh="分析不存在", analysis_id=str(analysis_id))
        self._assert_can_read(user, row.user_id)
        return row

    async def get_debate(self, user: User, analysis_id: UUID) -> list[DebateMessage]:
        report = await self.get_for_user(user, analysis_id)
        return await self.repo.list_debate(report.id)

    async def cancel(
        self, user: User, analysis_id: UUID, *, request_id: str | None = None
    ) -> AnalysisReport:
        report = await self.get_for_user(user, analysis_id)
        if report.status in ("completed", "failed", "cancelled"):
            raise ConflictError(
                message_zh="分析已結束，無法取消",
                status=report.status,
            )
        await self.repo.update_status(analysis_id, status="cancelled")
        await self.audit_repo.append(
            actor_id=user.id,
            action="analysis.cancelled",
            entity_type="analysis_report",
            entity_id=str(analysis_id),
            details={"previous_status": report.status},
            request_id=request_id,
        )
        await self.session.commit()
        ANALYSIS_TOTAL.labels(status="cancelled").inc()
        return report

    async def delete(
        self, admin: User, analysis_id: UUID, *, request_id: str | None = None
    ) -> None:
        """admin only：徹底刪除。"""
        if admin.role.upper() != "ADMIN":
            raise ForbiddenError(message_zh="僅 admin 可刪除分析")
        report = await self.repo.get_by_id(analysis_id)
        if report is None:
            raise NotFoundError(message_zh="分析不存在", analysis_id=str(analysis_id))
        await self.repo.delete(analysis_id)
        await self.audit_repo.append(
            actor_id=admin.id,
            action="analysis.deleted",
            entity_type="analysis_report",
            entity_id=str(analysis_id),
            details={"deleted_status": report.status},
            request_id=request_id,
        )
        await self.session.commit()

    # ── helpers ──────────────────────────────────────
    async def _infer_market(self, symbol: str) -> str:
        """從 symbol 推斷 market 欄位（symbol 必須 FK 到 stock_list.symbol）。

        v1.0.1：先查 stock_list 拿真實 market（TWSE/TPEX/NYSE/NASDAQ/AMEX/OTHER）；
        - 查到 → 直接用 DB 值（解原本 OTC/AMEX 被錯標 TWSE/NASDAQ 的 bug）
        - 查不到 → 退回 region 推斷（純數字 4-6 → TW → TWSE，其餘 → NASDAQ）
          這分支也讓 stock_list 未 seed 的測試環境仍能跑

        market 是 stock_list 上的列舉 (TWSE/TPEX/NYSE/NASDAQ/AMEX/OTHER)。
        """
        try:
            stmt = select(StockList.market).where(StockList.symbol == symbol)
            row_market = (await self.session.execute(stmt)).scalar_one_or_none()
            if row_market is not None:
                return str(row_market)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "analysis.infer_market.db_lookup_failed",
                symbol=symbol,
                error=str(exc),
            )

        # fallback：region 推斷
        try:
            region = detect_region(symbol)
            return "TWSE" if str(region).upper().endswith("TW") else "NASDAQ"
        except Exception:  # pragma: no cover
            return "TWSE" if symbol.isdigit() and 4 <= len(symbol) <= 6 else "NASDAQ"

    @staticmethod
    def _assert_can_read(user: User, owner_id: UUID) -> None:
        if user.role.upper() == "ADMIN":
            return
        if user.id != owner_id:
            raise ForbiddenError(message_zh="無權檢視他人的分析")


__all__ = ["AnalysisService"]
