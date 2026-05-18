"""DataPipelineService — 從 source(fallback) 抓資料、轉換、寫 repo。

依 PLAN.md 第 18.1 章 Service 層 + 第 14.10 章資料管線 + 第 10 章跨市場架構。

設計（P6 升級）：
- 兩種建構方式：
  (a) `DataPipelineService(sources_by_kind, session)`  ← P5 既有單市場（仍可用）
  (b) `DataPipelineService.with_dispatcher(dispatcher, session)` ← P6 跨市場（內部依 market 選 sources）
- sync_* 方法新增 `market` 參數（"TWSE" / "TPEX" / "NASDAQ" / ...）
- 若用 dispatcher 模式，自動依 market 取 region 對應 sources
- TW-only 業務（institutional / margin / monthly_revenue）：US symbol 拋 ValidationError
- 寫入直接 commit（caller 不需自己管理 transaction）
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from app.core.errors import ValidationError
from app.core.logging_config import get_logger
from app.core.market_dispatcher import (
    TW_MARKETS,
    Market,
    MarketDispatcher,
    detect_region,
    market_to_region,
)
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion
from app.data_sources.fallback import DataSourceFallback
from app.repos.financials_repo import FinancialsRepository
from app.repos.news_repo import NewsRepository
from app.repos.ohlcv_repo import OHLCVRepository
from app.repos.stock_repo import StockRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class DataPipelineService:
    """資料管線服務 — orchestrate fallback + repo upsert。"""

    def __init__(
        self,
        sources_by_kind: dict[DataKind, list[BaseDataSource]] | None,
        session: AsyncSession,
        *,
        dispatcher: MarketDispatcher | None = None,
    ) -> None:
        """
        Args:
            sources_by_kind: 既有 P5 用法 — 直接給單市場 source dict
            session: AsyncSession（建議用 RW，因為要寫 DB）
            dispatcher: P6 新增 — 跨市場 dispatcher（若給，sources_by_kind 可為 None）
        """
        if sources_by_kind is None and dispatcher is None:
            raise ValueError("DataPipelineService 至少需要 sources_by_kind 或 dispatcher 一個")
        self.sources_by_kind = sources_by_kind
        self.dispatcher = dispatcher
        self.session = session

        # Repository（共用同一 session）
        self.stock_repo = StockRepository(session)
        self.ohlcv_repo = OHLCVRepository(session)
        self.news_repo = NewsRepository(session)
        self.financials_repo = FinancialsRepository(session)

    @classmethod
    def with_dispatcher(
        cls, dispatcher: MarketDispatcher, session: AsyncSession
    ) -> DataPipelineService:
        """跨市場版本工廠方法。"""
        return cls(sources_by_kind=None, session=session, dispatcher=dispatcher)

    # ── public sync methods ──────────────────────────────

    async def sync_ohlcv(
        self,
        symbol: str,
        market: str,
        start: date,
        end: date,
    ) -> int:
        """抓 + 寫 OHLCV。"""
        sources = self._sources_for(DataKind.OHLCV, market=market)
        if not sources:
            raise ValueError("DataPipelineService: 無 OHLCV source 註冊")
        fb = DataSourceFallback(sources)
        df = await fb.fetch_ohlcv(symbol, start, end)
        if df.empty:
            logger.info("data_pipeline.sync_ohlcv.empty", symbol=symbol, market=market)
            return 0
        rows = df.to_dict(orient="records")
        for r in rows:
            r["symbol"] = symbol
        n = await self.ohlcv_repo.upsert_many(
            rows, source=sources[0].name if sources else None, commit=True
        )
        logger.info(
            "data_pipeline.sync_ohlcv.done",
            symbol=symbol,
            market=market,
            written=n,
        )
        return n

    async def sync_news_for_symbol(
        self,
        symbol: str | None = None,
        *,
        market: str | None = None,
        since: date | None = None,
    ) -> int:
        """抓 + 寫某股新聞。"""
        sources = self._sources_for(DataKind.NEWS, market=market, symbol=symbol)
        if not sources:
            raise ValueError("DataPipelineService: 無 NEWS source 註冊")
        fb = DataSourceFallback(sources)
        items = await fb.fetch_news(symbol, since=since)
        if not items:
            return 0
        default_market = market or ("TWSE" if symbol and _is_tw_symbol(symbol) else "NASDAQ")
        for it in items:
            it.setdefault("symbol", symbol)
            it.setdefault("market", default_market)
        n = await self.news_repo.upsert_many_by_url(items, commit=True)
        logger.info(
            "data_pipeline.sync_news.done",
            symbol=symbol,
            market=default_market,
            written=n,
        )
        return n

    async def sync_monthly_revenue(self, symbol: str, *, year: int | None = None) -> int:
        """月營收 — TW only。"""
        self._ensure_tw_only(symbol, "月營收")
        sources = self._sources_for(DataKind.MONTHLY_REVENUE, market="TWSE")
        if not sources:
            raise ValueError("DataPipelineService: 無 MONTHLY_REVENUE source 註冊")
        fb = DataSourceFallback(sources)
        items = await fb.fetch_monthly_revenue(symbol, year=year)
        if not items:
            return 0
        for it in items:
            it.setdefault("symbol", symbol)
            it.setdefault("source", sources[0].name)
        n = await self.financials_repo.upsert_monthly_revenue(items, commit=True)
        logger.info(
            "data_pipeline.sync_monthly_revenue.done",
            symbol=symbol,
            year=year,
            written=n,
        )
        return n

    async def sync_financial(
        self,
        symbol: str,
        *,
        market: str | None = None,
        year: int | None = None,
        quarter: int | None = None,
    ) -> int:
        """抓財報 → 寫 financial_statements（IS/BS/CF）。"""
        sources = self._sources_for(DataKind.FINANCIAL, market=market, symbol=symbol)
        if not sources:
            raise ValueError("DataPipelineService: 無 FINANCIAL source 註冊")
        fb = DataSourceFallback(sources)
        items = await fb.fetch_financial(symbol, year=year, quarter=quarter)
        rows = self._normalize_financial_rows(symbol, items, source=sources[0].name)
        if quarter is not None:
            rows = [r for r in rows if r["fiscal_quarter"] == quarter]
        if not rows:
            return 0
        n = await self.financials_repo.upsert_statements(rows, commit=True)
        logger.info(
            "data_pipeline.sync_financial.done",
            symbol=symbol,
            year=year,
            quarter=quarter,
            written=n,
        )
        return n

    async def sync_announcements(
        self,
        symbol: str,
        *,
        market: str | None = None,
        since: date | None = None,
    ) -> list[dict[str, Any]]:
        """抓公告 / filings — 回 list（P7 才寫 DB；P6 只回 raw 供 caller 處理）。"""
        sources = self._sources_for(DataKind.ANNOUNCEMENT, market=market, symbol=symbol)
        if not sources:
            raise ValueError("DataPipelineService: 無 ANNOUNCEMENT source 註冊")
        fb = DataSourceFallback(sources)
        items = await fb.fetch_announcement(symbol, since=since)
        logger.info(
            "data_pipeline.sync_announcements.done",
            symbol=symbol,
            count=len(items),
        )
        return items

    async def sync_institutional(self, symbol: str, start: date, end: date) -> int:
        """三大法人 — TW only（PLAN 10.5）。"""
        self._ensure_tw_only(symbol, "籌碼資料（三大法人）")
        sources = self._sources_for(DataKind.INSTITUTIONAL, market="TWSE")
        if not sources:
            raise ValueError("DataPipelineService: 無 INSTITUTIONAL source 註冊")
        fb = DataSourceFallback(sources)
        df = await fb.fetch_institutional(symbol, start, end)
        logger.info(
            "data_pipeline.sync_institutional.done",
            symbol=symbol,
            rows=0 if df is None else len(df),
        )
        # P7 才有對應 repo upsert；P6 暫回 row 數
        return 0 if df is None else len(df)

    # ── 內部 helpers ─────────────────────────────────────

    def _sources_for(
        self,
        kind: DataKind,
        *,
        market: str | None = None,
        symbol: str | None = None,
    ) -> list[BaseDataSource]:
        """依 dispatcher / sources_by_kind 拿對應 source list。"""
        if self.dispatcher is not None:
            region = self._resolve_region(market=market, symbol=symbol)
            return self.dispatcher.get_sources_for(region, kind)
        # P5 fallback：直接從 sources_by_kind 拿
        return list((self.sources_by_kind or {}).get(kind, []))

    @staticmethod
    def _resolve_region(*, market: str | None, symbol: str | None) -> MarketRegion:
        """從 market or symbol 推 region。"""
        if market is not None:
            try:
                return market_to_region(Market(market))
            except (ValueError, ValidationError):
                pass
        if symbol is not None:
            return detect_region(symbol)
        raise ValidationError(message_zh="無法決定市場區域：market 與 symbol 都未提供")

    @staticmethod
    def _ensure_tw_only(symbol: str, feature_zh: str) -> None:
        """確保 symbol 是 TW；否則拋 ValidationError。"""
        region = detect_region(symbol)
        if region != MarketRegion.TW:
            raise ValidationError(
                message_zh=f"{feature_zh}僅支援台股",
                symbol=symbol,
                region=region.value,
            )

    @staticmethod
    def _normalize_financial_rows(
        symbol: str, items: list[dict[str, Any]], *, source: str | None
    ) -> list[dict[str, Any]]:
        """P5 + P6 共用：把 source 回的 list 規範成 statements 寫入格式。

        - FinMind（TW）: 一筆 = 單一欄位（type+value）→ groupby (year, quarter) 後合併
        - yfinance / Alpha Vantage（US）: 一筆 = 一張完整 statement，直接 passthrough
        """
        if not items:
            return []

        # 判斷格式：第一筆有 fiscal_year + payload 視為「完整 statement」
        first = items[0]
        if (
            "fiscal_year" in first
            and "fiscal_quarter" in first
            and "statement_type" in first
            and "payload" in first
        ):
            return [
                {
                    "symbol": symbol,
                    "fiscal_year": int(it["fiscal_year"]),
                    "fiscal_quarter": int(it["fiscal_quarter"]),
                    "statement_type": str(it["statement_type"]),
                    "payload": it.get("payload") or {},
                    "source": it.get("source") or source,
                }
                for it in items
            ]

        # FinMind 風格：groupby (year, quarter)
        groups: dict[tuple[int, int], dict[str, Any]] = {}
        for it in items:
            d = it.get("date_parsed") or _try_parse_date(it.get("date"))
            if d is None:
                continue
            yr = d.year
            q = _quarter_from_month(d.month)
            key = (yr, q)
            if key not in groups:
                groups[key] = {
                    "symbol": symbol,
                    "fiscal_year": yr,
                    "fiscal_quarter": q,
                    "statement_type": "IS",
                    "payload": {"items": []},
                    "source": source,
                }
            groups[key]["payload"]["items"].append(
                {
                    "type": it.get("type"),
                    "origin_name": it.get("origin_name"),
                    "value": str(it.get("value")) if it.get("value") is not None else None,
                }
            )
        return list(groups.values())


def _try_parse_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        import pandas as pd

        return pd.to_datetime(str(v)).date()
    except Exception:
        return None


def _quarter_from_month(m: int) -> int:
    if 1 <= m <= 3:
        return 1
    if 4 <= m <= 6:
        return 2
    if 7 <= m <= 9:
        return 3
    return 4


def _is_tw_symbol(symbol: str) -> bool:
    try:
        return detect_region(symbol) == MarketRegion.TW
    except ValidationError:
        return False


# Re-export 給 caller（避免 import 散落）
__all__ = ["TW_MARKETS", "DataPipelineService", "Market", "MarketDispatcher"]
