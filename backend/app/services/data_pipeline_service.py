"""DataPipelineService — 從 source(fallback) 抓資料、轉換、寫 repo。

依 PLAN.md 第 18.1 章 Service 層 + 第 14.10 章資料管線。

設計：
- 每個 sync_* 方法 = 「抓 + 寫 + 回筆數」一條 pipeline
- 內部用 DataSourceFallback 包裝多個 source（priority + CB）
- 寫入直接 commit（caller 不需自己管理 transaction）
- P7 才會被 Celery task 包裝；P5 本身可獨立呼叫測試
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind
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
        sources_by_kind: dict[DataKind, list[BaseDataSource]],
        session: AsyncSession,
    ) -> None:
        """
        Args:
            sources_by_kind: 從 get_tw_sources()/get_us_sources() 拿到的 dict
            session: AsyncSession（建議用 RW，因為要寫 DB）
        """
        self.sources_by_kind = sources_by_kind
        self.session = session

        # Repository（共用同一 session）
        self.stock_repo = StockRepository(session)
        self.ohlcv_repo = OHLCVRepository(session)
        self.news_repo = NewsRepository(session)
        self.financials_repo = FinancialsRepository(session)

    # ── public sync methods ──────────────────────────────

    async def sync_ohlcv(
        self,
        symbol: str,
        market: str,
        start: date,
        end: date,
    ) -> int:
        sources = self.sources_by_kind.get(DataKind.OHLCV, [])
        if not sources:
            raise ValueError("DataPipelineService: 無 OHLCV source 註冊")
        fb = DataSourceFallback(sources)
        df = await fb.fetch_ohlcv(symbol, start, end)
        if df.empty:
            logger.info("data_pipeline.sync_ohlcv.empty", symbol=symbol)
            return 0
        # DataFrame → list[dict]，加 symbol（source 不會 hardcode symbol）
        rows = df.to_dict(orient="records")
        for r in rows:
            r["symbol"] = symbol
        n = await self.ohlcv_repo.upsert_many(
            rows, source=sources[0].name if sources else None, commit=True
        )
        logger.info("data_pipeline.sync_ohlcv.done", symbol=symbol, written=n)
        return n

    async def sync_news_for_symbol(
        self, symbol: str | None = None, *, since: date | None = None
    ) -> int:
        sources = self.sources_by_kind.get(DataKind.NEWS, [])
        if not sources:
            raise ValueError("DataPipelineService: 無 NEWS source 註冊")
        fb = DataSourceFallback(sources)
        items = await fb.fetch_news(symbol, since=since)
        if not items:
            return 0
        # 補 symbol（source 回傳可能沒帶）
        for it in items:
            it.setdefault("symbol", symbol)
            it.setdefault("market", "TWSE")  # 預設 TW 主板
        n = await self.news_repo.upsert_many_by_url(items, commit=True)
        logger.info("data_pipeline.sync_news.done", symbol=symbol, written=n)
        return n

    async def sync_monthly_revenue(self, symbol: str, *, year: int | None = None) -> int:
        sources = self.sources_by_kind.get(DataKind.MONTHLY_REVENUE, [])
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
        year: int | None = None,
        quarter: int | None = None,
    ) -> int:
        """抓財報 → 寫 financial_statements（IS/BS/CF）。

        因 FinMind 一次回該股全部歷史，且每筆是「單一欄位」（type+value），
        caller 須在 DataPipelineService 把 list 重組成 (year, quarter, statement_type) → dict。

        P5 範圍：簡化用 payload 整包存（按 source 回的 list 切 (year, quarter)），
        實際數值欄位可在 P7 再做映射補強。
        """
        sources = self.sources_by_kind.get(DataKind.FINANCIAL, [])
        if not sources:
            raise ValueError("DataPipelineService: 無 FINANCIAL source 註冊")
        fb = DataSourceFallback(sources)
        items = await fb.fetch_financial(symbol, year=year, quarter=quarter)
        rows = self._group_financial_payload(symbol, items, source=sources[0].name)
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

    # ── helpers ──────────────────────────────────────────

    @staticmethod
    def _group_financial_payload(
        symbol: str, items: list[dict[str, Any]], *, source: str | None
    ) -> list[dict[str, Any]]:
        """FinMind 一筆 = 一個欄位；把同 (year, quarter) 的彙整成 1 個 IS 筆。

        P5 簡化版：所有同 (year, quarter) 歸入 statement_type='IS'，原始細項放 payload。
        P7 才精準分 IS/BS/CF（依 FinMind 的 type prefix）。
        """
        groups: dict[tuple[int, int], dict[str, Any]] = {}
        for it in items:
            d = it.get("date_parsed") or _try_parse_date(it.get("date"))
            if d is None:
                continue
            yr = d.year
            # FinMind 季度推導：1Q=date.month in {3} (報告日期 ~ 3 月底 = Q4 上季) — 用月份判斷
            quarter = _quarter_from_month(d.month)
            key = (yr, quarter)
            if key not in groups:
                groups[key] = {
                    "symbol": symbol,
                    "fiscal_year": yr,
                    "fiscal_quarter": quarter,
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


__all__ = ["DataPipelineService"]
