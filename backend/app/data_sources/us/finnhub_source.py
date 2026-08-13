"""Finnhub — 美股新聞 / 公司基本資料 備源。

API 文件：https://finnhub.io/docs/api

免費版限制（PLAN 20.1）：60 requests/min → 1/sec。
注意：免費 plan 部分 endpoint 鎖（institutional ownership 等）。

P6 使用的 endpoints：
- /api/v1/company-news?symbol=AAPL&from=YYYY-MM-DD&to=YYYY-MM-DD
- /api/v1/stock/profile2?symbol=AAPL
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import httpx

from app.core.errors import (
    AuthError,
    ExternalServiceError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
)
from app.core.http_client import get_async_client
from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion, register_data_source

logger = get_logger(__name__)


@register_data_source
class FinnhubSource(BaseDataSource):
    """Finnhub — 美股新聞 / 公司資料備源。"""

    name = "finnhub"
    priority = 30
    supported_regions = (MarketRegion.US,)
    supported_kinds = (DataKind.NEWS, DataKind.COMPANY_INFO)
    rate_limit_per_sec = 1.0  # 60/min
    base_url = "https://finnhub.io"
    COMPANY_NEWS_PATH = "/api/v1/company-news"
    PROFILE_PATH = "/api/v1/stock/profile2"

    # ── 抽象 fetch_* 實作 ────────────────────────────────

    async def fetch_news(
        self, symbol: str | None = None, *, since: date | None = None
    ) -> list[dict[str, Any]]:
        """Finnhub /company-news — 需 symbol；無 symbol 回空。

        Finnhub 預設只回最近 30 天，since=None 自動填昨日 - 30 天。
        """
        if not symbol:
            return []

        end = date.today()
        start = since or (end - timedelta(days=30))

        items = await self._call_list(
            self.COMPANY_NEWS_PATH,
            params={
                "symbol": symbol.upper(),
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
        )

        out: list[dict[str, Any]] = []
        for raw in items:
            entry = self._normalize_news(raw, symbol)
            if entry is None:
                continue
            out.append(entry)
        return out

    async def fetch_company_info(self, symbol: str) -> dict[str, Any]:
        """Finnhub /stock/profile2 — 公司簡介。"""
        data = await self._call_dict(
            self.PROFILE_PATH,
            params={"symbol": symbol.upper()},
        )
        if not data:
            raise NotFoundError(
                message_zh=f"Finnhub 找不到 {symbol} 的公司資料",
                source=self.name,
                symbol=symbol,
            )
        return {
            "symbol": data.get("ticker") or symbol.upper(),
            "name": data.get("name"),
            "industry": data.get("finnhubIndustry"),
            "country": data.get("country"),
            "exchange": data.get("exchange"),
            "currency": data.get("currency"),
            "ipo": data.get("ipo"),
            "market_cap": data.get("marketCapitalization"),
            "share_outstanding": data.get("shareOutstanding"),
            "website": data.get("weburl"),
            "logo": data.get("logo"),
            "phone": data.get("phone"),
            "raw": data,
        }

    # ── 內部 ──────────────────────────────────────────────

    @property
    def api_key(self) -> str:
        key = self.settings.FINNHUB_API_KEY
        value = key.get_secret_value() if key is not None else ""
        if not value:
            raise AuthError(
                message_zh="Finnhub API key 未設定（FINNHUB_API_KEY）",
                source=self.name,
            )
        return value

    async def _request(self, path: str, *, params: dict[str, Any]) -> httpx.Response:
        params = {**params, "token": self.api_key}
        async with (
            self._rate_guard(),
            get_async_client(name=self.name, base_url=self.base_url) as client,
        ):
            try:
                resp = await client.get(path, params=params)
            except httpx.RequestError as e:
                raise ExternalServiceError(
                    message_zh="Finnhub 連線失敗",
                    source=self.name,
                    error=str(e),
                ) from e
        if resp.status_code == 401:
            raise AuthError(message_zh="Finnhub token 認證失敗", source=self.name)
        if resp.status_code == 403:
            raise ForbiddenError(
                message_zh="Finnhub 此 endpoint 在免費 plan 不可用",
                source=self.name,
            )
        if resp.status_code == 429:
            raise RateLimitError(
                message_zh="Finnhub 頻率過高（60/min）",
                source=self.name,
            )
        if resp.status_code >= 400:
            raise ExternalServiceError(
                message_zh=f"Finnhub 回應錯誤（{resp.status_code}）",
                source=self.name,
                status=resp.status_code,
            )
        return resp

    async def _call_list(self, path: str, *, params: dict[str, Any]) -> list[dict[str, Any]]:
        resp = await self._request(path, params=params)
        try:
            data = resp.json()
        except Exception as e:
            raise ExternalServiceError(
                message_zh="Finnhub 回傳非 JSON",
                source=self.name,
            ) from e
        if not isinstance(data, list):
            raise ExternalServiceError(
                message_zh="Finnhub 回應格式異常（預期 list）",
                source=self.name,
            )
        return data

    async def _call_dict(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        resp = await self._request(path, params=params)
        try:
            data = resp.json()
        except Exception as e:
            raise ExternalServiceError(
                message_zh="Finnhub 回傳非 JSON",
                source=self.name,
            ) from e
        if not isinstance(data, dict):
            raise ExternalServiceError(
                message_zh="Finnhub 回應格式異常（預期 dict）",
                source=self.name,
            )
        return data

    def _rate_guard(self):  # type: ignore[no-untyped-def]
        if self.limiter is not None:
            return self.limiter
        return _NullAsyncCtx()

    # ── 標準化 ────────────────────────────────────────────

    @staticmethod
    def _normalize_news(raw: dict[str, Any], symbol: str) -> dict[str, Any] | None:
        """Finnhub /company-news 一筆 → 統一 schema。

        Finnhub 欄位：
            category / datetime(epoch) / headline / id / image / related / source / summary / url
        """
        headline = raw.get("headline")
        url = raw.get("url")
        if not headline or not url:
            return None
        epoch = raw.get("datetime") or 0
        try:
            published_at = datetime.utcfromtimestamp(int(epoch))
        except (TypeError, ValueError, OSError, OverflowError):
            published_at = datetime.utcnow()
        return {
            "title": str(headline).strip(),
            "summary": raw.get("summary"),
            "url": str(url),
            "published_at": published_at,
            "source": "finnhub",
            "symbol": symbol.upper(),
            "image": raw.get("image"),
            "category": raw.get("category"),
        }


class _NullAsyncCtx:
    async def __aenter__(self) -> _NullAsyncCtx:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


__all__ = ["FinnhubSource"]
