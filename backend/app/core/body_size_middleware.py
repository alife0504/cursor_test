"""Phase 9 — Body size middleware（防 OOM / DoS）。

依 PLAN.md 第 19.2 章：POST/PUT body 1 MB 上限。

設計：
- 只擋 Content-Length（streaming / chunked 無 Content-Length 不在此擋；
  P11+ 可加 streaming-aware 版本，但目前 v1.0 業務沒有 stream upload）。
- 命中時 raise TooLargeError（→ 413）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging_config import get_logger
from app.core.request_id import get_current_trace_id
from app.core.response_envelope import envelope_error

logger = get_logger(__name__)

DEFAULT_MAX_BODY_BYTES = 1024 * 1024  # 1 MB


class BodySizeMiddleware(BaseHTTPMiddleware):
    """檢查 Content-Length；超過 max_bytes 立即 raise（不讀完 body）。"""

    def __init__(self, app, *, max_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 只檢查可能有 body 的 method
        if request.method.upper() in {"POST", "PUT", "PATCH"}:
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    cl = int(content_length)
                except ValueError:
                    cl = 0
                if cl > self.max_bytes:
                    logger.warning(
                        "body_size.rejected",
                        path=request.url.path,
                        method=request.method,
                        content_length=cl,
                        max_bytes=self.max_bytes,
                    )
                    trace_id = getattr(request.state, "trace_id", None) or get_current_trace_id()
                    return JSONResponse(
                        status_code=413,
                        content=envelope_error(
                            code="PAYLOAD_TOO_LARGE",
                            message=f"請求內容過大（最多 {self.max_bytes} bytes）",
                            trace_id=trace_id,
                            details={
                                "max_bytes": self.max_bytes,
                                "actual_bytes": cl,
                            },
                        ),
                    )
        return await call_next(request)


__all__ = ["DEFAULT_MAX_BODY_BYTES", "BodySizeMiddleware"]
