"""ws_router 轉發迴圈單元測試 — 斷線監看 + heartbeat + pubsub 轉發。

不依賴真實 Redis / WebSocket：用輕量 fake 物件驗證迴圈行為。
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import pytest

from app.api.v1 import ws_router
from app.api.v1.ws_router import _forward_pubsub, _watch_disconnect

pytestmark = pytest.mark.unit


class FakeWebSocket:
    """記錄 send_text；receive 依 queue 回放訊息。"""

    def __init__(self, receive_messages: list[dict[str, Any]] | None = None) -> None:
        self.sent: list[str] = []
        self._receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        for m in receive_messages or []:
            self._receive_queue.put_nowait(m)

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def receive(self) -> dict[str, Any]:
        return await self._receive_queue.get()


class FakePubSub:
    """get_message 依序回放 queue 內容；空了以後回 None（模擬 timeout）。"""

    def __init__(self, messages: list[dict[str, Any]] | None = None) -> None:
        self._messages = list(messages or [])

    async def get_message(self, *, ignore_subscribe_messages: bool = True, timeout: float = 1.0):
        await asyncio.sleep(0)  # 讓出控制權，模擬 IO
        if self._messages:
            return self._messages.pop(0)
        return None


async def test_watch_disconnect_returns_on_disconnect() -> None:
    ws = FakeWebSocket(
        receive_messages=[
            {"type": "websocket.receive", "text": "ignored client data"},
            {"type": "websocket.disconnect", "code": 1000},
        ]
    )
    # 在 1 秒內應該 return（收到 disconnect），不會掛住
    await asyncio.wait_for(_watch_disconnect(ws), timeout=1.0)


async def test_forward_pubsub_sends_channel_messages() -> None:
    ws = FakeWebSocket()
    pubsub = FakePubSub(
        messages=[
            {"type": "message", "data": b'{"event": "started", "data": {}}'},
            {"type": "message", "data": '{"event": "completed", "data": {}}'},
        ]
    )
    task = asyncio.create_task(_forward_pubsub(ws, pubsub))
    # 給轉發迴圈一點時間消化 2 則訊息
    for _ in range(50):
        if len(ws.sent) >= 2:
            break
        await asyncio.sleep(0.01)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert ws.sent[0] == '{"event": "started", "data": {}}'
    assert ws.sent[1] == '{"event": "completed", "data": {}}'


async def test_forward_pubsub_emits_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    # 把 heartbeat 間隔壓到 0 → 每次輪詢喚醒都會送 heartbeat
    monkeypatch.setattr(ws_router, "HEARTBEAT_INTERVAL_S", 0.0)
    monkeypatch.setattr(ws_router, "PUBSUB_POLL_TIMEOUT_S", 0.01)

    ws = FakeWebSocket()
    pubsub = FakePubSub()
    task = asyncio.create_task(_forward_pubsub(ws, pubsub))
    for _ in range(100):
        if ws.sent:
            break
        await asyncio.sleep(0.01)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert ws.sent, "應該至少送出一次 heartbeat"
    assert ws.sent[0] == ws_router.HEARTBEAT_PAYLOAD


async def test_forward_pubsub_cancellable_when_idle() -> None:
    """channel 完全沒訊息時，迴圈必須可被取消（不會無限阻塞）。"""
    ws = FakeWebSocket()
    pubsub = FakePubSub()
    task = asyncio.create_task(_forward_pubsub(ws, pubsub))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
