"""MOPS 公開資訊觀測站 — 財報 / 月營收 / 重大訊息 備源。

端點（v7.0 P5 撰寫時）：
- 月營收：https://mops.twse.com.tw/nas/t21/sii/t21sc03_<year>_<month>.html（HTML 表格）
- 重大訊息：https://mops.twse.com.tw/mops/web/ajax_t05st02（FORM POST 抓 HTML 表格）
- 財報：https://mops.twse.com.tw/mops/web/ajax_t164sb04（取得 IFRS 完整財報，年/季+code）

MOPS 偶爾改版 HTML 結構 → BeautifulSoup parsing 要 robust + 失敗 raise，交給 fallback。

P5 範圍：實作最常用的 monthly_revenue + announcement 兩個。
financial 直接 raise NotImplementedError（由 FinMind 處理）— 留給 future（v1.1）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.core.errors import ExternalServiceError, RateLimitError
from app.core.http_client import get_async_client
from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion, register_data_source

logger = get_logger(__name__)


@register_data_source
class MOPSSource(BaseDataSource):
    """MOPS — 財報 / 月營收 / 重大訊息 備源。"""

    name = "mops"
    priority = 30
    supported_regions = (MarketRegion.TW,)
    supported_kinds = (DataKind.ANNOUNCEMENT, DataKind.MONTHLY_REVENUE)
    rate_limit_per_sec = 0.5  # MOPS 公告建議
    base_url = "https://mops.twse.com.tw"

    MONTHLY_REVENUE_PATH = "/nas/t21/sii/t21sc03_{year}_{month}.html"
    ANNOUNCEMENT_PATH = "/mops/web/ajax_t05st02"

    # ── Monthly Revenue ───────────────────────────────────

    async def fetch_monthly_revenue(
        self, symbol: str, *, year: int | None = None
    ) -> list[dict[str, Any]]:
        """抓某年每月營收 — MOPS HTML 表格解析。

        若 year=None → 用今年。
        回傳 list[{symbol, year, month, revenue, revenue_mom, revenue_yoy, ytd_revenue, ytd_yoy}]
        """
        if year is None:
            from datetime import datetime

            year = datetime.utcnow().year

        out: list[dict[str, Any]] = []
        for month in range(1, 13):
            try:
                html = await self._fetch_monthly_html(year, month)
            except ExternalServiceError as e:
                # 月份還沒到 → 404，繼續下一個
                if str(e.details.get("status", "")).startswith("4"):
                    continue
                raise

            row = self._parse_monthly_for_symbol(html, symbol, year, month)
            if row is not None:
                out.append(row)
        return out

    async def _fetch_monthly_html(self, year: int, month: int) -> str:
        path = self.MONTHLY_REVENUE_PATH.format(year=year - 1911, month=month)
        async with (
            self._rate_guard(),
            get_async_client(name=self.name, base_url=self.base_url) as client,
        ):
            try:
                resp = await client.get(path)
            except httpx.RequestError as e:
                raise ExternalServiceError(
                    message_zh="MOPS 連線失敗", source=self.name, error=str(e)
                ) from e
        if resp.status_code == 429:
            raise RateLimitError(message_zh="MOPS 頻率過高", source=self.name)
        if resp.status_code >= 400:
            raise ExternalServiceError(
                message_zh=f"MOPS 月營收頁回應錯誤（{resp.status_code}）",
                source=self.name,
                status=resp.status_code,
            )
        # MOPS 月營收頁是 big5 編碼（HTML meta 標 big5）
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = "big5"
        return resp.text

    def _parse_monthly_for_symbol(
        self, html: str, symbol: str, year: int, month: int
    ) -> dict[str, Any] | None:
        """在 MOPS HTML 表格中找到 symbol 的那一列。

        MOPS 月營收表大致欄位：
        | 公司代號 | 公司名稱 | 當月營收 | 上月營收 | 去年當月營收 |
        | 上月比較增減(%) | 去年同月增減(%) | 當月累計營收 | 去年累計營收 | 前期比較增減(%)
        | 備註 |
        """
        soup = BeautifulSoup(html, "lxml")
        # MOPS 把表格分多個（各產業），用 find_all("tr") 取所有列
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 9:
                continue
            code = tds[0].get_text(strip=True)
            if code != symbol:
                continue
            revenue = _to_decimal_or_none(tds[2].get_text(strip=True))
            if revenue is None:
                # 找到該股但 revenue 為空 → 視為當月還未公告
                return None
            mom = _to_decimal_or_none(tds[5].get_text(strip=True))
            yoy = _to_decimal_or_none(tds[6].get_text(strip=True))
            ytd = _to_decimal_or_none(tds[7].get_text(strip=True))
            ytd_yoy = _to_decimal_or_none(tds[9].get_text(strip=True)) if len(tds) > 9 else None
            return {
                "symbol": symbol,
                "year": year,
                "month": month,
                "revenue": revenue,
                "revenue_mom": mom,
                "revenue_yoy": yoy,
                "ytd_revenue": ytd,
                "ytd_yoy": ytd_yoy,
                "source": self.name,
            }
        return None

    # ── Announcement ──────────────────────────────────────

    async def fetch_announcement(
        self, symbol: str, *, since: date | None = None
    ) -> list[dict[str, Any]]:
        """重大訊息 — POST ajax_t05st02。"""
        form = {
            "step": "1",
            "co_id": symbol,
            "year": "",  # 空 = 全部
            "month": "",
        }
        async with (
            self._rate_guard(),
            get_async_client(name=self.name, base_url=self.base_url) as client,
        ):
            try:
                resp = await client.post(self.ANNOUNCEMENT_PATH, data=form)
            except httpx.RequestError as e:
                raise ExternalServiceError(
                    message_zh="MOPS 連線失敗", source=self.name, error=str(e)
                ) from e

        if resp.status_code == 429:
            raise RateLimitError(message_zh="MOPS 頻率過高", source=self.name)
        if resp.status_code >= 400:
            raise ExternalServiceError(
                message_zh=f"MOPS 重大訊息回應錯誤（{resp.status_code}）",
                source=self.name,
                status=resp.status_code,
            )
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = "utf-8"
        return self._parse_announcements(resp.text, symbol, since)

    def _parse_announcements(
        self, html: str, symbol: str, since: date | None
    ) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        out: list[dict[str, Any]] = []
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            date_str = tds[0].get_text(strip=True)
            d = _roc_or_iso_to_date(date_str)
            if d is None:
                continue
            if since is not None and d < since:
                continue
            title = tds[3].get_text(strip=True) if len(tds) > 3 else ""
            if not title:
                continue
            out.append(
                {
                    "symbol": symbol,
                    "published_at": d,
                    "title": title,
                    "source": self.name,
                    "raw_row": [td.get_text(strip=True) for td in tds],
                }
            )
        return out

    # ── helpers ───────────────────────────────────────────

    def _rate_guard(self):  # type: ignore[no-untyped-def]
        if self.limiter is not None:
            return self.limiter
        return _NullAsyncCtx()


class _NullAsyncCtx:
    async def __aenter__(self) -> _NullAsyncCtx:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def _to_decimal_or_none(v: Any) -> Decimal | None:
    if v is None:
        return None
    s = str(v).replace(",", "").replace("%", "").strip()
    if not s or s in ("--", "X", "N/A"):
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def _roc_or_iso_to_date(s: str | None) -> date | None:
    """支援 民國 YYY/MM/DD 與 西元 YYYY-MM-DD。"""
    if not s:
        return None
    s = str(s).strip()
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 3:
            try:
                y, m, d = (int(p) for p in parts)
            except ValueError:
                return None
            # 民國 < 200 通常代表 ROC year
            if y < 200:
                y += 1911
            try:
                return date(y, m, d)
            except ValueError:
                return None
    if "-" in s:
        try:
            y, m, d = (int(p) for p in s.split("-"))
            return date(y, m, d)
        except ValueError:
            return None
    return None


__all__ = ["MOPSSource"]
