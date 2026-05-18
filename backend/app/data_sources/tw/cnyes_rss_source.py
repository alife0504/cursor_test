"""鉅亨網 cnyes RSS — 台股新聞主源。

端點：https://news.cnyes.com/rss/cat/tw_stock（台股總覽 RSS）
公開無 token、無嚴格 rate limit；但仍保守設 1 req/sec。

策略：
- 抓整個 RSS（最新 ~30 則）
- symbol=None → 全部
- symbol 給時 → 用「個股名稱 / 個股代號」匹配（caller 需提供 stock_list 名稱對照 — P5 簡化用 symbol 本身）
- 若 symbol 提供但找不到對照，預設用 symbol 字串做關鍵字匹配
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import feedparser
import httpx

from app.core.errors import ExternalServiceError
from app.core.http_client import get_async_client
from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion, register_data_source

logger = get_logger(__name__)


@register_data_source
class CnyesRSSSource(BaseDataSource):
    """鉅亨網 RSS — 台股新聞。"""

    name = "cnyes_rss"
    priority = 10  # 新聞主源
    supported_regions = (MarketRegion.TW,)
    supported_kinds = (DataKind.NEWS,)
    rate_limit_per_sec = 1.0
    base_url = "https://news.cnyes.com"
    RSS_PATH = "/rss/cat/tw_stock"

    async def fetch_news(
        self, symbol: str | None = None, *, since: date | None = None
    ) -> list[dict[str, Any]]:
        text = await self._fetch_rss_text()
        feed = feedparser.parse(text)
        entries: list[dict[str, Any]] = []
        for raw in feed.entries:
            entry = self._normalize_entry(raw)
            if entry is None:
                continue
            if since and entry["published_at"].date() < since:
                continue
            if symbol and not self._mentions_symbol(entry, symbol):
                continue
            entries.append(entry)
        return entries

    async def _fetch_rss_text(self) -> str:
        async with (
            self._rate_guard(),
            get_async_client(name=self.name, base_url=self.base_url) as client,
        ):
            try:
                resp = await client.get(self.RSS_PATH)
            except httpx.RequestError as e:
                raise ExternalServiceError(
                    message_zh="cnyes RSS 連線失敗",
                    source=self.name,
                    error=str(e),
                ) from e

        if resp.status_code >= 400:
            raise ExternalServiceError(
                message_zh=f"cnyes RSS 回應錯誤（{resp.status_code}）",
                source=self.name,
                status=resp.status_code,
            )
        if not resp.encoding:
            resp.encoding = "utf-8"
        return resp.text

    def _normalize_entry(self, raw: Any) -> dict[str, Any] | None:
        title = getattr(raw, "title", "") or raw.get("title") if hasattr(raw, "get") else ""
        if not title:
            return None

        link = getattr(raw, "link", None)
        summary = getattr(raw, "summary", "") or ""
        published_parsed = getattr(raw, "published_parsed", None)
        if published_parsed:
            try:
                published_at = datetime(*published_parsed[:6])
            except (TypeError, ValueError):
                published_at = datetime.utcnow()
        else:
            published_at = datetime.utcnow()

        return {
            "title": str(title).strip(),
            "summary": str(summary).strip() if summary else None,
            "url": str(link) if link else None,
            "published_at": published_at,
            "source": self.name,
        }

    @staticmethod
    def _mentions_symbol(entry: dict[str, Any], symbol: str) -> bool:
        """以 symbol（如 "2330"）為 keyword 在 title/summary 中尋找。

        P5 簡化版：用 symbol 字串本身做 substring 比對。Phase 7 接 stock_list
        後改成「symbol → 公司中文名（如「台積電」）」的精準匹配。
        """
        if not symbol:
            return True
        text = (entry.get("title", "") + " " + (entry.get("summary") or "")).lower()
        return symbol.lower() in text

    def _rate_guard(self):  # type: ignore[no-untyped-def]
        if self.limiter is not None:
            return self.limiter
        return _NullAsyncCtx()


class _NullAsyncCtx:
    async def __aenter__(self) -> _NullAsyncCtx:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


__all__ = ["CnyesRSSSource"]
