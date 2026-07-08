"""Agent Tool Registry — 全部走 ta_agent_ro session（防 prompt injection）。

依 PLAN.md 第 14.4 章（Tool 對應 DataKind）+ 第 19 章（安全：read-only session 防注入）。

設計：
- `ToolRegistry(ro_sessionmaker)` 注入 async sessionmaker（必須是 ta_agent_ro 的）。
- 8 個 method 對應 8 種資料查詢：
    get_ohlcv / get_company_info / get_financial / get_news / get_announcements
    get_institutional / get_margin / get_monthly_revenue
- 後三者僅 TW，非 TW symbol 直接 raise ValidationError。
- `get_langchain_tools()` 把所有 method 包成 langchain `StructuredTool`，供 P13+ LLM tool calling。
- 直接呼叫 method（不經 langchain）也可，便於單元測試。

P12 階段：method 都實作完整（用 ro session 查 DB），但 Analyst 還沒呼叫；
P13+ 起 Analyst 透過 `tools.get_xxx(...)` 取資料給 LLM。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.core.errors import ValidationError
from app.core.logging_config import get_logger
from app.core.market_dispatcher import (
    Market,
    detect_region,
    market_to_region,
)
from app.data_sources.base import MarketRegion
from app.models.financials import FinancialStatement
from app.models.news import Announcement, NewsMetadata
from app.models.price import StockPrice
from app.models.stock import StockInfo, StockList
from app.models.tw_specific import InstitutionalTrading, MarginTrading, MonthlyRevenue

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = get_logger(__name__)


# ── ToolRegistry ────────────────────────────────────────


class ToolRegistry:
    """所有 Agent Tool 的集合。

    必須注入 `ta_agent_ro` 對應的 async_sessionmaker。
    """

    def __init__(self, ro_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Args:
        ro_sessionmaker: ta_agent_ro 的 async_sessionmaker。
          建議透過 `app.core.database.ro_session` context manager 或
          直接傳 sessionmaker 物件。
        """
        self.ro = ro_sessionmaker

    # ── helper ─────────────────────────────────────
    def _assert_tw_only(self, symbol: str, tool_name: str) -> None:
        """檢查 symbol 是否為 TW；非 TW 拋 ValidationError。"""
        region = detect_region(symbol)
        if region != MarketRegion.TW:
            raise ValidationError(
                message_zh=f"{tool_name} 僅支援台股，{symbol} 為 {region.value}",
                tool=tool_name,
                symbol=symbol,
                region=region.value,
            )

    @staticmethod
    def _default_market_for(symbol: str) -> str:
        """從 symbol 推斷預設 market（TW → TWSE / US → NASDAQ）。

        P12 階段 stock_prices 並不存 market（用 symbol 連結 stock_list.market），
        故此函數僅給「用 market 過濾」的 tool 使用。
        """
        region = detect_region(symbol)
        if region == MarketRegion.TW:
            return Market.TWSE.value
        return Market.NASDAQ.value

    # ════════════════ 1. get_ohlcv ════════════════

    async def get_ohlcv(
        self,
        symbol: str,
        days_back: int = 60,
    ) -> list[dict[str, Any]]:
        """取得近 N 日 OHLCV（自動依 symbol 判市場）。

        Args:
            symbol: 股票代號（"2330" / "AAPL"）。
            days_back: 取最近幾天（calendar days，含週末）。

        Returns:
            list of {symbol, date, open, high, low, close, volume, turnover, source}。
            日期由舊到新排序。
        """
        if days_back <= 0 or days_back > 720:
            raise ValidationError(message_zh="days_back 必須在 1~720 之間")
        end = date.today()
        start = end - timedelta(days=days_back)
        async with self.ro() as session:
            stmt = (
                select(StockPrice)
                .where(
                    StockPrice.symbol == symbol,
                    StockPrice.date >= start,
                    StockPrice.date <= end,
                )
                .order_by(StockPrice.date.asc())
            )
            rows = (await session.execute(stmt)).scalars().all()
        out = [
            {
                "symbol": r.symbol,
                "date": r.date.isoformat(),
                "open": str(r.open) if r.open is not None else None,
                "high": str(r.high) if r.high is not None else None,
                "low": str(r.low) if r.low is not None else None,
                "close": str(r.close) if r.close is not None else None,
                "volume": int(r.volume or 0),
                "turnover": str(r.turnover) if r.turnover is not None else None,
                "source": r.source,
            }
            for r in rows
        ]
        logger.info("tool.get_ohlcv", symbol=symbol, days_back=days_back, rows=len(out))
        return out

    # ════════════════ 2. get_company_info ════════════════

    async def get_company_info(self, symbol: str) -> dict[str, Any]:
        """取得公司基本資料（stock_list + stock_info merge）。

        Returns:
            {symbol, name, market, industry, listed_at, full_name, sector,
             description, capital, employees, ...}；查無 → 空 dict + warning。
        """
        async with self.ro() as session:
            stmt_list = select(StockList).where(StockList.symbol == symbol)
            row_list = (await session.execute(stmt_list)).scalar_one_or_none()
            if row_list is None:
                logger.warning("tool.get_company_info.not_found", symbol=symbol)
                return {}

            stmt_info = select(StockInfo).where(StockInfo.symbol == symbol)
            row_info = (await session.execute(stmt_info)).scalar_one_or_none()

        out: dict[str, Any] = {
            "symbol": row_list.symbol,
            "name": row_list.name,
            "short_name": row_list.short_name,
            "market": row_list.market,
            "industry": row_list.industry,
            "listed_at": row_list.listed_at.isoformat() if row_list.listed_at else None,
            "is_active": row_list.is_active,
        }
        if row_info is not None:
            out.update(
                {
                    "full_name": row_info.full_name,
                    "sector": row_info.sector,
                    "sub_industry": row_info.sub_industry,
                    "description": row_info.description,
                    "website": row_info.website,
                    "capital": str(row_info.capital) if row_info.capital is not None else None,
                    "employees": row_info.employees,
                    "fiscal_year_end": row_info.fiscal_year_end,
                }
            )
        logger.info("tool.get_company_info", symbol=symbol)
        return out

    # ════════════════ 3. get_financial ════════════════

    async def get_financial(
        self,
        symbol: str,
        quarters_back: int = 4,
    ) -> list[dict[str, Any]]:
        """取得近 N 季財務報表（IS+BS+CF）。

        Args:
            quarters_back: 取最近幾季（含季報 + 年報；fiscal_quarter=0 是年報）。

        Returns:
            list of {fiscal_year, fiscal_quarter, statement_type, revenue, net_income, eps, ...}。
            按 (fiscal_year DESC, fiscal_quarter DESC) 排序，取前 quarters_back × 3（IS/BS/CF 各一）。
        """
        if quarters_back <= 0 or quarters_back > 20:
            raise ValidationError(message_zh="quarters_back 必須在 1~20 之間")
        limit_rows = quarters_back * 3  # IS / BS / CF
        async with self.ro() as session:
            stmt = (
                select(FinancialStatement)
                .where(FinancialStatement.symbol == symbol)
                .order_by(
                    FinancialStatement.fiscal_year.desc(),
                    FinancialStatement.fiscal_quarter.desc(),
                    FinancialStatement.statement_type.asc(),
                )
                .limit(limit_rows)
            )
            rows = (await session.execute(stmt)).scalars().all()
        out = [_financial_to_dict(r) for r in rows]
        logger.info("tool.get_financial", symbol=symbol, quarters=quarters_back, rows=len(out))
        return out

    # ════════════════ 4. get_news ════════════════

    async def get_news(
        self,
        symbol: str,
        days_back: int = 7,
        max_items: int = 20,
    ) -> list[dict[str, Any]]:
        """取得個股近 N 日新聞元資料（向量在 Qdrant，這裡只回 metadata）。

        Returns:
            list of {id, title, summary, source, url, sentiment, published_at, ...}。
        """
        if days_back <= 0 or days_back > 90:
            raise ValidationError(message_zh="days_back 必須在 1~90 之間")
        if max_items <= 0 or max_items > 100:
            raise ValidationError(message_zh="max_items 必須在 1~100 之間")
        since = datetime.now(tz=UTC) - timedelta(days=days_back)
        async with self.ro() as session:
            stmt = (
                select(NewsMetadata)
                .where(
                    NewsMetadata.symbol == symbol,
                    NewsMetadata.published_at >= since,
                )
                .order_by(NewsMetadata.published_at.desc())
                .limit(max_items)
            )
            rows = (await session.execute(stmt)).scalars().all()
        out = [
            {
                "id": str(r.id),
                "title": r.title,
                "summary": r.summary,
                "source": r.source,
                "url": r.url,
                "sentiment": r.sentiment,
                "sentiment_score": (
                    str(r.sentiment_score) if r.sentiment_score is not None else None
                ),
                "published_at": r.published_at.isoformat() if r.published_at else None,
            }
            for r in rows
        ]
        logger.info("tool.get_news", symbol=symbol, days_back=days_back, rows=len(out))
        return out

    # ════════════════ 4b. get_market_news（大盤/總經）════════════════

    async def get_market_news(
        self,
        days_back: int = 7,
        max_items: int = 20,
        market: str | None = None,
    ) -> list[dict[str, Any]]:
        """取得近 N 日大盤/總經新聞（symbol 為空的市場層級新聞）。

        cnyes RSS `/rss/cat/tw_stock` 抓的是「台股總覽」大盤新聞，ingestion 以
        symbol=NULL 存入 news_metadata。此工具撈那批「非個股」新聞，供 News/Sentiment
        分析師建立總經脈絡（原版 get_global_news 的等價功能）。

        Args:
            days_back: 回溯天數（1~90）。
            max_items: 最多回傳筆數（1~100）。
            market: 選填，"TWSE"/"TPEX"/"US"…；給則只回該市場的大盤新聞。

        Returns:
            list of {id, title, summary, source, url, sentiment, sentiment_score, published_at}。
        """
        if days_back <= 0 or days_back > 90:
            raise ValidationError(message_zh="days_back 必須在 1~90 之間")
        if max_items <= 0 or max_items > 100:
            raise ValidationError(message_zh="max_items 必須在 1~100 之間")
        since = datetime.now(tz=UTC) - timedelta(days=days_back)
        async with self.ro() as session:
            conds = [
                NewsMetadata.symbol.is_(None),
                NewsMetadata.published_at >= since,
            ]
            if market:
                conds.append(NewsMetadata.market == market)
            stmt = (
                select(NewsMetadata)
                .where(*conds)
                .order_by(NewsMetadata.published_at.desc())
                .limit(max_items)
            )
            rows = (await session.execute(stmt)).scalars().all()
        out = [
            {
                "id": str(r.id),
                "title": r.title,
                "summary": r.summary,
                "source": r.source,
                "url": r.url,
                "sentiment": r.sentiment,
                "sentiment_score": (
                    str(r.sentiment_score) if r.sentiment_score is not None else None
                ),
                "published_at": r.published_at.isoformat() if r.published_at else None,
            }
            for r in rows
        ]
        logger.info("tool.get_market_news", days_back=days_back, market=market, rows=len(out))
        return out

    # ════════════════ 5. get_announcements ════════════════

    async def get_announcements(
        self,
        symbol: str,
        days_back: int = 30,
    ) -> list[dict[str, Any]]:
        """取得個股近 N 日重大公告（公開資訊觀測站 / EDGAR）。"""
        if days_back <= 0 or days_back > 180:
            raise ValidationError(message_zh="days_back 必須在 1~180 之間")
        since = datetime.now(tz=UTC) - timedelta(days=days_back)
        async with self.ro() as session:
            stmt = (
                select(Announcement)
                .where(
                    Announcement.symbol == symbol,
                    Announcement.published_at >= since,
                )
                .order_by(Announcement.published_at.desc())
            )
            rows = (await session.execute(stmt)).scalars().all()
        out = [
            {
                "id": str(r.id),
                "announcement_type": r.announcement_type,
                "title": r.title,
                "content": r.content,
                "url": r.url,
                "published_at": r.published_at.isoformat() if r.published_at else None,
            }
            for r in rows
        ]
        logger.info(
            "tool.get_announcements",
            symbol=symbol,
            days_back=days_back,
            rows=len(out),
        )
        return out

    # ════════════════ 6. get_institutional（TW only）════════════════

    async def get_institutional(
        self,
        symbol: str,
        days_back: int = 30,
    ) -> list[dict[str, Any]]:
        """三大法人買賣超（台股 only）。"""
        self._assert_tw_only(symbol, "get_institutional")
        if days_back <= 0 or days_back > 180:
            raise ValidationError(message_zh="days_back 必須在 1~180 之間")
        end = date.today()
        start = end - timedelta(days=days_back)
        async with self.ro() as session:
            stmt = (
                select(InstitutionalTrading)
                .where(
                    InstitutionalTrading.symbol == symbol,
                    InstitutionalTrading.date >= start,
                    InstitutionalTrading.date <= end,
                )
                .order_by(InstitutionalTrading.date.asc())
            )
            rows = (await session.execute(stmt)).scalars().all()
        out = [
            {
                "date": r.date.isoformat(),
                "foreign_buy": int(r.foreign_buy),
                "foreign_sell": int(r.foreign_sell),
                "foreign_net": int(r.foreign_net),
                "trust_buy": int(r.trust_buy),
                "trust_sell": int(r.trust_sell),
                "trust_net": int(r.trust_net),
                "dealer_buy": int(r.dealer_buy),
                "dealer_sell": int(r.dealer_sell),
                "dealer_net": int(r.dealer_net),
            }
            for r in rows
        ]
        logger.info("tool.get_institutional", symbol=symbol, rows=len(out))
        return out

    # ════════════════ 7. get_margin（TW only）════════════════

    async def get_margin(
        self,
        symbol: str,
        days_back: int = 30,
    ) -> list[dict[str, Any]]:
        """融資融券（台股 only）。"""
        self._assert_tw_only(symbol, "get_margin")
        if days_back <= 0 or days_back > 180:
            raise ValidationError(message_zh="days_back 必須在 1~180 之間")
        end = date.today()
        start = end - timedelta(days=days_back)
        async with self.ro() as session:
            stmt = (
                select(MarginTrading)
                .where(
                    MarginTrading.symbol == symbol,
                    MarginTrading.date >= start,
                    MarginTrading.date <= end,
                )
                .order_by(MarginTrading.date.asc())
            )
            rows = (await session.execute(stmt)).scalars().all()
        out = [
            {
                "date": r.date.isoformat(),
                "margin_balance": int(r.margin_balance),
                "margin_buy": int(r.margin_buy),
                "margin_sell": int(r.margin_sell),
                "short_balance": int(r.short_balance),
                "short_buy": int(r.short_buy),
                "short_sell": int(r.short_sell),
            }
            for r in rows
        ]
        logger.info("tool.get_margin", symbol=symbol, rows=len(out))
        return out

    # ════════════════ 8. get_monthly_revenue（TW only）════════════════

    async def get_monthly_revenue(
        self,
        symbol: str,
        months_back: int = 12,
    ) -> list[dict[str, Any]]:
        """月營收（台股 only，第 10 號公報）。"""
        self._assert_tw_only(symbol, "get_monthly_revenue")
        if months_back <= 0 or months_back > 60:
            raise ValidationError(message_zh="months_back 必須在 1~60 之間")
        async with self.ro() as session:
            stmt = (
                select(MonthlyRevenue)
                .where(MonthlyRevenue.symbol == symbol)
                .order_by(
                    MonthlyRevenue.year.desc(),
                    MonthlyRevenue.month.desc(),
                )
                .limit(months_back)
            )
            rows = (await session.execute(stmt)).scalars().all()
        out = [
            {
                "year": r.year,
                "month": r.month,
                "revenue": str(r.revenue) if r.revenue is not None else None,
                "revenue_mom": str(r.revenue_mom) if r.revenue_mom is not None else None,
                "revenue_yoy": str(r.revenue_yoy) if r.revenue_yoy is not None else None,
                "ytd_revenue": str(r.ytd_revenue) if r.ytd_revenue is not None else None,
                "ytd_yoy": str(r.ytd_yoy) if r.ytd_yoy is not None else None,
                "announced_at": r.announced_at.isoformat() if r.announced_at else None,
            }
            for r in rows
        ]
        # 由新到舊改回由舊到新（方便 LLM 看趨勢）
        out.reverse()
        logger.info("tool.get_monthly_revenue", symbol=symbol, rows=len(out))
        return out

    # ════════════════ langchain 整合 ════════════════

    def get_langchain_tools(self) -> list[Any]:
        """把 ToolRegistry 的方法包成 langchain BaseTool list（給 P13+ LLM tool calling）。

        延後 import langchain_core，避免 P12 環境沒裝相關套件時 import 整支 ToolRegistry 就炸。
        """
        try:
            from langchain_core.tools import StructuredTool
        except ImportError:  # pragma: no cover
            logger.warning("tool.langchain_not_installed")
            return []

        return [
            StructuredTool.from_function(
                coroutine=self.get_ohlcv,
                name="get_ohlcv",
                description="取得近 N 日 OHLCV（自動依 symbol 判市場）；arg: symbol (str), days_back (int, default 60)",
            ),
            StructuredTool.from_function(
                coroutine=self.get_company_info,
                name="get_company_info",
                description="取得公司基本資料；arg: symbol (str)",
            ),
            StructuredTool.from_function(
                coroutine=self.get_financial,
                name="get_financial",
                description="取得近 N 季財務報表（IS/BS/CF）；arg: symbol (str), quarters_back (int, default 4)",
            ),
            StructuredTool.from_function(
                coroutine=self.get_news,
                name="get_news",
                description="取得個股近 N 日新聞元資料；arg: symbol (str), days_back (int, default 7), max_items (int, default 20)",
            ),
            StructuredTool.from_function(
                coroutine=self.get_market_news,
                name="get_market_news",
                description="取得近 N 日大盤/總經新聞（非個股）；arg: days_back (int, default 7), max_items (int, default 20), market (str, optional)",
            ),
            StructuredTool.from_function(
                coroutine=self.get_announcements,
                name="get_announcements",
                description="取得個股近 N 日重大公告；arg: symbol (str), days_back (int, default 30)",
            ),
            StructuredTool.from_function(
                coroutine=self.get_institutional,
                name="get_institutional",
                description="三大法人買賣超（台股 only）；arg: symbol (str), days_back (int, default 30)",
            ),
            StructuredTool.from_function(
                coroutine=self.get_margin,
                name="get_margin",
                description="融資融券（台股 only）；arg: symbol (str), days_back (int, default 30)",
            ),
            StructuredTool.from_function(
                coroutine=self.get_monthly_revenue,
                name="get_monthly_revenue",
                description="月營收（台股 only）；arg: symbol (str), months_back (int, default 12)",
            ),
        ]


