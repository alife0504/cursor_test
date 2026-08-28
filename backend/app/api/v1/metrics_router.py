"""Phase 11 / v1.1 — /metrics router（Prometheus format）。

認證：靜態 METRICS_TOKEN（供 Prometheus 抓取；JWT 會過期不適合 scrape）。
- 設定 settings.METRICS_TOKEN 後，需帶 `Authorization: Bearer <token>`。
- 未設定 → /metrics 停用（回 401），避免無認證外洩運維指標。

抓取流程：先 `collect_runtime_metrics(session)` 即時把業務 gauge 從 DB/redis/pool 設好
（跨程序一致），再 `generate_latest()` 輸出（含 HTTP middleware 累積的 histogram）。

注意：
- 路徑不在 /api/v1 下，直接用 /metrics（Prometheus 慣例）
- AuditMiddleware 已 exclude /metrics（避免每次抓 metrics 都寫 audit → 遞迴）
"""

from __future__ import annotations

import contextlib
import secrets

from fastapi import APIRouter, Depends, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.core.config import settings
from app.core.database import get_ro_session
from app.core.errors import AuthError
from app.core.metrics import collect_runtime_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics", summary="Prometheus metrics（靜態 token 認證）")
async def metrics(
    request: Request,
    session: AsyncSession = Depends(get_ro_session),
) -> Response:
    token = settings.METRICS_TOKEN.get_secret_value() if settings.METRICS_TOKEN else None
    if not token:
        raise AuthError(message_zh="metrics 未啟用（未設定 METRICS_TOKEN）")
    # 常數時間比對，避免裸 `!=` 的逐位元組短路形成 timing side-channel（與 CSRF/密碼比對一致）。
    if not secrets.compare_digest(request.headers.get("Authorization", ""), f"Bearer {token}"):
        raise AuthError(message_zh="metrics token 無效")

    # 抓取時即時把業務 gauge 從 DB/redis/pool 設好（失敗不擋 process 指標輸出）
    with contextlib.suppress(Exception):
        await collect_runtime_metrics(session)

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


__all__ = ["router"]
