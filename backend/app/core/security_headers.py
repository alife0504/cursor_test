"""安全 HTTP headers middleware（P18 升級加 nonce）。

依 PLAN.md 第 19 / 19.7 章：
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: 限制 camera / microphone / geolocation 等
- CSP：dev 寬鬆（允許 unsafe-eval 給 Next.js HMR）；prod 嚴格 nonce-based

P18 新增：
- request.state.csp_nonce 每 request 唯一
- prod 模式下把 nonce 嵌入 `script-src 'nonce-<value>'`
- 同時保留 `'strict-dynamic'` 允許動態 script 載入
- dev 模式不啟 nonce（用 CSP_DEV）

前端使用 nonce 方式：
- Next.js `next/script` 提供 `nonce={getServerNonce()}`
- inline script 用 `<Script nonce={nonce} dangerouslySetInnerHTML={...} />`
"""

from __future__ import annotations

import secrets
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


def build_prod_csp(nonce: str) -> str:
    """Prod 模式 nonce-based CSP（PLAN 19.7）。

    要點：
    - `script-src 'self' 'nonce-<n>' 'strict-dynamic'`：只允許含 nonce 的 inline script，
      且該 script 動態 import 的 script 也算可信
    - `style-src 'self' 'unsafe-inline'`：Tailwind 仍需 inline style（不可避）
    - frame-ancestors 'none'：嚴禁 iframe 嵌入（防 clickjacking）
    """
    return (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' 'strict-dynamic'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' wss: https:; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "object-src 'none';"
    )


# 保留 P9 / 早期版的 CSP_PROD（不含 nonce）作為 export，給 test 對比用
CSP_PROD_STATIC = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' wss: https:; "
    "frame-ancestors 'none';"
)


def _generate_nonce() -> str:
    """產生 base64-url-safe 16-byte nonce（22 字元）。"""
    return secrets.token_urlsafe(16)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """為所有 response 加安全 headers + 在 request.state 設定 CSP nonce。"""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 每 request 唯一 nonce（即使 dev 也設定，方便測試一致性）
        nonce = _generate_nonce()
        request.state.csp_nonce = nonce

        response = await call_next(request)

        # 通用安全 headers
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), interest-cohort=()",
        )

        # CSP（依環境決定）
        if settings.CSP_PROD_ENABLED or settings.APP_ENV == "prod":
            response.headers["Content-Security-Policy"] = build_prod_csp(nonce)
            # 給前端讀（next.config / SSR）
            response.headers.setdefault("X-CSP-Nonce", nonce)
        else:
            response.headers.setdefault("Content-Security-Policy", CSP_DEV)

        # 不要 leak server header
        response.headers["Server"] = "TradingAgents-TW"

        return response


__all__ = [
    "CSP_DEV",
    "CSP_PROD_STATIC",
    "SecurityHeadersMiddleware",
    "build_prod_csp",
]
