#!/usr/bin/env python3
# scripts/slo_report.py
"""Phase 19 — SLO 24h 報表（依 PLAN 第 9.2 + 16.4 章）。

每天 06:00 透過 Celery beat 或 crontab 跑：
  uv run python scripts/slo_report.py

輸出：
  docs/slo_reports/YYYY-MM-DD.json

任一 SLO 未達 → 透過 NotificationDispatcher 廣播 WARN 給 admin。

SLO 指標：
  1. API 可用性（從 audit_logs 的 HTTP status）目標 99%
  2. 分析完成率（analysis_reports.status）目標 95%
  3. 分析延遲 P95（execution_time）目標 < 300s
  4. 資料新鮮度（最新 OHLCV 的 ingested_at）目標 < 60min
  5. Audit chain 完整性（verify_chain）目標 100%

  + 錯誤預算消耗率（error budget burn rate）
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text

# 讓 script 能 import backend.app
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

# noqa: E402 — 必須在 sys.path append 之後
from app.core.config import get_settings  # noqa: E402
from app.core.database import ro_session  # noqa: E402
from app.core.logging_config import get_logger  # noqa: E402
from app.models.analysis import AnalysisReport  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402
from app.models.price import StockPrice  # noqa: E402
from app.repos.audit_repo import AuditRepository  # noqa: E402

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════
# SLO 目標（PLAN 9.2）
# ════════════════════════════════════════════════════════
SLO_TARGETS = {
    "api_availability": 0.99,
    "analysis_completion_rate": 0.95,
    "analysis_latency_p95_sec": 300.0,
    "data_freshness_minutes": 60.0,
    "audit_integrity": True,
}


# ════════════════════════════════════════════════════════
# 個別 SLI 計算
# ════════════════════════════════════════════════════════
async def compute_api_availability(session, since: datetime) -> dict[str, Any]:
    """從 audit_logs.details->>'status' 統計 HTTP 5xx / total。

    details 結構：{"status": 200, "elapsed_ms": 42, "query": "..."}
    """
    # total request 數
    total = await session.scalar(
        select(func.count(AuditLog.id))
        .where(AuditLog.timestamp >= since)
        .where(AuditLog.action == "http.request")
    )
    total = total or 0

    failed = await session.scalar(
        select(func.count(AuditLog.id))
        .where(AuditLog.timestamp >= since)
        .where(AuditLog.action == "http.request")
        .where(text("(details->>'status')::int >= 500"))
    )
    failed = failed or 0

    availability = 1.0 - (failed / total) if total > 0 else 1.0
    target = SLO_TARGETS["api_availability"]
    return {
        "target": target,
        "actual": round(availability, 6),
        "passed": availability >= target,
        "samples": {"total": total, "failed_5xx": failed},
    }


async def compute_analysis_completion_rate(session, since: datetime) -> dict[str, Any]:
    """analysis_reports.status = completed / total（含 failed, cancelled）。"""
    total = await session.scalar(
        select(func.count(AnalysisReport.id)).where(AnalysisReport.created_at >= since)
    )
    total = total or 0
    completed = await session.scalar(
        select(func.count(AnalysisReport.id))
        .where(AnalysisReport.created_at >= since)
        .where(AnalysisReport.status == "completed")
    )
    completed = completed or 0

    rate = (completed / total) if total > 0 else 1.0
    target = SLO_TARGETS["analysis_completion_rate"]
    return {
        "target": target,
        "actual": round(rate, 6),
        "passed": rate >= target,
        "samples": {"total": total, "completed": completed},
    }


async def compute_analysis_latency_p95(session, since: datetime) -> dict[str, Any]:
    """完成的分析 P95 延遲（completed_at - started_at，秒）。

    PG percentile_cont(0.95) WITHIN GROUP (ORDER BY ...)。
    """
    sql = text(
        """
        SELECT percentile_cont(0.95) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))
        ) AS p95
        FROM analysis_reports
        WHERE status = 'completed'
          AND completed_at IS NOT NULL
          AND started_at IS NOT NULL
          AND created_at >= :since
        """
    )
    row = await session.execute(sql, {"since": since})
    p95 = row.scalar()
    p95_val = float(p95) if p95 is not None else 0.0
    target = SLO_TARGETS["analysis_latency_p95_sec"]
    return {
        "target": target,
        "actual": round(p95_val, 3),
        "passed": p95_val == 0.0 or p95_val <= target,
        "samples": {"note": "p95 of (completed_at - started_at) seconds"},
    }


async def compute_data_freshness(session) -> dict[str, Any]:
    """最新一筆 stock_prices.ingested_at vs now（分鐘）。

    台股 1330 收盤 → ~1430 入庫；隔日清晨統計用「24h 內最新」即可。
    """
    latest_ts = await session.scalar(select(func.max(StockPrice.ingested_at)))
    if latest_ts is None:
        return {
            "target": SLO_TARGETS["data_freshness_minutes"],
            "actual": None,
            "passed": False,
            "samples": {"note": "no stock_prices row"},
        }

    now = datetime.now(UTC)
    delta_min = (now - latest_ts).total_seconds() / 60.0
    target = SLO_TARGETS["data_freshness_minutes"]
    # 週末 / 假日資料源不更新；放寬週末檢查
    weekday = now.weekday()  # 0=Mon, 6=Sun
    if weekday in (5, 6):  # 週六、週日
        passed = True
        note = "weekend skipped"
    else:
        passed = delta_min <= target
        note = ""
    return {
        "target": target,
        "actual": round(delta_min, 2),
        "passed": passed,
        "samples": {"latest_ingested_at": latest_ts.isoformat(), "note": note},
    }


async def compute_audit_integrity(session, since: datetime) -> dict[str, Any]:
    """verify_chain — 對 24h 內 audit_logs 重算 hash 對比。"""
    repo = AuditRepository(session)
    ok, broken = await repo.verify_chain(since=since)
    return {
        "target": True,
        "actual": ok,
        "passed": ok,
        "samples": {"broken_ids": broken[:10], "broken_count": len(broken)},
    }


# ════════════════════════════════════════════════════════
# 錯誤預算消耗率（error budget burn rate）
# ════════════════════════════════════════════════════════
def compute_error_budget(slo: dict[str, dict[str, Any]]) -> dict[str, float]:
    """每個 SLO 的「24h 消耗率」= (1 - actual) / (1 - target)。

    > 1.0 表示這 24h 內消耗的錯誤預算已超出當天份額。
    """
    out: dict[str, float] = {}
    for key, item in slo.items():
        target = item.get("target")
        actual = item.get("actual")
        if target is None or actual is None or isinstance(target, bool):
            continue
        if not isinstance(actual, (int, float, Decimal)):
            continue
        target_f = float(target)
        actual_f = float(actual)
        # latency / freshness 是「越低越好」
        if key in ("analysis_latency_p95_sec", "data_freshness_minutes"):
            if target_f <= 0:
                continue
            burn = max(0.0, (actual_f - target_f) / target_f)
        else:
            # rate 類，越高越好
            denom = 1.0 - target_f
            if denom <= 0:
                continue
            burn = max(0.0, (target_f - actual_f) / denom)
        out[key] = round(burn, 4)
    return out


# ════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════
async def run() -> dict[str, Any]:
    settings = get_settings()
    now = datetime.now(UTC)
    since = now - timedelta(hours=24)

    async with ro_session() as s:
        api_avail = await compute_api_availability(s, since)
        compl_rate = await compute_analysis_completion_rate(s, since)
        latency_p95 = await compute_analysis_latency_p95(s, since)
        freshness = await compute_data_freshness(s)
        integrity = await compute_audit_integrity(s, since)

    slo: dict[str, dict[str, Any]] = {
        "api_availability": api_avail,
        "analysis_completion_rate": compl_rate,
        "analysis_latency_p95_sec": latency_p95,
        "data_freshness_minutes": freshness,
        "audit_integrity": integrity,
    }
    burn = compute_error_budget(slo)

    breached = [k for k, v in slo.items() if not v.get("passed")]

    report = {
        "timestamp": now.isoformat(),
        "period_hours": 24,
        "app_env": settings.APP_ENV,
        "slo": slo,
        "error_budget_consumption": burn,
        "breached_slo": breached,
        "overall_passed": len(breached) == 0,
    }
    return report


async def maybe_notify(report: dict[str, Any]) -> None:
    """若有 breach，用 system.alert 事件廣播 WARN（給所有 admin 訂閱者）。"""
    if report["overall_passed"]:
        return
    try:
        from app.notifications import (
            NotificationDispatcher,
            NotifyEvent,
            NotifyLevel,
        )

        dispatcher = NotificationDispatcher()
        breached = report["breached_slo"]
        title = f"⚠️ SLO breach (24h): {', '.join(breached)}"
        # 摘要長度受限；只回未達的指標
        breach_detail = {k: report["slo"][k] for k in breached}
        body = json.dumps(breach_detail, default=str, ensure_ascii=False, indent=2)
        event = NotifyEvent(
            event_type="system.alert",
            title=title,
            body=body,
            level=NotifyLevel.WARN,
            metadata={"source": "slo_report", "breached": breached},
        )
        await dispatcher.dispatch(event)
        logger.warning("slo.breach", breached=breached)
    except Exception as exc:  # noqa: BLE001 — 通知失敗不阻擋報表
        logger.error("slo.notify_failed", error=str(exc))


def write_report(report: dict[str, Any]) -> Path:
    out_dir = ROOT / "docs" / "slo_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    out_path = out_dir / f"{today}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    return out_path


async def main() -> int:
    report = await run()
    out_path = write_report(report)
    # 避免 Windows cp950 console 編碼問題：用 ASCII fallback
    try:
        print(f"OK  SLO report -> {out_path}")
    except UnicodeEncodeError:
        sys.stdout.buffer.write(f"OK  SLO report -> {out_path}\n".encode("utf-8"))
    print(f"    overall_passed = {report['overall_passed']}")
    if report["breached_slo"]:
        print(f"    breached: {report['breached_slo']}")
        await maybe_notify(report)
        return 1
    return 0


if __name__ == "__main__":
    # Windows console 編碼修正
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
            sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass
    sys.exit(asyncio.run(main()))
