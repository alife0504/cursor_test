"""盤中即時走勢累積背景任務。

每 ~10 秒把加權指數 / 台指全的即時 snapshot 累積一點到 Redis，讓走勢線「一開盤就完整」——
因為 FinMind 的盤中序列（5 秒指數 / 逐筆）有發布延遲（當日盤中常抓到 0 筆、盤後才出），
只能靠即時 snapshot 逐點累積。休息時段自動不累積（見 accumulate_intraday_point）。
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging_config import get_logger
from app.services.market_service import MarketService
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.intraday.accumulate_intraday_tw",
    soft_time_limit=25,
    time_limit=40,
)
def accumulate_intraday_tw() -> dict[str, Any]:
    """每 10 秒（beat）累積加權/台指全一點；休息時段內部自動略過。"""
    return asyncio.run(_async_accumulate())


async def _async_accumulate() -> dict[str, Any]:
    # 累積只用 Redis + FinMind 即時源，不需 DB session
    svc = MarketService(None)  # type: ignore[arg-type]
    done: list[str] = []
    for sym in ("TAIEX", "TXF"):
        try:
            await svc.accumulate_intraday_point(sym)
            done.append(sym)
        except Exception as exc:  # 單一 symbol 失敗不影響另一個
            logger.warning("intraday.accumulate_failed", symbol=sym, error=str(exc))
    return {"ok": True, "accumulated": done}
