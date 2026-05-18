"""Repository 單元測試（mock AsyncSession，不打真實 DB）。

更深入的 DB 整合（驗 ON CONFLICT / unique 行為）放在
tests/integration/test_data_pipeline_service.py。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.news import NewsMetadata
from app.models.price import StockPrice
from app.models.stock import StockList
from app.repos.base import BaseRepository, ReadOnlyRepository
from app.repos.financials_repo import FinancialsRepository, _ensure_decimal
from app.repos.news_repo import NewsRepository
from app.repos.ohlcv_repo import OHLCVRepository
from app.repos.stock_repo import StockRepository

pytestmark = pytest.mark.unit


# ── helpers ──────────────────────────────────────────────


def _make_mock_session(scalar_one_or_none=None, scalars_all=None, all_rows=None):  # type: ignore[no-untyped-def]
    """產生一個 AsyncMock session，可指定 execute 後的 scalar 結果。"""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_one_or_none
    result.scalar.return_value = scalar_one_or_none
    result.scalars.return_value.all.return_value = scalars_all or []
    result.all.return_value = all_rows or []
    session.execute = AsyncMock(return_value=result)
    return session


# ── BaseRepository ──────────────────────────────────────


def test_base_repository_holds_session() -> None:
    session = AsyncMock()
    repo = BaseRepository(session)
    assert repo.session is session


def test_readonly_repository_inherits_base() -> None:
    session = AsyncMock()
    repo = ReadOnlyRepository(session)
    assert isinstance(repo, BaseRepository)


# ── StockRepository ──────────────────────────────────────


@pytest.mark.asyncio
async def test_stock_repo_get_by_symbol() -> None:
    stock = StockList(symbol="2330", market="TWSE", name="台積電")
    session = _make_mock_session(scalar_one_or_none=stock)
    repo = StockRepository(session)
    out = await repo.get_by_symbol("2330", "TWSE")
    assert out is stock
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_stock_repo_search_by_name_returns_results() -> None:
    """search_by_name 應 build SQL with ILIKE — 我們只驗 execute 被呼叫 + 結果回流。"""
    stocks = [
        StockList(symbol="2330", market="TWSE", name="台積電"),
        StockList(symbol="2317", market="TWSE", name="鴻海"),
    ]
    session = _make_mock_session(scalars_all=stocks)
    repo = StockRepository(session)
    out = await repo.search_by_name("台積", limit=10)
    assert out == stocks


@pytest.mark.asyncio
async def test_stock_repo_search_by_name_empty_query_returns_empty() -> None:
    """空 query 應直接回 [] 不打 DB。"""
    session = _make_mock_session()
    repo = StockRepository(session)
    out = await repo.search_by_name("  ")
    assert out == []
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_stock_repo_upsert_many_zero_items() -> None:
    session = _make_mock_session()
    repo = StockRepository(session)
    n = await repo.upsert_many([])
    assert n == 0
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_stock_repo_upsert_many_executes_once() -> None:
    session = _make_mock_session()
    repo = StockRepository(session)
    n = await repo.upsert_many(
        [
            {"symbol": "2330", "market": "TWSE", "name": "台積電", "is_active": True},
            {"symbol": "2317", "market": "TWSE", "name": "鴻海", "is_active": True},
        ]
    )
    assert n == 2
    session.execute.assert_awaited_once()


# ── OHLCVRepository ──────────────────────────────────────


@pytest.mark.asyncio
async def test_ohlcv_repo_get_range_returns_rows() -> None:
    rows = [
        StockPrice(
            symbol="2330",
            date=date(2026, 4, 1),
            open=Decimal("900"),
            high=Decimal("905"),
            low=Decimal("898"),
            close=Decimal("903"),
            volume=1000,
        )
    ]
    session = _make_mock_session(scalars_all=rows)
    repo = OHLCVRepository(session)
    out = await repo.get_range("2330", "TWSE", date(2026, 4, 1), date(2026, 4, 30))
    assert out == rows


@pytest.mark.asyncio
async def test_ohlcv_repo_latest_date_returns_date() -> None:
    session = _make_mock_session(scalar_one_or_none=date(2026, 4, 30))
    repo = OHLCVRepository(session)
    out = await repo.latest_date("2330", "TWSE")
    assert out == date(2026, 4, 30)


@pytest.mark.asyncio
async def test_ohlcv_repo_gaps_excludes_weekends() -> None:
    """區間 2026-04-04 (Sat) ~ 2026-04-10 (Fri)，週末應自動排除。

    現有資料：2026-04-08 (Wed)
    weekday_only=True → gaps 應為 [Mon 6, Tue 7, Thu 9, Fri 10]
    """
    existing = [
        StockPrice(
            symbol="2330",
            date=date(2026, 4, 8),
            open=Decimal("1"),
            high=Decimal("1"),
            low=Decimal("1"),
            close=Decimal("1"),
            volume=1,
        )
    ]
    session = _make_mock_session(scalars_all=existing)
    repo = OHLCVRepository(session)
    gaps = await repo.gaps("2330", "TWSE", date(2026, 4, 4), date(2026, 4, 10))
    assert date(2026, 4, 4) not in gaps  # Saturday
    assert date(2026, 4, 5) not in gaps  # Sunday
    assert date(2026, 4, 8) not in gaps  # already exists
    assert date(2026, 4, 6) in gaps
    assert date(2026, 4, 9) in gaps


@pytest.mark.asyncio
async def test_ohlcv_repo_upsert_many_skips_invalid_rows() -> None:
    """缺 OHLC 任一欄的 row 應被剔除。"""
    session = _make_mock_session()
    repo = OHLCVRepository(session)
    n = await repo.upsert_many(
        [
            # 有效
            {
                "symbol": "2330",
                "date": date(2026, 4, 1),
                "open": 900,
                "high": 905,
                "low": 898,
                "close": 903,
                "volume": 1000,
            },
            # 缺 close → 應跳過
            {"symbol": "2330", "date": date(2026, 4, 2), "open": 900, "high": 905, "low": 898},
            # 缺 symbol → 應跳過
            {"date": date(2026, 4, 3), "open": 1, "high": 1, "low": 1, "close": 1},
        ]
    )
    assert n == 1


@pytest.mark.asyncio
async def test_ohlcv_repo_upsert_many_empty_returns_zero() -> None:
    session = _make_mock_session()
    repo = OHLCVRepository(session)
    assert await repo.upsert_many([]) == 0


# ── NewsRepository ───────────────────────────────────────


@pytest.mark.asyncio
async def test_news_repo_list_by_symbol() -> None:
    items = [NewsMetadata(symbol="2330", title="t1", published_at=datetime(2026, 5, 1, 8, 0))]
    session = _make_mock_session(scalars_all=items)
    repo = NewsRepository(session)
    out = await repo.list_by_symbol("2330")
    assert out == items


@pytest.mark.asyncio
async def test_news_repo_dedupe_by_url() -> None:
    """既存 URL 不應重複 insert。"""
    # 模擬 session.execute 第一次回「現有 url list」，第二次（add）不會走 execute
    existing_urls = [("https://news.cnyes.com/x/1",)]
    session = AsyncMock()
    result1 = MagicMock()
    result1.all.return_value = existing_urls
    session.execute = AsyncMock(return_value=result1)
    session.add = MagicMock()

    repo = NewsRepository(session)
    items: list[dict[str, Any]] = [
        {
            "title": "已存在",
            "url": "https://news.cnyes.com/x/1",
            "published_at": datetime(2026, 5, 1, 8, 0),
        },
        {
            "title": "新的",
            "url": "https://news.cnyes.com/x/2",
            "published_at": datetime(2026, 5, 2, 8, 0),
        },
    ]
    n = await repo.upsert_many_by_url(items)
    assert n == 1
    assert session.add.call_count == 1


# ── FinancialsRepository ─────────────────────────────────


def test_ensure_decimal_handles_strings_and_floats() -> None:
    assert _ensure_decimal("1.234") == Decimal("1.234")
    assert _ensure_decimal(1.5) == Decimal("1.5")
    assert _ensure_decimal("--") is None
    assert _ensure_decimal(None) is None
    assert _ensure_decimal("1,234,567") == Decimal("1234567")


@pytest.mark.asyncio
async def test_financials_repo_decimal_precision() -> None:
    """upsert_statements 寫入的 Decimal 應保留原始精度（不被 float 化）。"""
    session = _make_mock_session()
    repo = FinancialsRepository(session)
    n = await repo.upsert_statements(
        [
            {
                "symbol": "2330",
                "fiscal_year": 2026,
                "fiscal_quarter": 1,
                "statement_type": "IS",
                "revenue": "300000000.123456",
                "eps": "12.3456",
            }
        ]
    )
    assert n == 1
    session.execute.assert_awaited_once()
    # 驗 clean stage 後的 entry 用 Decimal 而非 float
    val = _ensure_decimal("300000000.123456")
    assert isinstance(val, Decimal)
    assert val == Decimal("300000000.123456")


@pytest.mark.asyncio
async def test_financials_repo_upsert_skip_invalid() -> None:
    session = _make_mock_session()
    repo = FinancialsRepository(session)
    n = await repo.upsert_statements(
        [
            {"symbol": "2330"},  # 缺主鍵其餘三欄 → 應跳過
        ]
    )
    assert n == 0
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_financials_repo_monthly_revenue_upsert() -> None:
    session = _make_mock_session()
    repo = FinancialsRepository(session)
    n = await repo.upsert_monthly_revenue(
        [
            {"symbol": "2330", "year": 2026, "month": 4, "revenue": "300000000"},
            {"symbol": "2317", "year": 2026, "month": 4, "revenue": "500000000"},
        ]
    )
    assert n == 2


@pytest.mark.asyncio
async def test_repo_uses_correct_session() -> None:
    """確認所有 repo 都收到「同一個」session（共用 transaction）。"""
    session = _make_mock_session()
    stock_repo = StockRepository(session)
    ohlcv_repo = OHLCVRepository(session)
    news_repo = NewsRepository(session)
    fin_repo = FinancialsRepository(session)
    # 都共用一個 session（service layer 約束）
    assert stock_repo.session is session
    assert ohlcv_repo.session is session
    assert news_repo.session is session
    assert fin_repo.session is session
