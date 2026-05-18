"""sync_ohlcv celery task 整合測試（PLAN 第 14.7、14.10 章）。

需 docker compose up（timescaledb healthy + alembic upgrade head 完成）。

驗證：
- _async_sync_one 真實寫入 stock_prices 表
- task object 的 retry config 正確（autoretry_for / max_retries）
- _async_fan_out_market 從 stock_list 撈 active 後 dispatch n 個 task
- task_failure signal 在 task 失敗時觸發（透過直接呼叫 dlq 模擬）
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.circuit_breaker import CIRCUIT_BREAKERS, CircuitBreaker
from app.core.config import settings
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion
from app.workers.tasks import sync_ohlcv as sync_ohlcv_mod

pytestmark = pytest.mark.integration


# ─────────── Fake source（同 test_data_pipeline_service） ───────────


class _FakeOHLCVSource(BaseDataSource):
    name = "_fake_ohlcv_task"
    priority = 10
    supported_regions = (MarketRegion.TW,)
    supported_kinds = (DataKind.OHLCV,)
    rate_limit_per_sec = None

    def __init__(self, *, name: str = "_fake_ohlcv_task", behavior: str = "ok") -> None:
        self.name = name
        self.priority = 10
        self.supported_regions = (MarketRegion.TW,)
        self.supported_kinds = (DataKind.OHLCV,)
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
                "open": [Decimal("100"), Decimal("101")],
                "high": [Decimal("102"), Decimal("103")],
                "low": [Decimal("99"), Decimal("100")],
                "close": [Decimal("101"), Decimal("102")],
                "volume": [10000, 20000],
                "turnover": [Decimal("1010000"), Decimal("2040000")],
            }
        )


# ─────────── 共用：DB fixture ───────────


@pytest.fixture
async def rw_engine():  # type: ignore[no-untyped-def]
    engine = create_async_engine(settings.postgres_dsn_rw)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    # 確保 stock_list 有 _T_TASK 和 _T_FANOUT_X（FK 需要）
    async with sm() as session:
        for sym, mkt, name in (
            ("_T_TASK", "TWSE", "celery_task_test"),
            ("_T_FANOUT_1", "TWSE", "fan_out_1"),
            ("_T_FANOUT_2", "TWSE", "fan_out_2"),
            ("_T_FANOUT_3", "TPEX", "fan_out_3"),
        ):
            await session.execute(
                text(
                    "INSERT INTO stock_list (symbol, market, name, is_active) "
                    "VALUES (:s, :m, :n, true) "
                    "ON CONFLICT (symbol) DO UPDATE SET is_active = true"
                ),
                {"s": sym, "m": mkt, "n": name},
            )
        await session.commit()

    yield engine

    # cleanup：刪測試資料
    async with sm() as session:
        await session.execute(
            text("DELETE FROM stock_prices WHERE symbol LIKE '\\_T\\_%' ESCAPE '\\'")
        )
        await session.execute(
            text("DELETE FROM stock_list WHERE symbol LIKE '\\_T\\_%' ESCAPE '\\'")
        )
        await session.commit()
    await engine.dispose()


# ─────────── Tests ───────────


@pytest.mark.asyncio
async def test_sync_ohlcv_one_writes_db(rw_engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """直接呼叫 _async_sync_one → 應寫入 stock_prices 2 row。"""
    fake_source = _FakeOHLCVSource(name="_fake_a", behavior="ok")
    fake_sources = {DataKind.OHLCV: [fake_source]}

    monkeypatch.setattr(sync_ohlcv_mod, "get_tw_sources", lambda _s: fake_sources)

    result = await sync_ohlcv_mod._async_sync_one("_T_TASK", "TWSE", days_back=2)

    assert result["symbol"] == "_T_TASK"
    assert result["written"] >= 2

    # 驗 DB 真的有
    sm = async_sessionmaker(rw_engine, expire_on_commit=False)
    async with sm() as session:
        n = (
            await session.execute(
                text("SELECT count(*) FROM stock_prices WHERE symbol = :s"),
                {"s": "_T_TASK"},
            )
        ).scalar()
        assert int(n or 0) >= 2


def test_sync_ohlcv_one_task_has_autoretry_for_http() -> None:
    """task 設定：autoretry on httpx.HTTPError + max_retries=3。"""
    task = sync_ohlcv_mod.sync_ohlcv_one
    assert task.max_retries == 3
    autoretry = getattr(task, "autoretry_for", ()) or ()
    # celery 在 task wrapper 上會把 autoretry_for 存成 tuple
    assert any(issubclass(httpx.HTTPError, e) or e is httpx.HTTPError for e in autoretry)


@pytest.mark.asyncio
async def test_sync_ohlcv_tw_all_fans_out_in_batches(
    rw_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """fan_out 應從 stock_list 撈 active TW symbols，並對每個 symbol 排程 task。"""
    dispatched: list[tuple[Any, dict[str, Any]]] = []

    def _fake_apply_async(args: Any = None, **kwargs: Any) -> None:
        dispatched.append((args, kwargs))

    monkeypatch.setattr(sync_ohlcv_mod.sync_ohlcv_one, "apply_async", _fake_apply_async)

    result = await sync_ohlcv_mod._async_fan_out_market(["TWSE", "TPEX"], batch_size=2, days_back=5)

    # 至少 fixture 注入的 3 支 _T_FANOUT_* + 任何已存在的真實 stock
    # 我們只驗：dispatched 數量 == result["count"]，且每筆 args[0] 是 string symbol
    assert result["count"] >= 3
    assert len(dispatched) == result["count"]
    for args, kwargs in dispatched:
        assert isinstance(args, list)
        assert len(args) == 3  # symbol, market, days_back
        assert isinstance(args[0], str)
        assert args[2] == 5
        assert kwargs.get("countdown", 0) >= 0


@pytest.mark.asyncio
async def test_sync_ohlcv_failure_writes_dlq(monkeypatch: pytest.MonkeyPatch) -> None:
    """模擬 task_failure signal → DLQ 寫入。"""
    from contextlib import contextmanager

    from app.workers import dlq

    class _MS:
        def __init__(self) -> None:
            self.added: list[Any] = []
            self.committed = False

        def add(self, x: Any) -> None:
            self.added.append(x)

        def commit(self) -> None:
            self.committed = True

        def rollback(self) -> None:
            pass

        def close(self) -> None:
            pass

    ms = _MS()

    @contextmanager
    def _ctx():
        yield ms

    monkeypatch.setattr(dlq, "sync_rw_session", _ctx)

    class _Sender:
        name = "app.workers.tasks.sync_ohlcv.sync_ohlcv_one"
        request = type("R", (), {"retries": 2})()

    class _Einfo:
        traceback = "tb-content"

    dlq.write_to_dlq(
        sender=_Sender(),
        task_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        exception=httpx.HTTPError("boom"),
        args=["_T_TASK", "TWSE", 7],
        kwargs={},
        einfo=_Einfo(),
    )

    assert len(ms.added) == 1
    assert ms.committed is True
    row = ms.added[0]
    assert row.task_name == "app.workers.tasks.sync_ohlcv.sync_ohlcv_one"
    assert row.retry_count == 2
    assert row.resolved is False
