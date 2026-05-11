"""統一 HTTP client wrapper（httpx + tenacity retry）。

依 PLAN.md 第 14.2 章 retry 規範：
- 3 次嘗試
- exponential 2-30s + jitter 0-2s
- 只 retry 4xx 中的 429 / 5xx / connection error / timeout

使用方式：
    async with get_async_client(name="finmind") as client:
        resp = await client.get(url)
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from app.core.config import settings
from app.core.errors import ExternalServiceError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# 可 retry 的例外（其他例外不重試，避免重試成本浪費）
_RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    httpx.ReadError,
)


def _default_timeout() -> httpx.Timeout:
    """依 settings 產生 httpx Timeout 物件。"""
    return httpx.Timeout(
        connect=settings.HTTP_CONNECT_TIMEOUT_S,
        read=settings.HTTP_READ_TIMEOUT_S,
        write=settings.HTTP_READ_TIMEOUT_S,
        pool=settings.HTTP_TOTAL_TIMEOUT_S,
    )


def get_async_client(
    *,
    name: str,
    base_url: str = "",
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    limits: httpx.Limits | None = None,
) -> httpx.AsyncClient:
    """建立 AsyncClient。

    Args:
        name: 用途識別（用於 log + circuit breaker 命名，如 "finmind"、"yfinance"）
        base_url: 預設 base_url
        headers: 預設 headers
        timeout: 自訂 timeout（None = 用 settings 預設）
        limits: 連線池限制

    Returns:
        AsyncClient（必須 async with 使用）
    """
    return httpx.AsyncClient(
        base_url=base_url,
        headers=headers or {},
        timeout=timeout or _default_timeout(),
        limits=limits or httpx.Limits(max_connections=20, max_keepalive_connections=10),
        follow_redirects=False,  # 安全：不自動跟 redirect（防 SSRF）
    )


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    source_name: str,
    raise_on_4xx: bool = True,
    **kwargs: Any,
) -> httpx.Response:
    """帶 retry 的 HTTP request。

    Args:
        client: httpx.AsyncClient
        method: GET / POST / ...
        url: target URL
        source_name: 用於 log + 錯誤訊息（如 "finmind"）
        raise_on_4xx: 4xx 是否包成 ExternalServiceError raise

    Raises:
        ExternalServiceError: 三次重試都失敗，或 4xx（若 raise_on_4xx=True）

    Returns:
        httpx.Response
    """
    last_exc: Exception | None = None

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(settings.HTTP_RETRY_MAX_ATTEMPTS),
        wait=(
            wait_exponential(
                multiplier=1,
                min=settings.HTTP_RETRY_MIN_WAIT_S,
                max=settings.HTTP_RETRY_MAX_WAIT_S,
            )
            + wait_random(min=0, max=2)
        ),
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        reraise=True,
    ):
        with attempt:
            try:
                response = await client.request(method, url, **kwargs)

                # 5xx 視為可 retry
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"{source_name} {method} {url} → {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                # 429 也 retry（rate limit）
                if response.status_code == 429:
                    raise httpx.HTTPStatusError(
                        f"{source_name} rate limited (429)",
                        request=response.request,
                        response=response,
                    )

                # 4xx（非 429）：不 retry，視 raise_on_4xx 決定
                if response.status_code >= 400 and raise_on_4xx:
                    logger.warning(
                        "http.client_error",
                        source=source_name,
                        method=method,
                        url=url,
                        status=response.status_code,
                    )
                    raise ExternalServiceError(
                        message_zh=f"{source_name} 回應錯誤（{response.status_code}）",
                        source=source_name,
                        method=method,
                        url=url,
                        status=response.status_code,
                    )

                return response

            except httpx.HTTPStatusError as e:
                last_exc = e
                # 5xx / 429 → tenacity 會 retry 直到 max_attempts
                # 但 retry_if_exception_type 沒包 HTTPStatusError，這裡需要主動 raise 一個 retryable
                logger.warning(
                    "http.retryable_error",
                    source=source_name,
                    method=method,
                    url=url,
                    status=e.response.status_code if e.response else "?",
                    attempt=attempt.retry_state.attempt_number,
                )
                raise TimeoutError(str(e)) from e

    # 不會到這裡（reraise=True 會直接 raise 最後一個例外）
    raise ExternalServiceError(
        message_zh=f"{source_name} 服務不可用（重試 {settings.HTTP_RETRY_MAX_ATTEMPTS} 次仍失敗）",
        source=source_name,
        last_exception=str(last_exc) if last_exc else "unknown",
    )


__all__ = ["get_async_client", "request_with_retry"]
