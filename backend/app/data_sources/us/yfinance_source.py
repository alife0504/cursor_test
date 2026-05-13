"""yfinance — 美股 OHLCV / 公司基本資料 / 財報 / 新聞 主源。

注意（PLAN P6 第 7 段「已知陷阱」）：
- yfinance 是同步包裝 Yahoo Finance HTTP，呼叫一定要 run_in_executor 避免 block event loop
- yfinance 對 symbol 大小寫敏感 → 統一 .upper()
- BRK.B 對應 yfinance 的格式是「BRK-B」（dot → hyphen）
- 空 DataFrame 視為 NotFound
- yfinance 內部錯誤五花八門（YFRateLimitError、Exception、KeyError ...），統一包成 ExternalServiceError

設計：
- 同步 yfinance 呼叫包進 asyncio.get_running_loop().run_in_executor(None, ...)
- rate_limit_per_sec=2.0（保守，Yahoo 沒官方 limit 但太快會被擋）
- _normalize_ohlcv 與 FinMind 對齊輸出欄位：date / open / high / low / close / volume / turnover
"""

from __future__ import annotations

import asyncio
import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd

from app.core.errors import ExternalServiceError, NotFoundError
from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion, register_data_source

logger = get_logger(__name__)


@register_data_source
class YFinanceSource(BaseDataSource):
    """yfinance — 美股主源。"""

    name = "yfinance"
    priority = 10  # 美股主源
    supported_regions = (MarketRegion.US,)
    supported_kinds = (
        DataKind.OHLCV,
        DataKind.COMPANY_INFO,
        DataKind.FINANCIAL,
        DataKind.NEWS,
    )
    rate_limit_per_sec = 2.0
    base_url = "https://query2.finance.yahoo.com"  # 僅供 health_check / log；實際 yfinance 自管

    # ── 抽象 fetch_* 實作 ────────────────────────────────

    async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """抓 OHLCV — yfinance.download() 同步 → run_in_executor。

        Args:
            symbol: 美股代號（如 "AAPL"、"BRK.B"）
            start: 起始日期（含）
            end: 結束日期（含）— yfinance 預設 exclusive，需 +1 day

        Returns:
            DataFrame 欄位：date / open / high / low / close / volume / turnover
        """
        normalized_symbol = self._normalize_symbol(symbol)

        # yfinance end 是 exclusive，+1 day
        end_exclusive = end + timedelta(days=1)

        df = await self._run_sync(
            lambda: self._yf_download(
                normalized_symbol, start.isoformat(), end_exclusive.isoformat()
            )
        )
        if df is None or df.empty:
            raise NotFoundError(
                message_zh=f"yfinance 找不到 {symbol} 的 OHLCV 資料",
                symbol=symbol,
                start=start.isoformat(),
                end=end.isoformat(),
            )
        return self._normalize_ohlcv(df, symbol)

    async def fetch_company_info(self, symbol: str) -> dict[str, Any]:
        """抓公司基本資料 — yfinance.Ticker(symbol).info。"""
        normalized = self._normalize_symbol(symbol)
        info = await self._run_sync(lambda: self._yf_info(normalized))
        if not info:
            raise NotFoundError(
                message_zh=f"yfinance 找不到 {symbol} 的公司基本資料",
                symbol=symbol,
            )
        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName"),
            "industry": info.get("industry"),
            "sector": info.get("sector"),
            "country": info.get("country"),
            "website": info.get("website"),
            "employees": info.get("fullTimeEmployees"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency"),
            "raw": {k: v for k, v in info.items() if not _is_unserializable(v)},
        }

    async def fetch_financial(
        self,
        symbol: str,
        *,
        year: int | None = None,
        quarter: int | None = None,
    ) -> list[dict[str, Any]]:
        """抓財報 — yfinance.Ticker(symbol).income_stmt / balance_sheet / cashflow。

        Returns list of normalized statements。yfinance 一次回所有期間，
        caller 可自行依 year/quarter 篩。
        """
        normalized = self._normalize_symbol(symbol)
        statements = await self._run_sync(lambda: self._yf_financial(normalized))
        if not statements:
            raise NotFoundError(
                message_zh=f"yfinance 找不到 {symbol} 的財報",
                symbol=symbol,
            )
        out: list[dict[str, Any]] = []
        for stmt_type, df in statements.items():
            if df is None or df.empty:
                continue
            for col in df.columns:
                period_date = _to_date_safely(col)
                if period_date is None:
                    continue
                if year is not None and period_date.year != year:
                    continue
                items: list[dict[str, Any]] = []
                for idx, value in df[col].items():
                    items.append(
                        {
                            "type": str(idx),
                            "value": _to_decimal_or_none(value),
                        }
                    )
                out.append(
                    {
                        "symbol": symbol,
                        "fiscal_year": period_date.year,
                        "fiscal_quarter": _quarter_from_month(period_date.month),
                        "period_end": period_date,
                        "statement_type": stmt_type,
                        "payload": {"items": items},
                        "source": self.name,
                    }
                )
        return out

    async def fetch_news(
        self, symbol: str | None = None, *, since: date | None = None
    ) -> list[dict[str, Any]]:
        """抓新聞 — yfinance.Ticker(symbol).news。

        symbol=None：yfinance 不支援抓「大盤新聞」，回空 list（與 cnyes 對齊）。
        """
        if not symbol:
            return []
        normalized = self._normalize_symbol(symbol)
        items = await self._run_sync(lambda: self._yf_news(normalized))
        if not items:
            return []
        out: list[dict[str, Any]] = []
        for raw in items:
            entry = self._normalize_news_entry(raw, symbol)
            if entry is None:
                continue
            if since is not None and entry["published_at"].date() < since:
                continue
            out.append(entry)
        return out

    # ── 內部：同步 yfinance 呼叫 ───────────────────────────

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """yfinance: BRK.B → BRK-B；統一大寫；移除空白。"""
        s = str(symbol or "").strip().upper()
        if not s:
            raise ExternalServiceError(message_zh="symbol 不可為空", source="yfinance")
        return s.replace(".", "-")

    async def _run_sync(self, fn):  # type: ignore[no-untyped-def]
        """把同步呼叫包成 async。處理 rate limit + 統一錯誤包裝。"""

        async def _call():  # type: ignore[no-untyped-def]
            loop = asyncio.get_running_loop()
            try:
                return await loop.run_in_executor(None, fn)
            except NotFoundError:
                raise
            except Exception as e:
                # yfinance 各種內部錯誤（YFRateLimitError / YFPricesMissingError / KeyError 等）
                logger.warning(
                    "yfinance.sync_call_failed",
                    error_type=type(e).__name__,
                    error=str(e),
                )
                raise ExternalServiceError(
                    message_zh="yfinance 呼叫失敗",
                    source=self.name,
                    error_type=type(e).__name__,
                    error=str(e),
                ) from e

        if self.limiter is not None:
            async with self.limiter:
                return await _call()
        return await _call()

    @staticmethod
    def _yf_download(symbol: str, start: str, end: str) -> pd.DataFrame:
        """同步 yfinance.download — 在 executor 中執行。"""
        import yfinance as yf

        df = yf.download(
            symbol,
            start=start,
            end=end,
            progress=False,
            auto_adjust=False,
            threads=False,
            timeout=30,
        )
        # yfinance >=0.2.40：MultiIndex columns when single symbol — flatten
        if isinstance(df, pd.DataFrame) and isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        return df

    @staticmethod
    def _yf_info(symbol: str) -> dict[str, Any]:
        import yfinance as yf

        t = yf.Ticker(symbol)
        info = t.info or {}
        return dict(info)

    @staticmethod
    def _yf_financial(symbol: str) -> dict[str, pd.DataFrame]:
        import yfinance as yf

        t = yf.Ticker(symbol)
        return {
            "IS": t.income_stmt,
            "BS": t.balance_sheet,
            "CF": t.cashflow,
        }

    @staticmethod
    def _yf_news(symbol: str) -> list[dict[str, Any]]:
        import yfinance as yf

        t = yf.Ticker(symbol)
        return list(t.news or [])

    # ── 標準化 helpers ───────────────────────────────────

    @staticmethod
    def _normalize_ohlcv(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """yfinance df → 統一 OHLCV 欄位（與 FinMind 對齊）。

        yfinance 欄位：Date(index) / Open / High / Low / Close / Adj Close / Volume
        """
        if df.empty:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "volume", "turnover"]
            )
        # index = Date
        out = df.reset_index().rename(
            columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )
        # 只取需要的欄位
        keep = [c for c in ("date", "open", "high", "low", "close", "volume") if c in out.columns]
        out = out[keep].copy()
        out["date"] = pd.to_datetime(out["date"]).dt.date
        for col in ("open", "high", "low", "close"):
            if col in out.columns:
                out[col] = out[col].apply(_to_decimal_or_none)
        if "volume" in out.columns:
            out["volume"] = out["volume"].fillna(0).astype("int64")
        # yfinance 不直接給「成交金額」；給 close × volume 估算（標 turnover 但 caller 可忽略）
        if "close" in out.columns and "volume" in out.columns:
            out["turnover"] = [
                (c * v if c is not None else None)
                for c, v in zip(out["close"], out["volume"], strict=False)
            ]
        return out

    @staticmethod
    def _normalize_news_entry(raw: dict[str, Any], symbol: str) -> dict[str, Any] | None:
        """yfinance .news 一筆 → 統一 schema。

        yfinance 各版本欄位略異；v0.2.4x 後可能巢狀在 ['content']。
        """
        if not isinstance(raw, dict):
            return None
        # v0.2.4x 後：raw["content"]["title"] / .url
        content = raw.get("content") if isinstance(raw.get("content"), dict) else raw
        title = content.get("title")
        if not title:
            return None
        url = (
            content.get("canonicalUrl", {}).get("url")
            if isinstance(content.get("canonicalUrl"), dict)
            else None
        )
        url = url or content.get("link") or content.get("url")
        pub_raw = (
            content.get("pubDate")
            or content.get("displayTime")
            or content.get("providerPublishTime")
        )
        published_at = _parse_news_pub_date(pub_raw) or datetime.utcnow()
        return {
            "title": str(title).strip(),
            "summary": content.get("summary") or content.get("description"),
            "url": str(url) if url else None,
            "published_at": published_at,
            "source": "yfinance",
            "symbol": symbol,
        }


# ── module-level helpers ──────────────────────────────────


def _parse_news_pub_date(v: Any) -> datetime | None:
    """容錯解析多種 yfinance pubDate 格式。"""
    if v is None:
        return None
    # epoch seconds
    if isinstance(v, int | float):
        try:
            return datetime.utcfromtimestamp(int(v))
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            # ISO format
            return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
        try:
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            return None
    return None


def _to_decimal_or_none(v: Any) -> Decimal | None:
    """安全轉 Decimal；None / NaN / 空字串 → None。"""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return Decimal(str(v))
    if isinstance(v, int):
        return Decimal(v)
    if isinstance(v, str):
        s = v.strip()
        if not s or s.lower() == "nan":
            return None
        try:
            return Decimal(s)
        except Exception:
            return None
    return None


def _to_date_safely(v: Any) -> date | None:
    """容錯轉 date — 接受 Timestamp / datetime / date / 字串。"""
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    try:
        return pd.to_datetime(v).date()
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


def _is_unserializable(v: Any) -> bool:
    """過濾 yfinance.info 中不可序列化的奇特物件（list of complex / Ticker 等）。"""
    return callable(v)


__all__ = ["YFinanceSource"]
