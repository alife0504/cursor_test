"""DataPipelineService 整合測試 — 真實 PG upsert + mock data source。

需 docker compose up（timescaledb healthy）+ alembic upgrade head 完成。

驗證：
- sync_ohlcv 將 fallback 抓的 DataFrame 寫入 DB（含 ON CONFLICT 行為）
- sync_ohlcv 在 primary fail 時自動 fallback 到 secondary
- sync_news 透過 url dedupe
- sync_monthly_revenue 寫入 monthly_revenue 表
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.circuit_breaker import CIRCUIT_BREAKERS, CircuitBreaker
from app.core.config import settings
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion
from app.services.data_pipeline_service import DataPipelineService

pytestmark = pytest.mark.integration


# ── 共用：真實 DB session ─────────────────────────────


@pytest.fixture
async def rw_session():  # type: ignore[no-untyped-def]
    # ⚠️ 安全閘門：本 fixture 的測試會對真實代號(2330/2317/6488)寫入並 DELETE 股價/月營收，
    # 誤跑在正式/開發庫會清掉真實資料。只允許在專用測試庫或明確 opt-in 時執行。
    from tests.integration.conftest import require_writable_test_db

    require_writable_test_db()
    engine = create_async_engine(settings.postgres_dsn_rw)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        # 1) 確保 2330 / 2317 / 6488 在 stock_list 內（後續 FK 需要）
        for sym, market, name in (
            ("2330", "TWSE", "台積電"),
            ("2317", "TWSE", "鴻海"),
            ("6488", "TPEX", "環球晶"),
        ):
            await session.execute(
                text(
                    "INSERT INTO stock_list (symbol, market, name, is_active) "
                    "VALUES (:s, :m, :n, true) "
                    "ON CONFLICT (symbol) DO UPDATE SET is_active = true"
                ),
                {"s": sym, "m": market, "n": name},
            )
        await session.commit()
        yield session
    await engine.dispose()


# ── 假 source ─────────────────────────────────────────


class _FakeOHLCVSource(BaseDataSource):
    name = "_fake_ohlcv"
    priority = 10
    supported_regions = (MarketRegion.TW,)
    supported_kinds = (DataKind.OHLCV,)
    rate_limit_per_sec = None

    def __init__(self, *, name: str, priority: int, behavior: str = "ok") -> None:
        self.name = name
        self.priority = priority
        self.behavior = behavior
        CIRCUIT_BREAKERS.pop(name, None)
        self.cb = CIRCUIT_BREAKERS.setdefault(name, CircuitBreaker(name=name))
        self.limiter = None

    async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        if self.behavior == "fail":
            raise RuntimeError(f"{self.name} pretend fail")
        return pd.DataFrame(
            {
                "date": [start, end],
                "open": [Decimal("900"), Decimal("910")],
                "high": [Decimal("905"), Decimal("915")],
                "low": [Decimal("898"), Decimal("905")],
                "close": [Decimal("903"), Decimal("912")],
                "volume": [1000, 2000],
                "turnover": [Decimal("900000"), Decimal("1800000")],
            }
        )


class _FakeNewsSource(BaseDataSource):
    name = "_fake_news"
    priority = 10
    supported_regions = (MarketRegion.TW,)
    supported_kinds = (DataKind.NEWS,)
    rate_limit_per_sec = None

    def __init__(self, *, items: list[dict[str, Any]] | None = None) -> None:
        self.name = "_fake_news"
        self.priority = 10
        CIRCUIT_BREAKERS.pop(self.name, None)
        self.cb = CIRCUIT_BREAKERS.setdefault(self.name, CircuitBreaker(name=self.name))
        self.limiter = None
        self._items = items or []

    async def fetch_news(
        self, symbol: str | None = None, *, since: date | None = None
    ) -> list[dict[str, Any]]:
        return list(self._items)


class _FakeMonthlyRevSource(BaseDataSource):
    name = "_fake_mr"
    priority = 10
    supported_regions = (MarketRegion.TW,)
    supported_kinds = (DataKind.MONTHLY_REVENUE,)
    rate_limit_per_sec = None

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.name = "_fake_mr"
        self.priority = 10
        CIRCUIT_BREAKERS.pop(self.name, None)
        self.cb = CIRCUIT_BREAKERS.setdefault(self.name, CircuitBreaker(name=self.name))
        self.limiter = None
        self._items = items

    async def fetch_monthly_revenue(
        self, symbol: str, *, year: int | None = None
    ) -> list[dict[str, Any]]:
        return list(self._items)


# ── tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_ohlcv_writes_db(rw_session) -> None:  # type: ignore[no-untyped-def]
    src = _FakeOHLCVSource(name="primary_ok", priority=10, behavior="ok")
    service = DataPipelineService({DataKind.OHLCV: [src]}, rw_session)
    n = await service.sync_ohlcv("2330", "TWSE", date(2026, 4, 1), date(2026, 4, 2))
    assert n == 2
    # 驗 DB 中有資料
    result = await rw_session.execute(
        text("SELECT close FROM stock_prices WHERE symbol = '2330' ORDER BY date")
    )
    rows = result.all()
    assert len(rows) >= 2
    # 清理
    await rw_session.execute(text("DELETE FROM stock_prices WHERE symbol = '2330'"))
    await rw_session.commit()


@pytest.mark.asyncio
async def test_sync_uses_fallback_when_primary_down(rw_session) -> None:  # type: ignore[no-untyped-def]
    primary = _FakeOHLCVSource(name="primary_fail", priority=10, behavior="fail")
    secondary = _FakeOHLCVSource(name="secondary_ok", priority=20, behavior="ok")
    service = DataPipelineService({DataKind.OHLCV: [primary, secondary]}, rw_session)
    n = await service.sync_ohlcv("2317", "TWSE", date(2026, 4, 1), date(2026, 4, 2))
    assert n == 2
    # primary 應記錄一次失敗
    assert primary.cb.failure_count == 1
    # 清理
    await rw_session.execute(text("DELETE FROM stock_prices WHERE symbol = '2317'"))
    await rw_session.commit()


@pytest.mark.asyncio
async def test_sync_ohlcv_idempotent_via_on_conflict(rw_session) -> None:  # type: ignore[no-untyped-def]
    """連跑兩次 sync 應 idempotent — ON CONFLICT DO UPDATE 不會炸主鍵。"""
    src = _FakeOHLCVSource(name="idem_ok", priority=10, behavior="ok")
    service = DataPipelineService({DataKind.OHLCV: [src]}, rw_session)
    await service.sync_ohlcv("6488", "TPEX", date(2026, 4, 1), date(2026, 4, 2))
    n2 = await service.sync_ohlcv("6488", "TPEX", date(2026, 4, 1), date(2026, 4, 2))
    assert n2 == 2  # 第二次仍寫 2 筆（但是 update）
    # 應只有兩筆
    result = await rw_session.execute(
        text("SELECT COUNT(*) FROM stock_prices WHERE symbol = '6488'")
    )
    count = result.scalar_one()
    assert count == 2
    await rw_session.execute(text("DELETE FROM stock_prices WHERE symbol = '6488'"))
    await rw_session.commit()


@pytest.mark.asyncio
async def test_sync_news_dedupe(rw_session) -> None:  # type: ignore[no-untyped-def]
    """同 url 第二次 sync 不重複 insert。"""
    items = [
        {
            "title": "新聞 A",
            "url": "https://test.example.com/news/a1",
            "summary": "測試",
            "published_at": datetime(2026, 5, 1, 8, 0),
        },
        {
            "title": "新聞 B",
            "url": "https://test.example.com/news/b1",
            "summary": "測試",
            "published_at": datetime(2026, 5, 2, 9, 0),
        },
    ]
    src = _FakeNewsSource(items=items)
    service = DataPipelineService({DataKind.NEWS: [src]}, rw_session)

    n1 = await service.sync_news_for_symbol("2330")
    assert n1 == 2
    n2 = await service.sync_news_for_symbol("2330")
    assert n2 == 0  # url 已存在

    # 清理
    await rw_session.execute(
        text("DELETE FROM news_metadata WHERE url LIKE 'https://test.example.com/news/%'")
    )
    await rw_session.commit()


@pytest.mark.asyncio
async def test_sync_monthly_revenue_writes_db(rw_session) -> None:  # type: ignore[no-untyped-def]
    items = [
        {
            "symbol": "2330",
            "year": 2026,
            "month": 1,
            "revenue": "300000000.50",
            "revenue_yoy": "12.34",
        },
        {
            "symbol": "2330",
            "year": 2026,
            "month": 2,
            "revenue": "320000000",
            "revenue_yoy": "13.45",
        },
    ]
    src = _FakeMonthlyRevSource(items)
    service = DataPipelineService({DataKind.MONTHLY_REVENUE: [src]}, rw_session)
    n = await service.sync_monthly_revenue("2330", year=2026)
    assert n == 2
    # 驗 DB
    result = await rw_session.execute(
        text(
            "SELECT month, revenue FROM monthly_revenue "
            "WHERE symbol = '2330' AND year = 2026 ORDER BY month"
        )
    )
    rows = result.all()
    assert len(rows) == 2
    assert rows[0][1] == Decimal("300000000.50")
    # 清理
    await rw_session.execute(
        text("DELETE FROM monthly_revenue WHERE symbol = '2330' AND year = 2026")
    )
    await rw_session.commit()
