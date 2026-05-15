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
from sqlalchemy import func, text
from starlette.responses import JSONResponse

from app.api.v1.auth_router import router as auth_router
from app.api.v1.market_router import router as market_router
from app.api.v1.screener_router import router as screener_router
from app.api.v1.stocks_router import router as stocks_router
from app.api.v1.users_router import router as users_router
from app.api.v1.watchlist_router import router as watchlist_router
from app.core.audit_middleware import AuditMiddleware
from app.core.body_size_middleware import BodySizeMiddleware
from app.core.config import settings
from app.core.csrf_middleware import CSRFMiddleware
from app.core.database import (
    dispose_db_connections,
    get_ro_engine,
    get_rw_engine,
    test_db_connection,
)
from app.core.error_handlers import register_exception_handlers
from app.core.errors import ExternalServiceError
from app.core.logging_config import configure_logging, get_logger
from app.core.market_dispatcher import MarketDispatcher
from app.core.qdrant_client import (
    dispose_qdrant_client,
    test_qdrant_connection,
)
from app.core.qdrant_init import ensure_collections
from app.core.rate_limit import RateLimitMiddleware
from app.core.redis_client import (
    RedisDB,
    dispose_redis_pools,
    get_redis,
    test_redis_connection,
)
from app.core.request_id import RequestIDMiddleware
from app.core.response_envelope import envelope_success
from app.core.security import JWTService, TokenBlacklist
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.ws_ticket import WSTicketService
from app.data_sources.tw import get_tw_sources
from app.data_sources.us import get_us_sources

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

        # P4：確保 Qdrant 7 個 collections 存在（idempotent）
        try:
            await ensure_collections()
        except Exception as e:
            logger.critical("qdrant.ensure_collections_failed", error=str(e))
            raise ExternalServiceError(
                message_zh="Qdrant collections 初始化失敗", source="qdrant"
            ) from e

    # P6：建立跨市場 dispatcher（即使 PYTEST_RUNNING 也建，但不打網路）
    try:
        app.state.dispatcher = MarketDispatcher(
            tw_sources=get_tw_sources(settings),
            us_sources=get_us_sources(settings),
        )
        logger.info(
            "market_dispatcher.ready",
            tw_kinds=sorted(k.value for k in app.state.dispatcher.tw),
            us_kinds=sorted(k.value for k in app.state.dispatcher.us),
        )
    except Exception as e:
        logger.critical("market_dispatcher.init_failed", error=str(e))
        raise ExternalServiceError(
            message_zh="MarketDispatcher 初始化失敗", source="dispatcher"
        ) from e

    # P8：auth 相關 service 掛 app.state（讓 router 取用同一份單例）
    try:
        app.state.jwt_service = JWTService(settings)
        ws_redis = await get_redis(RedisDB.WS_TICKET)
        app.state.ws_ticket_service = WSTicketService(ws_redis)
        bl_redis = await get_redis(RedisDB.JWT_BLACKLIST)
        app.state.token_blacklist = TokenBlacklist(bl_redis)
        logger.info(
            "auth.services.ready",
            access_ttl_min=int(JWTService.ACCESS_TTL.total_seconds() // 60),
            refresh_ttl_days=int(JWTService.REFRESH_TTL.total_seconds() // 86400),
        )
    except Exception as e:
        logger.critical("auth.services.init_failed", error=str(e))
        raise ExternalServiceError(message_zh="Auth 服務初始化失敗", source="auth") from e

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


# ── Middleware（Phase 9）─────────────────────
# Starlette 規則：最後 add 的 middleware 最先進、最後出（LIFO）。
#
# 預期執行順序（request 進入 → response 出去）：
#   1. SecurityHeadersMiddleware（最外層；幫 response 加 header）
#   2. CORSMiddleware（CORS pre-flight）
#   3. RateLimitMiddleware（Redis-based L1-L3 擋暴衝）
#   4. CSRFMiddleware（POST/PUT/DELETE 驗 X-CSRF-Token）
#   5. BodySizeMiddleware（Content-Length > 1MB 直接 413）
#   6. AuditMiddleware（response 後寫 audit_logs）
#   7. RequestIDMiddleware（最內層；產 trace_id）
#
# 因此 add 順序（先 add 的最內層）由內到外：
add_order_inner_to_outer = [
    RequestIDMiddleware,  # 最先 add = 最內層
    AuditMiddleware,
    BodySizeMiddleware,
    CSRFMiddleware,
    RateLimitMiddleware,
]

app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(BodySizeMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)

# 抑制 unused 變數警告（這個 list 只是文件化用）
_ = add_order_inner_to_outer


# ── Exception handlers ────────────────────────────────────
register_exception_handlers(app)


# ── Routers ───────────────────────────────────────────────
# Phase 8: auth router
app.include_router(auth_router)

# Phase 10: 業務 API 第一批
app.include_router(stocks_router)
app.include_router(watchlist_router)
app.include_router(market_router)
app.include_router(screener_router)
app.include_router(users_router)


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
    """seeded 條件（PLAN 第 13.3 章）：stock_list ≥ 100 + 至少 1 支有 OHLCV。

    回 200 + envelope；data.seeded 為 bool，data.stock_count / data.has_prices 提供 detail。
    DB 查詢失敗 → seeded=false + reason="db_error"（不回 5xx，避免讓 onboarding 死循環）。
    """
    from sqlalchemy import select

    from app.models.price import StockPrice
    from app.models.stock import StockList

    data: dict[str, Any] = {
        "seeded": False,
        "stock_count": 0,
        "has_prices": False,
        "threshold_stock": 100,
    }

    try:
        ro = get_ro_engine()
        async with ro.connect() as conn:
            stock_count = (
                await conn.execute(select(func.count()).select_from(StockList))
            ).scalar() or 0
            data["stock_count"] = int(stock_count)

            has_prices_row = (await conn.execute(select(StockPrice.symbol).limit(1))).first()
            data["has_prices"] = has_prices_row is not None

        data["seeded"] = data["stock_count"] >= 100 and data["has_prices"]
        if not data["seeded"]:
            reason_parts: list[str] = []
            if data["stock_count"] < 100:
                reason_parts.append(
                    f"stock_list={data['stock_count']} < 100（先跑 make seed-stocks）"
                )
            if not data["has_prices"]:
                reason_parts.append(
                    'stock_prices 為空（先跑 make backfill ARGS="--region TW --symbol 2330 --years 1"）'
                )
            data["reason"] = "; ".join(reason_parts)
    except Exception as exc:  # pragma: no cover  - defensive
        logger.warning("health.seeded.query_failed", error=str(exc))
        data["reason"] = f"db_error: {type(exc).__name__}"

    return JSONResponse(
        status_code=200,
        content=envelope_success(data, trace_id=request.state.trace_id),
    )


__all__ = ["app"]
