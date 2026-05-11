"""FastAPI app entrypoint — Phase 3 最小版。

依 PLAN.md 第 13.3 章三層健康檢查 + 第 17 章工程規範。

提供：
- /health/live    程式還活著
- /health/ready   依賴可連（DB / Redis / Qdrant）
- /health/seeded  P7 stock_list seed 完才回 true（暫回 false）

Lifespan：
- startup：configure_logging → 三服務 fail-fast probe
- shutdown：dispose connection pools

Middleware（外 → 內）：
1. SecurityHeadersMiddleware
2. CORSMiddleware
3. RequestIDMiddleware
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.database import (
    dispose_db_connections,
    get_ro_engine,
    get_rw_engine,
    test_db_connection,
)
from app.core.error_handlers import register_exception_handlers
from app.core.errors import ExternalServiceError
from app.core.logging_config import configure_logging, get_logger
from app.core.qdrant_client import (
    dispose_qdrant_client,
    test_qdrant_connection,
)
from app.core.redis_client import (
    RedisDB,
    dispose_redis_pools,
    get_redis,
    test_redis_connection,
)
from app.core.request_id import RequestIDMiddleware
from app.core.response_envelope import envelope_success
from app.core.security_headers import SecurityHeadersMiddleware

# 先 configure_logging 避免 import 期間的 log 沒設定好
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """startup → 跑 fail-fast probe；shutdown → dispose pool。"""
    logger.info(
        "app.startup",
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
        log_format=settings.LOG_FORMAT,
    )

    # 跳過 startup probe（pytest 用）
    if not settings.PYTEST_RUNNING:
        try:
            await test_db_connection()
        except Exception as e:
            logger.critical("db.startup_probe_failed", error=str(e))
            raise ExternalServiceError(message_zh="資料庫連線失敗", source="postgres") from e

        try:
            await test_redis_connection()
        except Exception as e:
            logger.critical("redis.startup_probe_failed", error=str(e))
            raise ExternalServiceError(message_zh="Redis 連線失敗", source="redis") from e

        try:
            await test_qdrant_connection()
        except Exception as e:
            logger.critical("qdrant.startup_probe_failed", error=str(e))
            raise ExternalServiceError(message_zh="Qdrant 連線失敗", source="qdrant") from e

    yield

    logger.info("app.shutdown")
    await dispose_db_connections()
    await dispose_redis_pools()
    await dispose_qdrant_client()


app = FastAPI(
    title="TradingAgents-TW Secure Edition",
    version=settings.APP_VERSION,
    description="多 Agent AI 投資分析平台 — 台股主、美股輔",
    lifespan=lifespan,
    # docs / redoc 在 dev 開放，prod 視需要關閉（P19 處理）
    docs_url="/docs" if settings.APP_ENV != "prod" else None,
    redoc_url="/redoc" if settings.APP_ENV != "prod" else None,
    openapi_url="/openapi.json" if settings.APP_ENV != "prod" else None,
)


# ── Middleware（外層先 add，最後執行）─────────────────────
# Starlette 規則：最後 add 的 middleware 最先進、最後出
# 順序（外 → 內）：SecurityHeaders → CORS → RequestID
# 因此 add 順序（先 add 的最內層）：RequestID → CORS → SecurityHeaders

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)


# ── Exception handlers ────────────────────────────────────
register_exception_handlers(app)


# ════════════════ Health endpoints ════════════════


@app.get("/health/live", tags=["health"])
async def health_live(request: Request) -> JSONResponse:
    """程式還活著（不檢查依賴）。"""
    return JSONResponse(
        status_code=200,
        content=envelope_success(
            {"status": "alive", "version": settings.APP_VERSION},
            trace_id=request.state.trace_id,
        ),
    )


@app.get("/health/ready", tags=["health"])
async def health_ready(request: Request) -> JSONResponse:
    """依賴可連 + DB pool 至少 1 idle + redis ping + qdrant healthz。"""
    deps: dict[str, Any] = {}
    all_ok = True

    # DB rw + ro
    try:
        rw = get_rw_engine()
        async with rw.connect() as conn:
            await conn.execute(text("SELECT 1"))
        ro = get_ro_engine()
        async with ro.connect() as conn:
            await conn.execute(text("SELECT 1"))
        deps["db"] = "ok"
    except Exception as e:
        deps["db"] = f"error: {type(e).__name__}"
        all_ok = False

    # Redis
    try:
        redis = await get_redis(RedisDB.CACHE)
        ok = await redis.ping()
        deps["redis"] = "ok" if ok else "error"
        if not ok:
            all_ok = False
    except Exception as e:
        deps["redis"] = f"error: {type(e).__name__}"
        all_ok = False

    # Qdrant
    try:
        await test_qdrant_connection()
        deps["qdrant"] = "ok"
    except Exception as e:
        deps["qdrant"] = f"error: {type(e).__name__}"
        all_ok = False

    body = envelope_success(
        {"status": "ready" if all_ok else "not_ready", "dependencies": deps},
        trace_id=request.state.trace_id,
    )
    return JSONResponse(status_code=200 if all_ok else 503, content=body)


@app.get("/health/seeded", tags=["health"])
async def health_seeded(request: Request) -> JSONResponse:
    """P7 stock_list seed 完才回 true。P3 階段暫回 false。"""
    return JSONResponse(
        status_code=200,
        content=envelope_success(
            {"seeded": False, "reason": "P7 not done (stock_list 尚未 seed)"},
            trace_id=request.state.trace_id,
        ),
    )


__all__ = ["app"]
