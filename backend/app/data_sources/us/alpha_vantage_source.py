"""Alpha Vantage — 美股 OHLCV / 財報 備源。

API 文件：https://www.alphavantage.co/documentation/

免費版限制（PLAN 20.1）：25 requests/day → 每秒 0.4 已經很寬鬆。
注意（PLAN P6 第 7 段「已知陷阱」）：
- 配額耗盡時 API 仍回 200 + Note 欄位（不是 4xx）→ 主動檢查 Note
- "Error Message" 欄位代表 symbol 錯
- "Information" 欄位代表「請升級會員」

API key 為 None 時：raise AuthError（但放行到 fallback 處理，不在 init 時 fail）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pandas as pd

from app.core.errors import (
    AuthError,
    ExternalServiceError,
    NotFoundError,
    QuotaExceededError,
)
from app.core.http_client import get_async_client
from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion, register_data_source

logger = get_logger(__name__)


@register_data_source
class AlphaVantageSource(BaseDataSource):
    """Alpha Vantage — 美股備源。"""

    name = "alpha_vantage"
    priority = 20  # 備源
    supported_regions = (MarketRegion.US,)
    supported_kinds = (DataKind.OHLCV, DataKind.FINANCIAL)
    rate_limit_per_sec = 0.4  # 25/day 配額對應保守值
    base_url = "https://www.alphavantage.co"
    QUERY_PATH = "/query"

    # ── 抽象 fetch_* 實作 ────────────────────────────────

    async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """TIME_SERIES_DAILY — 回該股全部歷史，caller filter 範圍。"""
        outputsize = "full" if (end - start).days > 100 else "compact"

        data = await self._call(
            function="TIME_SERIES_DAILY",
            symbol=symbol.upper(),
            outputsize=outputsize,
            datatype="json",
        )

        series = data.get("Time Series (Daily)")
        if not series:
            raise NotFoundError(
                message_zh=f"Alpha Vantage 找不到 {symbol} 的 OHLCV",
                symbol=symbol,
            )
        return self._normalize_ohlcv(series, start, end)

    async def fetch_financial(
        self,
        symbol: str,
        *,
        year: int | None = None,
        quarter: int | None = None,
    ) -> list[dict[str, Any]]:
        """INCOME_STATEMENT / BALANCE_SHEET / CASH_FLOW — 三個 endpoint。"""
        out: list[dict[str, Any]] = []
        for fn, stmt_type in (
            ("INCOME_STATEMENT", "IS"),
            ("BALANCE_SHEET", "BS"),
            ("CASH_FLOW", "CF"),
        ):
            payload = await self._call(function=fn, symbol=symbol.upper())
            # 年/季報分兩欄位
            for key, default_quarter in (
                ("annualReports", None),
                ("quarterlyReports", "auto"),
            ):
                reports = payload.get(key) or []
                for r in reports:
                    fy_end = _to_date_or_none(r.get("fiscalDateEnding"))
                    if fy_end is None:
                        continue
                    if year is not None and fy_end.year != year:
                        continue
                    derived_q = _quarter_from_month(fy_end.month)
                    fq = (
                        derived_q
                        if default_quarter == "auto"
                        else (quarter if quarter is not None else 4)
                    )
                    if quarter is not None and default_quarter == "auto" and derived_q != quarter:
                        continue
                    items = [
                        {"type": k, "value": _to_decimal_or_none(v)}
                        for k, v in r.items()
                        if k not in {"fiscalDateEnding", "reportedCurrency"}
                    ]
                    out.append(
                        {
                            "symbol": symbol.upper(),
                            "fiscal_year": fy_end.year,
                            "fiscal_quarter": fq,
                            "period_end": fy_end,
                            "statement_type": stmt_type,
                            "payload": {
                                "currency": r.get("reportedCurrency"),
                                "items": items,
                            },
                            "source": self.name,
                        }
                    )
        return out

    # ── 內部 ──────────────────────────────────────────────

    @property
    def api_key(self) -> str:
        key = self.settings.ALPHA_VANTAGE_API_KEY
        value = key.get_secret_value() if key is not None else ""
        if not value:
            raise AuthError(
                message_zh="Alpha Vantage API key 未設定（ALPHA_VANTAGE_API_KEY）",
                source=self.name,
            )
        return value

    async def _call(self, **params: Any) -> dict[str, Any]:
        params["apikey"] = self.api_key
        async with (
            self._rate_guard(),
            get_async_client(name=self.name, base_url=self.base_url) as client,
        ):
            try:
                resp = await client.get(self.QUERY_PATH, params=params)
            except httpx.RequestError as e:
                raise ExternalServiceError(
                    message_zh="Alpha Vantage 連線失敗",
                    source=self.name,
                    error=str(e),
                ) from e

        if resp.status_code >= 500:
            raise ExternalServiceError(
                message_zh=f"Alpha Vantage 服務錯誤（{resp.status_code}）",
                source=self.name,
                status=resp.status_code,
            )
        if resp.status_code >= 400:
            raise ExternalServiceError(
                message_zh=f"Alpha Vantage 回應錯誤（{resp.status_code}）",
                source=self.name,
                status=resp.status_code,
            )

        try:
            data = resp.json()
        except Exception as e:
            raise ExternalServiceError(
                message_zh="Alpha Vantage 回傳非 JSON",
                source=self.name,
                body=resp.text[:500],
            ) from e

        if not isinstance(data, dict):
            raise ExternalServiceError(
                message_zh="Alpha Vantage 回應格式異常",
                source=self.name,
            )

        # 業務錯誤（即使 HTTP 200）
        if "Error Message" in data:
            raise NotFoundError(
                message_zh=f"Alpha Vantage 找不到 symbol：{data['Error Message']}",
                source=self.name,
            )
        # 配額用盡：Note 或 Information 欄位
        note = data.get("Note") or data.get("Information")
        if note:
            raise QuotaExceededError(
                message_zh="Alpha Vantage 配額已用盡或頻率過高",
                source=self.name,
                note=str(note),
            )
        return data

    def _rate_guard(self):  # type: ignore[no-untyped-def]
        if self.limiter is not None:
            return self.limiter
        return _NullAsyncCtx()

    # ── 標準化 ────────────────────────────────────────────

    @staticmethod
    def _normalize_ohlcv(series: dict[str, dict[str, str]], start: date, end: date) -> pd.DataFrame:
        """Alpha Vantage daily series → 統一 OHLCV DataFrame（filter 日期範圍）。

        AV 欄位：
            "1. open" / "2. high" / "3. low" / "4. close" / "5. volume"
        """
        rows: list[dict[str, Any]] = []
        for date_str, fields in series.items():
            try:
                d = date.fromisoformat(date_str)
            except ValueError:
                continue
            if d < start or d > end:
                continue
            rows.append(
                {
                    "date": d,
                    "open": _to_decimal_or_none(fields.get("1. open")),
                    "high": _to_decimal_or_none(fields.get("2. high")),
                    "low": _to_decimal_or_none(fields.get("3. low")),
                    "close": _to_decimal_or_none(fields.get("4. close")),
                    "volume": _to_int(fields.get("5. volume")),
                }
            )
        if not rows:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "volume", "turnover"]
            )
        df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
        df["turnover"] = [
            (c * v if c is not None else None)
            for c, v in zip(df["close"], df["volume"], strict=False)
        ]
        return df


# ── helpers ─────────────────────────────────────────────


class _NullAsyncCtx:
    async def __aenter__(self) -> _NullAsyncCtx:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def _to_decimal_or_none(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    s = str(v) if isinstance(v, int | float) else str(v).strip()
    if not s or s.lower() in {"none", "nan", "n/a"}:
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def _to_int(v: Any) -> int:
    if v is None:
        return 0
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (ValueError, TypeError):
        return 0


def _to_date_or_none(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        return None


def _quarter_from_month(m: int) -> int:
    if 1 <= m <= 3:
        return 1
    if 4 <= m <= 6:
        return 2
    if 7 <= m <= 9:
        return 3
    return 4


__all__ = ["AlphaVantageSource"]
