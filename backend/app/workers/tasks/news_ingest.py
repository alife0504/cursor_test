"""新聞抓取 task — TW / US（PLAN 第 14.7 章）。

P7 階段：抓 → 寫 news 表 metadata。
P12 升級：embedding → upsert Qdrant news_embeddings collection（本檔不處理）。

設計：
- 大盤新聞（symbol=None）每次抓最近 24 小時
- per-symbol 新聞（高關注股）走 fan-out（在 P10 watchlist 完成後再啟用）
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from celery.utils.log import get_task_logger
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.data_sources.tw import get_tw_sources
from app.data_sources.us import get_us_sources
from app.services.data_pipeline_service import DataPipelineService
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


def _new_engine_sm():
    engine = create_async_engine(
        settings.postgres_dsn_rw,
        pool_size=2,
        max_overflow=1,
        pool_pre_ping=True,
        echo=False,
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(
    name="app.workers.tasks.news_ingest.ingest_tw_news",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=600,
)
def ingest_tw_news(hours_back: int = 24) -> dict[str, Any]:
    """抓 TW 大盤新聞（最近 N 小時）→ 寫 news 表。

    來源：cnyes_rss（priority 10，主源）。
    """
    return asyncio.run(_async_ingest("TWSE", hours_back))


@celery_app.task(
    name="app.workers.tasks.news_ingest.ingest_us_news",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=600,
)
def ingest_us_news(hours_back: int = 24) -> dict[str, Any]:
    """抓 US 大盤新聞（最近 N 小時）→ 寫 news 表。

    來源：finnhub（priority 10）。
    """
    return asyncio.run(_async_ingest("NASDAQ", hours_back))


@celery_app.task(
    name="app.workers.tasks.news_ingest.ingest_tw_news_bulk",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=600,
)
def ingest_tw_news_bulk(days_back: int = 3) -> dict[str, Any]:
    """全市場台股新聞（FinMind TaiwanStockNews，一次抓全部）。

    取代被 WAF 擋的 MOPS 與稀疏的 cnyes RSS —— 單日 ~1,593 筆 / 576 檔。
    """
    return asyncio.run(_async_ingest_bulk(days_back))


async def _async_ingest_bulk(days_back: int) -> dict[str, Any]:
    sources = get_tw_sources(settings)
    engine, sm = _new_engine_sm()
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            written = await service.sync_news_bulk_tw(days_back=days_back)
        logger.info("news_ingest.bulk.done written=%d", written)
        return {"written": int(written)}
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.workers.tasks.news_ingest.ingest_tw_announcements",
    autoretry_for=(httpx.HTTPError, httpx.TimeoutException),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=180,
)
def ingest_tw_announcements() -> dict[str, Any]:
    """官方重大訊息（TWSE OpenAPI 當日全市場）——MOPS 被擋的替代，每日累積。"""
    return asyncio.run(_async_ingest_announcements())


async def _async_ingest_announcements() -> dict[str, Any]:
    sources = get_tw_sources(settings)
    engine, sm = _new_engine_sm()
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            written = await service.sync_announcements_twse()
        logger.info("news_ingest.announcements.done written=%d", written)
        return {"written": int(written)}
    finally:
        await engine.dispose()


async def _async_ingest(market: str, hours_back: int) -> dict[str, Any]:
    sources = get_tw_sources(settings) if market in ("TWSE", "TPEX") else get_us_sources(settings)
    since_dt = datetime.now(UTC) - timedelta(hours=hours_back)
    since = since_dt.date()

    engine, sm = _new_engine_sm()
    try:
        async with sm() as session:
            service = DataPipelineService(sources_by_kind=sources, session=session)
            try:
                written = await service.sync_news_for_symbol(
                    symbol=None, market=market, since=since
                )
            except ValueError as e:
                # 無 NEWS source 註冊（測試環境可能發生）
                logger.warning("news_ingest.no_source market=%s err=%s", market, e)
                return {"market": market, "written": 0, "skipped": True}
        logger.info("news_ingest.done market=%s written=%d", market, written)
        return {"market": market, "written": int(written)}
    finally:
        await engine.dispose()


__all__ = ["ingest_tw_announcements", "ingest_tw_news", "ingest_tw_news_bulk", "ingest_us_news"]
