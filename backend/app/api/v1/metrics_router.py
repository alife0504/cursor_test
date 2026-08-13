"""Phase 11 — /metrics router（Prometheus format, admin only）。

依 PLAN.md 第 16.1 章三大支柱 + 第 16.2 章 metrics 範例。

注意：
- 路徑不在 /api/v1 下，直接用 /metrics（Prometheus 慣例）
- AuditMiddleware 已 exclude /metrics（避免每次抓 metrics 都寫 audit → 遞迴）
- response 是 Prometheus text exposition format（不是 envelope）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.api.dependencies import admin_only

if TYPE_CHECKING:
    from app.models.user import User


router = APIRouter(tags=["metrics"])


@router.get("/metrics", summary="Prometheus metrics（admin only）")
async def metrics(
    _admin: User = Depends(admin_only),
) -> Response:
    body = generate_latest()
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)


__all__ = ["router"]
