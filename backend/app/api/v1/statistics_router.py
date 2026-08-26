"""Phase 17 v1.1 — /api/v1/statistics/* router。

真實準確率：把分析當下的 signal，對上「分析建立之後」N 日的實際報酬計算命中率。
- 需登入；user-scoped（只統計呼叫者自己的分析）。
- RO session（純讀取彙總）。
- PIT 正確性見 app/services/statistics_service.py。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_ro_session
from app.core.response_envelope import envelope_success
from app.services.statistics_service import compute_accuracy

if TYPE_CHECKING:
    from app.models.user import User


router = APIRouter(prefix="/api/v1/statistics", tags=["statistics"])


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


@router.get("/accuracy", summary="真實命中率（signal vs N 日實際報酬，user-scoped）")
async def get_accuracy(
    request: Request,
    horizon_days: int = Query(30, ge=1, le=365, description="報酬視窗（日曆天）"),
    lookback_days: int = Query(180, ge=1, le=1095, description="回看多久內建立的分析"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_ro_session),
) -> dict:
    data = await compute_accuracy(
        session,
        user_id=user.id,
        horizon_days=horizon_days,
        lookback_days=lookback_days,
    )
    return envelope_success(data, trace_id=_trace_id(request))


__all__ = ["router"]
