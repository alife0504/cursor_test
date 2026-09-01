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

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text
from starlette.responses import JSONResponse

from app.api.v1.admin_router import router as admin_router
from app.api.v1.analysis_router import router as analysis_router
from app.api.v1.auth_router import router as auth_router
from app.api.v1.exports_router import router as exports_router
from app.api.v1.market_router import router as market_router
from app.api.v1.metrics_router import router as metrics_router
from app.api.v1.notifications_router import router as notifications_router
from app.api.v1.orders_router import router as orders_router
from app.api.v1.portfolio_router import router as portfolio_router
from app.api.v1.reports_router import router as reports_router
from app.api.v1.screener_router import router as screener_router
from app.api.v1.statistics_router import router as statistics_router
from app.api.v1.stocks_router import router as stocks_router
from app.api.v1.system_router import router as system_router
from app.api.v1.users_router import router as users_router
from app.api.v1.watchlist_router import router as watchlist_router
from app.api.v1.ws_router import router as ws_router
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
from app.core.metrics_middleware import MetricsMiddleware
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
from app.llm import get_llm_chain

# 先 configure_logging 避免 import 期間的 log 沒設定好
configure_logging()
logger = get_logger(__name__)


async def _probe_with_retry(
    probe: Callable[[], Awaitable[None]],
    *,
    name: str,
    retries: int,
    delay_s: float,
) -> None:
    """跑 startup probe；失敗時退避重試，retries 用盡仍失敗才 raise。

    目的：讓「依賴啟動較慢 / 短暫抖動」(容器冷啟排序、筆電休眠喚醒、redis 重啟)
    不會一啟動就 raise 殺掉整個 process —— 服務能在依賴恢復後乾淨啟動，這對
    「持續運行、不隨意停止」很關鍵。真正長時間掛掉才 fail-fast（交給 supervisor 重啟）。
    """
    last: Exception | None = None
    total = max(1, retries)
    for attempt in range(1, total + 1):
        try:
            await probe()
            if attempt > 1:
                logger.info("startup.probe.recovered", probe=name, attempt=attempt)
            return
        except Exception as e:  # startup probe 要吞所有錯再決定 retry/fail
            last = e
            logger.warning(
                "startup.probe.retry",
                probe=name,
                attempt=attempt,
                retries=total,
                error=str(e),
            )
            if attempt < total:
                await asyncio.sleep(min(delay_s * attempt, 10.0))
    if last is not None:
        raise last


@asynccontextmanager
async def lifespan(app: FastAPI):
    """startup → 跑 probe（退避重試）；shutdown → dispose pool。"""
    logger.info(
        "app.startup",
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
        log_format=settings.LOG_FORMAT,
    )

    # 跳過 startup probe（pytest 用）
    if not settings.PYTEST_RUNNING:
        _retries = settings.STARTUP_PROBE_RETRIES
        _delay = settings.STARTUP_PROBE_DELAY_S
        try:
            await _probe_with_retry(
                test_db_connection, name="postgres", retries=_retries, delay_s=_delay
            )
        except Exception as e:
            logger.critical("db.startup_probe_failed", error=str(e))
            raise ExternalServiceError(message_zh="資料庫連線失敗", source="postgres") from e

        try:
            await _probe_with_retry(
                test_redis_connection, name="redis", retries=_retries, delay_s=_delay
            )
        except Exception as e:
            logger.critical("redis.startup_probe_failed", error=str(e))
            raise ExternalServiceError(message_zh="Redis 連線失敗", source="redis") from e

        # Qdrant 為「可降級」依賴（非核心）：僅 RAG 決策記憶會用到，agents/memory.py 全程對
        # Qdrant 失敗優雅降級（retrieve 回空、store no-op）。故啟動時 Qdrant 不可用**不阻斷**
        # 整個後端啟動——否則 Qdrant 一掛，連登入/看盤/報表等完全不碰 Qdrant 的網頁也全部無法
        # 服務（本不必要的 SPOF）。改為記錄 + 標記 app.state.qdrant_ready 供 /health/ready 回報。
        app.state.qdrant_ready = False
        try:
            await _probe_with_retry(
                test_qdrant_connection, name="qdrant", retries=_retries, delay_s=_delay
            )
            # P4：確保 Qdrant 7 個 collections 存在（idempotent）
            await ensure_collections()
            app.state.qdrant_ready = True
        except Exception as e:
            logger.critical(
                "qdrant.startup_degraded",
                error=str(e),
                note="Qdrant 不可用，後端仍啟動；決策記憶(RAG)降級，其餘功能不受影響",
            )

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

    # P14：建 LLM Fallback Chain + 每個 provider 跑 readiness ping
    # PYTEST_RUNNING 跳過真實 ping（避免 unit/integration test 燒配額）
    try:
        app.state.llm_chain = get_llm_chain(settings)
        if not settings.PYTEST_RUNNING:
            for name, provider in app.state.llm_chain.providers.items():
                try:
                    ok = await provider.health_check()
                except Exception as exc:  # pragma: no cover
                    ok = False
                    logger.warning("llm.health.exception", provider=name, error=str(exc))
                logger.info("llm.health.checked", provider=name, ok=ok)
        logger.info(
            "llm_chain.ready",
            primary=app.state.llm_chain.primary,
            providers=list(app.state.llm_chain.providers.keys()),
        )
    except ValueError as e:
        # 無任何 LLM provider 配置 → prod 應該 fatal；dev 也阻塞啟動（避免 silent 失敗）
        logger.critical("llm_chain.no_provider", error=str(e))
        raise ExternalServiceError(message_zh=str(e), source="llm") from e

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


