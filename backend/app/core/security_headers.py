"""安全 HTTP headers middleware。

依 PLAN.md 第 19 章安全架構：
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: 限制 camera / microphone / geolocation 等
- CSP：dev 寬鬆，prod 嚴格 nonce-based（P9/P18 才加 nonce）
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

# CSP dev 版（寬鬆，允許 unsafe-eval 給 Next.js dev mode）
CSP_DEV = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' ws: wss: https:; "
    "frame-ancestors 'none';"
)

# CSP prod 版（P18 才會加 nonce 替換 unsafe-inline）
# 暫時與 dev 同，P18 升級為 nonce-based
CSP_PROD = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "  # tailwind 仍需 inline style
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' wss: https:; "
    "frame-ancestors 'none';"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """為所有 response 加安全 headers。"""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        # 通用安全 headers
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), interest-cohort=()",
        )

        # CSP（依環境）
        if settings.CSP_PROD_ENABLED or settings.APP_ENV == "prod":
            response.headers.setdefault("Content-Security-Policy", CSP_PROD)
        else:
            response.headers.setdefault("Content-Security-Policy", CSP_DEV)

        # 不要 leak server header
        response.headers["Server"] = "TradingAgents-TW"

        return response


__all__ = ["CSP_DEV", "CSP_PROD", "SecurityHeadersMiddleware"]
