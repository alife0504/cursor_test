"""HTTP metrics middleware — 觀測每個 request 的耗時 / 方法 / 狀態 / 路由。

- 用「路由樣板」路徑（如 /api/v1/analysis/{analysis_id}）而非原始 URL，避免
  per-id 造成 Prometheus label 基數爆炸。
- 排除 /metrics 本身與 health 探針，避免自我觀測噪音。
- backend 為單一 uvicorn worker → in-memory histogram 一致正確。
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import HTTP_REQUEST_DURATION

_EXCLUDE_PREFIXES = ("/metrics", "/health")


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in _EXCLUDE_PREFIXES):
            return await call_next(request)

        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            # 路由樣板（避免 per-id 高基數）；比對不到就歸為 "unmatched"
            route = request.scope.get("route")
            tmpl = getattr(route, "path", None) or "unmatched"
            HTTP_REQUEST_DURATION.labels(
                method=request.method, status=str(status), path=tmpl
            ).observe(elapsed)
