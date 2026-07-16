"""MOPS source 單元測試（含 BeautifulSoup parsing）。"""

from __future__ import annotations

from datetime import date
from datetime import datetime as _dt
from decimal import Decimal

import httpx
import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS
from app.core.config import settings
from app.core.errors import ExternalServiceError
from app.data_sources.tw.mops_source import (
    MOPSSource,
    _roc_or_iso_to_date,
    _to_decimal_or_none,
)

pytestmark = pytest.mark.unit


# ── helpers ─────────────────────────────────────────────


def test_roc_or_iso_to_date_parses_both() -> None:
    assert _roc_or_iso_to_date("114/05/12") == date(2025, 5, 12)
    assert _roc_or_iso_to_date("2026-04-01") == date(2026, 4, 1)
    assert _roc_or_iso_to_date("") is None
    assert _roc_or_iso_to_date("garbage") is None


def test_to_decimal_or_none_strips_percent() -> None:
    assert _to_decimal_or_none("12.5%") == Decimal("12.5")
    assert _to_decimal_or_none("1,234,567") == Decimal("1234567")
    assert _to_decimal_or_none("--") is None
    assert _to_decimal_or_none(None) is None


# ── parse_monthly_for_symbol ───────────────────────────


SAMPLE_MONTHLY_HTML = """
<html><body>
<table>
<tr>
  <td>2330</td><td>台積電</td><td>300,000,000</td><td>250,000,000</td><td>280,000,000</td>
  <td>20.00</td><td>7.14</td><td>900,000,000</td><td>850,000,000</td><td>5.88</td>
</tr>
<tr>
  <td>2317</td><td>鴻海</td><td>500,000,000</td><td>490,000,000</td><td>510,000,000</td>
  <td>2.04</td><td>-1.96</td><td>1,500,000,000</td><td>1,500,000,000</td><td>0.00</td>
</tr>
</table>
</body></html>
"""


def test_parse_monthly_for_symbol_found() -> None:
    src = MOPSSource(settings)
    out = src._parse_monthly_for_symbol(SAMPLE_MONTHLY_HTML, "2330", 2026, 4)
    assert out is not None
    assert out["symbol"] == "2330"
    assert out["year"] == 2026
    assert out["month"] == 4
    assert out["revenue"] == Decimal("300000000")
    assert out["revenue_mom"] == Decimal("20.00")
    assert out["revenue_yoy"] == Decimal("7.14")
    assert out["ytd_revenue"] == Decimal("900000000")
    assert out["ytd_yoy"] == Decimal("5.88")


def test_parse_monthly_for_symbol_not_found() -> None:
    src = MOPSSource(settings)
    out = src._parse_monthly_for_symbol(SAMPLE_MONTHLY_HTML, "9999", 2026, 4)
    assert out is None


SAMPLE_ANN_HTML = """
<html><body>
<table>
<tr><td>114/05/12</td><td>2330</td><td>台積電</td><td>本公司董事會決議現金股利</td></tr>
<tr><td>114/04/30</td><td>2330</td><td>台積電</td><td>第一季法說會公告</td></tr>
</table>
</body></html>
"""


def test_parse_announcements_with_since_filter() -> None:
    src = MOPSSource(settings)
    out = src._parse_announcements(SAMPLE_ANN_HTML, "2330", date(2025, 5, 1))
    assert len(out) == 1
    assert out[0]["title"] == "本公司董事會決議現金股利"
    assert out[0]["published_at"] == date(2025, 5, 12)


def test_parse_announcements_no_filter_returns_all() -> None:
    src = MOPSSource(settings)
    out = src._parse_announcements(SAMPLE_ANN_HTML, "2330", since=None)
    assert len(out) == 2


# ── HTTP mock ─────────────────────────────────────────


@pytest.fixture
def mops() -> MOPSSource:
    CIRCUIT_BREAKERS.pop("mops", None)
    src = MOPSSource(settings)
    src.limiter = None  # 測試不限速
    return src


@pytest.fixture
def mock_get(monkeypatch):  # type: ignore[no-untyped-def]
    state = {"response_factory": None}

    async def fake_get(self, url, **kwargs):  # type: ignore[no-untyped-def]
        f = state["response_factory"]
        return f(url, kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return state


def _html_resp(status: int, body: str) -> httpx.Response:
    req = httpx.Request("GET", "https://mops.twse.com.tw/x")
    return httpx.Response(status_code=status, request=req, text=body)


@pytest.mark.asyncio
async def test_fetch_monthly_revenue_full_year(mops: MOPSSource, mock_get) -> None:
    """月營收 — 整年 12 月份呼叫。"""
    mock_get["response_factory"] = lambda url, kw: _html_resp(200, SAMPLE_MONTHLY_HTML)
    out = await mops.fetch_monthly_revenue("2330", year=2026)
    # 12 個月都用同一 HTML，所以都會抓到「2330」 → 12 筆
    assert len(out) == 12
    assert all(r["symbol"] == "2330" for r in out)


@pytest.mark.asyncio
async def test_fetch_monthly_revenue_skips_404_only_for_months_not_yet_ended(
    mops: MOPSSource, mock_get
) -> None:
    """**尚未到來**的月份 404 → 跳過（資料本來就還沒產生）。

    刻意依「今天」計算而非寫死月份：原測試寫死「前 3 月 200、其餘 404」並斷言 len==3，
    等時間走到年中就會把「已過月份卻 404」也當成正常，反而保護了靜默失敗。
    """
    today = _dt.utcnow().date()
    calls = {"n": 0}

    def factory(url, kw):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        # 依呼叫順序即為月份 1..12
        return (
            _html_resp(200, SAMPLE_MONTHLY_HTML)
            if calls["n"] < today.month
            else _html_resp(404, "")
        )

    mock_get["response_factory"] = factory
    out = await mops.fetch_monthly_revenue("2330", year=today.year)
    assert len(out) == today.month - 1


@pytest.mark.asyncio
async def test_fetch_monthly_revenue_past_month_404_raises(mops: MOPSSource, mock_get) -> None:
    """**已過**月份仍 404 = 來源壞了或被擋 → 必須大聲失敗，不可靜默回空。

    這正是 MOPS 現況：對 python-httpx 一律 404（對 curl 則回「安全性考量」攔截頁）。
    原本一律 swallow 所有 4xx → 12 個月全被當成「還沒到」→ 回 0 筆看起來像「查無資料」，
    與 FinMind 307 同型的無聲故障。
    """
    mock_get["response_factory"] = lambda url, kw: _html_resp(404, "")
    with pytest.raises(ExternalServiceError):
        await mops.fetch_monthly_revenue("2330", year=2024)  # 整年都是過去


@pytest.mark.asyncio
async def test_fetch_monthly_revenue_server_error_propagates(mops: MOPSSource, mock_get) -> None:
    mock_get["response_factory"] = lambda url, kw: _html_resp(500, "boom")
    with pytest.raises(ExternalServiceError):
        await mops.fetch_monthly_revenue("2330", year=2026)
