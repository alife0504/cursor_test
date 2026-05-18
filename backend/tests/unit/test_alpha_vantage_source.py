"""Alpha Vantage source 單元測試（mock httpx，不打網路）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pydantic
import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS
from app.core.config import settings
from app.core.errors import (
    AuthError,
    ExternalServiceError,
    NotFoundError,
    QuotaExceededError,
)
from app.data_sources.us.alpha_vantage_source import AlphaVantageSource

pytestmark = pytest.mark.unit


@pytest.fixture
def av_source(monkeypatch) -> AlphaVantageSource:  # type: ignore[no-untyped-def]
    """為了不要因 .env 未填 API key 就跳過，動態注入一個。"""
    current = settings.ALPHA_VANTAGE_API_KEY
    if current is None or not current.get_secret_value():
        monkeypatch.setattr(
            settings,
            "ALPHA_VANTAGE_API_KEY",
            pydantic.SecretStr("test-key"),
        )
    src = AlphaVantageSource(settings)
    CIRCUIT_BREAKERS.pop("alpha_vantage", None)
    src.cb = CIRCUIT_BREAKERS.setdefault("alpha_vantage", type(src.cb)(name="alpha_vantage"))
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
    req = httpx.Request("GET", "https://www.alphavantage.co/query")
    return httpx.Response(status_code=status, request=req, json=json_data)


@pytest.mark.asyncio
async def test_url_constructed_correctly(av_source: AlphaVantageSource, mock_transport) -> None:
    captured: dict[str, Any] = {}

    def factory(method, url, kwargs):  # type: ignore[no-untyped-def]
        captured["method"] = method
        captured["url"] = url
        captured["params"] = kwargs.get("params", {})
        return _make_response(
            status=200,
            json_data={
                "Time Series (Daily)": {
                    "2026-04-01": {
                        "1. open": "180.00",
                        "2. high": "182.00",
                        "3. low": "179.00",
                        "4. close": "181.00",
                        "5. volume": "50000000",
                    }
                }
            },
        )

    mock_transport["response_factory"] = factory
    df = await av_source.fetch_ohlcv("AAPL", date(2026, 4, 1), date(2026, 4, 5))
    assert captured["params"]["function"] == "TIME_SERIES_DAILY"
    assert captured["params"]["symbol"] == "AAPL"
    assert captured["params"]["apikey"] == "test-key"
    assert not df.empty
    assert df.iloc[0]["close"] == Decimal("181.00")


@pytest.mark.asyncio
async def test_rate_limit_note_raises_quota_exceeded(
    av_source: AlphaVantageSource, mock_transport
) -> None:
    """AV 配額用盡 → 回 200 + Note 欄位 → 應 raise QuotaExceededError。"""
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(
        status=200,
        json_data={"Note": "Thank you for using Alpha Vantage! ... 25 requests/day"},
    )
    with pytest.raises(QuotaExceededError):
        await av_source.fetch_ohlcv("AAPL", date(2026, 4, 1), date(2026, 4, 5))


@pytest.mark.asyncio
async def test_information_field_also_raises_quota(
    av_source: AlphaVantageSource, mock_transport
) -> None:
    """Information 欄位（升級會員提示）視為配額耗盡。"""
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(
        status=200,
        json_data={"Information": "Please subscribe to premium"},
    )
    with pytest.raises(QuotaExceededError):
        await av_source.fetch_ohlcv("AAPL", date(2026, 4, 1), date(2026, 4, 5))


@pytest.mark.asyncio
async def test_error_message_raises_not_found(
    av_source: AlphaVantageSource, mock_transport
) -> None:
    """錯誤 symbol → Error Message → NotFoundError。"""
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(
        status=200,
        json_data={"Error Message": "Invalid API call. Please check input."},
    )
    with pytest.raises(NotFoundError):
        await av_source.fetch_ohlcv("ZZZZ", date(2026, 4, 1), date(2026, 4, 5))


@pytest.mark.asyncio
async def test_outputsize_full_when_range_over_100_days(
    av_source: AlphaVantageSource, mock_transport
) -> None:
    captured: dict[str, Any] = {}

    def factory(method, url, kwargs):  # type: ignore[no-untyped-def]
        captured["params"] = kwargs.get("params", {})
        return _make_response(
            status=200,
            json_data={
                "Time Series (Daily)": {
                    "2026-04-01": {
                        "1. open": "180",
                        "2. high": "182",
                        "3. low": "179",
                        "4. close": "181",
                        "5. volume": "1",
                    }
                }
            },
        )

    mock_transport["response_factory"] = factory
    await av_source.fetch_ohlcv("AAPL", date(2025, 1, 1), date(2026, 4, 1))
    assert captured["params"]["outputsize"] == "full"


@pytest.mark.asyncio
async def test_compact_outputsize_when_short_range(
    av_source: AlphaVantageSource, mock_transport
) -> None:
    captured: dict[str, Any] = {}

    def factory(method, url, kwargs):  # type: ignore[no-untyped-def]
        captured["params"] = kwargs.get("params", {})
        return _make_response(
            status=200,
            json_data={
                "Time Series (Daily)": {
                    "2026-04-01": {
                        "1. open": "180",
                        "2. high": "182",
                        "3. low": "179",
                        "4. close": "181",
                        "5. volume": "1",
                    }
                }
            },
        )

    mock_transport["response_factory"] = factory
    await av_source.fetch_ohlcv("AAPL", date(2026, 4, 1), date(2026, 4, 5))
    assert captured["params"]["outputsize"] == "compact"


@pytest.mark.asyncio
async def test_decimal_precision_preserved(av_source: AlphaVantageSource, mock_transport) -> None:
    """價格用 Decimal 保留小數精度（不能變 float）。"""
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(
        status=200,
        json_data={
            "Time Series (Daily)": {
                "2026-04-01": {
                    "1. open": "180.1234",
                    "2. high": "182.5678",
                    "3. low": "179.0001",
                    "4. close": "181.9999",
                    "5. volume": "50000000",
                }
            }
        },
    )
    df = await av_source.fetch_ohlcv("AAPL", date(2026, 4, 1), date(2026, 4, 5))
    assert df.iloc[0]["open"] == Decimal("180.1234")
    assert df.iloc[0]["close"] == Decimal("181.9999")


@pytest.mark.asyncio
async def test_missing_api_key_raises_auth(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """ALPHA_VANTAGE_API_KEY=None / 空字串 → AuthError。"""
    monkeypatch.setattr(settings, "ALPHA_VANTAGE_API_KEY", None)
    src = AlphaVantageSource(settings)
    src.limiter = None
    with pytest.raises(AuthError):
        await src.fetch_ohlcv("AAPL", date(2026, 4, 1), date(2026, 4, 5))


@pytest.mark.asyncio
async def test_5xx_raises_external_service(av_source: AlphaVantageSource, mock_transport) -> None:
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(status=503)
    with pytest.raises(ExternalServiceError):
        await av_source.fetch_ohlcv("AAPL", date(2026, 4, 1), date(2026, 4, 5))
