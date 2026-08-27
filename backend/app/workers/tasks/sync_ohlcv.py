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
from app.data_sources.base import DataKind
from app.data_sources.tw import get_tw_sources
from app.data_sources.us import get_us_sources
from app.models.stock import StockList
from app.repos.ohlcv_repo import OHLCVRepository
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


# 大盤指數：我方 symbol → 上游查詢用 data_id。
# FinMind 的櫃買指數是 `TPEx`（大小寫敏感，查 `TPEX` 會回空陣列）；我方 stock_prices /
# market_service 統一用 `TPEX`，故查詢與儲存代號需分離。
TW_INDEX_IDS: dict[str, str] = {"TAIEX": "TAIEX", "TPEX": "TPEx"}


@celery_app.task(
    name="app.workers.tasks.sync_ohlcv.sync_index_tw",
    soft_time_limit=180,
    time_limit=300,
)
def sync_index_tw(days_back: int = 30) -> dict[str, Any]:
    """同步大盤指數（加權 TAIEX / 櫃買 TPEX）OHLCV。

    指數在 stock_list 是 market='OTHER' 且 is_active=false，不會被 sync_ohlcv_tw_all 的
    fan-out 選中 → 過去只能靠 seed 腳本塞假資料，dashboard 的指數因此長期凍結。
    本任務直接以 TW source chain 補上（本地庫沒有指數歷史時會自動 fallback 到 FinMind API）。
    """
    return asyncio.run(_async_sync_index_tw(days_back))


async def _async_sync_index_tw(days_back: int) -> dict[str, Any]:
    """對每個指數詢問所有 TW OHLCV source，採用「涵蓋天數最多」的那個。

    不用一般的 DataSourceFallback：它只要第一個 source 回傳**任何**資料就算成功，而本地
    FinMind 庫目前 TAIEX/TPEx 各只有 1 列（2026-07-06），會直接勝出並蓋掉有完整歷史的
    FinMind API → 指數只剩 1 天，畫不出趨勢也算不出漲跌。指數要的是連續序列，
    「拿到 1 列」不該算成功。本地庫補齊後，它自然會因涵蓋最完整而被選中。
    """
    end = datetime.now(UTC).date()
    start = end - timedelta(days=days_back)
    ohlcv_sources = get_tw_sources(settings).get(DataKind.OHLCV, [])

    engine, sm = _new_async_engine_and_sessionmaker()
    out: dict[str, Any] = {}
    try:
        async with sm() as session:
            repo = OHLCVRepository(session)
            for our_symbol, upstream_id in TW_INDEX_IDS.items():
                best_df = None
                best_src: str | None = None
                for src in ohlcv_sources:
                    try:
                        df = await src.fetch_ohlcv(upstream_id, start, end)
                    except Exception:  # 單一 source 掛掉不影響其他
                        logger.warning(
                            "sync_index_tw.source_failed symbol=%s source=%s",
                            our_symbol,
                            src.name,
                            exc_info=True,
                        )
                        continue
                    if df is None or df.empty:
                        continue
                    if best_df is None or len(df) > len(best_df):
                        best_df, best_src = df, src.name

                if best_df is None:
                    logger.warning("sync_index_tw.no_data symbol=%s", our_symbol)
                    out[our_symbol] = {"written": 0, "source": None}
                    continue

                rows = best_df.to_dict(orient="records")
                for r in rows:
                    r["symbol"] = our_symbol
                n = await repo.upsert_many(rows, source=best_src, commit=True)
                out[our_symbol] = {"written": int(n), "source": best_src}
        logger.info("sync_index_tw.done %s", out)
        return {"written": out}
    finally:
        await engine.dispose()


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


# ─────────── 交易日曆同步（實際交易日）───────────


@celery_app.task(
    name="app.workers.tasks.sync_ohlcv.sync_trading_calendar_tw",
    soft_time_limit=300,
    time_limit=600,
    max_retries=0,
)
def sync_trading_calendar_tw() -> dict[str, Any]:
    """同步台股「實際交易日」到 trading_calendar。

    來源＝finmind-platform bronze.taiwan_stock_price 中「市場性有價格」(>500 檔)的日期，
    自然排除颱風/臨時休市（那些日子全市場無成交）。供資料缺口偵測與 N 交易日計算。
    """
    return asyncio.run(_async_sync_trading_calendar())


async def _async_sync_trading_calendar() -> dict[str, Any]:
    if not settings.FINMIND_LOCAL_ENABLED or not settings.FINMIND_LOCAL_PASSWORD:
        logger.warning("trading_calendar.skip finmind_local 未啟用")
        return {"skipped": "finmind_local_disabled"}

    from sqlalchemy import Date, bindparam, text
    from sqlalchemy.dialects.postgresql import ARRAY

    from app.data_sources.tw.finmind_local_source import FinMindLocalSource

    fm = FinMindLocalSource(settings)
    rows = await fm._query(
        "SELECT date FROM bronze.taiwan_stock_price "
        "GROUP BY date HAVING count(*) > 500 ORDER BY date"
    )
    dates = [r["date"] for r in rows]
    if not dates:
        return {"skipped": "no_trading_days"}

    engine = create_async_engine(
        settings.postgres_dsn_rw, pool_size=2, max_overflow=1, pool_pre_ping=True
    )
    sm = async_sessionmaker(engine, expire_on_commit=False)
    ins = text(
        "INSERT INTO trading_calendar (date, market) "
        "SELECT unnest(:dates), 'TW' ON CONFLICT (date, market) DO NOTHING"
    ).bindparams(bindparam("dates", type_=ARRAY(Date)))
    try:
        async with sm() as session:
            res = await session.execute(ins, {"dates": dates})
            await session.commit()
        inserted = res.rowcount or 0
        logger.info("trading_calendar.done trading_days=%d inserted=%d", len(dates), inserted)
        return {"trading_days": len(dates), "inserted": inserted}
    finally:
        await engine.dispose()


__all__ = [
    "BATCH_COUNTDOWN_STEP",
    "TW_BATCH_SIZE",
    "US_BATCH_SIZE",
    "sync_ohlcv_one",
    "sync_ohlcv_tw_all",
    "sync_ohlcv_us_all",
    "sync_trading_calendar_tw",
]
