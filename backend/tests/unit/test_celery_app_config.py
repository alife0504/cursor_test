"""Celery app 設定單元測試（PLAN 第 14.7 章 + 14.10 章）。

只驗 conf 物件，不 connect Redis（不需 docker compose up）。
"""

from __future__ import annotations

import pytest

from app.workers.celery_app import CELERY_REDIS_DB, _build_redis_url, celery_app

pytestmark = pytest.mark.unit


def test_broker_url_uses_redis_password() -> None:
    """broker URL 含 settings.REDIS_PASSWORD（且不會在錯誤的地方有 SecretStr 物件 repr）。"""
    url = _build_redis_url(CELERY_REDIS_DB)
    assert url.startswith("redis://:")
    assert f"/{CELERY_REDIS_DB}" in url
    # SecretStr 不能洩漏進 URL
    assert "SecretStr" not in url


def test_celery_app_broker_and_backend_use_db_1() -> None:
    """Broker + result backend 都應該走 db=1（與 main app cache 用的 db=0 隔離）。"""
    assert celery_app.conf.broker_url.endswith("/1")
    assert celery_app.conf.result_backend.endswith("/1")


def test_timezone_is_taipei() -> None:
    """beat schedule 用 Asia/Taipei（PLAN 15.5 三層時區規則）。"""
    assert celery_app.conf.timezone == "Asia/Taipei"
    assert celery_app.conf.enable_utc is True


def test_task_time_limits_set() -> None:
    """全域 default 超時：hard ≥ soft，hard ≤ 1200s（PLAN 14.8）。"""
    soft = celery_app.conf.task_soft_time_limit
    hard = celery_app.conf.task_time_limit
    assert isinstance(soft, int) and isinstance(hard, int)
    assert hard >= soft > 0
    assert hard <= 1200


def test_beat_schedule_has_tw_ohlcv() -> None:
    """Beat schedule 必須有 TW OHLCV 排程（key = tw-ohlcv-after-close）。"""
    sched = celery_app.conf.beat_schedule
    assert "tw-ohlcv-after-close" in sched
    entry = sched["tw-ohlcv-after-close"]
    assert entry["task"] == "app.workers.tasks.sync_ohlcv.sync_ohlcv_tw_all"
    # crontab 物件有 hour / day_of_week / minute attribute
    cron = entry["schedule"]
    assert hasattr(cron, "hour")


def test_beat_schedule_has_us_ohlcv() -> None:
    """美股盤後排程也要在。"""
    sched = celery_app.conf.beat_schedule
    assert "us-ohlcv-after-close" in sched


def test_beat_schedule_has_cleanup_orphans() -> None:
    """Orphan cleanup 每日排程（PLAN 15.4）。"""
    sched = celery_app.conf.beat_schedule
    assert "cleanup-orphans-daily" in sched
    assert "cleanup-idempotency-daily" in sched


def test_beat_schedule_has_verify_audit() -> None:
    """Audit chain verify 排程（P9 升級為真實校驗）。"""
    sched = celery_app.conf.beat_schedule
    assert "verify-audit-chain-daily" in sched


def test_acks_late_enabled() -> None:
    """task_acks_late + reject_on_worker_lost = 可靠 worker（PLAN 14.7）。"""
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True


def test_worker_prefetch_and_max_tasks() -> None:
    """prefetch=1 / max_tasks_per_child=50（PLAN 14.7）。"""
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.worker_max_tasks_per_child == 50


def test_serializer_is_json_only() -> None:
    """禁用 pickle（避免反序列化 RCE）。"""
    assert celery_app.conf.task_serializer == "json"
    assert "json" in celery_app.conf.accept_content
    assert "pickle" not in celery_app.conf.accept_content


def test_includes_all_task_modules() -> None:
    """include 必須涵蓋 5 個 task module。"""
    expected = {
        "app.workers.tasks.sync_ohlcv",
        "app.workers.tasks.news_ingest",
        "app.workers.tasks.financial",
        "app.workers.tasks.cleanup",
        "app.workers.tasks.verify_audit",
    }
    actual = set(celery_app.conf.include or [])
    assert expected <= actual, f"missing modules: {expected - actual}"
