"""Phase 9 — RateLimiter 單元測試（fakeredis）。

依 PLAN 第 19.3 章 + 第二十八章 L 項。
"""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest

from app.core.rate_limit import RateLimiter

pytestmark = pytest.mark.unit


def _run(coro):
    return asyncio.run(coro)


def test_within_limit_allowed() -> None:
    async def _t():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        limiter = RateLimiter(r)
        result = await limiter.check("rate:test:a", limit=5, window_sec=60)
        assert result.allowed is True
        assert result.count == 1
        assert result.limit == 5
        await r.aclose()

    _run(_t())


def test_over_limit_blocked() -> None:
    async def _t():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        limiter = RateLimiter(r)
        # 連 5 次 OK
        for _ in range(5):
            assert (await limiter.check("rate:test:b", limit=5, window_sec=60)).allowed
        # 第 6 次擋
        result = await limiter.check("rate:test:b", limit=5, window_sec=60)
        assert result.allowed is False
        assert result.count == 6
        assert result.retry_after_sec > 0
        await r.aclose()

    _run(_t())


def test_window_resets_after_expire() -> None:
    """fakeredis 不會自然過期；用 DEL 模擬 window 結束。"""

    async def _t():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        limiter = RateLimiter(r)
        for _ in range(5):
            await limiter.check("rate:test:c", limit=5, window_sec=60)
        # 模擬時間流逝（DEL 等同 EXPIRE 到期）
        await r.delete("rate:test:c")
        # 計數重置
        result = await limiter.check("rate:test:c", limit=5, window_sec=60)
        assert result.allowed is True
        assert result.count == 1
        await r.aclose()

    _run(_t())


def test_different_keys_independent() -> None:
    async def _t():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        limiter = RateLimiter(r)
        # key A 滿
        for _ in range(5):
            await limiter.check("rate:test:keyA", limit=5, window_sec=60)
        # key B 仍 OK
        result = await limiter.check("rate:test:keyB", limit=5, window_sec=60)
        assert result.allowed is True
        await r.aclose()

    _run(_t())


def test_atomic_increment_under_concurrency() -> None:
    """20 個並發 task 對同一 key 各 +1；最終 count 應為 20。"""

    async def _t():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        limiter = RateLimiter(r)

        async def _hit():
            await limiter.check("rate:test:concurrent", limit=1000, window_sec=60)

        await asyncio.gather(*[_hit() for _ in range(20)])
        # 最後一次 check 來看 count 是否 == 21（前 20 次 + 此次 = 21）
        last = await limiter.check("rate:test:concurrent", limit=1000, window_sec=60)
        assert last.count == 21
        await r.aclose()

    _run(_t())


def test_redis_down_fails_open() -> None:
    """Redis 故障時 limiter 應回 allowed=True（fail-open），不擋 request。"""

    class _BrokenRedis:
        async def script_load(self, _script):
            raise RuntimeError("redis-down")

        async def evalsha(self, *_args, **_kwargs):
            raise RuntimeError("redis-down")

    async def _t():
        limiter = RateLimiter(_BrokenRedis())  # type: ignore[arg-type]
        result = await limiter.check("rate:test:down", limit=5, window_sec=60)
        assert result.allowed is True  # fail-open

    _run(_t())


def test_retry_after_set_when_limited() -> None:
    """超量時 retry_after_sec 應 > 0。"""

    async def _t():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        limiter = RateLimiter(r)
        for _ in range(3):
            await limiter.check("rate:test:retry", limit=3, window_sec=60)
        result = await limiter.check("rate:test:retry", limit=3, window_sec=60)
        assert result.allowed is False
        assert result.retry_after_sec >= 1
        await r.aclose()

    _run(_t())
