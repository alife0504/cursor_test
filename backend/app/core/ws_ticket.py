"""Phase 8 — WebSocket 一次性 ticket（Redis db5）。

依 PLAN.md 第 19.1 章：WS 連線不能用 cookie / Authorization header（瀏覽器 WS API 限制），
必須先 HTTP 取一次性 ticket，再連 WS 時把 ticket 放 subprotocol。

協定：
- 前端：fetch POST /api/v1/auth/ws-ticket（帶 access token）→ 取 `ticket`
- 前端：new WebSocket(url, ["tradingagents.v1", f"ticket.{ticket}"])
- 後端：accept handshake 時讀 subprotocol → consume ticket → 拿到 user_id

Redis key: wst:{ticket}  Value: user_id  TTL: 60 秒
一次性：consume 用 GETDEL（Redis 6.2+，原子的 GET+DEL）。
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from redis.asyncio import Redis

TICKET_TTL_SECONDS = 60
"""一次性 ticket TTL；60s 足夠前端走完拿 ticket → 開 WS 的流程。"""

TICKET_PREFIX = "wst:"


class WSTicketService:
    """產生 + 消費 WebSocket 一次性 ticket。"""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def _key(ticket: str) -> str:
        return f"{TICKET_PREFIX}{ticket}"

    async def issue(self, user_id: UUID | str) -> str:
        """為指定 user 發一個一次性 ticket（60s TTL）。"""
        ticket = secrets.token_urlsafe(32)
        await self.redis.setex(
            self._key(ticket),
            TICKET_TTL_SECONDS,
            str(user_id),
        )
        return ticket

    async def consume(self, ticket: str) -> str | None:
        """嘗試消費 ticket。成功回 user_id（str），失敗或過期回 None。

        實作：GETDEL（Redis 6.2+）保證 atomicity；ticket 一次有效。
        若 Redis < 6.2，退路是 pipeline GET+DEL（非原子，但接受）。
        """
        if not ticket:
            return None
        try:
            value = await self.redis.getdel(self._key(ticket))
        except AttributeError:
            # 舊版 redis-py 無 getdel：退路用 pipeline
            async with self.redis.pipeline() as pipe:
                pipe.get(self._key(ticket))
                pipe.delete(self._key(ticket))
                got, _ = await pipe.execute()
            value = got
        if value is None:
            return None
        # redis-py decode_responses=True 已自動轉 str
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return value


__all__ = ["TICKET_PREFIX", "TICKET_TTL_SECONDS", "WSTicketService"]
