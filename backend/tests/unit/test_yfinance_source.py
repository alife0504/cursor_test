"""yfinance source 單元測試（mock yfinance，不打網路）。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS, CircuitState
from app.core.config import settings
from app.core.errors import ExternalServiceError, NotFoundError
from app.data_sources.us.yfinance_source import YFinanceSource

pytestmark = pytest.mark.unit


@pytest.fixture
def yf_source() -> YFinanceSource:
    src = YFinanceSource(settings)
    CIRCUIT_BREAKERS.pop("yfinance", None)
    src.cb = CIRCUIT_BREAKERS.setdefault("yfinance", type(src.cb)(name="yfinance"))
    src.limiter = None
    return src


def _sample_ohlcv_df() -> pd.DataFrame:
    """模擬 yfinance.download 回的 DataFrame（單 symbol，DatetimeIndex）。"""
    df = pd.DataFrame(
        {
            "Open": [180.0, 181.5],
            "High": [182.0, 183.0],
            "Low": [179.5, 180.0],
            "Close": [181.0, 182.5],
            "Adj Close": [181.0, 182.5],
            "Volume": [50_000_000, 48_000_000],
        },
        index=pd.to_datetime(["2026-04-01", "2026-04-02"]),
    )
    df.index.name = "Date"
    return df


def test_normalize_ohlcv_columns() -> None:
    """_normalize_ohlcv 應產生統一欄位 + Decimal OHLC + int volume + 估算 turnover。"""
    df = YFinanceSource._normalize_ohlcv(_sample_ohlcv_df(), "AAPL")
    # adjusted_close 納入（US 已提供還原價；對齊 ohlcv_repo 期待的 key）
    assert list(df.columns) == [
        "date",
        "open",
        "high",
        "low",
        "close",
        "adjusted_close",
        "volume",
        "turnover",
    ]
    assert df.iloc[0]["date"] == date(2026, 4, 1)
    assert df.iloc[0]["open"] == Decimal("180.0")
    assert df.iloc[0]["close"] == Decimal("181.0")
    assert df.iloc[0]["adjusted_close"] == Decimal("181.0")
    assert df.iloc[0]["volume"] == 50_000_000
    # turnover = close * volume
    assert df.iloc[0]["turnover"] == Decimal("181.0") * 50_000_000


def test_normalize_symbol_brk_dot_to_hyphen() -> None:
    """BRK.B → BRK-B（yfinance 規格）+ 統一大寫。"""
    assert YFinanceSource._normalize_symbol("brk.b") == "BRK-B"
    assert YFinanceSource._normalize_symbol("AAPL") == "AAPL"
    with pytest.raises(ExternalServiceError):
        YFinanceSource._normalize_symbol(" ")


def test_normalize_ohlcv_empty_returns_empty_df() -> None:
    df = YFinanceSource._normalize_ohlcv(pd.DataFrame(), "AAPL")
    assert df.empty
    assert "date" in df.columns


@pytest.mark.asyncio
async def test_fetch_ohlcv_empty_dataframe_raises_not_found(
    yf_source: YFinanceSource, monkeypatch
) -> None:
    """yfinance 回空 DataFrame → NotFoundError。"""
    monkeypatch.setattr(
        YFinanceSource, "_yf_download", staticmethod(lambda *a, **kw: pd.DataFrame())
    )
    with pytest.raises(NotFoundError):
        await yf_source.fetch_ohlcv("ZZZZ", date(2026, 4, 1), date(2026, 4, 5))


@pytest.mark.asyncio
async def test_fetch_ohlcv_async_wrap_executor(yf_source: YFinanceSource, monkeypatch) -> None:
    """同步 yfinance 呼叫應透過 run_in_executor，不能 block event loop。"""
    captured: dict[str, Any] = {}

    def fake_download(symbol: str, start: str, end: str) -> pd.DataFrame:
        captured["symbol"] = symbol
        captured["start"] = start
        captured["end"] = end
        return _sample_ohlcv_df()

    monkeypatch.setattr(YFinanceSource, "_yf_download", staticmethod(fake_download))
    df = await yf_source.fetch_ohlcv("AAPL", date(2026, 4, 1), date(2026, 4, 2))
    assert captured["symbol"] == "AAPL"
    # end 是 exclusive +1 day
    assert captured["end"] == "2026-04-03"
    assert not df.empty
    assert df.iloc[0]["date"] == date(2026, 4, 1)


@pytest.mark.asyncio
async def test_fetch_ohlcv_internal_error_wrapped_as_external_service(
    yf_source: YFinanceSource, monkeypatch
) -> None:
    """yfinance 內部例外應包成 ExternalServiceError（不直接拋 KeyError 給 caller）。"""

    def raise_internal(*a: Any, **kw: Any) -> pd.DataFrame:
        raise KeyError("yfinance internal pretend failure")

    monkeypatch.setattr(YFinanceSource, "_yf_download", staticmethod(raise_internal))
    with pytest.raises(ExternalServiceError):
        await yf_source.fetch_ohlcv("AAPL", date(2026, 4, 1), date(2026, 4, 5))


@pytest.mark.asyncio
async def test_news_filter_by_symbol_and_since(yf_source: YFinanceSource, monkeypatch) -> None:
    """fetch_news 過濾 since 並標 symbol。"""
    now = datetime.utcnow()
    items = [
        {
            "content": {
                "title": "Apple beats Q1",
                "canonicalUrl": {"url": "https://example.com/1"},
                "pubDate": now.isoformat(),
                "summary": "S1",
            }
        },
        {
            "content": {
                "title": "Old news",
                "canonicalUrl": {"url": "https://example.com/2"},
                "pubDate": "2020-01-01T00:00:00",
                "summary": "old",
            }
        },
    ]
    monkeypatch.setattr(YFinanceSource, "_yf_news", staticmethod(lambda s: items))
    result = await yf_source.fetch_news("AAPL", since=date(2025, 1, 1))
    assert len(result) == 1
    assert result[0]["title"] == "Apple beats Q1"
    assert result[0]["symbol"] == "AAPL"
    assert result[0]["url"] == "https://example.com/1"


@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_repeated_failures(yf_source: YFinanceSource) -> None:
    """連續 threshold 次失敗 → CB OPEN。"""
    threshold = settings.CB_FAILURE_THRESHOLD
    for _ in range(threshold):
        await yf_source.cb.record_failure()
    assert yf_source.cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_fetch_company_info_returns_normalized_dict(
    yf_source: YFinanceSource, monkeypatch
) -> None:
    info = {
        "longName": "Apple Inc.",
        "industry": "Consumer Electronics",
        "sector": "Technology",
        "country": "US",
        "website": "https://www.apple.com",
        "fullTimeEmployees": 161000,
        "marketCap": 3_000_000_000_000,
        "currency": "USD",
    }
    monkeypatch.setattr(YFinanceSource, "_yf_info", staticmethod(lambda s: info))
    result = await yf_source.fetch_company_info("AAPL")
    assert result["symbol"] == "AAPL"
    assert result["name"] == "Apple Inc."
    assert result["industry"] == "Consumer Electronics"
    assert result["employees"] == 161000
