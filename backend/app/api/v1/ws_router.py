"""Phase 11 — /api/v1/ws/* WebSocket router。

依 PLAN.md 第 19.1 章 WS 認證：Subprotocol + Ticket。

協定（前端）：
    const ticket = await fetch('/api/v1/auth/ws-ticket').then(...);
    const ws = new WebSocket(
        `ws://host/api/v1/ws/analysis/${id}`,
        ["tradingagents.v1", `ticket.${ticket}`],
    );

協定（後端）：
1. 從 subprotocol 取 `ticket.<XXX>` → consume（一次性，60s TTL）
2. IDOR 防護：驗 user 對 analysis 有讀取權限（admin 可看所有；其他 role 只能看自己的）
3. accept(subprotocol="tradingagents.v1")
4. 訂閱 Redis db4 pubsub channel `analysis:{id}` → 把每則訊息轉發給 client
5. 併行監看 `websocket.receive()`：client 斷線立即結束 coroutine 並清理 pubsub
   （若只顧著 pubsub.listen()，channel 閒置時 coroutine 會永遠掛著 → 慢漏）
6. 每 30s 送 heartbeat event，避免 nginx / proxy 以 idle 為由切斷長分析的連線
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import get_rw_engine
from app.core.logging_config import get_logger
from app.core.redis_client import RedisDB, get_redis
from app.core.ws_ticket import WSTicketService
from app.repos.analysis_repo import AnalysisRepository
from app.repos.user_repo import UserRepository

logger = get_logger(__name__)

WS_SUBPROTOCOL = "tradingagents.v1"
TICKET_PREFIX = "ticket."

# heartbeat：慢分析（LLM 多輪辯論可達數分鐘）期間讓 proxy/nginx 知道連線還活著
HEARTBEAT_INTERVAL_S = 30.0
# pubsub 輪詢喚醒間隔：get_message timeout；兼顧「即時轉發」與「可週期檢查 heartbeat」
PUBSUB_POLL_TIMEOUT_S = 1.0

HEARTBEAT_PAYLOAD = '{"event": "heartbeat", "data": {}}'

router = APIRouter(prefix="/api/v1/ws", tags=["ws"])


async def _forward_pubsub(websocket: WebSocket, pubsub: Any) -> None:
    """pubsub → websocket 轉發迴圈 + 週期 heartbeat。

    用 `get_message(timeout=...)` 而非 `listen()`：listen() 在 channel 閒置時
    無限阻塞，coroutine 無法週期喚醒送 heartbeat，也無法被上層乾淨取消。
    """
    last_beat = time.monotonic()
    while True:
        msg = await pubsub.get_message(
            ignore_subscribe_messages=True, timeout=PUBSUB_POLL_TIMEOUT_S
        )
        if msg is not None and msg.get("type") == "message":
            data = msg.get("data")
            if data is not None:
                text = data.decode("utf-8") if isinstance(data, bytes) else str(data)
                await websocket.send_text(text)
        now = time.monotonic()
        if now - last_beat >= HEARTBEAT_INTERVAL_S:
            await websocket.send_text(HEARTBEAT_PAYLOAD)
            last_beat = now


async def _watch_disconnect(websocket: WebSocket) -> None:
    """持續 receive 直到 client 斷線（收到 websocket.disconnect 即 return）。

    為什麼需要：轉發迴圈只 send 不 receive，client 斷線（尤其是沒送 close frame
    的網路中斷）時 send 端未必立刻察覺；這裡收到 disconnect 訊息就讓上層收尾，
    避免 coroutine + pubsub 訂閱懸掛（慢漏）。client 主動送來的資料一律忽略。
    """
    while True:
        message = await websocket.receive()
        if message.get("type") == "websocket.disconnect":
            return


def _extract_ticket(subprotocols: list[str]) -> str | None:
    for s in subprotocols:
        if s.startswith(TICKET_PREFIX):
            return s[len(TICKET_PREFIX) :]
    return None


async def _get_ticket_service(websocket: WebSocket) -> WSTicketService:
    svc: WSTicketService | None = getattr(websocket.app.state, "ws_ticket_service", None)
    if svc is None:
        redis = await get_redis(RedisDB.WS_TICKET)
        svc = WSTicketService(redis)
        websocket.app.state.ws_ticket_service = svc
    return svc


@router.websocket("/analysis/{analysis_id}")
async def ws_analysis(websocket: WebSocket, analysis_id: str) -> None:
    """訂閱單一 analysis 的 pubsub 事件。

    錯誤碼用 WebSocket close code：
    - 1008 policy violation：認證 / 權限失敗
    - 1011 internal error：未知例外
    """
    subprotocols = websocket.scope.get("subprotocols", []) or []
    ticket = _extract_ticket(subprotocols)
    if not ticket:
        await websocket.close(code=1008, reason="missing ticket")
        return

    ticket_service = await _get_ticket_service(websocket)
    user_id_str = await ticket_service.consume(ticket)
    if not user_id_str:
        await websocket.close(code=1008, reason="invalid or expired ticket")
        return

    # 解析 IDs
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        await websocket.close(code=1008, reason="invalid user id in ticket")
        return
    try:
        analysis_uuid = UUID(analysis_id)
    except ValueError:
        await websocket.close(code=1008, reason="invalid analysis id")
        return

    # IDOR 檢查 — 必須在 accept 前完成
    engine = get_rw_engine()
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        user = await UserRepository(session).get_by_id(user_id)
        analysis = await AnalysisRepository(session).get_by_id(analysis_uuid)
        if user is None or not user.is_active or user.deleted_at is not None:
            await websocket.close(code=1008, reason="invalid user")
            return
        if analysis is None:
            await websocket.close(code=1008, reason="analysis not found")
            return
        if user.role.upper() != "ADMIN" and analysis.user_id != user_id:
            logger.warning(
                "ws.analysis.forbidden",
                user_id=str(user_id),
                analysis_id=str(analysis_uuid),
            )
            await websocket.close(code=1008, reason="forbidden")
            return

    # accept + subscribe
    await websocket.accept(subprotocol=WS_SUBPROTOCOL)
    logger.info(
        "ws.analysis.connected",
        user_id=str(user_id),
        analysis_id=str(analysis_uuid),
    )

    pubsub_redis = await get_redis(RedisDB.PUBSUB)
    pubsub = pubsub_redis.pubsub()
    channel = f"analysis:{analysis_uuid}"
    try:
        await pubsub.subscribe(channel)
        forward = asyncio.create_task(_forward_pubsub(websocket, pubsub))
        watcher = asyncio.create_task(_watch_disconnect(websocket))
        try:
            done, _pending = await asyncio.wait(
                {forward, watcher}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                exc = task.exception()
                if exc is not None:
                    raise exc
        finally:
            for task in (forward, watcher):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await task
        # watcher 正常 return = client 斷線
        logger.info(
            "ws.analysis.disconnected",
            user_id=str(user_id),
            analysis_id=str(analysis_uuid),
        )
    except WebSocketDisconnect:
        logger.info(
            "ws.analysis.disconnected",
            user_id=str(user_id),
            analysis_id=str(analysis_uuid),
        )
    except Exception as e:  # pragma: no cover - 安全網
        logger.warning("ws.analysis.error", error=str(e), error_type=type(e).__name__)
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason="internal error")
    finally:
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(channel)
        with contextlib.suppress(Exception):
            await pubsub.close()


__all__ = ["router"]
