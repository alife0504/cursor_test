"""RequestID middleware — 為每個 request 產生 / 傳播 trace_id。

依 PLAN.md 第 16.1 章可觀測性規範。

設計：
- 從 header X-Request-ID 取（前端或 nginx 先設）
- 若無，自動 uuid4 生成
- 用 contextvars.ContextVar 儲存 → structlog 自動帶入 log
- response 一定回 X-Request-ID header（給前端 display + 日誌串接）
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

# UUID v4 正則（用來驗證外部傳入的 X-Request-ID）
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# 接受的 X-Request-ID 最大長度（避免 log injection / DoS）
_MAX_REQUEST_ID_LENGTH = 64

REQUEST_ID_HEADER = "X-Request-ID"


def _validate_or_new_request_id(value: str | None) -> str:
    """若外部傳入合法 UUID 則用，否則生成新的 uuid4。

    安全：限長 + 限字符（避免 log injection）。
    """
    if not value:
        return str(uuid.uuid4())
    if len(value) > _MAX_REQUEST_ID_LENGTH:
        return str(uuid.uuid4())
    # 寬容：接受 UUID 或純 alphanumeric + dash + underscore（給其他 client）
    if _UUID_PATTERN.match(value):
        return value
    if re.match(r"^[A-Za-z0-9_-]+$", value):
        return value
    return str(uuid.uuid4())


class RequestIDMiddleware(BaseHTTPMiddleware):
    """從 header 取或生成 trace_id，綁到 contextvars + response header。"""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        external = request.headers.get(REQUEST_ID_HEADER)
        request_id = _validate_or_new_request_id(external)

        # 綁到 contextvars，structlog 全鏈路自動帶
        clear_contextvars()  # 防上一個 request 殘留
        bind_contextvars(trace_id=request_id)

        # 也存一份在 request.state，給 router / dependency 用
        request.state.trace_id = request_id

        try:
            response = await call_next(request)
        except Exception:
            # 即使下游 raise，也要保證 contextvars 清除（finally）
            raise
        finally:
            # response 結束清 contextvars（避免 worker reuse 時殘留）
            # 但這時 response 還沒送出，留到 response 處理完
            pass

        # 回 X-Request-ID header
        response.headers[REQUEST_ID_HEADER] = request_id

        # response 送出後清 contextvars
        # 注意：這裡清掉 contextvars 是 best-effort（async 邏輯複雜），
        # 但 RequestID middleware 是最外層，每個 request 開頭都會 clear，
        # 所以不一定需要在這裡 clear（reuse worker 時也會被覆寫）。
        return response


def get_current_trace_id() -> str:
    """從 structlog contextvars 取 trace_id，無則回 'no-trace'。"""
    ctx = structlog.contextvars.get_contextvars()
    return ctx.get("trace_id", "no-trace")


__all__ = ["REQUEST_ID_HEADER", "RequestIDMiddleware", "get_current_trace_id"]
