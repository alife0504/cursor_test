"""Audit chain 校驗 task（PLAN 第 19.6 章 + 第 16.3 章告警）。

P9 真實實作：用 AuditRepository.verify_chain() 重算全表 hash chain。
- 用 ro engine（防止 verify 意外寫入）
- 斷裂時 log CRITICAL（P18 才接 LINE / Telegram 告警）
- 排程：每日 04:30（P7 已註冊 beat schedule）
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


async def _async_verify() -> dict[str, Any]:
    """非同步執行 verify chain，於 task 內透過 asyncio.run 包起來。"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.core.database import get_ro_engine
    from app.repos.audit_repo import AuditRepository

    engine = get_ro_engine()
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        repo = AuditRepository(session)
        ok, broken = await repo.verify_chain()
    return {
        "ok": ok,
        "broken_count": len(broken),
        "broken_ids": broken[:10],  # 最多回前 10 筆避免訊息過大
    }


@celery_app.task(
    name="app.workers.tasks.verify_audit.verify_chain",
    soft_time_limit=600,
    time_limit=900,
)
def verify_chain() -> dict[str, Any]:
    """每日 04:30 排程觸發，跑 audit_logs hash chain 完整性校驗。"""
    started_at = datetime.now(UTC).isoformat()
    try:
        result = asyncio.run(_async_verify())
    except Exception as e:  # pragma: no cover  - 安全網
        logger.exception("audit_chain.verify_failed_with_exception")
        return {
            "status": "error",
            "error": type(e).__name__,
            "message": str(e),
            "ran_at": started_at,
        }

    if result["ok"]:
        logger.info(
            "audit_chain.integrity_ok",
            ran_at=started_at,
            broken_count=0,
        )
        return {
            "status": "ok",
            "ran_at": started_at,
            "broken_count": 0,
        }

    # 斷裂 → CRITICAL log（P18 才接通知）
    logger.critical(
        "audit_chain.broken",
        broken_count=result["broken_count"],
        broken_ids=result["broken_ids"],
        ran_at=started_at,
    )
    return {
        "status": "broken",
        "ran_at": started_at,
        "broken_count": result["broken_count"],
        "broken_ids": result["broken_ids"],
    }


__all__ = ["verify_chain"]
