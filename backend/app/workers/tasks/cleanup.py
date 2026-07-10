"""Orphan cleanup + idempotency_keys 過期清理（PLAN 第 15.4、14.5 章）。

每小時 :40（原每日 04:00；提高頻率讓 worker 崩潰留下的 running 孤兒盡快收斂）：
- analysis_reports: status='running' 超過 30 分 → 'failed'
- pending_orders: status='PENDING' 超過 7 天 → 'EXPIRED'
- password_reset_tokens: expires_at < now → 刪
- user_sessions: expires_at < now → 刪
- notification_log: sent_at < 90 天前 → 刪除（hypertable retention 也會處理，
  這裡額外提早刪減少 DB 體積）

每日 04:15：
- idempotency_keys: expires_at < now → 刪

設計：
- 用 sync_rw_session（celery context 跑同步 SQLAlchemy 較直觀）
- 全部用 raw text() / SQL update 一次 done，避免 ORM round-trip
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from celery.utils.log import get_task_logger
from sqlalchemy import text

from app.core.database import sync_rw_session
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


# ─────────── 排程入口 ───────────


@celery_app.task(
    name="app.workers.tasks.cleanup.cleanup_orphans",
    soft_time_limit=300,
    time_limit=600,
)
def cleanup_orphans() -> dict[str, Any]:
    """每日 orphan cleanup（PLAN 15.4）。"""
    now = datetime.now(UTC)
    counts: dict[str, int] = {}

    with sync_rw_session() as session:
        # 1. analysis_reports running > 30 min → failed
        stuck_threshold = now - timedelta(minutes=30)
        result = session.execute(
            text(
                """
                UPDATE analysis_reports
                   SET status = 'failed',
                       error_msg = COALESCE(error_msg, '')
                                 || ' [auto-failed by cleanup_orphans: stuck > 30min]',
                       updated_at = NOW()
                 WHERE status = 'running'
                   AND COALESCE(started_at, created_at) < :threshold
                """
            ),
            {"threshold": stuck_threshold},
        )
        counts["analysis_reports_failed"] = result.rowcount or 0

        # 1b. analysis_reports queued 過久 → failed（enqueue 失敗/worker 長期不在的兜底）。
        # ⚠️ 門檻必須 > 最壞批次排空時間：自動選股一次可 enqueue SCREEN_MAX_ANALYSES(30) 筆，每筆
        # soft_time_limit=900s、prefetch=1，忙碌時後段可能合法排隊 1~2 小時。門檻太短會把「仍在
        # 健康佇列等待」的項目誤標 failed，且與 _claim_report_for_run 的狀態守衛交互造成靜默掉單。
        # 故取 120min（遠超批次排空），另有 _claim_report_for_run 對此 sentinel 的 re-claim 作雙保險。
        queued_threshold = now - timedelta(minutes=120)
        result = session.execute(
            text(
                """
                UPDATE analysis_reports
                   SET status = 'failed',
                       error_msg = COALESCE(error_msg, '')
                                 || ' [auto-failed by cleanup_orphans: stuck in queued > 120min '
                                 || '(enqueue failed or worker unavailable)]',
                       updated_at = NOW()
                 WHERE status = 'queued'
                   AND created_at < :threshold
                """
            ),
            {"threshold": queued_threshold},
        )
        counts["analysis_reports_queued_failed"] = result.rowcount or 0

        # 2. pending_orders PENDING > 7 day → EXPIRED
        order_threshold = now - timedelta(days=7)
        result = session.execute(
            text(
                """
                UPDATE pending_orders
                   SET status = 'EXPIRED',
                       updated_at = NOW()
                 WHERE status = 'PENDING'
                   AND created_at < :threshold
                """
            ),
            {"threshold": order_threshold},
        )
        counts["pending_orders_expired"] = result.rowcount or 0

        # 3. password_reset_tokens 過期 → 刪
        result = session.execute(
            text(
                "DELETE FROM password_reset_tokens "
                "WHERE expires_at < :now OR (used = true AND used_at < :one_day_ago)"
            ),
            {"now": now, "one_day_ago": now - timedelta(days=1)},
        )
        counts["password_reset_tokens_deleted"] = result.rowcount or 0

        # 4. user_sessions 過期 → 刪
        result = session.execute(
            text(
                "DELETE FROM user_sessions "
                "WHERE expires_at < :now OR (revoked = true AND revoked_at < :one_day_ago)"
            ),
            {"now": now, "one_day_ago": now - timedelta(days=1)},
        )
        counts["user_sessions_deleted"] = result.rowcount or 0

        # 5. notification_log > 90 day → 刪（hypertable retention 為主，這裡 reinforce）
        notif_threshold = now - timedelta(days=90)
        result = session.execute(
            text("DELETE FROM notification_log WHERE sent_at < :threshold"),
            {"threshold": notif_threshold},
        )
        counts["notification_log_deleted"] = result.rowcount or 0

        # 6. news_metadata / announcements 無 hypertable 也無 retention（0005 只留「可手動」）→
        # 只增不減會讓 DB 與 GIN 索引無界膨脹。保守清理 > 1 年的舊資料（分析只看近期，
        # 1 年前新聞/公告對台股當下決策無價值）。
        news_threshold = now - timedelta(days=365)
        result = session.execute(
            text("DELETE FROM news_metadata WHERE published_at < :threshold"),
            {"threshold": news_threshold},
        )
        counts["news_metadata_deleted"] = result.rowcount or 0
        result = session.execute(
            text("DELETE FROM announcements WHERE published_at < :threshold"),
            {"threshold": news_threshold},
        )
        counts["announcements_deleted"] = result.rowcount or 0

        session.commit()

    logger.info("cleanup_orphans.done counts=%s", counts)
    return counts


@celery_app.task(
    name="app.workers.tasks.cleanup.cleanup_idempotency_keys",
    soft_time_limit=120,
    time_limit=300,
)
def cleanup_idempotency_keys() -> dict[str, Any]:
    """idempotency_keys 過期清理（TTL 24h，PLAN 14.5）。"""
    now = datetime.now(UTC)
    with sync_rw_session() as session:
        result = session.execute(
            text("DELETE FROM idempotency_keys WHERE expires_at < :now"),
            {"now": now},
        )
        deleted = result.rowcount or 0
        session.commit()
    logger.info("cleanup_idempotency_keys.done deleted=%d", deleted)
    return {"deleted": deleted}


__all__ = ["cleanup_idempotency_keys", "cleanup_orphans"]
