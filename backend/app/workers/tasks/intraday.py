"""盤中即時走勢累積背景任務。

每 ~10 秒把加權指數 / 台指全的即時 snapshot 累積一點到 Redis，讓走勢線「一開盤就完整」——
因為 FinMind 的盤中序列（5 秒指數 / 逐筆）有發布延遲（當日盤中常抓到 0 筆、盤後才出），
只能靠即時 snapshot 逐點累積。休息時段自動不累積（見 accumulate_intraday_point）。
"""

from __future__ import annotations

import asyncio
import contextlib
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
    from celery.exceptions import SoftTimeLimitExceeded

    try:
        return asyncio.run(_async_accumulate())
    except SoftTimeLimitExceeded:
        # fire-and-forget：某 tick 因即時源(FinMind realtime)慢而逾時屬正常噪音，下一 tick(10s 後)
        # 即重試。優雅回收、**不讓例外傳播進 DLQ**（否則盤中每次慢就污染 DLQ、觸發前端警示 banner）。
        logger.warning("intraday.soft_timeout_skipped")
        return {"ok": False, "skipped": "soft_timeout"}


async def _async_accumulate() -> dict[str, Any]:
    # 累積只用 Redis + FinMind 即時源，不需 DB session
    from app.core.redis_client import dispose_redis_pools

    svc = MarketService(None)  # type: ignore[arg-type]
    done: list[str] = []
    try:
        for sym in ("TAIEX", "TXF"):
            try:
                await svc.accumulate_intraday_point(sym)
                done.append(sym)
            except Exception as exc:  # 單一 symbol 失敗不影響另一個
                logger.warning("intraday.accumulate_failed", symbol=sym, error=str(exc))
        return {"ok": True, "accumulated": done}
    finally:
        # Celery 每 tick 都用新的 asyncio.run() → 新 event loop；全域 async redis pool 的連線
        # 綁在上一個（已關閉）loop 上，下一 tick 第一個 redis 操作會丟 'Event loop is closed'
        # 被靜默吞成 cache-miss（實測 4 天 3.8 萬次 log 洪水，淹沒真正的 redis 故障訊號）。
        # tick 結束即釋放 pool，讓下一 tick 在自己的 loop 重建乾淨連線。prefork worker 單一
        # 子行程一次只跑一個 task（prefetch=1），此 dispose 不會影響其他任務。
        with contextlib.suppress(Exception):  # 釋放失敗不可影響任務結果
            await dispose_redis_pools()
