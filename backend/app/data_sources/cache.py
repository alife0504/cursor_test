"""Data source 24h stale cache — Redis-backed pyarrow parquet bytes。

依 PLAN.md 第 14.3 章「Circuit Breaker + 24h stale cache fallback」+ 第 7 段已知陷阱。

設計：
- 用 Redis db 0（CACHE）儲存，TTL = max_age_hours
- key 格式：`cache:ohlcv:{market}:{symbol}:{start}:{end}` — 含 market 防 NASDAQ 與 TWSE 撞 key
- value 用 pyarrow.parquet serialize（pickle 不安全；parquet bytes 跨語言安全）
- 統一 helper：cache_ohlcv() / get_cached_ohlcv() — 給 DataSourceFallback 當 stale_cache_loader
- 失敗（Redis 連線炸 / 序列化錯）→ log warning，回 None / 不寫入（不應炸主流程）

注意：
- 空 DataFrame 也快取（避免重打 source 抓空）
- parquet 不支援 Decimal-as-object → 寫前轉 float64，讀回保持 float（caller 要 cast 自己處理）
"""

from __future__ import annotations

import contextlib
import io
from datetime import date
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from app.core.logging_config import get_logger
from app.core.redis_client import RedisDB, get_redis

logger = get_logger(__name__)


CACHE_KEY_PREFIX = "cache"
DEFAULT_TTL_HOURS = 24


def make_ohlcv_key(symbol: str, market: str, start: date, end: date) -> str:
    """組 OHLCV cache key。"""
    return (
        f"{CACHE_KEY_PREFIX}:ohlcv:{market}:{symbol.upper()}"
        f":{start.isoformat()}:{end.isoformat()}"
    )


def make_news_key(symbol: str | None, market: str | None, since: date | None) -> str:
    sym = symbol.upper() if symbol else "ALL"
    mk = market or "ALL"
    si = since.isoformat() if since else "ANY"
    return f"{CACHE_KEY_PREFIX}:news:{mk}:{sym}:{si}"


# ── OHLCV cache ───────────────────────────────────────────


async def cache_ohlcv(
    symbol: str,
    market: str,
    df: pd.DataFrame,
    *,
    start: date,
    end: date,
    ttl_hours: int = DEFAULT_TTL_HOURS,
) -> bool:
    """把 OHLCV DataFrame 存入 Redis 24h。

    Returns:
        True 寫入成功；False 失敗（log warning）。
    """
    key = make_ohlcv_key(symbol, market, start, end)
    try:
        payload = _df_to_parquet_bytes(df)
    except Exception as e:
        logger.warning(
            "cache.serialize_failed",
            key=key,
            error_type=type(e).__name__,
            error=str(e),
        )
        return False

    try:
        redis = await get_redis(RedisDB.CACHE)
        await redis.set(key, payload, ex=ttl_hours * 3600)
        return True
    except Exception as e:
        logger.warning(
            "cache.write_failed",
            key=key,
            error_type=type(e).__name__,
            error=str(e),
        )
        return False


async def get_cached_ohlcv(
    symbol: str,
    market: str,
    start: date,
    end: date,
    *,
    max_age_hours: int = DEFAULT_TTL_HOURS,
) -> pd.DataFrame | None:
    """從 Redis 讀 OHLCV DataFrame。

    Args:
        max_age_hours: 不直接檢查（Redis TTL 已處理），保留參數給未來支援「比 TTL 更嚴」用。

    Returns:
        DataFrame 或 None（cache miss / 解析失敗）。
    """
    _ = max_age_hours  # placeholder（Redis TTL 已 expire 過期項）
    key = make_ohlcv_key(symbol, market, start, end)
    try:
        redis = await get_redis(RedisDB.CACHE)
        raw = await redis.get(key)
    except Exception as e:
        logger.warning(
            "cache.read_failed",
            key=key,
            error_type=type(e).__name__,
            error=str(e),
        )
        return None

    if raw is None:
        return None

    # Redis decode_responses=True 會把 bytes decode 成 str → 反向取 bytes
    raw_bytes = raw.encode("latin-1") if isinstance(raw, str) else raw

    try:
        return _parquet_bytes_to_df(raw_bytes)
    except Exception as e:
        logger.warning(
            "cache.deserialize_failed",
            key=key,
            error_type=type(e).__name__,
            error=str(e),
        )
        return None


# ── stale_cache_loader for DataSourceFallback ─────────────


async def ohlcv_stale_cache_loader(*, kind: str, **params: Any) -> pd.DataFrame | None:
    """符合 DataSourceFallback.stale_cache_loader 簽名的 callback。

    僅處理 kind == "ohlcv"，其他 kind 回 None。
    params 由 fallback._call 傳入：{"symbol", "start", "end"}（無 market 時用 "ANY"）。
    """
    if kind != "ohlcv":
        return None
    symbol = params.get("symbol")
    start = params.get("start")
    end = params.get("end")
    market = params.get("market") or "ANY"
    if not symbol or start is None or end is None:
        return None
    return await get_cached_ohlcv(symbol, market, start, end)


# ── parquet bytes helpers ─────────────────────────────────


def _df_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    """DataFrame → parquet bytes（in-memory）。

    Decimal-as-object 轉 float（parquet 不支援 object Decimal）。
    """
    if df is None or not isinstance(df, pd.DataFrame):
        raise ValueError("df 必須為 DataFrame")
    safe = df.copy()
    for col in safe.columns:
        # 處理 Decimal-as-object → float（不能轉的欄位如 str/date 保留原值）
        if safe[col].dtype == object:
            with contextlib.suppress(TypeError, ValueError):
                safe[col] = safe[col].apply(lambda v: float(v) if v is not None else None)

    table = pa.Table.from_pandas(safe, preserve_index=False)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    return buf.getvalue()


def _parquet_bytes_to_df(raw: bytes) -> pd.DataFrame:
    """parquet bytes → DataFrame。"""
    buf = io.BytesIO(raw)
    table = pq.read_table(buf)
    return table.to_pandas()


__all__ = [
    "CACHE_KEY_PREFIX",
    "DEFAULT_TTL_HOURS",
    "cache_ohlcv",
    "get_cached_ohlcv",
    "make_news_key",
    "make_ohlcv_key",
    "ohlcv_stale_cache_loader",
]
