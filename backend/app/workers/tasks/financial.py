"""財務資料 task — TW 月營收 / 三大法人 + US 季報（PLAN 第 14.7 章）。

設計：
- sync_monthly_revenue：fan-out 對所有 active TW symbols
- sync_institutional_tw：fan-out 對所有 active TW symbols
- sync_quarterly_financial_us：fan-out 對所有 active US symbols（季度 schedule，P7 task 註冊但 beat 不排定，留給 P10 manual trigger）
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from celery.utils.log import get_task_logger
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.database import make_worker_engine
from app.data_sources.tw import get_tw_sources
from app.data_sources.us import get_us_sources
from app.models.stock import StockList
from app.services.data_pipeline_service import DataPipelineService
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


# fan-out batch
TW_FIN_BATCH = 50
US_FIN_BATCH = 50
BATCH_COUNTDOWN_STEP = 10


def _new_engine_sm():
    engine = make_worker_engine(settings.postgres_dsn_rw, name="financial")
    return engine, async_sessionmaker(engine, expire_on_commit=False)


# ─────────── 單股 task ───────────


@celery_app.task(
    name="app.workers.tasks.financial.sync_monthly_revenue_one",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
)
def sync_monthly_revenue_one(symbol: str, year: int | None = None) -> dict[str, Any]:
    """單股月營收（TW only）。"""
    return asyncio.run(_async_monthly_revenue_one(symbol, year))


async def _async_monthly_revenue_one(symbol: str, year: int | None) -> dict[str, Any]:
    sources = get_tw_sources(settings)
    engine, sm = _new_engine_sm()
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            written = await service.sync_monthly_revenue(symbol, year=year)
        return {"symbol": symbol, "year": year, "written": int(written)}
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.workers.tasks.financial.sync_institutional_one",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
)
def sync_institutional_one(symbol: str, days_back: int = 30) -> dict[str, Any]:
    """單股三大法人（TW only）。"""
    return asyncio.run(_async_institutional_one(symbol, days_back))


async def _async_institutional_one(symbol: str, days_back: int) -> dict[str, Any]:
    sources = get_tw_sources(settings)
    end = datetime.now(UTC).date()
    start = end - timedelta(days=days_back)
    engine, sm = _new_engine_sm()
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            n = await service.sync_institutional(symbol, start, end)
        return {"symbol": symbol, "days_back": days_back, "rows": int(n)}
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.workers.tasks.financial.sync_margin_one",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
)
def sync_margin_one(symbol: str, days_back: int = 30) -> dict[str, Any]:
    """單股融資融券（TW only）。"""
    return asyncio.run(_async_margin_one(symbol, days_back))


async def _async_margin_one(symbol: str, days_back: int) -> dict[str, Any]:
    sources = get_tw_sources(settings)
    end = datetime.now(UTC).date()
    start = end - timedelta(days=days_back)
    engine, sm = _new_engine_sm()
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            n = await service.sync_margin(symbol, start, end)
        return {"symbol": symbol, "rows": int(n)}
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.workers.tasks.financial.sync_company_info_one",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
)
def sync_company_info_one(symbol: str) -> dict[str, Any]:
    """單股公司基本資料（TW only）。"""
    return asyncio.run(_async_company_info_one(symbol))


async def _async_company_info_one(symbol: str) -> dict[str, Any]:
    sources = get_tw_sources(settings)
    engine, sm = _new_engine_sm()
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            n = await service.sync_company_info(symbol)
        return {"symbol": symbol, "rows": int(n)}
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.workers.tasks.financial.sync_quarterly_financial_one",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=180,
    time_limit=300,
)
def sync_quarterly_financial_one(
    symbol: str,
    market: str,
    year: int | None = None,
    quarter: int | None = None,
) -> dict[str, Any]:
    """單股季報（IS/BS/CF）— TW 走 MOPS / US 走 yfinance + Alpha Vantage。"""
    return asyncio.run(_async_quarterly_one(symbol, market, year, quarter))


async def _async_quarterly_one(
    symbol: str, market: str, year: int | None, quarter: int | None
) -> dict[str, Any]:
    sources = get_tw_sources(settings) if market in ("TWSE", "TPEX") else get_us_sources(settings)
    engine, sm = _new_engine_sm()
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            n = await service.sync_financial(symbol, market=market, year=year, quarter=quarter)
        return {"symbol": symbol, "market": market, "written": int(n)}
    finally:
        await engine.dispose()


# ─────────── fan-out tasks（beat 排程觸發） ───────────


@celery_app.task(
    name="app.workers.tasks.financial.sync_monthly_revenue",
    # orchestrator 讀 stock_list 後 fan-out；DB 暫時性錯誤重試，避免稀疏排程(月一次)單次失敗
    # 就整週期零派發、整月資料不更新。
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
    soft_time_limit=120,
    time_limit=180,
)
def sync_monthly_revenue() -> dict[str, Any]:
    """fan-out：對所有 active TW 股票排月營收抓取。"""
    return asyncio.run(
        _fan_out_tw(
            sync_monthly_revenue_one.name,
            args_builder=lambda sym: [sym],
            kwargs_builder=lambda _sym: {},
        )
    )


@celery_app.task(
    name="app.workers.tasks.financial.sync_institutional_tw",
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
    soft_time_limit=120,
    time_limit=180,
)
def sync_institutional_tw() -> dict[str, Any]:
    """fan-out：對所有 active TW 股票排三大法人抓取。

    ⚠️ 已停用於 beat 排程 —— 同 margin，逐檔 fan-out 有 IP ban 風險；且 finmind 沒涵蓋的
    個股會落到 twse_openapi，那條路徑沒把 T86 欄位對映 → 存成 0/0/0（頁面顯示錯）。
    改用 sync_institutional_bulk_tw（每日一請求抓全市場、標準定義聚合）。保留供手動補洞。
    """
    return asyncio.run(
        _fan_out_tw(
            sync_institutional_one.name,
            args_builder=lambda sym: [sym],
            kwargs_builder=lambda _sym: {"days_back": 7},
        )
    )


@celery_app.task(
    name="app.workers.tasks.financial.sync_institutional_bulk_tw",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=420,
)
def sync_institutional_bulk_tw(days_back: int = 10) -> dict[str, Any]:
    """全市場三大法人（FinMind 不帶 data_id → 單日回整個市場）。取代逐檔 fan-out。"""
    return asyncio.run(_async_institutional_bulk(days_back))


async def _async_institutional_bulk(days_back: int) -> dict[str, Any]:
    sources = get_tw_sources(settings)
    engine, sm = _new_engine_sm()
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            written = await service.sync_institutional_bulk(days_back=days_back)
        logger.info("financial.institutional_bulk.done written=%d", written)
        return {"written": int(written)}
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.workers.tasks.financial.sync_margin_tw",
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
    soft_time_limit=120,
    time_limit=180,
)
def sync_margin_tw() -> dict[str, Any]:
    """fan-out：對所有 active TW 股票排融資融券抓取。

    ⚠️ 已停用於 beat 排程 —— 2,375 檔逐檔對 FinMind 打 API 會在數秒內爆量觸發
    「IP ban」（403 ip banned，retry_after ~640s），還會波及同 IP 的 realtime/OHLCV。
    改用 sync_margin_bulk_tw（每日一請求抓全市場）。保留本 task 供手動單檔補洞。
    """
    return asyncio.run(
        _fan_out_tw(
            sync_margin_one.name,
            args_builder=lambda sym: [sym],
            kwargs_builder=lambda _sym: {"days_back": 7},
        )
    )


@celery_app.task(
    name="app.workers.tasks.financial.sync_margin_bulk_tw",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=180,
    time_limit=300,
)
def sync_margin_bulk_tw(days_back: int = 10) -> dict[str, Any]:
    """全市場融資融券（FinMind 不帶 data_id → 單日回整個市場，逐日查）。

    取代 sync_margin_tw 的逐檔 fan-out：近 N 天只需 ~N 次請求，不會 IP ban。
    """
    return asyncio.run(_async_margin_bulk(days_back))


async def _async_margin_bulk(days_back: int) -> dict[str, Any]:
    sources = get_tw_sources(settings)
    engine, sm = _new_engine_sm()
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            written = await service.sync_margin_bulk(days_back=days_back)
        logger.info("financial.margin_bulk.done written=%d", written)
        return {"written": int(written)}
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.workers.tasks.financial.sync_stock_metrics_tw",
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
    soft_time_limit=300,
    time_limit=420,
)
def sync_stock_metrics_tw() -> dict[str, Any]:
    """刷新 stock_metrics 每檔最新指標快照（PE/殖利率/PBR/市值/RSI/EPS 成長）——選股篩選器用。"""
    return asyncio.run(_async_stock_metrics())


async def _async_stock_metrics() -> dict[str, Any]:
    from app.services.metrics_service import MetricsService

    engine, sm = _new_engine_sm()
    try:
        async with sm() as session:
            result = await MetricsService(session).sync_stock_metrics()
        logger.info("financial.stock_metrics.done result=%s", result)
        return {k: int(v) for k, v in result.items()}
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.workers.tasks.financial.sync_company_info_tw",
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
    soft_time_limit=120,
    time_limit=180,
)
def sync_company_info_tw() -> dict[str, Any]:
    """fan-out：對所有 active TW 股票排公司基本資料抓取（靜態資料，每週一次即可）。"""
    return asyncio.run(
        _fan_out_tw(
            sync_company_info_one.name,
            args_builder=lambda sym: [sym],
            kwargs_builder=lambda _sym: {},
        )
    )


@celery_app.task(
    name="app.workers.tasks.financial.sync_quarterly_financial_tw",
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
    soft_time_limit=180,
    time_limit=300,
)
def sync_quarterly_financial_tw() -> dict[str, Any]:
    """fan-out：對所有 active TW 股票排季報（IS/BS/CF）抓取。

    先前只有 US 有 fan-out，台股財報沒有任何排程也沒有 fan-out → financial_statements
    長期只有手動同步過的少數幾檔，基本面分析對其他股票全都拿不到資料。
    資料來自 FinMind 三張表（本地庫優先，缺則 fallback API）。
    """
    return asyncio.run(
        _fan_out_generic(
            markets=["TWSE", "TPEX"],
            batch_size=TW_FIN_BATCH,
            task_name=sync_quarterly_financial_one.name,
            args_builder=lambda sym, mkt: [sym, mkt],
            kwargs_builder=lambda _s, _m: {},
        )
    )


@celery_app.task(
    name="app.workers.tasks.financial.sync_quarterly_financial_us",
    soft_time_limit=120,
    time_limit=180,
)
def sync_quarterly_financial_us() -> dict[str, Any]:
    """fan-out：對所有 active US 股票排季報抓取。

    P7：beat 不自動排程（季度頻率，等用戶手動觸發或 P10 監聽財報日曆）。
    """
    return asyncio.run(
        _fan_out_us(
            sync_quarterly_financial_one.name,
            args_builder=lambda sym, mkt: [sym, mkt],
            kwargs_builder=lambda _s, _m: {},
        )
    )


async def _fan_out_tw(
    task_name: str,
    *,
    args_builder,
    kwargs_builder,
) -> dict[str, Any]:
    return await _fan_out_generic(
        markets=["TWSE", "TPEX"],
        batch_size=TW_FIN_BATCH,
        task_name=task_name,
        args_builder=lambda sym, _mkt: args_builder(sym),
        kwargs_builder=lambda sym, _mkt: kwargs_builder(sym),
    )


async def _fan_out_us(
    task_name: str,
    *,
    args_builder,
    kwargs_builder,
) -> dict[str, Any]:
    return await _fan_out_generic(
        markets=["NASDAQ", "NYSE", "AMEX"],
        batch_size=US_FIN_BATCH,
        task_name=task_name,
        args_builder=args_builder,
        kwargs_builder=kwargs_builder,
    )


async def _fan_out_generic(
    *,
    markets: list[str],
    batch_size: int,
    task_name: str,
    args_builder,
    kwargs_builder,
) -> dict[str, Any]:
    """共用 fan-out：從 stock_list 撈 active symbols 後分批 apply_async。"""
    engine, sm = _new_engine_sm()
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
        logger.warning("financial.fan_out.no_symbols task=%s markets=%s", task_name, markets)
        return {"task": task_name, "count": 0, "batches": 0}

    n_batches = 0
    for i in range(0, len(symbols), batch_size):
        chunk = symbols[i : i + batch_size]
        countdown = (i // batch_size) * BATCH_COUNTDOWN_STEP
        for sym, mkt in chunk:
            celery_app.send_task(
                task_name,
                args=args_builder(sym, mkt),
                kwargs=kwargs_builder(sym, mkt),
                countdown=countdown,
            )
        n_batches += 1
    logger.info(
        "financial.fan_out.scheduled task=%s markets=%s count=%d batches=%d",
        task_name,
        markets,
        len(symbols),
        n_batches,
    )
    return {"task": task_name, "count": len(symbols), "batches": n_batches}


# ─────────── 月營收成長率衍生（YoY / MoM / YTD）───────────


@celery_app.task(
    name="app.workers.tasks.financial.derive_monthly_revenue_growth_tw",
    soft_time_limit=600,
    time_limit=900,
    max_retries=0,
)
def derive_monthly_revenue_growth_tw(since_year: int | None = None) -> dict[str, Any]:
    """由 monthly_revenue.revenue 衍生 revenue_mom / revenue_yoy / ytd_revenue / ytd_yoy。

    台股最重要月頻訊號（營收年增率）。FinMind 只給 revenue，成長率須自算：
    - MoM = 對上月；YoY = 對去年同月；YTD = 今年 1..M 累計；YTD-YoY = 對去年同期累計。
    - PIT 安全：全部只用「過去/同期」的 revenue（YoY 用 M-12、MoM 用 M-1），無前視。
    - 冪等：只在數字有變動時更新；成長率為衍生欄位，隨 revenue 修正一併重算。

    Args:
        since_year: 只重算該年（含）之後；None＝全部回填。
    """
    return asyncio.run(_async_derive_revenue_growth(since_year))


async def _async_derive_revenue_growth(since_year: int | None) -> dict[str, Any]:
    engine, sm = _new_engine_sm()
    upd = text(
        """
        UPDATE monthly_revenue m SET
          -- 成長率欄為 Numeric(10,4)（max ±999999.9999%）；abs>=1e6 的是「基期近零」的無意義
          -- 極端值（無法表示且不具訊號價值）→ NULL。round(_,2) 後再夾。
          revenue_mom = (
            SELECT CASE WHEN abs(round((m.revenue - p.revenue) / p.revenue * 100, 2)) < 1000000
                        THEN round((m.revenue - p.revenue) / p.revenue * 100, 2) END
            FROM monthly_revenue p
            WHERE p.symbol = m.symbol AND p.revenue > 0
              AND ((m.month > 1 AND p.year = m.year AND p.month = m.month - 1)
                OR (m.month = 1 AND p.year = m.year - 1 AND p.month = 12))
          ),
          revenue_yoy = (
            SELECT CASE WHEN abs(round((m.revenue - p.revenue) / p.revenue * 100, 2)) < 1000000
                        THEN round((m.revenue - p.revenue) / p.revenue * 100, 2) END
            FROM monthly_revenue p
            WHERE p.symbol = m.symbol AND p.year = m.year - 1 AND p.month = m.month AND p.revenue > 0
          ),
          ytd_revenue = (
            SELECT sum(p.revenue) FROM monthly_revenue p
            WHERE p.symbol = m.symbol AND p.year = m.year AND p.month <= m.month
          ),
          ytd_yoy = (
            SELECT CASE WHEN py.s > 0 AND abs(round((cur.s - py.s) / py.s * 100, 2)) < 1000000
                        THEN round((cur.s - py.s) / py.s * 100, 2) END
            FROM (SELECT sum(p.revenue) s FROM monthly_revenue p
                    WHERE p.symbol = m.symbol AND p.year = m.year AND p.month <= m.month) cur,
                 (SELECT sum(p.revenue) s FROM monthly_revenue p
                    WHERE p.symbol = m.symbol AND p.year = m.year - 1 AND p.month <= m.month) py
          )
        WHERE (:since_year IS NULL OR m.year >= :since_year)
        """
    )
    try:
        async with sm() as session:
            res = await session.execute(upd, {"since_year": since_year})
            await session.commit()
        updated = res.rowcount or 0
        logger.info("monthly_revenue.growth_derived since_year=%s updated=%d", since_year, updated)
        return {"since_year": since_year, "updated_rows": updated}
    finally:
        await engine.dispose()


__all__ = [
    "derive_monthly_revenue_growth_tw",
    "sync_company_info_one",
    "sync_company_info_tw",
    "sync_institutional_bulk_tw",
    "sync_institutional_one",
    "sync_institutional_tw",
    "sync_margin_bulk_tw",
    "sync_margin_one",
    "sync_margin_tw",
    "sync_monthly_revenue",
    "sync_monthly_revenue_one",
    "sync_quarterly_financial_one",
    "sync_quarterly_financial_us",
    "sync_stock_metrics_tw",
]
