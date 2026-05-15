"""Phase 11 — /api/v1/orders/* schemas。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class OrderSummary(BaseSchema):
    """訂單列表元素。"""

    id: UUID
    user_id: UUID
    analysis_id: UUID | None = None
    symbol: str
    market: str
    side: str
    qty: int
    target_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    status: str
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    version: int
    created_at: datetime
    expires_at: datetime | None = None


class OrderApproveRequest(BaseSchema):
    """POST /orders/{id}/approve body（可選 notes + expected version）。"""

    notes: str | None = Field(default=None, max_length=500)
    expected_version: int | None = Field(default=None, ge=1)


class OrderRejectRequest(BaseSchema):
    """POST /orders/{id}/reject body。"""

    reason: str = Field(min_length=1, max_length=500)
    expected_version: int | None = Field(default=None, ge=1)


__all__ = [
    "OrderApproveRequest",
    "OrderRejectRequest",
    "OrderSummary",
]
