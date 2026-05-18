"""Redis client wrapper — 7 個 db 編號分用途 + connection pool。

依 PLAN.md 第 17.5 章快取規範：

| db | 用途           | TTL        |
|----|---------------|------------|
| 0  | cache         | 各業務設定 |
| 1  | celery broker | -          |
| 2  | rate limit    | window     |
| 3  | jwt blacklist | 與 token exp 同 |
| 4  | pubsub        | 即時       |
| 5  | ws ticket     | 60s        |
| 6  | idempotency   | 24h        |

每個 db 一個 ConnectionPool（避免互相影響）。
"""

from __future__ import annotations

from enum import IntEnum

import redis.asyncio as redis_async

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class RedisDB(IntEnum):
    """Redis db 編號常數。"""

    CACHE = 0
    CELERY = 1
    RATELIMIT = 2
    JWT_BLACKLIST = 3
    PUBSUB = 4
    WS_TICKET = 5
    IDEMPOTENCY = 6


# ── 全域 pool（lazy 初始化） ────────────────────────────

_pools: dict[int, redis_async.ConnectionPool] = {}


def get_redis_pool(db: int) -> redis_async.ConnectionPool:
    """取得 / 註冊指定 db 的 connection pool。"""
    if db not in _pools:
        _pools[db] = redis_async.ConnectionPool.from_url(
            settings.redis_url(db=db),
            max_connections=settings.POOL_SIZE_REDIS,
            decode_responses=True,
            socket_connect_timeout=5.0,
            socket_timeout=5.0,
            socket_keepalive=True,
        )
    return _pools[db]


async def get_redis(db: int = RedisDB.CACHE) -> redis_async.Redis:
    """取得指定 db 的 async Redis client（共用 pool）。

    用法：
        redis = await get_redis(RedisDB.CACHE)
        await redis.set("key", "value", ex=60)
    """
    pool = get_redis_pool(db)
    return redis_async.Redis(connection_pool=pool)


async def test_redis_connection() -> None:
    """startup fail-fast probe：對 db 0 + db 1 + db 4（pubsub）各 ping 一次。"""
    for db in (RedisDB.CACHE, RedisDB.CELERY, RedisDB.PUBSUB):
        client = await get_redis(db)
        result = await client.ping()
        assert result is True, f"redis db={db.value} ping failed"
    logger.info("redis.ready", pool_size=settings.POOL_SIZE_REDIS)


async def dispose_redis_pools() -> None:
    """shutdown 時關閉所有 pool。"""
    for db, pool in list(_pools.items()):
        await pool.aclose()
        del _pools[db]
    logger.info("redis.pools.disposed")


__all__ = [
    "RedisDB",
    "dispose_redis_pools",
    "get_redis",
    "get_redis_pool",
    "test_redis_connection",
]
