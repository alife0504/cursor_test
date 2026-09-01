"""系統健康 / 資料新鮮度 —— 供前端全站警示 banner 與 admin pipeline 頁消費。

委託人收尾要求「發現異常，網頁要顯示警示」。本端點回傳各關鍵資料表的新鮮度與整體狀態，
前端 SystemHealthBanner 依 status(warn/critical) 顯示紅/黃警示條，讓使用者不會在「看似正常
實則過期」的資料上做判斷。認證使用者皆可讀（新鮮度非敏感資訊）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_ro_session
from app.core.response_envelope import envelope_success
from app.models.user import User
from app.services.freshness_service import compute_freshness

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/data-freshness", summary="資料新鮮度 / 系統健康（認證使用者）")
async def data_freshness(
    request: Request,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_ro_session),
) -> dict[str, Any]:
    """回各關鍵表最新資料日、落後天數與整體 status(ok/warn/critical)。前端警示 banner 用。

    與全 API 一致採 envelope_success 包裝（前端讀 res.data.data）。
    """
    trace_id = getattr(request.state, "trace_id", "")
    return envelope_success(await compute_freshness(session), trace_id=trace_id)


__all__ = ["router"]
