"""ToolRegistry 單元測試 — 8 個 tool method，全部走 mocked ro session。

依 PLAN.md 第 14.4 章 + 第 19 章（read-only session）+ Phase 12 prompt 條 O（≥ 8 個測試）。

設計：用 in-memory mock async session 取代真 ro session，
避免 P12 unit test 依賴 docker compose up。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.agents.tools import ToolRegistry
from app.core.errors import ValidationError

pytestmark = pytest.mark.unit


# ── mock session helper ─────────────────────────────────


class _MockResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> Any:
        class _Inner:
            def __init__(self, rows: list[Any]) -> None:
                self._rows = rows

            def all(self) -> list[Any]:
                return self._rows

        return _Inner(self._rows)

    def scalar_one_or_none(self) -> Any:
        return self._rows[0] if self._rows else None


class _MockSession:
    def __init__(self) -> None:
        self.queries: list[Any] = []
        self.results: list[list[Any]] = []

    def queue(self, rows: list[Any]) -> None:
        self.results.append(rows)

    async def execute(self, stmt: Any) -> _MockResult:
        self.queries.append(stmt)
        rows = self.results.pop(0) if self.results else []
        return _MockResult(rows)

    async def __aenter__(self) -> _MockSession:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None


def _make_factory(session: _MockSession) -> Any:
    @asynccontextmanager
    async def _factory():
        yield session

    # 模擬 async_sessionmaker：呼叫 () 回 context manager
    return lambda: _factory()


# ── tests ───────────────────────────────────────────────


def test_tool_registry_constructor_stores_factory() -> None:
    s = _MockSession()
    f = _make_factory(s)
    r = ToolRegistry(f)
    assert r.ro is f


@pytest.mark.asyncio
async def test_get_ohlcv_returns_list() -> None:
    s = _MockSession()

    class _Row:
        symbol = "2330"
        date = date(2026, 5, 15)
        open = Decimal("600")
        high = Decimal("610")
        low = Decimal("595")
        close = Decimal("605")
        volume = 12345
        turnover = Decimal("7456380.00")
        source = "FinMind"

    s.queue([_Row()])
    r = ToolRegistry(_make_factory(s))
    out = await r.get_ohlcv("2330", days_back=30)
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["symbol"] == "2330"
    assert out[0]["close"] == "605"
    assert out[0]["source"] == "FinMind"


@pytest.mark.asyncio
async def test_get_ohlcv_invalid_days_back() -> None:
    s = _MockSession()
    r = ToolRegistry(_make_factory(s))
    with pytest.raises(ValidationError):
        await r.get_ohlcv("2330", days_back=0)
    with pytest.raises(ValidationError):
        await r.get_ohlcv("2330", days_back=10_000)


@pytest.mark.asyncio
async def test_get_company_info_merges_list_and_info() -> None:
    s = _MockSession()

    class _List:
        symbol = "2330"
        name = "台積電"
        short_name = "TSMC"
        market = "TWSE"
        industry = "半導體"
        listed_at = date(1994, 9, 5)
        is_active = True

    class _Info:
        full_name = "台灣積體電路製造股份有限公司"
        sector = "Semiconductors"
        sub_industry = None
        description = "晶圓代工龍頭"
        website = "https://www.tsmc.com"
        capital = Decimal("259303804970")
        employees = 73000
        fiscal_year_end = "12-31"

    s.queue([_List()])
    s.queue([_Info()])
    r = ToolRegistry(_make_factory(s))
    out = await r.get_company_info("2330")
    assert out["symbol"] == "2330"
    assert out["name"] == "台積電"
    assert out["industry"] == "半導體"
    assert out["full_name"].startswith("台灣積體")
    assert out["website"].startswith("https://")


@pytest.mark.asyncio
async def test_get_company_info_not_found() -> None:
    s = _MockSession()
    s.queue([])  # stock_list 查無
    r = ToolRegistry(_make_factory(s))
    out = await r.get_company_info("9999")
    assert out == {}


@pytest.mark.asyncio
async def test_get_institutional_blocks_non_tw() -> None:
    s = _MockSession()
    r = ToolRegistry(_make_factory(s))
    with pytest.raises(ValidationError):
        await r.get_institutional("AAPL", days_back=30)


@pytest.mark.asyncio
async def test_get_margin_blocks_non_tw() -> None:
    s = _MockSession()
    r = ToolRegistry(_make_factory(s))
    with pytest.raises(ValidationError):
        await r.get_margin("AAPL", days_back=30)


@pytest.mark.asyncio
async def test_get_monthly_revenue_blocks_non_tw() -> None:
    s = _MockSession()
    r = ToolRegistry(_make_factory(s))
    with pytest.raises(ValidationError):
        await r.get_monthly_revenue("AAPL", months_back=12)


@pytest.mark.asyncio
async def test_get_news_returns_metadata_list() -> None:
    s = _MockSession()

    class _Row:
        id = uuid4()
        title = "台積電 Q1 EPS 創高"
        summary = "本季毛利率 56%"
        source = "cnyes"
        url = "https://news.example.com/1"
        sentiment = "positive"
        sentiment_score = Decimal("0.85")
        published_at = datetime.now(tz=UTC) - timedelta(days=1)

    s.queue([_Row()])
    r = ToolRegistry(_make_factory(s))
    out = await r.get_news("2330", days_back=7, max_items=10)
    assert len(out) == 1
    assert out[0]["title"].startswith("台積電")
    assert out[0]["sentiment"] == "positive"
    assert out[0]["sentiment_score"] == "0.85"


def test_get_langchain_tools_yields_eight_tools() -> None:
    """get_langchain_tools 應回 8 個工具（即使 langchain 沒裝也至少不 raise）。"""
    s = _MockSession()
    r = ToolRegistry(_make_factory(s))
    tools = r.get_langchain_tools()
    # 若 langchain_core 沒裝會回 []；若有裝會 = 8
    assert isinstance(tools, list)
    assert len(tools) in (0, 8)
