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

from datetime import UTC, date, datetime, timedelta
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
from app.repos.market_repo import MarketRepository
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
        self.market_repo = MarketRepository(session)

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
        *,
        store_as: str | None = None,
    ) -> int:
        """抓 + 寫 OHLCV。

        Args:
            symbol: 上游查詢用代號
            store_as: 寫入 DB 時要用的代號（預設同 symbol）。給指數用：上游 FinMind 的
                櫃買指數是 `TPEx`（大小寫敏感，`TPEX` 會回空），我方統一存 `TPEX`。
        """
        sources = self._sources_for(DataKind.OHLCV, market=market)
        if not sources:
            raise ValueError("DataPipelineService: 無 OHLCV source 註冊")

        # **按優先序合併，而非「第一個有資料就用」**：
        # DataSourceFallback 只要來源回任何資料就採用，但對日期區間查詢「有資料」≠「涵蓋完整」。
        # 實測 finmind_local 只到 2026-07-07（本地庫回補中），卻因 priority 最高而勝出 →
        # 07-08 之後永遠拿不到，個股近期價格長期缺漏（finmind API 與 twse_openapi 都有到 07-15）。
        # 故逐一詢問各來源，每個日期由**優先序最高且有該日資料**的來源提供；
        # 一旦已涵蓋到請求上限即提早結束，本地庫補齊後就會退化成只打第一個來源。
        merged: dict[Any, dict[str, Any]] = {}
        used_names: list[str] = []
        for src in sources:
            if merged and max(merged) >= end:
                break  # 已涵蓋到 end，不必再問後面的來源（省配額）
            try:
                df = await src.fetch_ohlcv(symbol, start, end)
            except Exception:  # 單一來源失敗不影響其他
                logger.warning(
                    "data_pipeline.sync_ohlcv.source_failed",
                    symbol=symbol,
                    source=src.name,
                    exc_info=True,
                )
                continue
            if df is None or df.empty:
                continue
            added = 0
            for r in df.to_dict(orient="records"):
                d = r.get("date")
                if d is None or d in merged:
                    continue  # 已有較高優先序來源提供該日
                r["symbol"] = store_as or symbol
                r["_source"] = src.name
                merged[d] = r
                added += 1
            if added:
                used_names.append(src.name)

        if not merged:
            logger.info("data_pipeline.sync_ohlcv.empty", symbol=symbol, market=market)
            return 0

        # 逐來源分批寫入，讓 source 欄位標的是「該列實際的來源」而非整批一個值
        by_source: dict[str, list[dict[str, Any]]] = {}
        for r in merged.values():
            by_source.setdefault(r.pop("_source"), []).append(r)
        n = 0
        for name, batch in by_source.items():
            n += await self.ohlcv_repo.upsert_many(batch, source=name, commit=True)
        logger.info(
            "data_pipeline.sync_ohlcv.done",
            symbol=symbol,
            market=market,
            written=n,
            sources=used_names,
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

    async def sync_announcements_twse(self) -> int:
        """官方重大訊息（TWSE OpenAPI t187ap04_L，當日全市場）。

        MOPS 被 WAF 擋、無免費歷史替代，故改抓 TWSE 每日重大訊息、逐日累積（只有當日，
        無法回補過去）。ROC 日期/時間需轉西元。以 (symbol, published_at, title) 去重。
        """
        from datetime import datetime as _dt

        from app.core.http_client import get_async_client, request_with_retry
        from app.repos.news_repo import AnnouncementRepository

        url = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
        try:
            async with get_async_client(name="twse_openapi") as client:
                resp = await request_with_retry(
                    client, "GET", url, source_name="twse_openapi", raise_on_4xx=False
                )
            rows = resp.json() if resp.status_code == 200 else []
        except Exception as exc:
            logger.warning("data_pipeline.sync_announcements_twse.fetch_failed", error=str(exc))
            return 0
        if not isinstance(rows, list):
            return 0

        items: list[dict[str, Any]] = []
        for r in rows:
            symbol = (r.get("公司代號") or "").strip()
            title = (r.get("主旨 ") or r.get("主旨") or "").strip()
            if not symbol or not title:
                continue
            pub = _parse_roc_datetime(r.get("發言日期"), r.get("發言時間"))
            if pub is None:
                continue
            items.append(
                {
                    "symbol": symbol,
                    "market": "TWSE",
                    "title": title,
                    "content": (r.get("說明 ") or r.get("說明") or "").strip() or None,
                    "announcement_type": (r.get("符合條款 ") or r.get("符合條款") or "").strip()
                    or None,
                    "published_at": pub,
                    "extra_meta": {"source": "twse_openapi", "fact_date": r.get("事實發生日")},
                }
            )
        if not items:
            return 0
        _ = _dt  # 保留 import 供型別參考
        n = await AnnouncementRepository(self.session).upsert_many(items, commit=True)
        logger.info("data_pipeline.sync_announcements_twse.done", fetched=len(items), written=n)
        return n

    async def sync_margin(self, symbol: str, start: date, end: date) -> int:
        """融資融券 — TW only。按日期合併涵蓋（同 institutional）。"""
        self._ensure_tw_only(symbol, "融資融券")
        sources = self._sources_for(DataKind.MARGIN, market="TWSE")
        if not sources:
            raise ValueError("DataPipelineService: 無 MARGIN source 註冊")

        merged: dict[Any, dict[str, Any]] = {}
        by_source: dict[str, list[dict[str, Any]]] = {}
        for src in sources:
            if merged and max(merged) >= end:
                break
            try:
                df = await src.fetch_margin(symbol, start, end)
            except Exception:
                logger.warning(
                    "data_pipeline.sync_margin.source_failed",
                    symbol=symbol,
                    source=src.name,
                    exc_info=True,
                )
                continue
            if df is None or df.empty:
                continue
            for r in df.to_dict(orient="records"):
                d = r.get("date")
                if d is None or d in merged:
                    continue
                r["symbol"] = symbol
                merged[d] = r
                by_source.setdefault(src.name, []).append(r)

        if not merged:
            return 0
        n = 0
        for name, batch in by_source.items():
            n += await self.market_repo.upsert_margin(batch, source=name, commit=True)
        logger.info("data_pipeline.sync_margin.done", symbol=symbol, written=n)
        return n

    async def sync_margin_bulk(self, *, days_back: int = 10) -> int:
        """全市場融資融券（FinMind 不帶 data_id → 單日回整個市場，逐日查）。

        取代逐檔 fan-out：2,375 檔各打一次 API 會在幾秒內爆量 → FinMind 直接「IP ban」
        （實測 403 ip banned，retry_after ~640s），還會波及同 IP 的 realtime/OHLCV。
        改用「每天一次請求」抓整個市場，近日缺口 ~10 天只需 ~10 次請求。只寫 active 個股。
        """
        from app.core.config import settings
        from app.data_sources.tw.finmind_source import FinMindSource

        end = datetime.now(UTC).date()
        start = end - timedelta(days=days_back)
        rows = await FinMindSource(settings).fetch_all_margin(start, end)
        if not rows:
            return 0
        active = set(await self.market_repo.get_active_symbols("TWSE")) | set(
            await self.market_repo.get_active_symbols("TPEX")
        )
        batch = [r for r in rows if r.get("symbol") in active]
        if not batch:
            return 0
        n = await self.market_repo.upsert_margin(batch, source="finmind", commit=True)
        logger.info("data_pipeline.sync_margin_bulk.done", fetched=len(rows), written=n)
        return n

    async def sync_company_info(self, symbol: str) -> int:
        """公司基本資料 — TW only。FinMind 只提供產業別/名稱（無資本額/員工數），填可得者。"""
        self._ensure_tw_only(symbol, "公司基本資料")
        sources = self._sources_for(DataKind.COMPANY_INFO, market="TWSE")
        if not sources:
            raise ValueError("DataPipelineService: 無 COMPANY_INFO source 註冊")
        fb = DataSourceFallback(sources)
        info = await fb.fetch_company_info(symbol)
        if not info or not info.get("symbol"):
            return 0
        n = await self.stock_repo.upsert_stock_info(
            {
                "symbol": info["symbol"],
                "full_name": info.get("name"),
                "sector": info.get("industry"),
                "sub_industry": info.get("type"),
            },
            commit=True,
        )
        logger.info("data_pipeline.sync_company_info.done", symbol=symbol, written=n)
        return n

    async def sync_news_bulk_tw(self, *, days_back: int = 3) -> int:
        """全市場台股新聞（FinMind TaiwanStockNews，一次抓全部，取代 MOPS/稀疏 RSS）。

        逐日抓（含 published_at 過濾無效者），以 url dedupe upsert。回實際寫入筆數。
        """
        from app.core.config import settings
        from app.data_sources.tw.finmind_source import FinMindSource
        from app.domain.sentiment_lexicon import classify_sentiment

        end = datetime.now(UTC).date()
        start = end - timedelta(days=days_back)
        items = await FinMindSource(settings).fetch_all_news(start, end)
        items = [it for it in items if it.get("published_at") is not None]
        if not items:
            return 0
        # 情緒分類（詞典 net-score，免 LLM）——原本 sentiment 全 unknown、情緒分佈圖恆空
        for it in items:
            label, score = classify_sentiment(it.get("title"), it.get("summary"))
            it["sentiment"] = label
            it["sentiment_score"] = score
        n = await self.news_repo.upsert_many_by_url(items, commit=True)
        logger.info("data_pipeline.sync_news_bulk_tw.done", fetched=len(items), written=n)
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
        used = getattr(fb, "last_used_source", None) or (sources[0].name if sources else None)
        for it in items:
            it.setdefault("symbol", symbol)
            it.setdefault("source", used)
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
        used = getattr(fb, "last_used_source", None) or (sources[0].name if sources else None)
        rows = self._normalize_financial_rows(symbol, items, source=used)
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
        """三大法人 — TW only（PLAN 10.5）。

        與 sync_ohlcv 同：按優先序「合併涵蓋」而非「第一個有資料就用」。本地庫近期常缺
        （回補中），若讓它因 priority 最高就勝出，07-08 之後的三大法人會拿不到
        （finmind API / twse_openapi 有較新資料卻輪不到）。每個日期由優先序最高且有該日
        資料的來源提供。
        """
        self._ensure_tw_only(symbol, "籌碼資料（三大法人）")
        sources = self._sources_for(DataKind.INSTITUTIONAL, market="TWSE")
        if not sources:
            raise ValueError("DataPipelineService: 無 INSTITUTIONAL source 註冊")

        merged: dict[Any, dict[str, Any]] = {}
        by_source: dict[str, list[dict[str, Any]]] = {}
        for src in sources:
            if merged and max(merged) >= end:
                break  # 已涵蓋到 end
            try:
                df = await src.fetch_institutional(symbol, start, end)
            except Exception:
                logger.warning(
                    "data_pipeline.sync_institutional.source_failed",
                    symbol=symbol,
                    source=src.name,
                    exc_info=True,
                )
                continue
            if df is None or df.empty:
                continue
            for r in df.to_dict(orient="records"):
                d = r.get("date")
                if d is None or d in merged:
                    continue  # 已有較高優先序來源提供該日
                r["symbol"] = symbol
                merged[d] = r
                by_source.setdefault(src.name, []).append(r)

        if not merged:
            return 0

        n = 0
        for name, batch in by_source.items():
            n += await self.market_repo.upsert_institutional(batch, source=name, commit=True)
        logger.info(
            "data_pipeline.sync_institutional.done",
            symbol=symbol,
            written=n,
            sources=list(by_source),
        )
        return n

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

        # FinMind 風格：groupby (year, quarter, statement_type) 後把科目 pivot 進 typed 欄位。
        # statement_type 由 source 標（本地庫拆 IS/BS/CF）；未標者（如 API 損益源）預設 IS。
        groups: dict[tuple[int, int, str], dict[str, Any]] = {}
        for it in items:
            d = it.get("date_parsed") or _try_parse_date(it.get("date"))
            if d is None:
                continue
            yr = d.year
            q = _quarter_from_month(d.month)
            st = str(it.get("statement_type") or "IS")
            key = (yr, q, st)
            g = groups.get(key)
            if g is None:
                g = {
                    "symbol": symbol,
                    "fiscal_year": yr,
                    "fiscal_quarter": q,
                    "statement_type": st,
                    "payload": {"items": []},
                    "_by_type": {},
                    "source": source,
                }
                groups[key] = g
            t = it.get("type")
            v = it.get("value")
            g["payload"]["items"].append(
                {
                    "type": t,
                    "origin_name": it.get("origin_name"),
                    "value": str(v) if v is not None else None,
                }
            )
            # 同 (季, statement, type) 取第一個非空值（避免重複列覆蓋）
            if t is not None and v is not None and t not in g["_by_type"]:
                g["_by_type"][t] = v

        out: list[dict[str, Any]] = []
        for g in groups.values():
            by_type: dict[str, Any] = g.pop("_by_type")
            for candidates, col in _FINMIND_FIELD_MAP.get(g["statement_type"], ()):
                for c in candidates:
                    if c in by_type:
                        g[col] = by_type[c]
                        break
            out.append(g)

        _decumulate_cashflow_rows(out)
        return out


# FinMind type → financial_statements typed 欄位對映（依 statement_type 分組）。
# 每個目標欄位給一組候選 FinMind type（依優先序），pivot 時挑第一個存在的；
# 候選含跨股/跨年常見同義字（如 Liabilities vs TotalLiabilities）以提升覆蓋率。
# 數值已用 2330 Q1 會計恒等式驗證：TotalAssets = Liabilities + Equity。
_FINMIND_FIELD_MAP: dict[str, tuple[tuple[tuple[str, ...], str], ...]] = {
    "IS": (
        (("Revenue",), "revenue"),
        (("GrossProfit",), "gross_profit"),
        (("OperatingIncome",), "operating_income"),
        (
            (
                "IncomeAfterTaxes",
                "IncomeAfterTax",
                "NetIncome",
                "TotalConsolidatedProfitForThePeriod",
            ),
            "net_income",
        ),
        (("EPS",), "eps"),
    ),
    "BS": (
        (("TotalAssets",), "total_assets"),
        (("Liabilities", "TotalLiabilities"), "total_liabilities"),
        (("Equity", "TotalEquity"), "total_equity"),
    ),
    "CF": (
        (
            (
                "CashFlowsFromOperatingActivities",
                "NetCashInflowFromOperatingActivities",  # 舊年度用此名（本地庫 35,706 列）
                "NetCashFlowsFromOperatingActivities",
                "CashProvidedByOperatingActivities",
            ),
            "operating_cashflow",
        ),
        (
            (
                "CashProvidedByInvestingActivities",
                "CashFlowsProvidedFromInvestingActivities",
                "CashFlowsFromInvestingActivities",
            ),
            "investing_cashflow",
        ),
        (
            (
                "CashFlowsProvidedFromFinancingActivities",
                "CashProvidedByFinancingActivities",
                "CashFlowsFromFinancingActivities",
            ),
            "financing_cashflow",
        ),
    ),
}


# 現金流量表三欄為「年度累計(YTD)」基準，需還原成單季
_CF_CUMULATIVE_COLS: tuple[str, ...] = (
    "operating_cashflow",
    "investing_cashflow",
    "financing_cashflow",
)


def _decumulate_cashflow_rows(rows: list[dict[str, Any]]) -> None:
    """把 CF 列的年度累計(YTD)金額就地還原成「單季」，與 IS 的單季基準一致。

    背景（實測 fm-postgres 本地庫）：
    - 損益表是單季：2330 FY2024 Revenue 四季加總 = 2.894兆 = 台積電公告全年營收。
    - 現金流量表是年度累計：2330 FY2024 營業現金流 4363億→8140億→1.206兆→1.826兆，
      單調遞增且 Q4 = 公告全年數。全市場亦然（Q4/Q1 中位數 CF=3.64 vs IS=1.11）。
      這是台灣現金流量表的申報慣例（一律累計期初至期末）。

    不還原的話，Q2~Q4（75% 的列）的現金流會含前幾季，卻與同一 fiscal_quarter 上「只有那一季」
    的營收並列，下游算出的 OCF/營收等比率全錯。

    還原：單季_q = YTD_q − YTD_(q−1)，Q1 本身即單季。
    由大到小處理，確保相減時讀到的前一季仍是未被改寫的原始 YTD 值。
    缺前一季（資料有缺口）時填 None——寧可標示不知道，也不留下錯誤數字。
    """
    by_year: dict[tuple[str, int], dict[int, dict[str, Any]]] = {}
    for r in rows:
        if r.get("statement_type") != "CF":
            continue
        key = (str(r.get("symbol")), int(r["fiscal_year"]))
        by_year.setdefault(key, {})[int(r["fiscal_quarter"])] = r

    for quarters in by_year.values():
        for q in sorted(quarters, reverse=True):
            if q <= 1:
                continue  # Q1 的 YTD 就是單季
            cur = quarters[q]
            prev = quarters.get(q - 1)
            for col in _CF_CUMULATIVE_COLS:
                if cur.get(col) is None:
                    continue
                prev_val = prev.get(col) if prev is not None else None
                cur[col] = (cur[col] - prev_val) if prev_val is not None else None


def _parse_roc_datetime(roc_date: Any, roc_time: Any) -> datetime | None:
    """TWSE ROC 日期 '1150715' + 時間 '70004'/'070004' → tz-aware datetime（UTC 存）。

    ROC 年 = 西元 − 1911。時間為 HMMSS/HHMMSS（不足補零）。解析失敗回 None。
    """
    ds = str(roc_date or "").strip()
    if len(ds) < 7 or not ds.isdigit():
        return None
    try:
        year = int(ds[:3]) + 1911
        month = int(ds[3:5])
        day = int(ds[5:7])
        ts = str(roc_time or "0").strip().zfill(6)
        hh, mm, ss = int(ts[-6:-4] or 0), int(ts[-4:-2] or 0), int(ts[-2:] or 0)
        # 台北時間 → 以 UTC 存（台北 = UTC+8）
        return datetime(year, month, day, hh, mm, ss, tzinfo=UTC) - timedelta(hours=8)
    except (ValueError, TypeError):
        return None


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
