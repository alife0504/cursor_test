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

from datetime import timedelta

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
        "app.workers.tasks.adjusted",
        "app.workers.tasks.cleanup",
        "app.workers.tasks.verify_audit",
        # P12: LangGraph 主分析任務
        "app.workers.tasks.run_analysis",
        # 盤中即時走勢累積（每 10 秒）
        "app.workers.tasks.intraday",
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
    # 全域忽略 task 回傳值：本專案無任何 AsyncResult 讀取（前端輪詢 DB analysis_reports、
    # 非 celery 結果），且 intraday 每 10 秒的 fire-and-forget 結果曾實測堆積上萬個
    # celery-task-meta-* key 於 broker db1（白佔記憶體、拖慢 SCAN）。需回傳值的任務可個別
    # 加 @task(ignore_result=False)（目前無此需求；未用 chord/group）。
    task_ignore_result=True,
)


# ─────────── Beat schedule（PLAN 13.1 + Phase 7 prompt） ───────────
celery_app.conf.beat_schedule = {
    # 盤中即時走勢：每 10 秒累積加權/台指全一點到 Redis（讓走勢線一開盤就完整；
    # 休息時段任務內部自動略過）。FinMind 盤中序列有延遲，故靠即時 snapshot 累積。
    "intraday-accumulate": {
        "task": "app.workers.tasks.intraday.accumulate_intraday_tw",
        "schedule": timedelta(seconds=10),
        # expires：若 worker 被長分析佔滿（如自動選股 fan-out 30 筆 run_analysis）而 9 秒內
        # 排不到 slot，此 tick 直接作廢，不在 broker 堆積數百筆過時累積任務（餓死後集中排空）。
        "options": {"expires": 9},
    },
    # 台股 13:30 收盤 → 14:30 抓（給後台時間更新）
    "tw-ohlcv-after-close": {
        "task": "app.workers.tasks.sync_ohlcv.sync_ohlcv_tw_all",
        "schedule": crontab(hour=14, minute=30, day_of_week="mon-fri"),
    },
    # 大盤指數（TAIEX / TPEX）盤後：指數在 stock_list 是 market='OTHER'+is_active=false，
    # 不會被 tw-ohlcv-after-close 的 fan-out 選到 → 需獨立排程，否則 dashboard 指數永遠不動。
    "tw-index-after-close": {
        "task": "app.workers.tasks.sync_ohlcv.sync_index_tw",
        "schedule": crontab(hour=14, minute=35, day_of_week="mon-fri"),
    },
    # 台股還原權值回填：OHLCV 同步後（15:00）跑，把 FinMind 官方還原價寫入 adjusted_close。
    # 每日重跑因除權息會回溯重算歷史；週末也跑（回補假日新增的除息調整）。
    "tw-adjusted-close-daily": {
        "task": "app.workers.tasks.adjusted.sync_adjusted_close_tw",
        "schedule": crontab(hour=15, minute=0, day_of_week="mon-fri"),
    },
    # 美股盤後（ET 16:00 = 台北 04:00 隔日 / 夏令 05:00）→ 5:30 拉
    "us-ohlcv-after-close": {
        "task": "app.workers.tasks.sync_ohlcv.sync_ohlcv_us_all",
        "schedule": crontab(hour=5, minute=30, day_of_week="tue-sat"),
    },
    # TW 新聞每小時 15 分（FinMind 全市場，取代被 WAF 擋的 MOPS / 稀疏 RSS）
    "tw-news-hourly": {
        "task": "app.workers.tasks.news_ingest.ingest_tw_news_bulk",
        "schedule": crontab(minute=15),
    },
    # 官方重大訊息每日 15:20（TWSE 當日全市場，MOPS 替代，逐日累積）
    "tw-announcements-daily": {
        "task": "app.workers.tasks.news_ingest.ingest_tw_announcements",
        "schedule": crontab(hour=15, minute=20, day_of_week="mon-fri"),
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
    # TW 三大法人每日 15:00（盤後 1.5 小時）—— bulk 全市場（逐檔 fan-out 有 IP ban 風險，
    # 且 finmind 未涵蓋者落 twse_openapi 會存 0；bulk 一次抓全市場、標準定義聚合）。
    "tw-institutional-daily": {
        "task": "app.workers.tasks.financial.sync_institutional_bulk_tw",
        "schedule": crontab(hour=15, minute=0, day_of_week="mon-fri"),
    },
    # TW 融資融券每日 21:30 —— bulk 全市場，每日一請求（逐檔 fan-out 會 IP ban）。
    # 排 21:30 而非盤後 15:xx：TWSE 融資融券餘額約 21:00 才公布，太早跑抓不到當日；
    # 且 sync_margin_bulk 用 days_back=10 每次回抓近 10 天 → 即使某日 FinMind 延遲，
    # 隔天視窗仍會補上（idempotent upsert），不會有永久缺口。
    "tw-margin-daily": {
        "task": "app.workers.tasks.financial.sync_margin_bulk_tw",
        "schedule": crontab(hour=21, minute=30, day_of_week="mon-fri"),
    },
    # TW 選股指標快照每日 22:00（收盤後 PE/市值/RSI/EPS 成長全物化 → 選股篩選器用）。
    # 排最後：需當日 OHLCV（14:30）與 FinMind PER/市值 傍晚公布皆到位後才算得準。
    "tw-stock-metrics-daily": {
        "task": "app.workers.tasks.financial.sync_stock_metrics_tw",
        "schedule": crontab(hour=22, minute=0, day_of_week="mon-fri"),
    },
    # TW 公司基本資料每週日（靜態資料，變動極慢）
    "tw-company-info-weekly": {
        "task": "app.workers.tasks.financial.sync_company_info_tw",
        "schedule": crontab(hour=4, minute=0, day_of_week="sun"),
    },
    # TW 季報（IS/BS/CF）：財報公告期集中在 3/5/8/11 月中旬前，每週日補一次即可。
    # 先前完全沒有台股財報排程 → financial_statements 只有手動同步過的少數幾檔。
    "tw-quarterly-financial-weekly": {
        "task": "app.workers.tasks.financial.sync_quarterly_financial_tw",
        "schedule": crontab(hour=3, minute=0, day_of_week="sun"),
    },
    # Orphan cleanup 每小時（PLAN 15.4 原為每日 04:00；worker 崩潰留下的
    # status='running' 孤兒會讓前端無止境 5s 輪詢 → 改每小時，最慢 ~1.5h 內收斂）
    "cleanup-orphans-hourly": {
        "task": "app.workers.tasks.cleanup.cleanup_orphans",
        "schedule": crontab(minute=40),
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
