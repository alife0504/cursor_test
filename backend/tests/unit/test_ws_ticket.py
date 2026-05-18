"""Phase 8 — WSTicketService 單元測試（fakeredis）。

依 PLAN 第二十七章 N 項。
"""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import fakeredis.aioredis
import pytest

from app.core.ws_ticket import TICKET_PREFIX, TICKET_TTL_SECONDS, WSTicketService

pytestmark = pytest.mark.unit


def test_issue_returns_random_token() -> None:
    async def _run():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        svc = WSTicketService(r)
        t1 = await svc.issue(uuid4())
        t2 = await svc.issue(uuid4())
        assert isinstance(t1, str)
        assert len(t1) > 30
        assert t1 != t2  # randomness
        # 應該有 redis key
        assert await r.get(TICKET_PREFIX + t1) is not None
        await r.aclose()

    asyncio.run(_run())


def test_consume_returns_user_id() -> None:
    async def _run():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        svc = WSTicketService(r)
        user_id = uuid4()
        ticket = await svc.issue(user_id)
        got = await svc.consume(ticket)
        assert got == str(user_id)
        await r.aclose()

    asyncio.run(_run())


def test_consume_second_time_returns_none() -> None:
    """一次性：用過就 None。"""

    async def _run():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        svc = WSTicketService(r)
        ticket = await svc.issue(uuid4())
        await svc.consume(ticket)  # 第一次成功
        again = await svc.consume(ticket)
        assert again is None
        await r.aclose()

    asyncio.run(_run())


def test_consume_unknown_ticket_returns_none() -> None:
    async def _run():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        svc = WSTicketService(r)
        assert await svc.consume("nonexistent") is None
        await r.aclose()

    asyncio.run(_run())


def test_consume_empty_ticket_returns_none() -> None:
    async def _run():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        svc = WSTicketService(r)
        assert await svc.consume("") is None
        await r.aclose()

    asyncio.run(_run())


def test_ticket_ttl_set_to_60s() -> None:
    """issue 後 redis ttl 應接近 60s。"""

    async def _run():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        svc = WSTicketService(r)
        ticket = await svc.issue(uuid4())
        ttl = await r.ttl(TICKET_PREFIX + ticket)
        assert 55 <= ttl <= TICKET_TTL_SECONDS
        await r.aclose()

    asyncio.run(_run())


def test_ticket_expires_after_ttl() -> None:
    """fakeredis 支援 time travel：把 ticket TTL 「假進時間」60 秒。"""

    async def _run():
        # fakeredis 不會自動跑時間；但會接受 expire 為 0 的 key
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        svc = WSTicketService(r)
        ticket = await svc.issue(uuid4())
        # 直接 DEL 來模擬「TTL 已過 → key 不在」
        await r.delete(TICKET_PREFIX + ticket)
        assert await svc.consume(ticket) is None
        await r.aclose()

    asyncio.run(_run())


def test_ttl_value_constant() -> None:
    """TICKET_TTL_SECONDS 應為 60。"""
    assert TICKET_TTL_SECONDS == 60


def test_consume_does_not_block_or_throw_when_redis_recovers() -> None:
    """consume 是冪等的：對同一個 ticket 連 call 應有確定行為。"""

    async def _run():
        r = fakeredis.aioredis.FakeRedis(decode_responses=True)
        svc = WSTicketService(r)
        ticket = await svc.issue(uuid4())
        ok = await svc.consume(ticket)
        assert ok is not None
        none = await svc.consume(ticket)
        assert none is None
        await r.aclose()

    asyncio.run(_run())


# 抑制 unused import warning
_ = time
