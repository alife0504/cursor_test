"""DiscordNotifier 單元測試（不真打外部，用 httpx MockTransport）。"""

from __future__ import annotations

import json

import httpx
import pytest

from app.notifications.base import NotifyLevel
from app.notifications.discord_notifier import DiscordNotifier

pytestmark = pytest.mark.unit

_WEBHOOK = "https://discord.com/api/webhooks/123456789/abcDEF"


def _client(status: int, body: str = "") -> httpx.AsyncClient:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_send_success_204() -> None:
    """Discord 成功預設回 204 No Content。"""
    client = _client(204)
    try:
        n = DiscordNotifier({"webhook_url": _WEBHOOK}, client=client)
        r = await n.send("標題", "內容", level=NotifyLevel.SUCCESS)
        assert r.success is True
        assert r.status_code == 204
    finally:
        await client.aclose()


async def test_send_success_200() -> None:
    client = _client(200)
    try:
        n = DiscordNotifier({"webhook_url": _WEBHOOK}, client=client)
        r = await n.send("t", "b")
        assert r.success is True
    finally:
        await client.aclose()


async def test_http_error_is_failure() -> None:
    client = _client(500, "boom")
    try:
        n = DiscordNotifier({"webhook_url": _WEBHOOK}, client=client)
        r = await n.send("t", "b")
        assert r.success is False
        assert r.status_code == 500
    finally:
        await client.aclose()


async def test_missing_webhook_raises() -> None:
    """缺 webhook_url → 拋 ValueError（與既有 notifier 一致，由 dispatcher 接住記 failure）。"""
    n = DiscordNotifier({})
    with pytest.raises(ValueError, match="webhook_url"):
        await n.send("t", "b")


async def test_invalid_webhook_url_raises() -> None:
    """非 Discord 網域的 webhook → 拒絕（防 SSRF / 設錯目標）。"""
    n = DiscordNotifier({"webhook_url": "https://evil.example.com/hook"})
    with pytest.raises(ValueError, match="Discord Webhook"):
        await n.send("t", "b")


async def test_message_truncated_to_2000() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["content"] = json.loads(request.content)["content"]
        return httpx.Response(204)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        n = DiscordNotifier({"webhook_url": _WEBHOOK}, client=client)
        await n.send("標題", "x" * 5000)
        assert len(captured["content"]) <= 2000
    finally:
        await client.aclose()
