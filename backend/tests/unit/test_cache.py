"""data_sources.cache 單元測試 — pyarrow serialization + key 規範。

注意：實際 Redis 讀寫測試由 integration 範圍負責，這裡只測：
- key 組裝正確（含 market 防撞）
- DataFrame ↔ parquet bytes round-trip
- 空 DataFrame 也可序列化
- get_cached_ohlcv 在 Redis 異常時 graceful 回 None（mock redis）
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest

from app.data_sources import cache as cache_mod
from app.data_sources.cache import (
    _df_to_parquet_bytes,
    _parquet_bytes_to_df,
    get_cached_ohlcv,
    make_ohlcv_key,
)

pytestmark = pytest.mark.unit


def test_cache_key_includes_market() -> None:
    """key 必須含 market — TWSE 與 NASDAQ 同 symbol 不應撞 key（PLAN P6 第 7 段陷阱）。"""
    k1 = make_ohlcv_key("AAPL", "NASDAQ", date(2026, 4, 1), date(2026, 4, 30))
    k2 = make_ohlcv_key("AAPL", "TWSE", date(2026, 4, 1), date(2026, 4, 30))
    assert k1 != k2
    assert "NASDAQ" in k1
    assert "TWSE" in k2


def test_cache_key_uppercase_symbol() -> None:
    """symbol 統一大寫（aapl == AAPL）。"""
    k1 = make_ohlcv_key("aapl", "NASDAQ", date(2026, 4, 1), date(2026, 4, 30))
    k2 = make_ohlcv_key("AAPL", "NASDAQ", date(2026, 4, 1), date(2026, 4, 30))
    assert k1 == k2


def test_parquet_roundtrip_preserves_basic_types() -> None:
    """DataFrame → parquet bytes → DataFrame 應保留 date / float / int。"""
    df = pd.DataFrame(
        {
            "date": [date(2026, 4, 1), date(2026, 4, 2)],
            "open": [180.5, 181.0],
            "close": [181.0, 182.5],
            "volume": [100, 200],
        }
    )
    buf = _df_to_parquet_bytes(df)
    back = _parquet_bytes_to_df(buf)
    assert len(back) == 2
    assert back.iloc[0]["volume"] == 100
    assert back.iloc[0]["open"] == 180.5


def test_parquet_roundtrip_handles_decimal_via_float_conversion() -> None:
    """Decimal-as-object 自動轉 float（parquet 不支援 object Decimal）。"""
    df = pd.DataFrame(
        {
            "date": [date(2026, 4, 1)],
            "close": [Decimal("181.50")],  # object column
            "volume": [100],
        }
    )
    buf = _df_to_parquet_bytes(df)
    back = _parquet_bytes_to_df(buf)
    assert back.iloc[0]["close"] == 181.5  # float


def test_parquet_handles_empty_df() -> None:
    df = pd.DataFrame({"date": [], "open": [], "high": [], "low": [], "close": [], "volume": []})
    buf = _df_to_parquet_bytes(df)
    back = _parquet_bytes_to_df(buf)
    assert back.empty


def test_df_to_parquet_bytes_rejects_non_df() -> None:
    with pytest.raises(ValueError):
        _df_to_parquet_bytes(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_cached_ohlcv_returns_none_on_redis_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Redis 連線炸 → 不應拋出，回 None（讓主流程繼續）。"""

    class _ExplodingRedis:
        async def get(self, key: str) -> Any:
            raise RuntimeError("simulated redis failure")

    async def fake_get_redis(db: int = 0) -> Any:
        return _ExplodingRedis()

    monkeypatch.setattr(cache_mod, "get_redis", fake_get_redis)
    result = await get_cached_ohlcv("AAPL", "NASDAQ", date(2026, 4, 1), date(2026, 4, 30))
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_ohlcv_returns_none_on_cache_miss(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _EmptyRedis:
        async def get(self, key: str) -> Any:
            return None

    async def fake_get_redis(db: int = 0) -> Any:
        return _EmptyRedis()

    monkeypatch.setattr(cache_mod, "get_redis", fake_get_redis)
    result = await get_cached_ohlcv("AAPL", "NASDAQ", date(2026, 4, 1), date(2026, 4, 30))
    assert result is None
