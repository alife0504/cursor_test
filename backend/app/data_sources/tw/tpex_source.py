"""TPEX 證櫃中心 — 上櫃股票 OHLCV 備源。

端點：https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php
參數：d=民國年/月/日（例：114/05/12）；select=AL（全市場）；不能單獨查 stock —
所以策略是「給定日期 → 取得全市場 list，再 filter 該 symbol」。對 OHLCV 取歷史
需 loop 多日（caller 通常給 ≤ 30 天）。

P5 範圍：此 source 主要用於 OTC 股票備源（market='TPEX' 的股票）。
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
class TPEXSource(BaseDataSource):
    """TPEX 上櫃 OHLCV 備源。"""

    name = "tpex"
    priority = 25
    supported_regions = (MarketRegion.TW,)
    supported_kinds = (DataKind.OHLCV,)
    rate_limit_per_sec = 0.5  # 保守
    base_url = "https://www.tpex.org.tw"
    DAILY_CLOSE_PATH = "/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php"

    async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        if end < start:
            raise ValueError("end < start")
        rows: list[dict[str, Any]] = []
        cur = start
        while cur <= end:
            day_rows = await self._fetch_day(cur)
            match = [r for r in day_rows if str(r.get("symbol", "")).strip() == symbol]
            for r in match:
                r["date"] = cur
                rows.append(r)
            cur += timedelta(days=1)

        if not rows:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "volume", "turnover"]
            )
        df = pd.DataFrame(rows)
        return df

    async def _fetch_day(self, day: date) -> list[dict[str, Any]]:
        """單日全 TPEX 上櫃股票收盤資訊。"""
        roc_str = f"{day.year - 1911}/{day.month:02d}/{day.day:02d}"
        params = {"l": "zh-tw", "d": roc_str, "se": "AL", "_": "0"}

        async with (
            self._rate_guard(),
            get_async_client(name=self.name, base_url=self.base_url) as client,
        ):
            try:
                resp = await client.get(self.DAILY_CLOSE_PATH, params=params)
            except httpx.RequestError as e:
                raise ExternalServiceError(
                    message_zh="TPEX 連線失敗",
                    source=self.name,
                    error=str(e),
                ) from e

        if resp.status_code == 429:
            raise RateLimitError(message_zh="TPEX 頻率過高", source=self.name)
        if resp.status_code >= 400:
            raise ExternalServiceError(
                message_zh=f"TPEX 回應錯誤（{resp.status_code}）",
                source=self.name,
                status=resp.status_code,
            )

        try:
            payload = resp.json()
        except Exception as e:
            raise ExternalServiceError(
                message_zh="TPEX 回傳非 JSON",
                source=self.name,
            ) from e

        if not isinstance(payload, dict):
            raise ExternalServiceError(message_zh="TPEX 回應結構異常", source=self.name)

        # TPEX 格式：{"aaData": [["代號", "名稱", "收盤", "漲跌", ..., "開盤", "最高", "最低", ...], ...]}
        # 欄位位置依官方為準（v7.0 P5 撰寫時版本）：
        # [0]代號 [1]名稱 [2]收盤 [3]漲跌 [4]開盤 [5]最高 [6]最低 [8]成交股數 [9]成交金額(千元)
        rows = payload.get("aaData") or []
        if not isinstance(rows, list):
            return []

        out: list[dict[str, Any]] = []
        for raw in rows:
            if not isinstance(raw, list) or len(raw) < 10:
                continue
            try:
                out.append(
                    {
                        "symbol": str(raw[0]).strip(),
                        "name": str(raw[1]).strip(),
                        "close": _to_decimal(raw[2]),
                        "open": _to_decimal(raw[4]),
                        "high": _to_decimal(raw[5]),
                        "low": _to_decimal(raw[6]),
                        "volume": _to_int(raw[8]),
                        "turnover": _to_decimal(raw[9]) * 1000 if _to_decimal(raw[9]) else None,
                    }
                )
            except (IndexError, TypeError):
                continue
        return out

    def _rate_guard(self):  # type: ignore[no-untyped-def]
        if self.limiter is not None:
            return self.limiter
        return _NullAsyncCtx()


class _NullAsyncCtx:
    async def __aenter__(self) -> _NullAsyncCtx:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def _to_int(v: Any) -> int:
    if v is None:
        return 0
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


__all__ = ["TPEXSource"]
