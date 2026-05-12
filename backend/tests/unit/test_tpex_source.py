"""TPEX source 單元測試。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS
from app.core.config import settings
from app.core.errors import ExternalServiceError, RateLimitError
from app.data_sources.tw.tpex_source import TPEXSource, _to_decimal, _to_int

pytestmark = pytest.mark.unit


@pytest.fixture
def tpex() -> TPEXSource:
    CIRCUIT_BREAKERS.pop("tpex", None)
    src = TPEXSource(settings)
    src.limiter = None
    return src


@pytest.fixture
def mock_get(monkeypatch):  # type: ignore[no-untyped-def]
    state = {"response_factory": None, "calls": []}

    async def fake_get(self, url, **kwargs):  # type: ignore[no-untyped-def]
        state["calls"].append({"url": url, "params": kwargs.get("params")})
        f = state["response_factory"]
        if f is None:
            raise RuntimeError("No factory")
        return f(url, kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return state


def _resp(status: int, json_data: Any) -> httpx.Response:
    req = httpx.Request("GET", "https://www.tpex.org.tw/x")
    return httpx.Response(status_code=status, request=req, json=json_data)


def test_to_int_and_decimal_helpers() -> None:
    assert _to_int("1,234") == 1234
    assert _to_int("--") == 0
    assert _to_decimal("12.34") == Decimal("12.34")
    assert _to_decimal(None) is None


@pytest.mark.asyncio
async def test_fetch_ohlcv_filters_by_symbol(tpex: TPEXSource, mock_get) -> None:
    """TPEX 回多檔，要 filter 出指定 symbol。"""
    mock_get["response_factory"] = lambda url, kw: _resp(
        200,
        {
            "aaData": [
                ["6488", "環球晶", "500.0", "+5", "495", "510", "490", "8", "1000", "500"],
                ["6770", "力積電", "30.0", "-1", "31", "31.5", "29", "8", "5000", "150"],
            ]
        },
    )
    df = await tpex.fetch_ohlcv("6488", date(2026, 4, 1), date(2026, 4, 1))
    assert len(df) == 1
    assert df.iloc[0]["symbol"] == "6488"
    assert df.iloc[0]["close"] == Decimal("500.0")


@pytest.mark.asyncio
async def test_fetch_ohlcv_empty_when_no_match(tpex: TPEXSource, mock_get) -> None:
    mock_get["response_factory"] = lambda url, kw: _resp(
        200,
        {"aaData": [["6770", "力積電", "30", "-1", "31", "31", "29", "8", "100", "3"]]},
    )
    df = await tpex.fetch_ohlcv("9999", date(2026, 4, 1), date(2026, 4, 1))
    assert df.empty


@pytest.mark.asyncio
async def test_fetch_ohlcv_rate_limited(tpex: TPEXSource, mock_get) -> None:
    mock_get["response_factory"] = lambda url, kw: _resp(429, {})
    with pytest.raises(RateLimitError):
        await tpex.fetch_ohlcv("6488", date(2026, 4, 1), date(2026, 4, 1))


@pytest.mark.asyncio
async def test_fetch_ohlcv_server_error(tpex: TPEXSource, mock_get) -> None:
    mock_get["response_factory"] = lambda url, kw: _resp(500, {})
    with pytest.raises(ExternalServiceError):
        await tpex.fetch_ohlcv("6488", date(2026, 4, 1), date(2026, 4, 1))
