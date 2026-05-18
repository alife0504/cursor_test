"""MarketDispatcher 單元測試 — symbol regex / region 判斷 / 跨市場 dispatch。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.errors import NotFoundError, ValidationError
from app.core.market_dispatcher import (
    TW_SYMBOL_PATTERN,
    US_SYMBOL_PATTERN,
    Market,
    MarketDispatcher,
    MarketRegion,
    detect_region,
    market_to_region,
    validate_symbol_exists,
)
from app.data_sources.base import BaseDataSource, DataKind

pytestmark = pytest.mark.unit


# ── Symbol regex / detect_region ────────────────────────


@pytest.mark.parametrize("symbol", ["2330", "2317", "1101"])
def test_detect_region_tw_normal_4digit(symbol: str) -> None:
    assert detect_region(symbol) == MarketRegion.TW


@pytest.mark.parametrize("symbol", ["0050", "00878", "006208", "00692"])
def test_detect_region_tw_etf_5_6_digit(symbol: str) -> None:
    """ETF 涵蓋 4/5/6 碼開頭 0。"""
    assert detect_region(symbol) == MarketRegion.TW


def test_detect_region_tw_special_share_with_letter() -> None:
    """特別股 2884A、權證 043333P。"""
    assert detect_region("2884A") == MarketRegion.TW
    assert detect_region("043333P") == MarketRegion.TW


@pytest.mark.parametrize("symbol", ["AAPL", "MSFT", "TSLA", "NVDA", "GOOG"])
def test_detect_region_us_normal(symbol: str) -> None:
    assert detect_region(symbol) == MarketRegion.US


def test_detect_region_us_class_b() -> None:
    """BRK.B、RDS.A、BF.B 等 dual class（含 dot）。"""
    assert detect_region("BRK.B") == MarketRegion.US
    assert detect_region("BF.B") == MarketRegion.US


def test_detect_region_us_short_symbols() -> None:
    """F、T、X 等 1 字母 symbol。"""
    for s in ["F", "T", "X"]:
        assert detect_region(s) == MarketRegion.US


def test_detect_region_unknown_raises() -> None:
    """完全不符合的 symbol → ValidationError。"""
    for invalid in ["", "  ", "123", "TOOOLONG", "lowercase", "WITH-HYPHEN", "中文"]:
        with pytest.raises(ValidationError):
            detect_region(invalid)


def test_market_to_region_mapping() -> None:
    assert market_to_region(Market.TWSE) == MarketRegion.TW
    assert market_to_region(Market.TPEX) == MarketRegion.TW
    assert market_to_region(Market.NASDAQ) == MarketRegion.US
    assert market_to_region(Market.NYSE) == MarketRegion.US
    assert market_to_region(Market.AMEX) == MarketRegion.US


def test_tw_pattern_string_check() -> None:
    """直接檢查 regex pattern（PLAN 10.2）。"""
    assert TW_SYMBOL_PATTERN.match("2330")
    assert TW_SYMBOL_PATTERN.match("00878")
    assert not TW_SYMBOL_PATTERN.match("AAPL")
    assert US_SYMBOL_PATTERN.match("AAPL")
    assert US_SYMBOL_PATTERN.match("BRK.B")
    assert not US_SYMBOL_PATTERN.match("2330")


# ── MarketDispatcher ────────────────────────────────────


class _FakeSource(BaseDataSource):
    name = "_fake"
    priority = 10

    def __init__(self, *, name: str, region: MarketRegion, kinds: tuple[DataKind, ...]) -> None:
        self.name = name
        self.priority = 10
        self.supported_regions = (region,)
        self.supported_kinds = kinds
        self.limiter = None
        # 跳過 super().__init__()（避免 settings 依賴）

    async def fetch_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        return None


def _build_dispatcher() -> MarketDispatcher:
    tw_ohlcv = _FakeSource(name="finmind", region=MarketRegion.TW, kinds=(DataKind.OHLCV,))
    us_ohlcv = _FakeSource(name="yfinance", region=MarketRegion.US, kinds=(DataKind.OHLCV,))
    us_news = _FakeSource(name="finnhub", region=MarketRegion.US, kinds=(DataKind.NEWS,))
    return MarketDispatcher(
        tw_sources={DataKind.OHLCV: [tw_ohlcv]},
        us_sources={DataKind.OHLCV: [us_ohlcv], DataKind.NEWS: [us_news]},
    )


def test_dispatcher_returns_correct_sources_for_region() -> None:
    d = _build_dispatcher()
    tw_srcs = d.get_sources_for(MarketRegion.TW, DataKind.OHLCV)
    assert len(tw_srcs) == 1
    assert tw_srcs[0].name == "finmind"
    us_srcs = d.get_sources_for(MarketRegion.US, DataKind.OHLCV)
    assert us_srcs[0].name == "yfinance"


def test_dispatcher_returns_empty_when_no_match() -> None:
    """TW 沒有 NEWS source（測試）→ get_sources_for 回空 list。"""
    d = _build_dispatcher()
    assert d.get_sources_for(MarketRegion.TW, DataKind.NEWS) == []


def test_dispatcher_get_sources_for_symbol_auto_routes() -> None:
    d = _build_dispatcher()
    # 2330 → TW
    assert d.get_sources_for_symbol("2330", DataKind.OHLCV)[0].name == "finmind"
    # AAPL → US
    assert d.get_sources_for_symbol("AAPL", DataKind.OHLCV)[0].name == "yfinance"


# ── validate_symbol_exists ──────────────────────────────


class _FakeStockRepo:
    def __init__(self, existing: set[tuple[str, str]]) -> None:
        self._existing = existing

    async def get_by_symbol(self, symbol: str, market: str) -> Any:
        if (symbol, market) in self._existing:
            return object()
        return None


@pytest.mark.asyncio
async def test_validate_symbol_exists_returns_true_when_present() -> None:
    repo = _FakeStockRepo(existing={("2330", "TWSE")})
    assert await validate_symbol_exists("2330", Market.TWSE, repo) is True


@pytest.mark.asyncio
async def test_validate_symbol_exists_raises_when_missing() -> None:
    repo = _FakeStockRepo(existing=set())
    with pytest.raises(NotFoundError):
        await validate_symbol_exists("9999", Market.TWSE, repo)
