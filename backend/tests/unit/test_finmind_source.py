"""FinMind source 單元測試（mock httpx，不打網路）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS, CircuitState
from app.core.config import settings
from app.core.errors import AuthError, ExternalServiceError, RateLimitError
from app.data_sources.tw.finmind_source import FinMindSource

pytestmark = pytest.mark.unit


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def fm_source() -> FinMindSource:
    """每個測試一個獨立 FinMindSource；重置 CB；停用 limiter 加速測試。"""
    src = FinMindSource(settings)
    CIRCUIT_BREAKERS.pop("finmind", None)
    src.cb = CIRCUIT_BREAKERS.setdefault("finmind", type(src.cb)(name="finmind"))
    src.limiter = None  # 測試不限速
    return src


@pytest.fixture
def mock_transport(monkeypatch):  # type: ignore[no-untyped-def]
    """攔截 httpx.AsyncClient.request：之後 helper 動態設定 response。"""
    state = {"response_factory": None}

    async def fake_request(self, method, url, **kwargs):  # type: ignore[no-untyped-def]
        factory = state["response_factory"]
        if factory is None:
            raise RuntimeError("mock_transport: no response_factory set")
        return factory(method, url, kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    return state


def _make_response(*, status: int = 200, json_data: Any = None) -> httpx.Response:
    req = httpx.Request("GET", "https://api.finmindtrade.com/api/v4/data")
    return httpx.Response(status_code=status, request=req, json=json_data)


# ── Tests ────────────────────────────────────────────────


def test_normalize_ohlcv_columns() -> None:
    """_normalize_ohlcv 應產生統一欄位 + Decimal OHLC + int volume。"""
    raw = [
        {
            "date": "2026-04-01",
            "stock_id": "2330",
            "Trading_Volume": 12345678,
            "Trading_money": 8500000000,
            "open": "900",
            "max": "905",
            "min": "898",
            "close": "903",
        }
    ]
    df = FinMindSource._normalize_ohlcv(raw)
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume", "turnover"]
    assert df.iloc[0]["date"] == date(2026, 4, 1)
    assert df.iloc[0]["open"] == Decimal("900")
    assert df.iloc[0]["high"] == Decimal("905")
    assert df.iloc[0]["close"] == Decimal("903")
    assert df.iloc[0]["volume"] == 12345678
    assert df.iloc[0]["turnover"] == Decimal("8500000000")


def test_normalize_ohlcv_empty_returns_empty_df() -> None:
    df = FinMindSource._normalize_ohlcv([])
    assert df.empty
    assert "date" in df.columns


@pytest.mark.asyncio
async def test_fetch_ohlcv_calls_correct_endpoint(fm_source: FinMindSource, mock_transport) -> None:
    captured: dict[str, Any] = {}

    def factory(method, url, kwargs):  # type: ignore[no-untyped-def]
        captured["method"] = method
        captured["params"] = kwargs.get("params", {})
        return _make_response(
            status=200,
            json_data={
                "status": 200,
                "msg": "success",
                "data": [
                    {
                        "date": "2026-04-01",
                        "stock_id": "2330",
                        "Trading_Volume": 100,
                        "Trading_money": 90000,
                        "open": 900,
                        "max": 910,
                        "min": 895,
                        "close": 905,
                    }
                ],
            },
        )

    mock_transport["response_factory"] = factory
    df = await fm_source.fetch_ohlcv("2330", date(2026, 4, 1), date(2026, 4, 5))
    assert captured["method"] == "GET"
    assert captured["params"]["dataset"] == "TaiwanStockPrice"
    assert captured["params"]["data_id"] == "2330"
    assert captured["params"]["start_date"] == "2026-04-01"
    assert captured["params"]["end_date"] == "2026-04-05"
    assert not df.empty
    assert df.iloc[0]["close"] == Decimal("905")


@pytest.mark.asyncio
async def test_fetch_ohlcv_handles_empty_response(fm_source: FinMindSource, mock_transport) -> None:
    """data=[] 時應回空 DataFrame（不拋例外）。"""
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(
        status=200,
        json_data={"status": 200, "msg": "no data", "data": []},
    )
    df = await fm_source.fetch_ohlcv("9999", date(2026, 4, 1), date(2026, 4, 5))
    assert df.empty


@pytest.mark.asyncio
async def test_invalid_token_raises_auth_error(fm_source: FinMindSource, mock_transport) -> None:
    """FinMind 回 401 → AuthError。"""
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(
        status=401,
        json_data={"status": 401, "msg": "Invalid token"},
    )
    with pytest.raises(AuthError):
        await fm_source.fetch_ohlcv("2330", date(2026, 4, 1), date(2026, 4, 5))


@pytest.mark.asyncio
async def test_quota_exceeded_raises_rate_limit(fm_source: FinMindSource, mock_transport) -> None:
    """FinMind 業務 402 → RateLimitError（用 status 422 + msg 包含 'limit' 也算）。"""
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(
        status=200,
        json_data={"status": 402, "msg": "request limit reached"},
    )
    with pytest.raises(RateLimitError):
        await fm_source.fetch_ohlcv("2330", date(2026, 4, 1), date(2026, 4, 5))


@pytest.mark.asyncio
async def test_business_error_raises_external_service(
    fm_source: FinMindSource, mock_transport
) -> None:
    """FinMind status=500 in body → ExternalServiceError。"""
    mock_transport["response_factory"] = lambda *a, **kw: _make_response(
        status=200,
        json_data={"status": 500, "msg": "internal"},
    )
    with pytest.raises(ExternalServiceError):
        await fm_source.fetch_ohlcv("2330", date(2026, 4, 1), date(2026, 4, 5))


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures(
    fm_source: FinMindSource, mock_transport
) -> None:
    """連續 N 次（settings.CB_FAILURE_THRESHOLD）失敗 → CB OPEN。

    Note: 因 fetch_ohlcv 內部不會自己 record_failure（那是 fallback 的職責），
    這裡直接驗 CB 介面跟 record_failure 的累計行為，外掛 fallback 整合測在 fallback 測試。
    """
    threshold = settings.CB_FAILURE_THRESHOLD
    for _ in range(threshold):
        await fm_source.cb.record_failure()
    assert fm_source.cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_normalize_institutional_pivots_groups() -> None:
    raw = [
        {"date": "2026-04-01", "name": "Foreign_Investor", "buy": 1000, "sell": 200},
        {"date": "2026-04-01", "name": "Investment_Trust", "buy": 50, "sell": 30},
        {"date": "2026-04-01", "name": "Dealer_Hedging", "buy": 20, "sell": 10},
        {"date": "2026-04-01", "name": "Dealer_self", "buy": 5, "sell": 1},
    ]
    df = FinMindSource._normalize_institutional(raw)
    row = df.iloc[0]
    assert row["foreign_net"] == 800
    assert row["trust_net"] == 20
    # dealer_hedging + dealer_self 都歸 "dealer"
    assert row["dealer_buy"] == 25
    assert row["dealer_sell"] == 11
    assert row["dealer_net"] == 14


def test_normalize_monthly_revenue() -> None:
    raw = {
        "date": "2026-04-10",
        "stock_id": "2330",
        "country": "Taiwan",
        "revenue": "300000000",
        "revenue_month": 3,
        "revenue_year": 2026,
    }
    out = FinMindSource._normalize_monthly_revenue(raw)
    assert out["symbol"] == "2330"
    assert out["year"] == 2026
    assert out["month"] == 3
    assert out["revenue"] == Decimal("300000000")
