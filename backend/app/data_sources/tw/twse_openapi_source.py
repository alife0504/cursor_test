"""TWSE 證交所 — 上市股票 OHLCV 備源 + 三大法人。

兩個端點：
1. OpenAPI: https://openapi.twse.com.tw/v1/...（穩定但偏向「當日最新」）
2. STOCK_DAY: https://www.twse.com.tw/exchangeReport/STOCK_DAY?date=YYYYMMDD&stockNo=XXXX
   （月為單位，HTTP GET，回 JSON；穩定取歷史，但官方未保證 SLA — 用作備源）

策略（P5 prompt 第 F 段 + 第 7 段「已知陷阱」）：
- fetch_ohlcv() 用 STOCK_DAY（月為單位 loop）→ 取歷史
- TWSE 官方建議 ≤ 1 req/sec → rate_limit_per_sec=1.0
- 解析回的 data 是「民國年」字串日期（114/11/25），要轉西元
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pandas as pd

from app.core.errors import ExternalServiceError, RateLimitError
from app.core.http_client import get_async_client
from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion, register_data_source

logger = get_logger(__name__)


@register_data_source
class TWSEOpenAPISource(BaseDataSource):
    """TWSE — 上市股票 OHLCV 備源 + 三大法人。"""

    name = "twse_openapi"
    priority = 20  # 備源
    supported_regions = (MarketRegion.TW,)
    # ⚠️ 不宣告 DataKind.INSTITUTIONAL：fetch_institutional 回傳 T86 的**中文欄位**
    # （證券代號/外陸資買進股數…），未 pivot 成標準 foreign_buy/foreign_sell/… 英文欄名，
    # 消費端 market_repo.upsert_institutional 以 int(r.get('foreign_buy') or 0) 取值會全部得 0
    # → 靜默寫入「三大法人 0/0/0」假資料（比缺漏更糟，看似合法的零買賣超）。法人資料由
    # finmind_local（priority 5）與 finmind API（bulk 全市場，標準 pivot）供應，twse 不入合併候選。
    # 若未來要啟用，須先在 fetch_institutional 正確 pivot（外資=外陸資+外資自營、自營=自行+避險）。
    supported_kinds = (DataKind.OHLCV,)
    rate_limit_per_sec = 1.0  # TWSE 公告建議
    base_url = "https://www.twse.com.tw"
    STOCK_DAY_PATH = "/exchangeReport/STOCK_DAY"
    INSTITUTIONAL_PATH = "/fund/T86"

    async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """STOCK_DAY 月為單位查詢。loop 從 start ~ end 月。"""
        if end < start:
            raise ValueError("end < start")
        # 列出 start.year/start.month ~ end.year/end.month
        months: list[date] = []
        cur = date(start.year, start.month, 1)
        while cur <= end:
            months.append(cur)
            # 下個月 1 號
            cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)

        all_rows: list[dict[str, Any]] = []
        for m in months:
            month_str = m.strftime("%Y%m%d")
            rows = await self._fetch_stock_day(symbol, month_str)
            all_rows.extend(rows)

        df = pd.DataFrame(all_rows)
        if df.empty:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "volume", "turnover"]
            )
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[(df["date"] >= start) & (df["date"] <= end)].reset_index(drop=True)
        return df

    async def fetch_institutional(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """T86：每日三大法人買賣超（單日，全市場）。

        為了「給定股票 + 日期區間」，我們需要：對每個交易日 GET 一次然後 filter 該 symbol。
        因 P5 範圍下測試會 mock 整個流程，這裡保持簡潔實作；P7 排程才會大量呼叫。
        """
        rows: list[dict[str, Any]] = []
        cur = start
        while cur <= end:
            day_rows = await self._fetch_institutional_day(cur)
            for r in day_rows:
                if r.get("stock_id") == symbol:
                    r["date"] = cur
                    rows.append(r)
            cur += timedelta(days=1)

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        return df

    # ── 內部 ─────────────────────────────────────────────

    async def _fetch_stock_day(self, symbol: str, date_str: str) -> list[dict[str, Any]]:
        """單月 STOCK_DAY 查詢，回 list[dict]（date / open / high / low / close / volume / turnover）。"""
        params = {"response": "json", "date": date_str, "stockNo": symbol}
        async with (
            self._guard_rate_limit(),
            get_async_client(name=self.name, base_url=self.base_url) as client,
        ):
            resp = await self._safe_get(client, self.STOCK_DAY_PATH, params=params)

        payload = self._parse_json(resp)
        # TWSE 格式：{"stat": "OK", "fields": [...], "data": [[...], ...]}
        stat = str(payload.get("stat", ""))
        if stat == "":
            raise ExternalServiceError(message_zh="TWSE 回應格式異常", source=self.name)
        if stat not in ("OK", "ok"):
            # 例如「沒有符合條件」回 "很抱歉，沒有符合條件的資料!"
            return []
        fields: list[str] = payload.get("fields", [])
        data: list[list[Any]] = payload.get("data", [])
        idx = {f: i for i, f in enumerate(fields)}

        def col(name: str, row: list[Any]) -> Any:
            i = idx.get(name)
            if i is None or i >= len(row):
                return None
            return row[i]

        rows: list[dict[str, Any]] = []
        for r in data:
            d_str = col("日期", r)
            roc_date = _roc_to_date(d_str)
            if roc_date is None:
                continue
            rows.append(
                {
                    "date": roc_date,
                    "volume": _to_int(col("成交股數", r)),
                    "turnover": _to_decimal(col("成交金額", r)),
                    "open": _to_decimal(col("開盤價", r)),
                    "high": _to_decimal(col("最高價", r)),
                    "low": _to_decimal(col("最低價", r)),
                    "close": _to_decimal(col("收盤價", r)),
                }
            )
        return rows

    async def _fetch_institutional_day(self, day: date) -> list[dict[str, Any]]:
        """單日 T86：全市場三大法人。"""
        params = {"response": "json", "date": day.strftime("%Y%m%d"), "selectType": "ALL"}
        async with (
            self._guard_rate_limit(),
            get_async_client(name=self.name, base_url=self.base_url) as client,
        ):
            resp = await self._safe_get(client, self.INSTITUTIONAL_PATH, params=params)

        payload = self._parse_json(resp)
        if str(payload.get("stat", "")) not in ("OK", "ok"):
            return []
        fields: list[str] = payload.get("fields", [])
        data: list[list[Any]] = payload.get("data", [])
        if not fields or not data:
            return []
        rows: list[dict[str, Any]] = []
        for row in data:
            d = dict(zip(fields, row, strict=False))
            rows.append({"stock_id": str(d.get("證券代號", "")).strip(), **d})
        return rows

    def _guard_rate_limit(self):  # type: ignore[no-untyped-def]
        """如果有 limiter 就 enter 它；沒有則回 null context。"""
        if self.limiter is not None:
            return self.limiter
        return _null_async_ctx()

    async def _safe_get(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict[str, Any],
    ) -> httpx.Response:
        try:
            resp = await client.get(path, params=params)
        except httpx.RequestError as e:
            raise ExternalServiceError(
                message_zh="TWSE 連線失敗",
                source=self.name,
                error=str(e),
            ) from e
        if resp.status_code == 429:
            raise RateLimitError(message_zh="TWSE 頻率過高", source=self.name)
        if resp.status_code >= 400:
            raise ExternalServiceError(
                message_zh=f"TWSE 回應錯誤（{resp.status_code}）",
                source=self.name,
                status=resp.status_code,
            )
        return resp

    def _parse_json(self, resp: httpx.Response) -> dict[str, Any]:
        try:
            payload = resp.json()
        except Exception as e:
            raise ExternalServiceError(
                message_zh="TWSE 回傳非 JSON",
                source=self.name,
            ) from e
        if not isinstance(payload, dict):
            raise ExternalServiceError(
                message_zh="TWSE 回應結構異常",
                source=self.name,
            )
        return payload


class _NullAsyncCtx:
    async def __aenter__(self) -> _NullAsyncCtx:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def _null_async_ctx() -> _NullAsyncCtx:
    return _NullAsyncCtx()


def _roc_to_date(s: str | None) -> date | None:
    """民國日期字串 → date。例 "114/11/25" → 2025-11-25"""
    if not s:
        return None
    s = str(s).strip()
    parts = s.split("/")
    if len(parts) != 3:
        return None
    try:
        roc_year, m, d = (int(p) for p in parts)
    except ValueError:
        return None
    return date(roc_year + 1911, m, d)


def _to_int(v: Any) -> int:
    if v is None:
        return 0
    if isinstance(v, int):
        return v
    s = str(v).replace(",", "").strip()
    if not s or s in ("--", "X"):
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def _to_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if not s or s in ("--", "X"):
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


__all__ = ["TWSEOpenAPISource"]
