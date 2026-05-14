"""OHLCV 同步 task — 單股 + fan-out 全市場（PLAN 第 14.7、14.8、14.10 章）。

設計：
- 單股 task `sync_ohlcv_one`：呼叫 DataPipelineService.sync_ohlcv()。
  retry：HTTP 錯誤指數退避 3 次；最終失敗 → task_failure signal → DLQ。
- 全市場 fan-out `sync_ohlcv_tw_all` / `sync_ohlcv_us_all`：
  從 stock_list 撈 active symbols，分批 apply_async（避免 1500 個 task 一次擠進 broker）。

每個 task 在自己的 event loop / async engine 中執行（asyncio.run），
避免跨 task 共用 engine 造成的 "Event loop is closed" 問題。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.data_sources.tw import get_tw_sources
from app.data_sources.us import get_us_sources
from app.models.stock import StockList
from app.services.data_pipeline_service import DataPipelineService
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


# fan-out 一批的大小（避免 1500 個 task 一瞬間塞 broker queue）
TW_BATCH_SIZE = 50
US_BATCH_SIZE = 50
# 批次間 countdown（秒）— 拉開時間避免 rate-limit
BATCH_COUNTDOWN_STEP = 5


def _new_async_engine_and_sessionmaker():
    """每個 task 新建 async engine + sessionmaker（避免跨 event loop 衝突）。"""
    engine = create_async_engine(
        settings.postgres_dsn_rw,
        echo=False,
        pool_size=2,
        max_overflow=1,
        pool_pre_ping=True,
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


# ─────────── 單股 task ───────────


@celery_app.task(
    bind=True,
    name="app.workers.tasks.sync_ohlcv.sync_ohlcv_one",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=600,
    time_limit=900,
)
def sync_ohlcv_one(
    self: Any,
    symbol: str,
    market: str,
    days_back: int = 7,
) -> dict[str, Any]:
    """同步單支股票最近 N 天的 OHLCV。

    Args:
        symbol: e.g. "2330" / "AAPL"
        market: "TWSE" / "TPEX" / "NASDAQ" / "NYSE" / "AMEX"
        days_back: 抓最近幾天（default 7，足以涵蓋週末 + 節日）

    Returns:
        {"symbol": ..., "market": ..., "written": int}
    """
    logger.info("sync_ohlcv_one.start symbol=%s market=%s days=%d", symbol, market, days_back)
    return asyncio.run(_async_sync_one(symbol, market, days_back))


async def _async_sync_one(symbol: str, market: str, days_back: int) -> dict[str, Any]:
    end = datetime.now(UTC).date()
    start = end - timedelta(days=days_back)

    # 依 market 選 source group
    sources = get_tw_sources(settings) if market in ("TWSE", "TPEX") else get_us_sources(settings)

    engine, sm = _new_async_engine_and_sessionmaker()
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            written = await service.sync_ohlcv(symbol, market, start, end)
        logger.info("sync_ohlcv_one.done symbol=%s market=%s written=%d", symbol, market, written)
        return {"symbol": symbol, "market": market, "written": int(written)}
    finally:
        await engine.dispose()


# ─────────── fan-out tasks ───────────


@celery_app.task(
    name="app.workers.tasks.sync_ohlcv.sync_ohlcv_tw_all",
    soft_time_limit=120,
    time_limit=180,
)
def sync_ohlcv_tw_all(days_back: int = 7) -> dict[str, Any]:
    """fan-out：對所有 active TW 股票排程 sync_ohlcv_one。"""
    return asyncio.run(_async_fan_out_market(["TWSE", "TPEX"], TW_BATCH_SIZE, days_back))


@celery_app.task(
    name="app.workers.tasks.sync_ohlcv.sync_ohlcv_us_all",
    soft_time_limit=120,
    time_limit=180,
)
def sync_ohlcv_us_all(days_back: int = 7) -> dict[str, Any]:
    """fan-out：對所有 active US 股票排程 sync_ohlcv_one。"""
    return asyncio.run(_async_fan_out_market(["NASDAQ", "NYSE", "AMEX"], US_BATCH_SIZE, days_back))


async def _async_fan_out_market(
    markets: list[str], batch_size: int, days_back: int
) -> dict[str, Any]:
    """從 stock_list 撈 active symbols → 分批 apply_async sync_ohlcv_one。"""
    engine, sm = _new_async_engine_and_sessionmaker()
    try:
        async with sm() as session:
            stmt = select(StockList.symbol, StockList.market).where(
                StockList.is_active.is_(True),
                StockList.market.in_(markets),
            )
            rows = (await session.execute(stmt)).all()
        symbols = [(r.symbol, r.market) for r in rows]
    finally:
        await engine.dispose()

    if not symbols:
        logger.warning("sync_ohlcv.fan_out.no_symbols markets=%s", markets)
        return {"markets": markets, "count": 0, "batches": 0}

    n_batches = 0
    for i in range(0, len(symbols), batch_size):
        chunk = symbols[i : i + batch_size]
        countdown = (i // batch_size) * BATCH_COUNTDOWN_STEP
        for sym, mkt in chunk:
            sync_ohlcv_one.apply_async(
                args=[sym, mkt, days_back],
                countdown=countdown,
            )
        n_batches += 1

    logger.info(
        "sync_ohlcv.fan_out.scheduled markets=%s count=%d batches=%d",
        markets,
        len(symbols),
        n_batches,
    )
    return {"markets": markets, "count": len(symbols), "batches": n_batches}


__all__ = [
    "BATCH_COUNTDOWN_STEP",
    "TW_BATCH_SIZE",
    "US_BATCH_SIZE",
    "sync_ohlcv_one",
    "sync_ohlcv_tw_all",
    "sync_ohlcv_us_all",
]
