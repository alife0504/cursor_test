"""Audit chain 校驗 task（PLAN 第 19.6 章 + 第 16.3 章告警）。

⚠️ P7 階段為 STUB
================
audit_repo.verify_chain() 在 P9 才會建立。本 task 在 P7 只 log warning + 回 stub
結果，beat schedule 仍註冊，方便 P9 升級時直接替換實作即可（schedule 不變）。

P9 升級後實作大致：
    async def _async_verify():
        async with ro_session() as s:
            ok, broken = await AuditRepository(s).verify_chain()
            if not ok:
                logger.critical("audit.chain.broken", broken_ids=broken)
                # P18：notification_service.send_critical(...)
            return {"status": "ok" if ok else "broken", "checked": ..., "broken": broken}
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.verify_audit.verify_chain",
    soft_time_limit=600,
    time_limit=900,
)
def verify_chain() -> dict[str, Any]:
    """重算 audit_logs hash chain — P7 為 stub（P9 升級為真實校驗）。"""
    logger.warning(
        "verify_audit_chain task is STUB until P9. "
        "Real verification will be added in Phase 9 (when audit_repo is built)."
    )
    return {
        "status": "stub",
        "checked": 0,
        "broken": [],
        "ran_at": datetime.now(UTC).isoformat(),
        "note": "P9 will replace with audit_repo.verify_chain()",
    }


__all__ = ["verify_chain"]
