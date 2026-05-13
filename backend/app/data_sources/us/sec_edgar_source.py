"""SEC EDGAR — 美股公告 / 財報 主源（10-K / 10-Q / 8-K）。

API 文件：https://www.sec.gov/edgar/sec-api-documentation
- 端點 1：https://www.sec.gov/files/company_tickers.json — symbol → CIK 對照表
- 端點 2：https://data.sec.gov/submissions/CIK{10 位}.json — 最近 filings

注意（PLAN P6 第 7 段「已知陷阱」）：
- SEC EDGAR 強制要 User-Agent，否則 403 → __init__ 設好 client default header
- CIK 是 10 位數含前導零 → str(cik).zfill(10)
- 官方 rate limit 10/sec，保守 5/sec
- /submissions/CIK*.json 給 recent filings（最近 1000 筆），caller 自篩 form 類型
- symbol → CIK 對照表用 24h cache（避免每次都打 company_tickers.json）

P6 範圍：實作 fetch_announcement（10-K / 10-Q / 8-K filings），
fetch_financial 留 NotImplementedError（XBRL 解析複雜，留給 P11+ 的 financial 分析師）。
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from typing import Any

import httpx

from app.core.errors import ExternalServiceError, NotFoundError, RateLimitError
from app.core.http_client import get_async_client
from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion, register_data_source

logger = get_logger(__name__)


# 主要關注的 filing 表單類型（v1.0 範圍）
FILING_FORMS: frozenset[str] = frozenset({"10-K", "10-Q", "8-K", "20-F", "6-K"})


# CIK lookup 24h cache（簡易記憶體 cache；正式 cache 待 cache.py）
_CIK_CACHE: dict[str, tuple[str, float]] = {}
_CIK_CACHE_TTL_SECONDS = 24 * 3600


@register_data_source
class SECEdgarSource(BaseDataSource):
    """SEC EDGAR — 美股 filings 主源。"""

    name = "sec_edgar"
    priority = 10  # filings 主源
    supported_regions = (MarketRegion.US,)
    supported_kinds = (DataKind.ANNOUNCEMENT,)
    rate_limit_per_sec = 5.0  # 官方 10/sec，保守 5
    base_url = "https://data.sec.gov"
    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SUBMISSIONS_PATH = "/submissions/CIK{cik}.json"

    def __init__(self, settings: Any) -> None:
        super().__init__(settings)
        # SEC EDGAR 強制要 User-Agent，內含聯絡 email
        self._user_agent = f"TradingAgents-TW/{settings.APP_VERSION} ({settings.ADMIN_EMAIL})"
        self._headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }

    # ── 抽象 fetch_* 實作 ────────────────────────────────

    async def fetch_announcement(
        self, symbol: str, *, since: date | None = None
    ) -> list[dict[str, Any]]:
        """抓 10-K / 10-Q / 8-K filings。"""
        cik = await self._lookup_cik(symbol)
        submissions = await self._fetch_submissions(cik)
        return self._parse_filings(submissions, symbol, since=since)

    # ── CIK lookup ───────────────────────────────────────

    async def _lookup_cik(self, symbol: str) -> str:
        """symbol → CIK（10 位字串含前導零）。24h cache。"""
        sym_upper = symbol.upper()
        cached = _CIK_CACHE.get(sym_upper)
        now = time.monotonic()
        if cached is not None and (now - cached[1]) < _CIK_CACHE_TTL_SECONDS:
            return cached[0]

        async with (
            self._rate_guard(),
            get_async_client(
                name=self.name,
                base_url="",  # 直接打絕對 URL
                headers=self._headers,
            ) as client,
        ):
            try:
                resp = await client.get(self.TICKERS_URL)
            except httpx.RequestError as e:
                raise ExternalServiceError(
                    message_zh="SEC EDGAR ticker 表連線失敗",
                    source=self.name,
                    error=str(e),
                ) from e
        self._raise_on_http_error(resp)

        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise ExternalServiceError(
                message_zh="SEC EDGAR ticker 表非 JSON",
                source=self.name,
            ) from e

        # 結構：{"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
        if not isinstance(data, dict):
            raise ExternalServiceError(
                message_zh="SEC EDGAR ticker 表格式異常",
                source=self.name,
            )
        cik: str | None = None
        for _, row in data.items():
            if not isinstance(row, dict):
                continue
            if str(row.get("ticker", "")).upper() == sym_upper:
                raw_cik = row.get("cik_str")
                if raw_cik is None:
                    continue
                cik = str(int(raw_cik)).zfill(10)
                break

        if cik is None:
            raise NotFoundError(
                message_zh=f"SEC EDGAR 找不到 {symbol} 對應的 CIK",
                source=self.name,
                symbol=symbol,
            )

        _CIK_CACHE[sym_upper] = (cik, now)
        return cik

    async def _fetch_submissions(self, cik: str) -> dict[str, Any]:
        """取得該 CIK 的 submissions JSON。"""
        path = self.SUBMISSIONS_PATH.format(cik=cik)
        async with (
            self._rate_guard(),
            get_async_client(
                name=self.name,
                base_url=self.base_url,
                headers=self._headers,
            ) as client,
        ):
            try:
                resp = await client.get(path)
            except httpx.RequestError as e:
                raise ExternalServiceError(
                    message_zh="SEC EDGAR submissions 連線失敗",
                    source=self.name,
                    error=str(e),
                ) from e
        self._raise_on_http_error(resp)

        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise ExternalServiceError(
                message_zh="SEC EDGAR submissions 非 JSON",
                source=self.name,
            ) from e

    # ── parsing ──────────────────────────────────────────

    def _parse_filings(
        self,
        submissions: dict[str, Any],
        symbol: str,
        *,
        since: date | None,
    ) -> list[dict[str, Any]]:
        """從 submissions JSON 取出 recent filings，篩 10-K / 10-Q / 8-K。"""
        filings = (submissions or {}).get("filings", {}) or {}
        recent = filings.get("recent") or {}
        forms = recent.get("form") or []
        accession_numbers = recent.get("accessionNumber") or []
        filing_dates = recent.get("filingDate") or []
        primary_documents = recent.get("primaryDocument") or []
        primary_doc_descriptions = recent.get("primaryDocDescription") or []
        report_dates = recent.get("reportDate") or []

        out: list[dict[str, Any]] = []
        for i, form in enumerate(forms):
            if form not in FILING_FORMS:
                continue
            filing_date_str = filing_dates[i] if i < len(filing_dates) else None
            try:
                filing_date_obj = date.fromisoformat(filing_date_str) if filing_date_str else None
            except (ValueError, TypeError):
                filing_date_obj = None
            if filing_date_obj is None:
                continue
            if since is not None and filing_date_obj < since:
                continue
            accession = accession_numbers[i] if i < len(accession_numbers) else None
            primary_doc = primary_documents[i] if i < len(primary_documents) else None
            description = primary_doc_descriptions[i] if i < len(primary_doc_descriptions) else None
            report_date_str = report_dates[i] if i < len(report_dates) else None
            try:
                report_date_obj = date.fromisoformat(report_date_str) if report_date_str else None
            except (ValueError, TypeError):
                report_date_obj = None

            title = f"{form} — {description}" if description else form

            cik_raw = submissions.get("cik")
            cik_int: int | None = None
            if cik_raw is not None:
                try:
                    cik_int = int(cik_raw)
                except (TypeError, ValueError):
                    cik_int = None
            url = self._build_filing_url(accession, primary_doc, cik_int)

            out.append(
                {
                    "symbol": symbol.upper(),
                    "form": form,
                    "title": title,
                    "filed_at": filing_date_obj,
                    "report_date": report_date_obj,
                    "accession_number": accession,
                    "url": url,
                    "published_at": datetime.combine(filing_date_obj, datetime.min.time()),
                    "source": self.name,
                }
            )
        return out

    @staticmethod
    def _build_filing_url(
        accession: str | None,
        primary_doc: str | None,
        cik: int | None,
    ) -> str | None:
        """組 SEC EDGAR 直接連結。"""
        if not accession or cik is None:
            return None
        clean_accession = re.sub(r"[^0-9]", "", accession)
        if not clean_accession:
            return None
        if primary_doc:
            return (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/" f"{clean_accession}/{primary_doc}"
            )
        return (
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik:010d}"
            f"&type=&dateb=&owner=include&count=40"
        )

    # ── helpers ───────────────────────────────────────────

    def _raise_on_http_error(self, resp: httpx.Response) -> None:
        if resp.status_code == 403:
            raise ExternalServiceError(
                message_zh="SEC EDGAR 403（User-Agent 缺漏或被擋）",
                source=self.name,
                status=403,
            )
        if resp.status_code == 429:
            raise RateLimitError(
                message_zh="SEC EDGAR 頻率過高",
                source=self.name,
            )
        if resp.status_code == 404:
            raise NotFoundError(
                message_zh="SEC EDGAR 找不到資料",
                source=self.name,
                status=404,
            )
        if resp.status_code >= 400:
            raise ExternalServiceError(
                message_zh=f"SEC EDGAR 回應錯誤（{resp.status_code}）",
                source=self.name,
                status=resp.status_code,
            )

    def _rate_guard(self):  # type: ignore[no-untyped-def]
        if self.limiter is not None:
            return self.limiter
        return _NullAsyncCtx()


class _NullAsyncCtx:
    async def __aenter__(self) -> _NullAsyncCtx:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


__all__ = ["FILING_FORMS", "SECEdgarSource"]
