"""台股還原權值回填 — 把 FinMind 官方還原價寫入 stock_prices.adjusted_close。

來源：finmind-platform 的 `bronze.taiwan_stock_price_adj`（含息 back-adjust，最新日錨定＝raw；
權威、零數學風險）。目的：讓 statistics/backtest 的報酬用「含息還原價」計算，除息跳空
不再被誤當虧損（除息旺季 BUY 命中率不再被系統性低估）。

設計：
- 讀本地一次（date >= 我方 stock_prices 最小日），Python 依 stock_id 分組，逐標的用
  `unnest` 成對陣列做批次 UPDATE（只改 adjusted_close 有變動的列，冪等）。
- 還原價會隨新除權息「回溯重算歷史」→ 本任務排程每日重跑，保持 adjusted_close 最新。
- 指數（TAIEX/TPEX）、權證、美股在 adj 表無對應 → 該欄維持 NULL，下游 COALESCE 退回 close。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date
from typing import Any

from celery.utils.log import get_task_logger
from sqlalchemy import Date, Numeric, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.database import make_worker_engine
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


def _new_engine_sm():
    engine = make_worker_engine(settings.postgres_dsn_rw, name="adjusted")
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(
    name="app.workers.tasks.adjusted.sync_adjusted_close_tw",
    soft_time_limit=600,
    time_limit=900,
    max_retries=0,
)
def sync_adjusted_close_tw(since: str | None = None) -> dict[str, Any]:
    """台股 stock_prices.adjusted_close 回填/更新（every-day 排程 + 一次性 backfill）。

    Args:
        since: 只回填該日（含）之後；None＝我方 stock_prices 最小日（全回填）。
    """
    since_d = date.fromisoformat(since) if since else None
    return asyncio.run(_async_sync_adjusted_close(since_d))


async def _async_sync_adjusted_close(since: date | None) -> dict[str, Any]:
    if not settings.FINMIND_LOCAL_ENABLED or not settings.FINMIND_LOCAL_PASSWORD:
        logger.warning("adjusted_close.skip finmind_local 未啟用")
        return {"skipped": "finmind_local_disabled"}

    from app.data_sources.tw.finmind_local_source import FinMindLocalSource

    fm = FinMindLocalSource(settings)
    engine, sm = _new_engine_sm()
    try:
        # 我方台股標的 + 起始日
        async with sm() as s:
            our_syms = set(
                (await s.execute(text("SELECT DISTINCT symbol FROM stock_prices"))).scalars().all()
            )
            if since is None:
                since = await s.scalar(text("SELECT min(date) FROM stock_prices"))
        if since is None or not our_syms:
            return {"skipped": "no_local_prices"}

        # 本地還原價（一次撈；只保留我方有的標的）
        adj_rows = await fm._query(
            "SELECT stock_id, date, close FROM bronze.taiwan_stock_price_adj WHERE date >= $1",
            since,
        )
        by_sym: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
        for r in adj_rows:
            sid = r["stock_id"]
            if sid in our_syms and r["close"] is not None:
                by_sym[sid][0].append(r["date"])
                by_sym[sid][1].append(r["close"])

        # 逐標的 unnest 成對陣列批次 UPDATE（只改有變動的列）
        # 顯式 ARRAY bindparam：避免 SQLAlchemy 把 list 當 IN 展開；asyncpg 正確編碼為 PG 陣列。
        upd = text(
            """
                UPDATE stock_prices sp
                SET adjusted_close = v.adj
                FROM unnest(:dates, :adjs) AS v(dt, adj)
                WHERE sp.symbol = :sym AND sp.date = v.dt
                  AND sp.adjusted_close IS DISTINCT FROM v.adj
                """
        ).bindparams(
            bindparam("dates", type_=ARRAY(Date)),
            bindparam("adjs", type_=ARRAY(Numeric)),
        )
        updated = 0
        async with sm() as s:
            for sym, (dates, adjs) in by_sym.items():
                res = await s.execute(upd, {"sym": sym, "dates": dates, "adjs": adjs})
                updated += res.rowcount or 0
            await s.commit()

        logger.info(
            "adjusted_close.done since=%s symbols=%d updated_rows=%d",
            since,
            len(by_sym),
            updated,
        )
        return {"since": str(since), "symbols": len(by_sym), "updated_rows": updated}
    finally:
        await engine.dispose()
