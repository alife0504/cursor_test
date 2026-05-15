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

# ── Data pipeline ────────────────────────────────────
DATA_PIPELINE_LAST_SUCCESS = Gauge(
    "data_pipeline_last_success_seconds_ago",
    "資料管線上次成功距今秒數（依 worker 名稱）",
    ["worker"],
)

# ── Orders ────────────────────────────────────────────
ORDERS_APPROVED_TOTAL = Counter(
    "orders_approved_total",
    "已核准訂單累計",
)

ORDERS_REJECTED_TOTAL = Counter(
    "orders_rejected_total",
    "已拒絕訂單累計",
)


__all__ = [
    "ANALYSIS_DURATION",
    "ANALYSIS_TOTAL",
    "CELERY_DLQ_TOTAL",
    "CELERY_QUEUE_LENGTH",
    "DATA_PIPELINE_LAST_SUCCESS",
    "DB_CONNECTIONS_USED",
    "HTTP_REQUEST_DURATION",
    "LLM_COST_TODAY",
    "LLM_TOKENS_TOTAL",
    "ORDERS_APPROVED_TOTAL",
    "ORDERS_REJECTED_TOTAL",
]
