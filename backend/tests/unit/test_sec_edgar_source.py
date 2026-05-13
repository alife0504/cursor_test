"""SEC EDGAR source 單元測試（mock httpx，不打網路）。"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS
from app.core.config import settings
from app.core.errors import ExternalServiceError, NotFoundError, RateLimitError
from app.data_sources.us.sec_edgar_source import (
    _CIK_CACHE,
    FILING_FORMS,
    SECEdgarSource,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def sec_source() -> SECEdgarSource:
    src = SECEdgarSource(settings)
    CIRCUIT_BREAKERS.pop("sec_edgar", None)
    src.cb = CIRCUIT_BREAKERS.setdefault("sec_edgar", type(src.cb)(name="sec_edgar"))
    src.limiter = None
    _CIK_CACHE.clear()  # 每測試重置 CIK cache
    return src


@pytest.fixture
def mock_transport(monkeypatch):  # type: ignore[no-untyped-def]
    """攔截 httpx：依 URL pattern 路由不同 response。"""
    routes: dict[str, Any] = {}

    async def fake_request(self, method, url, **kwargs):  # type: ignore[no-untyped-def]
        url_str = str(url)
        for pattern, factory in routes.items():
            if pattern in url_str:
                return factory(url_str, kwargs)
        raise RuntimeError(f"mock_transport: no route for {url_str}")

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    return routes


def _make_response(*, status: int = 200, json_data: Any = None) -> httpx.Response:
    req = httpx.Request("GET", "https://data.sec.gov/")
    return httpx.Response(status_code=status, request=req, json=json_data)


def test_user_agent_includes_admin_email(sec_source: SECEdgarSource) -> None:
    """SEC EDGAR 強制 User-Agent；應含 ADMIN_EMAIL（PLAN P6 第 7 段陷阱）。"""
    ua = sec_source._headers["User-Agent"]
    assert "TradingAgents-TW" in ua
    assert settings.ADMIN_EMAIL in ua
    assert str(settings.APP_VERSION) in ua


def test_filing_forms_covers_10k_10q_8k() -> None:
    assert "10-K" in FILING_FORMS
    assert "10-Q" in FILING_FORMS
    assert "8-K" in FILING_FORMS


@pytest.mark.asyncio
async def test_cik_lookup_zero_pads_to_10_digits(
    sec_source: SECEdgarSource, mock_transport
) -> None:
    """Apple CIK = 320193，應 zfill 成 0000320193。"""

    def tickers_factory(url: str, kwargs: dict[str, Any]) -> httpx.Response:
        return _make_response(
            json_data={
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            }
        )

    mock_transport["company_tickers.json"] = tickers_factory
    cik = await sec_source._lookup_cik("AAPL")
    assert cik == "0000320193"


@pytest.mark.asyncio
async def test_cik_lookup_unknown_symbol_raises_not_found(
    sec_source: SECEdgarSource, mock_transport
) -> None:
    mock_transport["company_tickers.json"] = lambda url, kw: _make_response(json_data={})
    with pytest.raises(NotFoundError):
        await sec_source._lookup_cik("ZZZZZ")


@pytest.mark.asyncio
async def test_cik_lookup_cache_hit_skips_http(sec_source: SECEdgarSource, mock_transport) -> None:
    calls = {"count": 0}

    def factory(url: str, kw: dict[str, Any]) -> httpx.Response:
        calls["count"] += 1
        return _make_response(
            json_data={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"}}
        )

    mock_transport["company_tickers.json"] = factory
    await sec_source._lookup_cik("AAPL")
    await sec_source._lookup_cik("AAPL")
    await sec_source._lookup_cik("AAPL")
    # 第一次 HTTP，後兩次 cache hit
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_403_without_user_agent_raises(sec_source: SECEdgarSource, mock_transport) -> None:
    """模擬「沒帶 User-Agent」被擋 403。"""
    mock_transport["company_tickers.json"] = lambda url, kw: _make_response(status=403)
    with pytest.raises(ExternalServiceError):
        await sec_source._lookup_cik("AAPL")


@pytest.mark.asyncio
async def test_429_raises_rate_limit(sec_source: SECEdgarSource, mock_transport) -> None:
    mock_transport["company_tickers.json"] = lambda url, kw: _make_response(status=429)
    with pytest.raises(RateLimitError):
        await sec_source._lookup_cik("AAPL")


@pytest.mark.asyncio
async def test_fetch_announcement_filters_form_and_since(
    sec_source: SECEdgarSource, mock_transport
) -> None:
    """submissions JSON 應只回 10-K / 10-Q / 8-K，且 since 之後的。"""

    def tickers_factory(url: str, kw: dict[str, Any]) -> httpx.Response:
        return _make_response(
            json_data={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"}}
        )

    def submissions_factory(url: str, kw: dict[str, Any]) -> httpx.Response:
        return _make_response(
            json_data={
                "cik": "320193",
                "filings": {
                    "recent": {
                        "form": ["10-K", "10-Q", "8-K", "DEF 14A", "10-Q"],
                        "accessionNumber": [
                            "0000320193-26-000001",
                            "0000320193-26-000002",
                            "0000320193-26-000003",
                            "0000320193-26-000004",
                            "0000320193-25-000005",
                        ],
                        "filingDate": [
                            "2026-04-15",
                            "2026-04-20",
                            "2026-05-01",
                            "2026-05-02",
                            "2025-08-01",  # 在 since 之前
                        ],
                        "reportDate": [
                            "2026-03-31",
                            "2026-03-31",
                            "",
                            "",
                            "2025-06-30",
                        ],
                        "primaryDocument": [
                            "aapl-20260331.htm",
                            "aapl-20260331q.htm",
                            "aapl-8k.htm",
                            "aapl-def14a.htm",
                            "aapl-old.htm",
                        ],
                        "primaryDocDescription": [
                            "10-K",
                            "10-Q",
                            "8-K",
                            "Proxy",
                            "10-Q",
                        ],
                    }
                },
            }
        )

    mock_transport["company_tickers.json"] = tickers_factory
    mock_transport["submissions/CIK"] = submissions_factory

    items = await sec_source.fetch_announcement("AAPL", since=date(2026, 1, 1))

    forms = [it["form"] for it in items]
    # DEF 14A 應被過濾
    assert "DEF 14A" not in forms
    # 2025-08-01 那筆雖是 10-Q 但 < since，應被過濾
    assert all(it["filed_at"] >= date(2026, 1, 1) for it in items)
    # 主要 form 都有
    assert {"10-K", "10-Q", "8-K"}.issubset(set(forms))
    # 每筆有 URL
    for it in items:
        if it["accession_number"]:
            assert it["url"] is not None
            assert "sec.gov/Archives/edgar/data/" in it["url"]
