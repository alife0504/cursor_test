"""DataSourceFallback 單元測試 — 主源 → 備源 → 快取 行為。"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.core.circuit_breaker import CIRCUIT_BREAKERS, CircuitBreaker
from app.core.errors import ExternalServiceError
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion
from app.data_sources.fallback import DataSourceFallback

pytestmark = pytest.mark.unit


# ── 假 source ─────────────────────────────────────────


class _FakeSource(BaseDataSource):
    """測試用 source — 不真的呼叫網路。

    可控：
      - .behavior: "ok" | "fail" | "not_supported"
      - .calls: 計數器
    """

    name = "fake_base"  # subclass 會覆寫
    priority = 100
    supported_regions = (MarketRegion.TW,)
    supported_kinds = (DataKind.OHLCV,)
    rate_limit_per_sec = None

    def __init__(self, *, name: str, priority: int, behavior: str = "ok") -> None:
        # 直接準備 settings 替身（不走 BaseDataSource.__init__ 來避免依賴 settings）
        self.name = name
        self.priority = priority
        self.behavior = behavior
        self.calls = 0
        # 自己準備 CB
        CIRCUIT_BREAKERS.pop(name, None)
        self.cb = CIRCUIT_BREAKERS.setdefault(name, CircuitBreaker(name=name))
        self.limiter = None

    async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> Any:
        self.calls += 1
        if self.behavior == "ok":
            return f"ohlcv:{symbol}:{start}:{end} via {self.name}"
        if self.behavior == "not_supported":
            raise NotImplementedError
        raise RuntimeError(f"{self.name} pretend to fail")


@pytest.fixture(autouse=True)
def _clean_cbs() -> None:
    """每測試清空 CB registry。"""
    CIRCUIT_BREAKERS.clear()


# ── tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_uses_primary_when_healthy() -> None:
    primary = _FakeSource(name="primary", priority=10, behavior="ok")
    secondary = _FakeSource(name="secondary", priority=20, behavior="ok")
    fb = DataSourceFallback([primary, secondary])
    result = await fb.fetch_ohlcv("2330", date(2026, 4, 1), date(2026, 4, 5))
    assert "via primary" in result
    assert primary.calls == 1
    assert secondary.calls == 0


@pytest.mark.asyncio
async def test_falls_back_to_secondary_on_failure() -> None:
    primary = _FakeSource(name="primary", priority=10, behavior="fail")
    secondary = _FakeSource(name="secondary", priority=20, behavior="ok")
    fb = DataSourceFallback([primary, secondary])
    result = await fb.fetch_ohlcv("2330", date(2026, 4, 1), date(2026, 4, 5))
    assert "via secondary" in result
    assert primary.calls == 1
    assert secondary.calls == 1
    # primary 應該記錄 1 次失敗
    assert primary.cb.failure_count == 1


@pytest.mark.asyncio
async def test_skips_open_circuit_breakers() -> None:
    primary = _FakeSource(name="primary", priority=10, behavior="ok")
    secondary = _FakeSource(name="secondary", priority=20, behavior="ok")
    # 把 primary 的 CB 強制 OPEN
    for _ in range(primary.cb.failure_threshold):
        await primary.cb.record_failure()
    fb = DataSourceFallback([primary, secondary])
    result = await fb.fetch_ohlcv("2330", date(2026, 4, 1), date(2026, 4, 5))
    assert "via secondary" in result
    assert primary.calls == 0
    assert secondary.calls == 1


@pytest.mark.asyncio
async def test_uses_cache_when_all_fail() -> None:
    primary = _FakeSource(name="primary", priority=10, behavior="fail")
    secondary = _FakeSource(name="secondary", priority=20, behavior="fail")

    async def cache_loader(*, kind: str, **params: Any) -> str:
        return f"cached:{kind}:{params['symbol']}"

    fb = DataSourceFallback([primary, secondary], stale_cache_loader=cache_loader)
    result = await fb.fetch_ohlcv("2330", date(2026, 4, 1), date(2026, 4, 5))
    assert result == "cached:ohlcv:2330"


@pytest.mark.asyncio
async def test_raises_when_no_cache_either() -> None:
    primary = _FakeSource(name="primary", priority=10, behavior="fail")
    secondary = _FakeSource(name="secondary", priority=20, behavior="fail")

    async def empty_cache(*, kind: str, **params: Any) -> None:
        return None

    fb = DataSourceFallback([primary, secondary], stale_cache_loader=empty_cache)
    with pytest.raises(ExternalServiceError):
        await fb.fetch_ohlcv("2330", date(2026, 4, 1), date(2026, 4, 5))


@pytest.mark.asyncio
async def test_records_success_on_primary() -> None:
    """成功時應 record_success（讓 CB 從 HALF_OPEN 回 CLOSED）。"""
    primary = _FakeSource(name="primary", priority=10, behavior="ok")
    # 先製造一次失敗
    await primary.cb.record_failure()
    assert primary.cb.failure_count == 1
    fb = DataSourceFallback([primary])
    await fb.fetch_ohlcv("2330", date(2026, 4, 1), date(2026, 4, 5))
    # 連續成功應 reset failure_count
    assert primary.cb.failure_count == 0


@pytest.mark.asyncio
async def test_sources_sorted_by_priority() -> None:
    """傳入順序隨意；fallback 應依 priority 升序。"""
    high = _FakeSource(name="high", priority=99, behavior="ok")
    low = _FakeSource(name="low", priority=1, behavior="ok")
    fb = DataSourceFallback([high, low])  # 故意亂序
    result = await fb.fetch_ohlcv("2330", date(2026, 4, 1), date(2026, 4, 5))
    assert "via low" in result
    assert high.calls == 0


@pytest.mark.asyncio
async def test_no_sources_for_kind_raises() -> None:
    """sources 為 OHLCV 唯一 source；查 NEWS 應 raise（無 source 支援）。"""
    primary = _FakeSource(name="primary", priority=10, behavior="ok")
    fb = DataSourceFallback([primary])
    with pytest.raises(ExternalServiceError):
        await fb.fetch_news("2330")
