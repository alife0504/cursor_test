"""Phase 11 — Prometheus metrics 中央定義。

依 PLAN.md 第 16.1 / 16.2 章：
- /metrics endpoint admin only
- 範例：analysis_total / analysis_duration_seconds / llm_cost_usd_today / ...

設計：
- 用 `prometheus_client` 的全域 REGISTRY（單例）
- 所有 router / service 用 `from app.core.metrics import ...` 來增加值
- /metrics endpoint 直接 `generate_latest()` 輸出
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ── 分析（analysis）────────────────────────────────────
ANALYSIS_TOTAL = Counter(
    "analysis_total",
    "分析請求總數（依 status 標籤）",
    ["status"],
)

ANALYSIS_DURATION = Histogram(
    "analysis_duration_seconds",
    "分析從 queued 到 completed 的耗時（秒）",
    buckets=(5, 10, 30, 60, 120, 300, 600, 1200, 1800),
)

# ── LLM 成本 ────────────────────────────────────────
LLM_COST_TODAY = Gauge(
    "llm_cost_usd_today",
    "今日 LLM 使用累計 USD（每日重置）",
)

LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "LLM tokens 累計（依 provider / model 標籤）",
    ["provider", "model"],
)

# ── HTTP / DB ───────────────────────────────────────
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request 耗時（依 method / status / path）",
    ["method", "status", "path"],
    buckets=(0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
)

DB_CONNECTIONS_USED = Gauge(
    "db_connections_used",
    "目前正在使用的 DB 連線數（依 pool 名稱）",
    ["pool"],
)

# ── Rate limit ────────────────────────────────────────
RATE_LIMIT_REDIS_ERRORS = Counter(
    "rate_limit_redis_errors_total",
    "Rate limiter Redis 失敗次數（fail-open；升高代表限流暫時失效，需關注 Redis）",
    ["layer"],
)

# ── Auth（JWT 黑名單）────────────────────────────────
AUTH_BLACKLIST_REDIS_ERRORS = Counter(
    "auth_blacklist_redis_errors_total",
    "JWT 黑名單檢查 Redis 失敗次數（fail-open 放行；升高代表撤銷檢查暫時失效，需關注 Redis）",
)

# ── Celery ────────────────────────────────────────────
CELERY_QUEUE_LENGTH = Gauge(
    "celery_queue_length",
    "Celery queue 待處理任務數（依 queue 名稱）",
    ["queue"],
)

CELERY_DLQ_TOTAL = Counter(
    "celery_dlq_total",
    "Celery DLQ 累計筆數（依 task_name）",
    ["task_name"],
)

# 註：原 DATA_PIPELINE_LAST_SUCCESS gauge 已移除——它宣告後全專案從未 .set()，是會誤導的
# 「假監控」死指標。pipeline 停更改由 data_staleness_days{table} 覆蓋（各關鍵表落後天數，
# 見 freshness_service），該指標有真實資料且已接 Prometheus alert rules。

# ── Orders ────────────────────────────────────────────
ORDERS_APPROVED_TOTAL = Counter(
    "orders_approved_total",
    "已核准訂單累計",
)

ORDERS_REJECTED_TOTAL = Counter(
    "orders_rejected_total",
    "已拒絕訂單累計",
)


# ── 抓取時即時計算的業務 gauge（pull 模型）────────────────────
# 分析跑在 celery 程序、HTTP 在 backend 程序，in-memory counter 無法跨程序；
# 這些數字改由 /metrics 被抓取時「即時查 DB/redis/pool」設定，保證與真實狀態一致。
ANALYSES_TODAY = Gauge("analyses_today", "今日分析數（依 status）", ["status"])
ANALYSES_RUNNING = Gauge("analyses_running", "目前進行中分析數")
LLM_TOKENS_TODAY = Gauge("llm_tokens_today", "今日 LLM tokens 合計")
DB_SIZE_BYTES = Gauge("db_size_bytes", "應用資料庫大小（bytes）")
DLQ_PENDING = Gauge("dlq_pending_total", "未解決 Celery DLQ 筆數")

# 資料新鮮度/完整度 —— 兜底「不報錯只變空」的靜默失效（本輪深度審查兩個最痛的 confirmed
# 缺陷：_merge_complete 落後時漏抓最新交易日、月營收成長率被同步抹成 NULL，都不拋例外、
# 不進 DLQ、healthcheck 全綠，只是資料變舊/變空）。超閾值時由 Prometheus 告警。
DATA_STALENESS_DAYS = Gauge(
    "data_staleness_days",
    "關鍵資料表最新日相對台北今日的落後天數（0=今日；持續>4 天=靜默停更，扣除週末後仍舊）",
    ["table"],
)
MONTHLY_REVENUE_YOY_NULL_RATIO = Gauge(
    "monthly_revenue_yoy_null_ratio",
    "近 24 個月月營收 revenue_yoy 為 NULL 的比例（衍生 task 失敗/被覆寫時逼近 1）",
)


async def collect_runtime_metrics(session: object) -> None:
    """/metrics 被抓取時呼叫：即時從 DB / redis / pool 設定業務 gauge。

    以 session（AsyncSession）查詢；每個查詢獨立防護：失敗即 rollback，避免污染同一
    session 的後續查詢（asyncpg 在錯誤後會進入 aborted transaction）。任何子項失敗都
    不擋整體 /metrics（process 指標仍會輸出）。
    """
    import contextlib
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from sqlalchemy import func, select, text

    from app.models.analysis import AnalysisReport
    from app.models.quota import LLMUsage

    now_tpe = datetime.now(ZoneInfo("Asia/Taipei"))
    today_start = now_tpe.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)

    async def _guard(fn: object) -> None:
        """跑單一查詢；失敗記 warning 並 rollback（避免污染 session 後續查詢）。"""
        try:
            await fn()  # type: ignore[operator]
        except Exception as exc:
            logger.warning(
                "metrics.collect_failed op=%s error=%s", getattr(fn, "__name__", "?"), exc
            )
            with contextlib.suppress(Exception):
                await session.rollback()  # type: ignore[attr-defined]

    async def _analyses_by_status() -> None:
        rows = await session.execute(  # type: ignore[attr-defined]
            select(AnalysisReport.status, func.count())
            .where(AnalysisReport.created_at >= today_start)
            .group_by(AnalysisReport.status)
        )
        seen = set()
        for status, cnt in rows:
            ANALYSES_TODAY.labels(status=status).set(int(cnt))
            seen.add(status)
        for st in ("queued", "running", "completed", "failed", "cancelled"):
            if st not in seen:
                ANALYSES_TODAY.labels(status=st).set(0)

    async def _running() -> None:
        r = await session.scalar(  # type: ignore[attr-defined]
            select(func.count())
            .select_from(AnalysisReport)
            .where(AnalysisReport.status == "running")
        )
        ANALYSES_RUNNING.set(int(r or 0))

    async def _cost() -> None:
        r = await session.scalar(  # type: ignore[attr-defined]
            select(func.coalesce(func.sum(LLMUsage.cost_usd), 0)).where(
                LLMUsage.created_at >= today_start
            )
        )
        LLM_COST_TODAY.set(float(r or 0))

    async def _tokens() -> None:
        r = await session.scalar(  # type: ignore[attr-defined]
            select(func.coalesce(func.sum(LLMUsage.total_tokens), 0)).where(
                LLMUsage.created_at >= today_start
            )
        )
        LLM_TOKENS_TODAY.set(int(r or 0))

    async def _dbsize() -> None:
        r = await session.scalar(text("SELECT pg_database_size(current_database())"))  # type: ignore[attr-defined]
        DB_SIZE_BYTES.set(int(r or 0))

    async def _dlq() -> None:
        r = await session.scalar(  # type: ignore[attr-defined]
            text("SELECT count(*) FROM celery_dead_letters WHERE resolved = false")
        )
        DLQ_PENDING.set(int(r or 0))

    async def _data_staleness() -> None:
        # 用共用 freshness 服務（單一真相來源）：涵蓋所有關鍵表（含原本被個股遮蔽的大盤指數、
        # 財報/月營收/選股指標/交易日曆/新聞/公告），與 /system/data-freshness 端點、alert
        # rules 同一份閾值與判定，避免各處各自為政。
        from app.services.freshness_service import compute_freshness

        health = await compute_freshness(session)  # type: ignore[arg-type]
        for c in health.get("checks", []):
            if c.get("staleness_days") is not None:
                DATA_STALENESS_DAYS.labels(table=c["key"]).set(int(c["staleness_days"]))

    async def _revenue_yoy_null() -> None:
        cutoff = (now_tpe.year - 2) * 100 + now_tpe.month  # 近 24 個月（YYYYMM 比較）
        r = await session.scalar(  # type: ignore[attr-defined]
            text(
                "SELECT count(*) FILTER (WHERE revenue_yoy IS NULL)::float "
                "/ NULLIF(count(*), 0) FROM monthly_revenue "
                "WHERE (year * 100 + month) >= :cutoff"
            ),
            {"cutoff": cutoff},
        )
        if r is not None:
            MONTHLY_REVENUE_YOY_NULL_RATIO.set(float(r))

    for op in (
        _analyses_by_status,
        _running,
        _cost,
        _tokens,
        _dbsize,
        _dlq,
        _data_staleness,
        _revenue_yoy_null,
    ):
        await _guard(op)

    # DB pool 使用中連線數
    with contextlib.suppress(Exception):
        from app.core.database import get_ro_engine, get_rw_engine

        for name, eng in (("rw", get_rw_engine()), ("ro", get_ro_engine())):
            with contextlib.suppress(Exception):
                DB_CONNECTIONS_USED.labels(pool=name).set(eng.pool.checkedout())

    # celery 佇列長度（broker redis db=CELERY 的 'celery' list）
    with contextlib.suppress(Exception):
        from app.core.redis_client import RedisDB, get_redis

        r = await get_redis(RedisDB.CELERY)
        CELERY_QUEUE_LENGTH.labels(queue="celery").set(int(await r.llen("celery")))


__all__ = [
    "ANALYSES_RUNNING",
    "ANALYSES_TODAY",
    "ANALYSIS_DURATION",
    "ANALYSIS_TOTAL",
    "CELERY_DLQ_TOTAL",
    "CELERY_QUEUE_LENGTH",
    "DATA_STALENESS_DAYS",
    "DB_CONNECTIONS_USED",
    "DB_SIZE_BYTES",
    "DLQ_PENDING",
    "HTTP_REQUEST_DURATION",
    "LLM_COST_TODAY",
    "LLM_TOKENS_TODAY",
    "LLM_TOKENS_TOTAL",
    "MONTHLY_REVENUE_YOY_NULL_RATIO",
    "ORDERS_APPROVED_TOTAL",
    "ORDERS_REJECTED_TOTAL",
    "RATE_LIMIT_REDIS_ERRORS",
    "collect_runtime_metrics",
]
