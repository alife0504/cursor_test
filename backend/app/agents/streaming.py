"""LangGraph analysis streaming events — Redis pubsub publisher。

依 PLAN.md 第 17.5 章快取規範（redis db=4 pubsub）+ 第 14.6 章 Graceful。

設計：
- channel: `analysis:{analysis_id}`
- payload（JSON 字串）：
    {
      "event":  "started" | "analyst_completed" | "debate_argument" |
                "synthesis_completed" | "completed" | "failed",
      "data":   {...},               # event-specific
      "ts":     "ISO 8601 UTC"
    }
- async fire-and-forget：publish 失敗（Redis 不可用）不可擋分析流程；只 log warning。
- celery sync 場景：提供 `publish_event_sync()`（用 redis-py 同步 client）。

WebSocket subscriber 在 `ws_router` 訂閱 channel，把每筆 message 推給前端。
client 失連自負責 reconnect；已發出的 message 不重送（pubsub 設計）。
"""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.redis_client import RedisDB, get_redis

logger = get_logger(__name__)


# 公開事件名稱常數
EVENT_STARTED = "started"
EVENT_ANALYST_COMPLETED = "analyst_completed"
EVENT_DEBATE_ARGUMENT = "debate_argument"
EVENT_SYNTHESIS_COMPLETED = "synthesis_completed"
EVENT_COMPLETED = "completed"
EVENT_FAILED = "failed"


def _channel(analysis_id: str | object) -> str:
    """組 pubsub channel 名稱。"""
    return f"analysis:{analysis_id}"


def _build_payload(event: str, data: Any) -> str:
    """組 JSON 字串。Decimal / datetime 等用 str() 序列化避免炸掉。"""
    body = {
        "event": event,
        "data": data if data is not None else {},
        "ts": datetime.now(tz=UTC).isoformat(),
    }
    return json.dumps(body, ensure_ascii=False, default=str)


async def publish_event(
    analysis_id: str | object,
    event: str,
    data: dict[str, Any] | None = None,
) -> bool:
    """async publish — 用 asyncio Redis client（db=4 PUBSUB）。

    Returns:
        True 表示 Redis 接受 publish（不代表有 subscriber 收到）；
        False 表示 Redis 不可用 / publish 失敗（已 log，不 raise）。
    """
    try:
        client = await get_redis(RedisDB.PUBSUB)
        payload = _build_payload(event, data)
        receivers = await client.publish(_channel(analysis_id), payload)
        logger.debug(
            "streaming.publish",
            analysis_id=str(analysis_id),
            event_name=event,
            receivers=int(receivers or 0),
        )
        return True
    except Exception as exc:  # pragma: no cover  - fire-and-forget
        logger.warning(
            "streaming.publish_failed",
            analysis_id=str(analysis_id),
            event_name=event,
            error=str(exc),
        )
        return False


def publish_event_sync(
    analysis_id: str | object,
    event: str,
    data: dict[str, Any] | None = None,
) -> bool:
    """同步版（celery worker / signal context 用）。

    用 redis-py sync client；不共用 async pool（避免跨 loop 衝突）。
    """
    try:
        import redis as _redis_sync

        client = _redis_sync.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD.get_secret_value(),
            db=int(RedisDB.PUBSUB),
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
            decode_responses=True,
        )
        payload = _build_payload(event, data)
        try:
            receivers = client.publish(_channel(analysis_id), payload)
        finally:
            with contextlib.suppress(Exception):  # pragma: no cover
                client.close()
        logger.debug(
            "streaming.publish_sync",
            analysis_id=str(analysis_id),
            event_name=event,
            receivers=int(receivers or 0),
        )
        return True
    except Exception as exc:  # pragma: no cover  - fire-and-forget
        logger.warning(
            "streaming.publish_sync_failed",
            analysis_id=str(analysis_id),
            event_name=event,
            error=str(exc),
        )
        return False


__all__ = [
    "EVENT_ANALYST_COMPLETED",
    "EVENT_COMPLETED",
    "EVENT_DEBATE_ARGUMENT",
    "EVENT_FAILED",
    "EVENT_STARTED",
    "EVENT_SYNTHESIS_COMPLETED",
    "publish_event",
    "publish_event_sync",
]
