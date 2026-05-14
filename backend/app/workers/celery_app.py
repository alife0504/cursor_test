"""Celery app 工廠 — broker/backend 走 Redis db=1，beat 走 Asia/Taipei timezone。

依 PLAN.md 第 14.7 章 worker 設定 + 第 14.8 章任務超時 + 第 15.5 章時區三層
+ 第 13.1 章 Bootstrap 流程（5：celery_worker + celery_beat → 排程開始）。

設計：
- broker = backend = `redis://:<pwd>@<host>:<port>/1`
  與 main app 用 db=0 區分，避免 cache key 衝突（PLAN 第 14.5 章 idempotency 用 db=6）
- include 所有 task module（sync_ohlcv / news_ingest / financial / cleanup / verify_audit）
- 全域 default：task_time_limit=1200s（hard）/ soft=900s；個別 task 可覆寫
- beat schedule 依 TW/US 盤後時區安排
- import dlq 模組才能讓 task_failure signal 生效
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _build_redis_url(db: int) -> str:
    """從 settings 組 redis://:pwd@host:port/db。

    為什麼不直接用 `settings.redis_url(db)`：保留本檔可在 unit test 中
    monkeypatch `_build_redis_url` 改 broker（避免改 settings singleton）。
    """
    pwd = settings.REDIS_PASSWORD.get_secret_value()
    return f"redis://:{pwd}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{db}"


# Celery DB（broker + result backend 共用 db=1，跟 main app cache 的 db=0 隔離）
CELERY_REDIS_DB = 1


celery_app: Celery = Celery(
    "tradingagents",
    broker=_build_redis_url(CELERY_REDIS_DB),
    backend=_build_redis_url(CELERY_REDIS_DB),
    include=[
        "app.workers.tasks.sync_ohlcv",
        "app.workers.tasks.news_ingest",
        "app.workers.tasks.financial",
        "app.workers.tasks.cleanup",
        "app.workers.tasks.verify_audit",
    ],
)

# ─────────── 全域設定（PLAN 14.7 + 14.8） ───────────
celery_app.conf.update(
    # 時區：beat 用 Asia/Taipei，DB / log 仍 UTC（PLAN 15.5 三層規則）
    timezone=settings.DEFAULT_TIMEZONE,  # "Asia/Taipei"
    enable_utc=True,
    # task 追蹤
    task_track_started=True,
    # 預設超時（個別 task 可覆寫）— PLAN 14.8：sync_ohlcv soft=600/hard=900
    # 全域給寬鬆一點（hard=1200 / soft=900），避免長 task 被誤砍
    task_time_limit=1200,
    task_soft_time_limit=900,
    # Worker 設定（PLAN 14.7）
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    # 可靠性：late ack + reject on lost
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Beat 防 schedule miss（PLAN 已知陷阱：beat 重啟漏跑）
    beat_max_loop_interval=60,
    # JSON serializer（不用 pickle，避免反序列化 RCE）
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # result TTL：1 天就好（DLQ 已負責持久化失敗紀錄）
    result_expires=86400,
)


# ─────────── Beat schedule（PLAN 13.1 + Phase 7 prompt） ───────────
celery_app.conf.beat_schedule = {
    # 台股 13:30 收盤 → 14:30 抓（給後台時間更新）
    "tw-ohlcv-after-close": {
        "task": "app.workers.tasks.sync_ohlcv.sync_ohlcv_tw_all",
        "schedule": crontab(hour=14, minute=30, day_of_week="mon-fri"),
    },
    # 美股盤後（ET 16:00 = 台北 04:00 隔日 / 夏令 05:00）→ 5:30 拉
    "us-ohlcv-after-close": {
        "task": "app.workers.tasks.sync_ohlcv.sync_ohlcv_us_all",
        "schedule": crontab(hour=5, minute=30, day_of_week="tue-sat"),
    },
    # TW 新聞每小時 15 分（避開整點）
    "tw-news-hourly": {
        "task": "app.workers.tasks.news_ingest.ingest_tw_news",
        "schedule": crontab(minute=15),
    },
    # US 新聞每 3 小時 10 分
    "us-news-3h": {
        "task": "app.workers.tasks.news_ingest.ingest_us_news",
        "schedule": crontab(hour="*/3", minute=10),
    },
    # TW 月營收：每月 11 號（依公司法第 10 號公報，10 日前公告）
    "tw-monthly-revenue": {
        "task": "app.workers.tasks.financial.sync_monthly_revenue",
        "schedule": crontab(hour=9, minute=0, day_of_month=11),
    },
    # TW 三大法人每日 15:00（盤後 1.5 小時）
    "tw-institutional-daily": {
        "task": "app.workers.tasks.financial.sync_institutional_tw",
        "schedule": crontab(hour=15, minute=0, day_of_week="mon-fri"),
    },
    # Orphan cleanup 每日 04:00（PLAN 15.4）
    "cleanup-orphans-daily": {
        "task": "app.workers.tasks.cleanup.cleanup_orphans",
        "schedule": crontab(hour=4, minute=0),
    },
    # Idempotency-Key TTL 清理（每日 04:15，避開 orphan task）
    "cleanup-idempotency-daily": {
        "task": "app.workers.tasks.cleanup.cleanup_idempotency_keys",
        "schedule": crontab(hour=4, minute=15),
    },
    # Audit chain 校驗（P7 stub；P9 升級為真實 verify）
    "verify-audit-chain-daily": {
        "task": "app.workers.tasks.verify_audit.verify_chain",
        "schedule": crontab(hour=4, minute=30),
    },
}


# 觸發 dlq 的 signal 註冊（必須在 task module load 之前 import）
# 這裡只 import 一次；後續 task module 不需要再 import dlq
from app.workers import dlq as _dlq  # noqa: E402, F401  # side-effect: register signal

__all__ = ["CELERY_REDIS_DB", "celery_app"]