# ── helper ─────────────────────────────────────────────


def _financial_to_dict(row: FinancialStatement) -> dict[str, Any]:
    """FinancialStatement 轉 dict（含常用欄位 + raw payload）。"""
    out: dict[str, Any] = {
        "fiscal_year": row.fiscal_year,
        "fiscal_quarter": row.fiscal_quarter,
        "statement_type": row.statement_type,
    }
    # 常見欄位 explicit（盡量不漏；payload 為 raw）
    for col in (
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "eps",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "operating_cashflow",
        "investing_cashflow",
        "financing_cashflow",
    ):
        if hasattr(row, col):
            v = getattr(row, col)
            out[col] = str(v) if v is not None else None
    if hasattr(row, "announced_at") and row.announced_at:
        out["announced_at"] = row.announced_at.isoformat()
    if hasattr(row, "payload"):
        out["payload"] = row.payload
    return out


# ── 提供「自帶 ro_sessionmaker」的工廠 ───────────────


def get_default_tool_registry() -> ToolRegistry:
    """以全域 `ro_sessionmaker` 建立 ToolRegistry。

    僅在 FastAPI / Celery 任務內呼叫（事件迴圈內），不要在 module load 時呼叫。
    """
    from app.core import database

    if database._ro_sessionmaker is None:
        database.get_ro_engine()
    assert database._ro_sessionmaker is not None
    return ToolRegistry(database._ro_sessionmaker)


# Re-export 一些 helper（給 Analyst / Researcher 用）
__all__ = [
    "ToolRegistry",
    "get_default_tool_registry",
    "market_to_region",
]
