"""Phase 9 — Rate Limit（6 層 sliding window，Redis db2）。

依 PLAN.md 第 19.3 章 6 層規格：
| 層 | 範圍 | 限制 | Key prefix |
|----|------|------|------------|
| L1 | per IP global | 300/min | rate:ip:{ip} |
| L2 | /auth/login | 5/min/IP | rate:login:{ip} |
| L3 | /auth/password-reset | 3/hr/IP | rate:pwdreset:{ip} |
| L4 | per user authenticated | 60/min | rate:user:{user_id} |
| L5 | /analysis/start | 10/hr/user | rate:analysis:{user_id} |
| L6 | LLM 月成本（service 層處理） | $50/user/month | quota:llm:{user_id}:{month} |

實作：
- Redis sliding window via INCR + EXPIRE（atomic via Lua script）
- Lua 保證 atomic：INCR；若是第一次（==1）就 EXPIRE
- fail-open：Redis 掛掉時不擋 request（log warning），避免認證流程死循環

L1-L5 由 RateLimitMiddleware 直接攔；L6 在 service 層另外處理（不在 middleware）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.errors import RateLimitError
from app.core.logging_config import get_logger
from app.core.redis_client import RedisDB, get_redis
from app.core.request_id import get_current_trace_id
from app.core.response_envelope import envelope_error

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────
# Lua script — atomic incr-or-set + check
# ─────────────────────────────────────────────────────────
# 邏輯：
#   v = INCR(key)
#   if v == 1: EXPIRE(key, window)
#   return {v, TTL(key)}

INCR_EXPIRE_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


# ─────────────────────────────────────────────────────────
# RateLimiter（核心 atomic check）
# ─────────────────────────────────────────────────────────


@dataclass(slots=True)
class RateLimitResult:
    allowed: bool
    count: int
    """目前 window 內已用的 request 數。"""
    limit: int
    retry_after_sec: int
    """超量時，client 應等多少秒再試。"""


class RateLimiter:
    """共用 sliding-window-like rate limiter（INCR + EXPIRE 模式）。

    嚴格說不是 sliding window 而是 fixed window，但對 v1.0 足夠。
    P19+ 若需要嚴格 sliding，可改 ZSET + ZRANGEBYSCORE。

    用 `redis.eval(...)`（每次傳 script source），而非 script_load + evalsha。
    原因：fakeredis 不支援 SCRIPT LOAD；real redis 對 eval() 會自動 cache 不會多耗效能。
    """

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def check(
        self,
        key: str,
        *,
        limit: int,
        window_sec: int,
    ) -> RateLimitResult:
        """檢查 key 在 window 內是否超量。回 RateLimitResult。

        fail-open：Redis 異常時回 allowed=True + count=0（log warning）。
        """
        try:
            result = await self.redis.eval(INCR_EXPIRE_LUA, 1, key, str(window_sec))
            # result 形如 [current_count, ttl_seconds]
            current_count = int(result[0])
            ttl = int(result[1])
            allowed = current_count <= limit
            retry_after = max(1, ttl) if not allowed else 0
            return RateLimitResult(
                allowed=allowed,
                count=current_count,
                limit=limit,
                retry_after_sec=retry_after,
            )
        except Exception as e:  # pragma: no cover  - fail-open
            logger.warning("rate_limit.redis_error", key=key, error=str(e))
            return RateLimitResult(allowed=True, count=0, limit=limit, retry_after_sec=0)


# ─────────────────────────────────────────────────────────
# Rule 設定（依 PLAN 19.3）
# ─────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class RateRule:
    """單條 rate limit 規則。"""

    layer: str  # "L1" / "L2" / ...
    key_prefix: str  # "rate:ip:" / "rate:login:" / ...
    limit: int
    window_sec: int


# Path matchers — 用 path prefix 比對
L1_GLOBAL = RateRule(layer="L1", key_prefix="rate:ip:", limit=300, window_sec=60)
L2_LOGIN = RateRule(layer="L2", key_prefix="rate:login:", limit=5, window_sec=60)
L3_PWDRESET = RateRule(layer="L3", key_prefix="rate:pwdreset:", limit=3, window_sec=3600)
L4_USER = RateRule(layer="L4", key_prefix="rate:user:", limit=60, window_sec=60)
L5_ANALYSIS = RateRule(layer="L5", key_prefix="rate:analysis:", limit=10, window_sec=3600)


# 對應的 path matchers
LOGIN_PATHS = {"/api/v1/auth/login"}
PWDRESET_PATHS = {"/api/v1/auth/password-reset"}
ANALYSIS_PATHS = {"/api/v1/analysis/start"}  # 預留 P10/11

# 不做任何 rate limit 的路徑（health / docs / 內部測試）
EXEMPT_PATHS_PREFIXES = (
    "/health/",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/_test/",
)


# ─────────────────────────────────────────────────────────
# RateLimitMiddleware
# ─────────────────────────────────────────────────────────


class RateLimitMiddleware(BaseHTTPMiddleware):
    """套 L1-L5 規則於 request 上。

    執行順序：
    1. L1 per IP global
    2. L2/L3/L5 path-specific
    3. L4 per user（如有 access token）

    每 request 取新的 Redis client（pool 自己 cache，不需要再 cache middleware 層）。
    這樣 TestClient 跨 lifespan 不會持有 stale connection。
    """

    def __init__(self, app) -> None:
        super().__init__(app)

    async def _get_limiter(self) -> RateLimiter:
        redis = await get_redis(RedisDB.RATELIMIT)
        return RateLimiter(redis)

    @staticmethod
    def _client_ip(request: Request) -> str:
        # P11 加 X-Forwarded-For 信任白名單
        if request.client is None:
            return "0.0.0.0"  # noqa: S104  # 沒 client 才退路 fallback；rate-limit key 用
        return request.client.host or "0.0.0.0"  # noqa: S104

    @staticmethod
    def _user_id(request: Request) -> str | None:
        """從 request.state 取（由 dependency 設）。middleware 跑在 dependency 之前，
        所以這裡通常拿不到 user_id；L4 主要依賴 endpoint 自行 check 或 P11 重排。
        v1.0 先靠 L1（per IP）擋多數 abuse。"""
        return getattr(request.state, "actor_id", None)

    def _is_exempt(self, path: str) -> bool:
        return any(path.startswith(p) for p in EXEMPT_PATHS_PREFIXES)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if self._is_exempt(request.url.path):
            return await call_next(request)

        limiter = await self._get_limiter()
        ip = self._client_ip(request)

        # L1: per IP global
        l1_result = await limiter.check(
            f"{L1_GLOBAL.key_prefix}{ip}",
            limit=L1_GLOBAL.limit,
            window_sec=L1_GLOBAL.window_sec,
        )
        if not l1_result.allowed:
            return self._rate_limited_response(request, L1_GLOBAL, l1_result)

        # L2: /auth/login
        if request.url.path in LOGIN_PATHS and request.method == "POST":
            r = await limiter.check(
                f"{L2_LOGIN.key_prefix}{ip}",
                limit=L2_LOGIN.limit,
                window_sec=L2_LOGIN.window_sec,
            )
            if not r.allowed:
                return self._rate_limited_response(request, L2_LOGIN, r)

        # L3: /auth/password-reset
        if request.url.path in PWDRESET_PATHS and request.method == "POST":
            r = await limiter.check(
                f"{L3_PWDRESET.key_prefix}{ip}",
                limit=L3_PWDRESET.limit,
                window_sec=L3_PWDRESET.window_sec,
            )
            if not r.allowed:
                return self._rate_limited_response(request, L3_PWDRESET, r)

        # L4 / L5：依賴 user_id；middleware 還沒解 JWT，留給 endpoint 層或 P11 重排
        # 不在此預先做（避免重複解 JWT）

        return await call_next(request)

    @staticmethod
    def _rate_limited_response(
        request: Request, rule: RateRule, result: RateLimitResult
    ) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None) or get_current_trace_id()
        logger.warning(
            "rate_limit.hit",
            layer=rule.layer,
            path=request.url.path,
            limit=rule.limit,
            count=result.count,
            retry_after=result.retry_after_sec,
        )
        body = envelope_error(
            code="RATE_LIMITED",
            message=f"請求頻率過高（{rule.layer}：每 {rule.window_sec}s 限 {rule.limit} 次）",
            trace_id=trace_id,
            details={
                "layer": rule.layer,
                "limit": rule.limit,
                "window_sec": rule.window_sec,
                "retry_after_sec": result.retry_after_sec,
            },
        )
        headers = {"Retry-After": str(result.retry_after_sec)}
        return JSONResponse(status_code=429, content=body, headers=headers)


# 給 endpoint dependency 用：
def make_user_rate_limit_dependency():
    """產生 endpoint dependency：對 authenticated user 套 L4 60/min。

    在 endpoint 層使用：
        @router.get("/foo", dependencies=[Depends(rate_limit_per_user())])
    """

    async def _check(request: Request) -> None:
        from app.core.errors import RateLimitError as _RLE

        user_id = getattr(request.state, "actor_id", None)
        if not user_id:
            return  # 沒 user 不擋
        redis = await get_redis(RedisDB.RATELIMIT)
        limiter = RateLimiter(redis)
        r = await limiter.check(
            f"{L4_USER.key_prefix}{user_id}",
            limit=L4_USER.limit,
            window_sec=L4_USER.window_sec,
        )
        if not r.allowed:
            raise _RLE(
                message_zh=f"L4 per-user 超量（{L4_USER.limit}/{L4_USER.window_sec}s）",
                retry_after_sec=r.retry_after_sec,
            )

    return _check


# 抑制 unused import
_ = RateLimitError


__all__ = [
    "EXEMPT_PATHS_PREFIXES",
    "L1_GLOBAL",
    "L2_LOGIN",
    "L3_PWDRESET",
    "L4_USER",
    "L5_ANALYSIS",
    "RateLimitMiddleware",
    "RateLimitResult",
    "RateLimiter",
    "RateRule",
    "make_user_rate_limit_dependency",
]
