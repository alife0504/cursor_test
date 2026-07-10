"""/api/v1/portfolio/* router — 權威持倉讀取（第二輪審計 S07/S08 修補）。

前端原以「最新 100 筆 APPROVED 訂單客戶端重算」推導持倉，>100 單帳號會截斷最舊開倉單
→ 淨額失真、甚至憑空空單。改由此端點直接回 portfolio_positions（核准時已淨額合併的權威來源），
per-user 隔離。
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_rw_session
from app.core.response_envelope import envelope_success
from app.schemas.orders import PortfolioPositionOut
from app.services.order_service import OrderService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])

_CENT = Decimal("0.01")


@router.get("/positions", summary="目前持倉（權威來源，per-user）")
async def list_positions(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    service = OrderService(session)
    positions = await service.list_positions(user)
    items = []
    for p in positions:
        qty = int(p.qty)
        avg = Decimal(p.avg_cost)
        items.append(
            PortfolioPositionOut(
                symbol=p.symbol,
                market=p.market,
                qty=qty,
                avg_cost=avg,
                # 成本基礎用 |qty|：空單（qty<0）不在「累計成本」欄顯示負數
                total_cost=(avg * abs(qty)).quantize(_CENT),
                realized_pnl=Decimal(p.realized_pnl).quantize(_CENT),
                opened_at=p.opened_at,
            ).model_dump(mode="json")
        )
    return envelope_success(items, trace_id=getattr(request.state, "trace_id", "") or "")


__all__ = ["router"]
