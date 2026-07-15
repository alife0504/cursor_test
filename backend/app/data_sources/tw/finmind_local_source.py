"""FinMind 本地資料庫源 — 盤後(EOD)資料直接查自架的 finmind DB（fm-postgres）。

背景：使用者的 FinMind API token 只授權「即時盤」；盤後歷史資料改用本地自架的 FinMind
資料平台（C:/Projects/finmind-platform 的 fm-postgres，database=finmind）。本源把該庫的
`bronze.taiwan_stock_price` 直接讀成標準 OHLCV，並以最高優先序插進 TW fallback 鏈——盤後
一律走本地庫（免 API 配額、免限流），FinMind API 源只當即時/備援。

啟用條件：settings.FINMIND_LOCAL_ENABLED 且 FINMIND_LOCAL_PASSWORD 有值；否則 get_tw_sources
不會把本源加入鏈，完全不影響現有行為。

本地表欄位（bronze.taiwan_stock_price）：
  stock_id / date / open / max / min / close / "Trading_Volume" / "Trading_money" / Trading_turnover
標準化輸出（與 FinMindSource 一致）：date / open / high / low / close / volume / turnover
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from app.core.config import settings
from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion, register_data_source

logger = get_logger(__name__)


def _to_decimal_or_none(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


@register_data_source
class FinMindLocalSource(BaseDataSource):
    """本地自架 FinMind DB（盤後 EOD 主源）。"""

    name = "finmind_local"
    priority = 5  # 比 finmind API(10) 更優先：盤後一律走本地庫
    supported_regions = (MarketRegion.TW,)
    supported_kinds = (
        DataKind.OHLCV,
        DataKind.INSTITUTIONAL,
        DataKind.FINANCIAL,
        DataKind.MONTHLY_REVENUE,
    )

    async def _connect(self):
        import asyncpg

        pw = settings.FINMIND_LOCAL_PASSWORD
        return await asyncpg.connect(
            host=settings.FINMIND_LOCAL_HOST,
            port=settings.FINMIND_LOCAL_PORT,
            user=settings.FINMIND_LOCAL_USER,
            password=pw.get_secret_value() if pw else None,
            database=settings.FINMIND_LOCAL_DB,
            timeout=8,
        )

    async def _query(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(sql, *params)
        finally:
            await conn.close()
        return [dict(r) for r in rows]

    async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        cols = ["date", "open", "high", "low", "close", "volume", "turnover"]
        data = await self._query(
            """
            SELECT date, open, max AS high, min AS low, close,
                   "Trading_Volume" AS volume, "Trading_money" AS turnover
            FROM bronze.taiwan_stock_price
            WHERE stock_id = $1 AND date >= $2 AND date <= $3
            ORDER BY date
            """,
            symbol,
            start,
            end,
        )
        if not data:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        for c in ("open", "high", "low", "close", "turnover"):
            if c in df.columns:
                df[c] = df[c].apply(_to_decimal_or_none)
        if "volume" in df.columns:
            df["volume"] = df["volume"].fillna(0).astype("int64")
        return df[[c for c in cols if c in df.columns]].copy()

    async def fetch_institutional(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """三大法人買賣超（本地庫）。raw 欄位與 FinMind API 一致 → 重用 API 源的 pivot 正規化。"""
        from app.data_sources.tw.finmind_source import FinMindSource

        data = await self._query(
            """
            SELECT date, stock_id, name, buy, sell
            FROM bronze.taiwan_stock_institutional_investors_buy_sell
            WHERE stock_id = $1 AND date >= $2 AND date <= $3
            ORDER BY date
            """,
            symbol,
            start,
            end,
        )
        return FinMindSource._normalize_institutional(data)

    async def fetch_financial(
        self, symbol: str, *, year: int | None = None, quarter: int | None = None
    ) -> list[dict[str, Any]]:
        """財報（本地庫）。每列一個科目(type/value)，重用 API 源的單筆正規化。"""
        from app.data_sources.tw.finmind_source import FinMindSource

        if year is not None:
            data = await self._query(
                """
                SELECT stock_id, date, type, value, origin_name
                FROM bronze.taiwan_stock_financial_statements
                WHERE stock_id = $1 AND date >= $2 AND date <= $3
                ORDER BY date
                """,
                symbol,
                date(year, 1, 1),
                date(year, 12, 31),
            )
        else:
            data = await self._query(
                """
                SELECT stock_id, date, type, value, origin_name
                FROM bronze.taiwan_stock_financial_statements
                WHERE stock_id = $1
                ORDER BY date
                """,
                symbol,
            )
        return [FinMindSource._normalize_financial(row) for row in data]

    async def fetch_monthly_revenue(
        self, symbol: str, *, year: int | None = None
    ) -> list[dict[str, Any]]:
        """月營收（本地庫），重用 API 源的單筆正規化。"""
        from app.data_sources.tw.finmind_source import FinMindSource

        if year is not None:
            data = await self._query(
                """
                SELECT stock_id, date, country, revenue, revenue_month, revenue_year
                FROM bronze.taiwan_stock_month_revenue
                WHERE stock_id = $1 AND revenue_year = $2
                ORDER BY date
                """,
                symbol,
                year,
            )
        else:
            data = await self._query(
                """
                SELECT stock_id, date, country, revenue, revenue_month, revenue_year
                FROM bronze.taiwan_stock_month_revenue
                WHERE stock_id = $1
                ORDER BY date
                """,
                symbol,
            )
        return [FinMindSource._normalize_monthly_revenue(row) for row in data]


__all__ = ["FinMindLocalSource"]
