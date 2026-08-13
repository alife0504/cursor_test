"""Phase 11 — /api/v1/reports/* router。

GET /api/v1/reports/{id}：與 /api/v1/analysis/{id} 類似但放完整 report_md。
（前端設計上 analysis 是「請求」、reports 是「最終文章」）

注意：本 Phase 兩者後端共用 AnalysisReport 表，本 router 只是給前端語意上的 alias。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_rw_session
from app.core.response_envelope import envelope_success
from app.core.validators import validate_uuid
from app.schemas.analysis import AnalysisDetail
from app.services.analysis_service import AnalysisService

if TYPE_CHECKING:
    from app.models.user import User


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


@router.get("/{report_id}", summary="取得分析報告完整內容（含 report_md）")
async def get_report(
    report_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = AnalysisService(session)
    uid = validate_uuid(report_id)
    report = await service.get_for_user(user, uid)
    return envelope_success(
        AnalysisDetail.model_validate(report).model_dump(mode="json"),
        trace_id=_trace_id(request),
    )


__all__ = ["router"]
