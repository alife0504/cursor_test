"""資料新鮮度 / 系統健康 —— 單一真相來源（供 /metrics gauge、/system/health 端點、前端警示 banner 共用）。

委託人收尾要求：「資料永遠正確且自動更新+自動檢查、發現異常網頁要顯示警示」。
本模組把「各關鍵表最新到哪天、落後幾天、是否超閾值」集中定義，讓：
- collect_runtime_metrics（Prometheus gauge）
- GET /system/data-freshness（前端 SystemHealthBanner + admin pipeline 頁）
- Prometheus alert rules（依 gauge 閾值）
三者用**同一份閾值與判定邏輯**，不會各自為政、彼此矛盾。

判定：staleness_days = 台北今日 - 該表最新資料日（曆日）。用曆日 + 各表寬鬆閾值吸收週末；
月頻/季頻表用較大閾值。狀態：<=warn→ok；<=crit→warn；>crit→critical。整體取最差。
（長假如農曆年市場連休 ~9 天時 daily 表會短暫 warn，屬可接受的少數真實「資料確實較舊」情形。）
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class FreshnessSpec:
    key: str
    label: str
    # 回傳「最新資料日(date)」的靜態 SQL（表名為常數、非使用者輸入）
    sql: str
    warn_days: int
    crit_days: int


# 各關鍵資料表的新鮮度規格（涵蓋所有 beat 自動更新的資料類型，補足原本只監控 3 表的盲區）。
_SPECS: tuple[FreshnessSpec, ...] = (
    FreshnessSpec(
        "stock_prices",
        "台股日K",
        "SELECT max(date) FROM stock_prices WHERE symbol ~ '^[0-9]'",
        4,
        8,
    ),
    # 大盤指數：原 staleness 用全表 max(date) 會被 2000+ 個股撐住 → 指數停更偵測不到。獨立量測。
    FreshnessSpec(
        "index",
        "大盤指數(TAIEX)",
        "SELECT max(date) FROM stock_prices WHERE symbol = 'TAIEX'",
        4,
        8,
    ),
    FreshnessSpec(
        "institutional_trading", "三大法人", "SELECT max(date) FROM institutional_trading", 4, 8
    ),
    FreshnessSpec("margin_trading", "融資融券", "SELECT max(date) FROM margin_trading", 5, 10),
    FreshnessSpec("stock_metrics", "選股指標", "SELECT max(as_of_date) FROM stock_metrics", 4, 8),
    FreshnessSpec(
        "trading_calendar",
        "交易日曆",
        "SELECT max(date) FROM trading_calendar WHERE market = 'TW'",
        6,
        12,
    ),
    # 月營收：月頻資料「天生」落後——某月營收次月 10 日才公告，故最新資料的月初日距今永遠約
    # 40~62 天仍屬正常。閾值須大於此天生落後：warn=75(缺上一個月)、crit=110(缺兩個月以上)，
    # 才不會對「已是最新可得月」的健康資料誤報。
    FreshnessSpec(
        "monthly_revenue",
        "月營收",
        "SELECT make_date((max(year*100+month))/100, (max(year*100+month))%100, 1) FROM monthly_revenue",
        75,
        110,
    ),
    FreshnessSpec("news", "新聞", "SELECT max(published_at)::date FROM news_metadata", 2, 5),
    FreshnessSpec(
        "announcements", "重大公告", "SELECT max(published_at)::date FROM announcements", 6, 12
    ),
)


def _status(staleness_days: int | None, spec: FreshnessSpec) -> str:
    if staleness_days is None:
        return "unknown"
    if staleness_days <= spec.warn_days:
        return "ok"
    if staleness_days <= spec.crit_days:
        return "warn"
    return "critical"


_RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}


async def compute_freshness(session: Any) -> dict[str, Any]:
    """計算所有關鍵表新鮮度 + DLQ，回傳結構化健康狀態（整體 status 取最差）。

    每個查詢獨立防護：單表失敗記 unknown 不影響其他，且不拋例外（絕不因健康檢查本身而讓
    /metrics 或 banner 端點掛掉）。
    """
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    checks: list[dict[str, Any]] = []

    for spec in _SPECS:
        latest: date | None = None
        try:
            latest = await session.scalar(text(spec.sql))
        except Exception as exc:
            logger.warning("freshness.query_failed key=%s error=%s", spec.key, exc)
            with __import__("contextlib").suppress(Exception):
                await session.rollback()
        staleness = (today - latest).days if latest is not None else None
        checks.append(
            {
                "key": spec.key,
                "label": spec.label,
                "as_of": latest.isoformat() if latest is not None else None,
                "staleness_days": staleness,
                "warn_days": spec.warn_days,
                "crit_days": spec.crit_days,
                "status": _status(staleness, spec),
            }
        )

    # DLQ 未解決筆數（pipeline 失敗訊號）
    dlq_pending: int | None = None
    dlq_status = "unknown"
    try:
        dlq_pending = int(
            await session.scalar(
                text("SELECT count(*) FROM celery_dead_letters WHERE resolved = false")
            )
            or 0
        )
        dlq_status = "ok" if dlq_pending == 0 else ("warn" if dlq_pending < 50 else "critical")
    except Exception as exc:
        logger.warning("freshness.dlq_failed error=%s", exc)
        with __import__("contextlib").suppress(Exception):
            await session.rollback()

    overall = "ok"
    for c in checks:
        if _RANK[c["status"]] > _RANK[overall]:
            overall = c["status"]
    if _RANK[dlq_status] > _RANK[overall]:
        overall = dlq_status

    # 給前端 banner 用的精簡訊息（只列真正異常者）
    problems = [c for c in checks if c["status"] in ("warn", "critical")]
    problem_labels = [f"{c['label']}({c['staleness_days']}天)" for c in problems]
    if dlq_status in ("warn", "critical"):
        problem_labels.append(f"任務失敗佇列({dlq_pending})")

    return {
        "status": overall,  # ok / warn / critical / unknown
        "checks": checks,
        "dlq_pending": dlq_pending,
        "dlq_status": dlq_status,
        "problem_summary": "、".join(problem_labels),
        "generated_at": datetime.now(UTC).isoformat(),
    }


__all__ = ["FreshnessSpec", "compute_freshness"]
