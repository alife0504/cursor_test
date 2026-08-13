"""MarketDispatcher 端到端 — 跨市場路由 + DataPipelineService 整合。

驗證：
- 2330 → finmind（TW）
- AAPL → yfinance（US）
- 0050（ETF）走 TW pipeline
- BRK.B 走 US pipeline
- US symbol 呼 sync_institutional 拋 ValidationError（TW only）
- 不認識的 symbol → ValidationError
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS, CircuitBreaker
from app.core.errors import ValidationError
from app.core.market_dispatcher import MarketDispatcher, MarketRegion, detect_region
from app.data_sources.base import BaseDataSource, DataKind

pytestmark = pytest.mark.integration


# ── 假 source（不打網路） ─────────────────────────────


class _FakeOHLCVSource(BaseDataSource):
    name = "_fake_ohlcv"
    priority = 10

    def __init__(self, *, name: str, region: MarketRegion) -> None:
        self.name = name
        self.priority = 10
        self.supported_regions = (region,)
        self.supported_kinds = (DataKind.OHLCV,)
        self.limiter = None
        CIRCUIT_BREAKERS.pop(name, None)
        self.cb = CIRCUIT_BREAKERS.setdefault(name, CircuitBreaker(name=name))

    async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": [start, end],
                "open": [Decimal("100"), Decimal("101")],
                "high": [Decimal("105"), Decimal("106")],
                "low": [Decimal("99"), Decimal("100")],
                "close": [Decimal("104"), Decimal("105")],
                "volume": [1000, 2000],
                "turnover": [Decimal("100000"), Decimal("210000")],
            }
        )


@pytest.fixture
def dispatcher() -> MarketDispatcher:
    tw_src = _FakeOHLCVSource(name="finmind_fake", region=MarketRegion.TW)
    us_src = _FakeOHLCVSource(name="yfinance_fake", region=MarketRegion.US)
    return MarketDispatcher(
        tw_sources={DataKind.OHLCV: [tw_src]},
        us_sources={DataKind.OHLCV: [us_src]},
    )


# ── tests ────────────────────────────────────────────


def test_2330_routes_to_tw_sources(dispatcher: MarketDispatcher) -> None:
    """2330（台積電）→ TW source。"""
    assert detect_region("2330") == MarketRegion.TW
    srcs = dispatcher.get_sources_for_symbol("2330", DataKind.OHLCV)
    assert len(srcs) == 1
    assert srcs[0].name == "finmind_fake"


def test_aapl_routes_to_us_sources(dispatcher: MarketDispatcher) -> None:
    """AAPL → US source。"""
    assert detect_region("AAPL") == MarketRegion.US
    srcs = dispatcher.get_sources_for_symbol("AAPL", DataKind.OHLCV)
    assert len(srcs) == 1
    assert srcs[0].name == "yfinance_fake"


def test_0050_etf_routes_to_tw(dispatcher: MarketDispatcher) -> None:
    """ETF 00878 / 0050 → TW source。"""
    assert detect_region("0050") == MarketRegion.TW
    assert detect_region("00878") == MarketRegion.TW
    srcs = dispatcher.get_sources_for_symbol("00878", DataKind.OHLCV)
    assert srcs[0].name == "finmind_fake"


def test_brkb_class_b_routes_to_us(dispatcher: MarketDispatcher) -> None:
    """BRK.B（dual class）→ US source。"""
    assert detect_region("BRK.B") == MarketRegion.US
    srcs = dispatcher.get_sources_for_symbol("BRK.B", DataKind.OHLCV)
    assert srcs[0].name == "yfinance_fake"


def test_invalid_symbol_raises(dispatcher: MarketDispatcher) -> None:
    """不認識的格式 → ValidationError。"""
    for bad in ["", "lower", "中文", "TOOOOLONG"]:
        with pytest.raises(ValidationError):
            dispatcher.get_sources_for_symbol(bad, DataKind.OHLCV)


def test_us_symbol_no_institutional_sources(dispatcher: MarketDispatcher) -> None:
    """US 沒有 INSTITUTIONAL source（dispatcher 回空 list）。

    DataPipelineService.sync_institutional 應靠 detect_region 直接拒絕，
    這裡先驗 dispatcher 層的行為。
    """
    srcs = dispatcher.get_sources_for(MarketRegion.US, DataKind.INSTITUTIONAL)
    assert srcs == []


@pytest.mark.asyncio
async def test_pipeline_sync_institutional_us_symbol_raises_validation() -> None:
    """DataPipelineService.sync_institutional("AAPL") → ValidationError（TW only）。

    Note: 為了不依賴 DB，這裡 mock session；只測 region 守門邏輯。
    """
    from app.services.data_pipeline_service import DataPipelineService

    class _MockSession:
        async def execute(self, *a: Any, **kw: Any) -> Any:
            return None

        async def commit(self) -> None:
            pass

    d = MarketDispatcher(tw_sources={}, us_sources={})
    svc = DataPipelineService.with_dispatcher(d, _MockSession())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        await svc.sync_institutional("AAPL", date(2026, 4, 1), date(2026, 4, 30))
