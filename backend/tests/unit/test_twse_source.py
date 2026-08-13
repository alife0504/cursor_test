"""TWSE source 單元測試。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS
from app.core.config import settings
from app.core.errors import ExternalServiceError, RateLimitError
from app.data_sources.tw.twse_openapi_source import (
    TWSEOpenAPISource,
    _roc_to_date,
    _to_decimal,
    _to_int,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def twse() -> TWSEOpenAPISource:
    CIRCUIT_BREAKERS.pop("twse_openapi", None)
    src = TWSEOpenAPISource(settings)
    src.limiter = None  # 測試不限速
    return src


@pytest.fixture
def mock_get(monkeypatch):  # type: ignore[no-untyped-def]
    state = {"response_factory": None, "calls": []}

    async def fake_get(self, url, **kwargs):  # type: ignore[no-untyped-def]
        state["calls"].append({"url": url, "params": kwargs.get("params")})
        factory = state["response_factory"]
        if factory is None:
            raise RuntimeError("No response factory")
        return factory(url, kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return state


def _make_response(status: int, json_data: Any) -> httpx.Response:
    req = httpx.Request("GET", "https://www.twse.com.tw/x")
    return httpx.Response(status_code=status, request=req, json=json_data)


def test_roc_to_date_converts() -> None:
    assert _roc_to_date("114/05/12") == date(2025, 5, 12)
    assert _roc_to_date("113/01/01") == date(2024, 1, 1)
    assert _roc_to_date("") is None
    assert _roc_to_date(None) is None
    assert _roc_to_date("not/a/date") is None


def test_to_int_handles_commas() -> None:
    assert _to_int("12,345") == 12345
    assert _to_int(None) == 0
    assert _to_int("--") == 0
    assert _to_int("X") == 0
    assert _to_int("1.5") == 1


def test_to_decimal_handles_commas() -> None:
    assert _to_decimal("12,345.67") == Decimal("12345.67")
    assert _to_decimal(None) is None
    assert _to_decimal("--") is None


@pytest.mark.asyncio
async def test_fetch_ohlcv_single_month(twse: TWSEOpenAPISource, mock_get) -> None:
    """STOCK_DAY 單月查詢 → 解析 fields/data 結構。"""
    mock_get["response_factory"] = lambda url, kw: _make_response(
        200,
        {
            "stat": "OK",
            "fields": [
                "日期",
                "成交股數",
                "成交金額",
                "開盤價",
                "最高價",
                "最低價",
                "收盤價",
                "漲跌價差",
                "成交筆數",
            ],
            "data": [
                ["114/04/01", "1,000", "900,000", "900", "905", "898", "903", "+3", "200"],
                ["114/04/02", "2,000", "1,800,000", "904", "910", "902", "908", "+5", "300"],
            ],
        },
    )
    df = await twse.fetch_ohlcv("2330", date(2025, 4, 1), date(2025, 4, 5))
    assert len(df) == 2
    assert df.iloc[0]["date"] == date(2025, 4, 1)
    assert df.iloc[0]["open"] == Decimal("900")
    assert df.iloc[0]["volume"] == 1000


@pytest.mark.asyncio
async def test_fetch_ohlcv_empty_when_no_data(twse: TWSEOpenAPISource, mock_get) -> None:
    mock_get["response_factory"] = lambda url, kw: _make_response(
        200,
        {"stat": "很抱歉，沒有符合條件的資料!", "fields": [], "data": []},
    )
    df = await twse.fetch_ohlcv("9999", date(2025, 4, 1), date(2025, 4, 30))
    assert df.empty


@pytest.mark.asyncio
async def test_fetch_ohlcv_rate_limited_raises(twse: TWSEOpenAPISource, mock_get) -> None:
    mock_get["response_factory"] = lambda url, kw: _make_response(429, {})
    with pytest.raises(RateLimitError):
        await twse.fetch_ohlcv("2330", date(2025, 4, 1), date(2025, 4, 5))


@pytest.mark.asyncio
async def test_fetch_ohlcv_server_error(twse: TWSEOpenAPISource, mock_get) -> None:
    mock_get["response_factory"] = lambda url, kw: _make_response(500, {})
    with pytest.raises(ExternalServiceError):
        await twse.fetch_ohlcv("2330", date(2025, 4, 1), date(2025, 4, 5))
