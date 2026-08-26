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

# 資產負債表 / 現金流量表要拉的 FinMind type（含跨股常見同義字，取超集；
# 實際 pivot 時 _normalize_financial_rows 會依優先序挑第一個存在者）。
_BS_TYPES: tuple[str, ...] = (
    "TotalAssets",
    "Liabilities",
    "TotalLiabilities",
    "Equity",
    "TotalEquity",
    "EquityAttributableToOwnersOfParent",
)
_CF_TYPES: tuple[str, ...] = (
    "CashFlowsFromOperatingActivities",
    "NetCashInflowFromOperatingActivities",  # 舊年度用此名（本地庫 35,706 列）
    "NetCashFlowsFromOperatingActivities",
    "CashProvidedByOperatingActivities",
    "CashProvidedByInvestingActivities",
    "CashFlowsProvidedFromInvestingActivities",
    "CashFlowsFromInvestingActivities",
    "CashFlowsProvidedFromFinancingActivities",
    "CashProvidedByFinancingActivities",
    "CashFlowsFromFinancingActivities",
)


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
        DataKind.MARGIN,
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
        # adjusted_close 取自 FinMind 官方還原價 taiwan_stock_price_adj（含息還原，back-adjust，
        # 最新日錨定＝raw）。LEFT JOIN：無還原價的標的（指數/權證）該欄為 NULL，下游 COALESCE 退回 close。
        cols = ["date", "open", "high", "low", "close", "adjusted_close", "volume", "turnover"]
        data = await self._query(
            """
            SELECT p.date, p.open, p.max AS high, p.min AS low, p.close,
                   a.close AS adjusted_close,
                   p."Trading_Volume" AS volume, p."Trading_money" AS turnover
            FROM bronze.taiwan_stock_price p
            LEFT JOIN bronze.taiwan_stock_price_adj a
                   ON a.stock_id = p.stock_id AND a.date = p.date
            WHERE p.stock_id = $1 AND p.date >= $2 AND p.date <= $3
            ORDER BY p.date
            """,
            symbol,
            start,
            end,
        )
        if not data:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        for c in ("open", "high", "low", "close", "adjusted_close", "turnover"):
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
        """財報（本地庫）。三張表合併回傳，各筆帶 statement_type 標籤：

        - 損益表  taiwan_stock_financial_statements   → statement_type="IS"（全科目）
        - 資產負債 taiwan_stock_balance_sheet          → statement_type="BS"（僅取需對映欄位）
        - 現金流量 taiwan_stock_cash_flows_statement   → statement_type="CF"（僅取需對映欄位）

        每列一個科目(type/value)，重用 API 源的單筆正規化；下游 _normalize_financial_rows
        依 statement_type 分組並把科目 pivot 進 typed 欄位（revenue/total_assets/... ）。
        BS/CF 表科目上百，僅拉會用到的 type 以免 payload 膨脹、查詢變慢。
        """
        from app.data_sources.tw.finmind_source import FinMindSource

        lo = date(year, 1, 1) if year is not None else None
        hi = date(year, 12, 31) if year is not None else None

        async def _pull(table: str, types: tuple[str, ...] | None) -> list[dict[str, Any]]:
            params: list[Any] = [symbol]
            sql = f"SELECT stock_id, date, type, value, origin_name FROM bronze.{table} WHERE stock_id = $1"  # noqa: S608 — table 為固定常數，非使用者輸入
            if lo is not None:
                params += [lo, hi]
                sql += f" AND date >= ${len(params) - 1} AND date <= ${len(params)}"
            if types is not None:
                params.append(list(types))
                sql += f" AND type = ANY(${len(params)})"
            sql += " ORDER BY date"
            return await self._query(sql, *params)

        out: list[dict[str, Any]] = []
        for table, types, st in (
            ("taiwan_stock_financial_statements", None, "IS"),
            ("taiwan_stock_balance_sheet", _BS_TYPES, "BS"),
            ("taiwan_stock_cash_flows_statement", _CF_TYPES, "CF"),
        ):
            for row in await _pull(table, types):
                d = FinMindSource._normalize_financial(row)
                d["statement_type"] = st
                out.append(d)
        return out

    async def fetch_dividend_events(self, start: date, end: date) -> list[dict[str, Any]]:
        """除權息事件（本地庫）— 給財報日曆用。

        bronze.taiwan_stock_dividend 一列 = 一檔一次配息決議，其中：
        - CashExDividendTradingDate  現金股利除息交易日
        - StockExDividendTradingDate 股票股利除權交易日
        兩者可能其一為空字串（只配息或只配股），且格式為 'YYYY-MM-DD' 文字，故先以 regex
        濾掉空值/異常值再轉 date，避免 cast 失敗。
        回傳每個「除權息交易日」一筆事件。
        """
        rows = await self._query(
            """
            SELECT stock_id, ex_date, kind, cash, stock_div
            FROM (
                SELECT stock_id,
                       nullif("CashExDividendTradingDate", '')::date AS ex_date,
                       'cash'::text AS kind,
                       "CashEarningsDistribution"::numeric AS cash,
                       NULL::numeric AS stock_div
                FROM bronze.taiwan_stock_dividend
                WHERE "CashExDividendTradingDate" ~ '^\\d{4}-\\d{2}-\\d{2}$'
                UNION ALL
                SELECT stock_id,
                       nullif("StockExDividendTradingDate", '')::date,
                       'stock'::text,
                       NULL::numeric,
                       "StockEarningsDistribution"::numeric
                FROM bronze.taiwan_stock_dividend
                WHERE "StockExDividendTradingDate" ~ '^\\d{4}-\\d{2}-\\d{2}$'
            ) t
            WHERE ex_date >= $1 AND ex_date <= $2
            ORDER BY ex_date, stock_id
            """,
            start,
            end,
        )
        return [dict(r) for r in rows]

    async def fetch_margin(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """融資融券（本地庫），重用 API 源的 normalize（欄位/型別一致）。"""
        from app.data_sources.tw.finmind_source import FinMindSource

        data = await self._query(
            """
            SELECT stock_id, date,
                   "MarginPurchaseBuy", "MarginPurchaseSell", "MarginPurchaseTodayBalance",
                   "MarginPurchaseLimit", "ShortSaleBuy", "ShortSaleSell",
                   "ShortSaleTodayBalance", "ShortSaleLimit"
            FROM bronze.taiwan_stock_margin_purchase_short_sale
            WHERE stock_id = $1 AND date >= $2 AND date <= $3
            ORDER BY date
            """,
            symbol,
            start,
            end,
        )
        return FinMindSource._normalize_margin(data)

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
