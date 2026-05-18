"""Phase 8 — CSRF token (double-submit cookie pattern)。

依 PLAN.md 第 19.1 章：refresh 路徑必須帶 X-CSRF-Token + SameSite=Strict cookie。

設計（double-submit cookie）：
1. login 成功時同時種 httpOnly refresh_token + 非 httpOnly csrf_token cookie。
2. 前端 JS 讀 csrf_token cookie，再把同樣的值塞進 `X-CSRF-Token` header 發 refresh request。
3. 後端比對 header == cookie。攻擊者無法跨網域讀對方的 csrf cookie，所以 CSRF 攻擊失敗。
"""

from __future__ import annotations

import secrets

CSRF_TOKEN_BYTES = 32
"""urlsafe base64 後約 43 字元。"""


def generate_csrf_token() -> str:
    """隨機產生 CSRF token（cryptographically secure）。"""
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def verify_csrf_token(req_token: str | None, cookie_token: str | None) -> bool:
    """constant-time 比對 header 與 cookie 的 CSRF token。

    任一為空或不等長都回 False；不洩漏訊息。
    """
    if not req_token or not cookie_token:
        return False
    return secrets.compare_digest(req_token, cookie_token)


__all__ = ["CSRF_TOKEN_BYTES", "generate_csrf_token", "verify_csrf_token"]
