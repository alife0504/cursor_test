"""Phase 9 — CSRF middleware（double-submit cookie pattern）。

依 PLAN.md 第 19.1 章 + 第 19.7 章。

設計：
- 只對 state-changing methods（POST/PUT/PATCH/DELETE）驗證
- 排除清單：login / password-reset / password-reset-confirm
  （這些 endpoint 還沒登入沒 cookie；CSRF 保護不適用）
- 同 origin policy：cookie 與 header 都來自同源；攻擊者跨網域無法讀對方 cookie
- 比對用 `secrets.compare_digest`（constant-time，防 timing attack）
- 失敗 → raise ForbiddenError（403）
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.csrf import verify_csrf_token
from app.core.logging_config import get_logger
from app.core.request_id import get_current_trace_id
from app.core.response_envelope import envelope_error

logger = get_logger(__name__)

# 不需要 CSRF 驗證的 POST 路徑（用戶還沒有 cookie）
CSRF_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/password-reset",
        "/api/v1/auth/password-reset/confirm",
    }
)

# 只對這些 method 驗證
CSRF_PROTECTED_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


class CSRFMiddleware(BaseHTTPMiddleware):
    """double-submit cookie CSRF 驗證。

    僅在 state-changing methods + 非豁免路徑時驗證。
    """

    def __init__(
        self,
        app,
        *,
        exempt_paths: frozenset[str] = CSRF_EXEMPT_PATHS,
        exempt_path_prefixes: tuple[str, ...] = ("/health/", "/docs", "/openapi.json", "/_test/"),
    ) -> None:
        super().__init__(app)
        self.exempt_paths = exempt_paths
        self.exempt_path_prefixes = exempt_path_prefixes

    def _is_exempt(self, path: str) -> bool:
        if path in self.exempt_paths:
            return True
        return any(path.startswith(p) for p in self.exempt_path_prefixes)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method.upper() not in CSRF_PROTECTED_METHODS:
            return await call_next(request)

        if self._is_exempt(request.url.path):
            return await call_next(request)

        header_token = request.headers.get(CSRF_HEADER_NAME)
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

        if not verify_csrf_token(header_token, cookie_token):
            logger.warning(
                "csrf.rejected",
                path=request.url.path,
                method=request.method,
                has_header=bool(header_token),
                has_cookie=bool(cookie_token),
            )
            trace_id = getattr(request.state, "trace_id", None) or get_current_trace_id()
            return JSONResponse(
                status_code=403,
                content=envelope_error(
                    code="FORBIDDEN",
                    message="CSRF 驗證失敗",
                    trace_id=trace_id,
                ),
            )

        return await call_next(request)


__all__ = [
    "CSRF_COOKIE_NAME",
    "CSRF_EXEMPT_PATHS",
    "CSRF_HEADER_NAME",
    "CSRF_PROTECTED_METHODS",
    "CSRFMiddleware",
]
