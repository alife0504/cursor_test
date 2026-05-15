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
5. WebSocketDisconnect 時 unsubscribe + close pubsub
"""

from __future__ import annotations

import contextlib
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

router = APIRouter(prefix="/api/v1/ws", tags=["ws"])


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
        async for msg in pubsub.listen():
            if msg.get("type") != "message":
                continue
            data = msg.get("data")
            if data is None:
                continue
            text = data.decode("utf-8") if isinstance(data, bytes) else str(data)
            await websocket.send_text(text)
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
