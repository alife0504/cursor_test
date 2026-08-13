"""Phase 14 — WebSocket streaming 事件整合測試（≥ 4 個測試）。

策略：監聽 redis pubsub channel `analysis:{id}`，呼叫 `publish_event(_sync)` 後驗證 message。
不啟動 WS endpoint；直接 verify pubsub layer 即可（WS 端讀同一 channel，邏輯等價）。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid as _uuid

import pytest
import redis.asyncio as redis_async

from app.agents.streaming import (
    EVENT_ANALYST_COMPLETED,
    EVENT_COMPLETED,
    EVENT_FAILED,
    EVENT_STARTED,
    publish_event_sync,
)
from app.core.config import settings
from app.core.redis_client import RedisDB

pytestmark = pytest.mark.integration


async def _collect_one(
    channel: str, *, ready_evt: asyncio.Event | None = None, timeout: float = 3.0
) -> dict | None:
    """訂閱 channel，等下一則 message；timeout → None。

    用獨立 client（不走 get_redis pool）避免跨 event loop 問題。
    """
    client = redis_async.Redis.from_url(
        settings.redis_url(db=int(RedisDB.PUBSUB)),
        decode_responses=True,
        socket_connect_timeout=5.0,
        socket_timeout=5.0,
    )
    ps = client.pubsub()
    try:
        await ps.subscribe(channel)
        # 等 subscribe confirm — 用 get_message 直到 subscribe 訊息出現
        for _ in range(20):
            msg0 = await ps.get_message(timeout=0.5)
            if msg0 is not None and msg0.get("type") == "subscribe":
                break
        if ready_evt is not None:
            ready_evt.set()
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                return None
            msg = await ps.get_message(ignore_subscribe_messages=True, timeout=remaining)
            if msg is None:
                continue
            if msg.get("type") != "message":
                continue
            data_raw = msg.get("data")
            if isinstance(data_raw, bytes):
                data_raw = data_raw.decode("utf-8")
            return json.loads(data_raw)
    finally:
        with contextlib.suppress(Exception):
            await ps.unsubscribe(channel)
            await ps.aclose()
        with contextlib.suppress(Exception):
            await client.aclose()


async def _run_pub_sub(event_name: str, data: dict) -> dict | None:
    analysis_id = _uuid.uuid4()
    channel = f"analysis:{analysis_id}"
    ready = asyncio.Event()
    sub_task = asyncio.create_task(_collect_one(channel, ready_evt=ready))
    await ready.wait()
    # 用同步版（避免共用 async pool 跨 loop）
    ok = publish_event_sync(str(analysis_id), event_name, data)
    assert ok is True
    return await sub_task


async def test_started_event_published() -> None:
    msg = await _run_pub_sub(EVENT_STARTED, {"symbol": "2330"})
    assert msg is not None
    assert msg["event"] == "started"
    assert msg["data"]["symbol"] == "2330"
    assert "ts" in msg


async def test_analyst_completed_events_published() -> None:
    msg = await _run_pub_sub(EVENT_ANALYST_COMPLETED, {"node": "market", "preview": "..."})
    assert msg is not None
    assert msg["event"] == "analyst_completed"
    assert msg["data"]["node"] == "market"


async def test_completed_event_includes_signal() -> None:
    msg = await _run_pub_sub(
        EVENT_COMPLETED, {"action": "BUY", "confidence": 75, "duration_s": 12.3}
    )
    assert msg is not None
    assert msg["event"] == "completed"
    assert msg["data"]["action"] == "BUY"
    assert msg["data"]["confidence"] == 75


async def test_failed_event_published_on_error() -> None:
    msg = await _run_pub_sub(EVENT_FAILED, {"error": "graph timeout"})
    assert msg is not None
    assert msg["event"] == "failed"
    assert msg["data"]["error"] == "graph timeout"


def test_publish_event_sync_works_for_celery() -> None:
    """同步版（celery worker 用）也應該能成功 publish（即使沒人 subscribe，回 True）。"""
    analysis_id = _uuid.uuid4()
    ok = publish_event_sync(str(analysis_id), EVENT_STARTED, {"x": 1})
    assert ok is True
