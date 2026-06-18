"""統一的 client IP 取得。

預設只信任「直連 peer」(`request.client.host`)，避免任何人偽造 X-Forwarded-For
繞過限流 / 稽核。部署在受信任反向代理（nginx 等）後，把 `TRUST_PROXY_HEADERS=True`
並設好 `TRUSTED_PROXY_HOPS`，才會從 X-Forwarded-For 取對真實 client IP。

被 rate_limit / audit_middleware / auth_router 共用，取代直接讀 `request.client.host`。
"""

from __future__ import annotations

from starlette.requests import Request

from app.core.config import settings


def get_client_ip(request: Request) -> str:
    """取真實 client IP；回傳必為非空字串（無從判斷時回 "0.0.0.0"）。

    X-Forwarded-For 形如 ``client, proxy1, ..., proxyN``：每層代理把「收到請求的來源」
    附在尾端。把直連 peer 接在鏈尾後，從右往左跳過 `TRUSTED_PROXY_HOPS` 個受信任代理，
    取得真實 client（鏈長不足時退回鏈首）。
    """
    peer = request.client.host if request.client else None

    if not settings.TRUST_PROXY_HEADERS:
        return peer or "0.0.0.0"  # noqa: S104

    xff = request.headers.get("x-forwarded-for")
    if xff:
        chain = [p.strip() for p in xff.split(",") if p.strip()]
        if peer:
            chain.append(peer)
        hops = max(0, settings.TRUSTED_PROXY_HOPS)
        idx = len(chain) - 1 - hops
        if 0 <= idx < len(chain):
            return chain[idx]
        if chain:
            return chain[0]

    real = request.headers.get("x-real-ip")
    if real and real.strip():
        return real.strip()

    return peer or "0.0.0.0"  # noqa: S104


__all__ = ["get_client_ip"]
