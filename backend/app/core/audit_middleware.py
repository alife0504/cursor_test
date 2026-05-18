"""Phase 9 — AuditMiddleware：每 HTTP request 寫一筆 audit_logs。

依 PLAN.md 第 19.6 章 Audit + 第 16.3 章告警。

設計：
- 在 RequestIDMiddleware 之後跑（要拿 trace_id）
- 排除：/health/*, /metrics, /docs, /openapi.json, /redoc, /_test/*
- response 完成後寫 DB（async session via get_rw_session 邏輯但獨立 sessionmaker）
- 寫失敗時 log warning，不擋 response（PLAN 已知陷阱）
- 不寫 sensitive header / body（依 17.1 章遮蔽欄位）
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


AUDIT_EXCLUDED_PATH_PREFIXES: tuple[str, ...] = (
    "/health/",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/_test/",
    "/favicon.ico",
)


def should_audit(path: str) -> bool:
    """是否該 audit 此 path。"""
    return not any(path.startswith(p) for p in AUDIT_EXCLUDED_PATH_PREFIXES)


class AuditMiddleware(BaseHTTPMiddleware):
    """寫 HTTP request audit log。

    存的欄位：
    - action: f"http.{method.lower()}"  (例如 http.post)
    - entity_type: "endpoint"
    - entity_id: request.url.path
    - details: {"status": int, "elapsed_ms": int, "query": str|None}
    - actor_id: 若 dependency 已解 JWT 並設 request.state.actor_id
    - request_id: request.state.trace_id
    - ip / user_agent
    """

    def __init__(self, app) -> None:
        super().__init__(app)
        # session maker lazy 建（避免 import 期 DB 還沒 ready）
        self._sessionmaker = None
        self._sessionmaker_engine_id: int | None = None

    async def _get_sessionmaker(self):
        """每次拿 sessionmaker 都檢查綁定的 engine 是否還是目前 rw engine。

        為什麼：TestClient lifespan 結束時會 dispose_db_connections 把全域 engine 設 None，
        下一個 test 起來時 engine 是新物件。若 sessionmaker 還指向舊 engine 會炸
        "Event loop is closed" 或 "'NoneType' has no attribute 'send'"。
        """
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from app.core.database import get_rw_engine

        engine = get_rw_engine()
        if self._sessionmaker is None or self._sessionmaker_engine_id != id(engine):
            self._sessionmaker = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
            self._sessionmaker_engine_id = id(engine)
        return self._sessionmaker

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        # 排除非業務 endpoint
        if not should_audit(request.url.path):
            return response

        # 寫 audit；任何例外都不擋 response
        try:
            await self._write_audit(request, response, elapsed_ms)
        except Exception as e:  # pragma: no cover  - 安全網
            logger.warning(
                "audit.write_failed",
                path=request.url.path,
                method=request.method,
                error=type(e).__name__,
                error_msg=str(e),
            )
        return response

    async def _write_audit(
        self,
        request: Request,
        response: Response,
        elapsed_ms: int,
    ) -> None:
        from app.repos.audit_repo import AuditRepository

        trace_id = getattr(request.state, "trace_id", None)
        actor_id_str = getattr(request.state, "actor_id", None)
        actor_id: UUID | None = None
        if actor_id_str:
            try:
                actor_id = UUID(str(actor_id_str))
            except (ValueError, TypeError):
                actor_id = None

        ip = self._client_ip(request)
        user_agent = request.headers.get("user-agent")

        details: dict = {
            "status": int(response.status_code),
            "elapsed_ms": elapsed_ms,
        }
        if request.url.query:
            # 不存 sensitive query；query 不太可能含密碼但限長度
            details["query"] = request.url.query[:512]

        maker = await self._get_sessionmaker()
        async with maker() as session:
            repo = AuditRepository(session)
            await repo.append(
                actor_id=actor_id,
                action=f"http.{request.method.lower()}",
                entity_type="endpoint",
                entity_id=request.url.path[:100],
                details=details,
                ip=ip,
                user_agent=(user_agent[:500] if user_agent else None),
                request_id=trace_id,
            )
            await session.commit()

    @staticmethod
    def _client_ip(request: Request) -> str | None:
        if request.client is None:
            return None
        host = request.client.host
        if not host:
            return None
        # 驗 IP 格式（與 auth_router._client_ip 同邏輯）
        import ipaddress

        try:
            ipaddress.ip_address(host)
        except ValueError:
            return None
        return host


__all__ = ["AUDIT_EXCLUDED_PATH_PREFIXES", "AuditMiddleware", "should_audit"]
