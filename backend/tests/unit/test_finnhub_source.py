"""Finnhub source 單元測試（mock httpx，不打網路）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx
import pydantic
import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS
from app.core.config import settings
from app.core.errors import AuthError, ForbiddenError, NotFoundError, RateLimitError
from app.data_sources.us.finnhub_source import FinnhubSource

pytestmark = pytest.mark.unit


@pytest.fixture
def fh_source(monkeypatch) -> FinnhubSource:  # type: ignore[no-untyped-def]
    current = settings.FINNHUB_API_KEY
    if current is None or not current.get_secret_value():
        monkeypatch.setattr(settings, "FINNHUB_API_KEY", pydantic.SecretStr("test-fh-key"))
    src = FinnhubSource(settings)
    CIRCUIT_BREAKERS.pop("finnhub", None)
    src.cb = CIRCUIT_BREAKERS.setdefault("finnhub", type(src.cb)(name="finnhub"))
    src.limiter = None
    return src


@pytest.fixture
def mock_transport(monkeypatch):  # type: ignore[no-untyped-def]
    state: dict[str, Any] = {"response_factory": None}

    async def fake_request(self, method, url, **kwargs):  # type: ignore[no-untyped-def]
        factory = state["response_factory"]
        if factory is None:
            raise RuntimeError("mock_transport: no response_factory set")
        return factory(method, url, kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    return state


def _make_response(*, status: int = 200, json_data: Any = None) -> httpx.Response:
    req = httpx.Request("GET", "https://finnhub.io/api/v1/company-news")
    return httpx.Response(status_code=status, request=req, json=json_data)


@pytest.mark.asyncio
async def test_fetch_news_normalizes_finnhub_schema(
    fh_source: FinnhubSource, mock_transport
) -> None:
    """Finnhub /company-news 一筆 → 統一 schema。"""
    epoch = int(datetime(2026, 5, 1, 8, 0).timestamp())
    payload = [
        {
            "category": "company",
            "datetime": epoch,
            "headline": "Apple announces new iPhone",
            "id": 1,
            "image": "https://img.example/1.jpg",
            "related": "AAPL",
            "source": "Reuters",
            "summary": "Lorem ipsum",
            "url": "https://example.com/news/1",
        }
    ]
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(
        status=200, json_data=payload
    )
    items = await fh_source.fetch_news("AAPL", since=date(2026, 4, 1))
    assert len(items) == 1
    assert items[0]["title"] == "Apple announces new iPhone"
    assert items[0]["url"] == "https://example.com/news/1"
    assert items[0]["symbol"] == "AAPL"
    assert items[0]["source"] == "finnhub"


@pytest.mark.asyncio
async def test_fetch_news_no_symbol_returns_empty(fh_source: FinnhubSource) -> None:
    """symbol=None → 空 list（不打 API）。"""
    result = await fh_source.fetch_news(None)
    assert result == []


@pytest.mark.asyncio
async def test_403_raises_forbidden(fh_source: FinnhubSource, mock_transport) -> None:
    """免費 plan 不可用 endpoint → 403 → ForbiddenError。"""
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(status=403)
    with pytest.raises(ForbiddenError):
        await fh_source.fetch_news("AAPL")


@pytest.mark.asyncio
async def test_401_raises_auth_error(fh_source: FinnhubSource, mock_transport) -> None:
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(status=401)
    with pytest.raises(AuthError):
        await fh_source.fetch_news("AAPL")


@pytest.mark.asyncio
async def test_429_raises_rate_limit(fh_source: FinnhubSource, mock_transport) -> None:
    """免費版 60/min；429 → RateLimitError。"""
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(status=429)
    with pytest.raises(RateLimitError):
        await fh_source.fetch_news("AAPL")


@pytest.mark.asyncio
async def test_fetch_company_info_normalizes_profile(
    fh_source: FinnhubSource, mock_transport
) -> None:
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(
        status=200,
        json_data={
            "ticker": "AAPL",
            "name": "Apple Inc",
            "finnhubIndustry": "Technology",
            "country": "US",
            "exchange": "NASDAQ",
            "currency": "USD",
            "marketCapitalization": 3000000,
            "shareOutstanding": 16000,
            "weburl": "https://www.apple.com",
        },
    )
    info = await fh_source.fetch_company_info("AAPL")
    assert info["symbol"] == "AAPL"
    assert info["name"] == "Apple Inc"
    assert info["industry"] == "Technology"
    assert info["website"] == "https://www.apple.com"


@pytest.mark.asyncio
async def test_empty_company_info_raises_not_found(
    fh_source: FinnhubSource, mock_transport
) -> None:
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(status=200, json_data={})
    with pytest.raises(NotFoundError):
        await fh_source.fetch_company_info("ZZZZ")