# ── Middleware（Phase 9 + Phase 12 audit fix）─────────────────────
# Starlette 規則：`add_middleware()` 用 `list.insert(0, ...)` 把新 middleware 放最前
# → request 進入時從 user_middleware[0] 開始；最後 add 的最外層、第一個 add 的最內層
#
# Phase 12 audit fix：RequestID 必須最外層（最後 add），讓所有 response（含 BodySize/CSRF/
# RateLimit 短路 413/403/429）都能帶到 X-Request-ID；audit middleware 也要外於 short-circuit
# middleware 才能 log 到「被擋住的攻擊行為」。
#
# 預期執行順序（request 進入 → response 出去）：
#   1. RequestIDMiddleware（最外層；產 trace_id；所有 response 必經此處加 X-Request-ID）
#   2. SecurityHeadersMiddleware（response header 加 CSP / X-Frame-Options 等）
#   3. CORSMiddleware（CORS pre-flight）
#   4. AuditMiddleware（包含 short-circuit response 都會寫 audit）
#   5. RateLimitMiddleware（Redis-based L1-L3 擋暴衝）
#   6. CSRFMiddleware（POST/PUT/DELETE 驗 X-CSRF-Token）
#   7. BodySizeMiddleware（最內層；Content-Length > 1MB 直接 413）
#
# 因此 add 順序（先 add 的最內層）由內到外：
add_order_inner_to_outer = [
    BodySizeMiddleware,  # 最先 add = 最內層（最接近 endpoint）
    CSRFMiddleware,
    RateLimitMiddleware,
    AuditMiddleware,  # 在 short-circuit middleware 外層 → 可 log 被擋的 request
    CORSMiddleware,
    SecurityHeadersMiddleware,
    RequestIDMiddleware,  # 最後 add = 最外層 → 所有 response 都帶 X-Request-ID
]

app.add_middleware(BodySizeMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MetricsMiddleware)  # 觀測 HTTP 耗時/狀態（Prometheus）
app.add_middleware(RequestIDMiddleware)  # 必須最後 add（最外層）

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

# Phase 11: 業務 API 第二批 + admin + ws + /metrics
app.include_router(analysis_router)
app.include_router(orders_router)
app.include_router(portfolio_router)
app.include_router(reports_router)
app.include_router(statistics_router)
app.include_router(exports_router)
app.include_router(notifications_router)
app.include_router(admin_router)
app.include_router(ws_router)
app.include_router(metrics_router)
app.include_router(system_router)


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

    # Qdrant：可降級依賴。不可用時標 degraded 但**不翻 not_ready**（後端仍能服務所有非 RAG 功能，
    # 決策記憶降級）。與啟動時 Qdrant 非致命的設計一致；監控可據 degraded 告警。
    try:
        await test_qdrant_connection()
        deps["qdrant"] = "ok"
    except Exception as e:
        deps["qdrant"] = f"degraded: {type(e).__name__}"

    body = envelope_success(
        {"status": "ready" if all_ok else "not_ready", "dependencies": deps},
        trace_id=request.state.trace_id,
    )
    return JSONResponse(status_code=200 if all_ok else 503, content=body)


@app.get("/health/workers", tags=["health"])
async def health_workers(request: Request) -> JSONResponse:
    """Celery worker/broker 活性探針（供監控告警用；不影響 /health/ready）。

    深度審計發現：/health/ready 只驗 DB/Redis/Qdrant，worker 全掛時 API 仍回 200 →
    分析請求全部堆在 queued 卻無人處理、無自動偵測面。此端點以 celery inspect ping
    （短 timeout）回報線上 worker 數；worker 皆離線時回 503，供監控告警。
    """
    import asyncio

    workers: dict[str, Any] = {}
    ok = True
    try:
        from app.workers.celery_app import celery_app as _celery

        # celery control.ping 是同步阻塞呼叫（最長 timeout 秒）；用 to_thread 丟到執行緒，
        # 避免在 async 端點裡卡住整個 event loop（否則探針期間全 API 停擺）。
        replies = await asyncio.to_thread(lambda: _celery.control.ping(timeout=2.0) or [])
        online = [next(iter(r.keys())) for r in replies if isinstance(r, dict) and r]
        workers = {"online_count": len(online), "workers": online}
        ok = len(online) > 0
    except Exception as e:  # pragma: no cover - 探針本身失敗
        workers = {"error": f"{type(e).__name__}: {e}"}
        ok = False

    body = envelope_success(
        {"status": "ok" if ok else "no_workers", "celery": workers},
        trace_id=request.state.trace_id,
    )
    return JSONResponse(status_code=200 if ok else 503, content=body)


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
