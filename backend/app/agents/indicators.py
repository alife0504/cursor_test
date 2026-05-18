"""技術指標計算 — 純 numpy / pandas，不依賴 ta-lib（Windows 安裝痛苦）。

依 PLAN.md 第 18.2 章 + Phase 13 prompt 條 M。

設計：
- 函數輸入皆接受 `list[float|str]` 或 `np.ndarray`，內部統一轉 float numpy array。
- 計算結果亦回 list[float|None]（None 表示資料不足；JSON 友善）。
- 容錯：輸入長度不足時不 raise，回相對應長度的 None list。
- 不做 lookahead：每個指標只用「當下與之前」的資料。

提供的指標：
- RSI(period=14)
- MACD(fast=12, slow=26, signal=9)
- KD / Stochastic(period=9)
- BBANDS(period=20, std=2)
- MA(period)

主要 entry point：
  `compute_indicators(ohlcv: list[dict]) -> dict[str, Any]`
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ── 內部 utility ────────────────────────────────────────


def _to_float_array(seq: list[Any] | np.ndarray) -> np.ndarray:
    """容錯轉 float array — 接受 None / str / Decimal。"""
    out: list[float] = []
    for x in seq:
        if x is None:
            out.append(math.nan)
            continue
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            out.append(math.nan)
    return np.asarray(out, dtype=np.float64)


def _list_with_none(arr: np.ndarray) -> list[float | None]:
    """NaN → None；用於 JSON 序列化。"""
    return [None if math.isnan(v) else float(v) for v in arr]


# ── 單一指標 ────────────────────────────────────────────


def compute_rsi(closes: list[float] | np.ndarray, period: int = 14) -> list[float | None]:
    """RSI (Relative Strength Index)，採 Wilder 平滑（pandas EWM alpha=1/period）。"""
    arr = _to_float_array(closes)
    n = len(arr)
    if n < period + 1:
        return [None] * n

    delta = np.diff(arr)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)

    # Wilder 平滑 = EMA with alpha=1/period
    s_gain = pd.Series(gain).ewm(alpha=1 / period, adjust=False).mean().to_numpy()
    s_loss = pd.Series(loss).ewm(alpha=1 / period, adjust=False).mean().to_numpy()

    rs = np.divide(s_gain, s_loss, out=np.full_like(s_gain, np.inf), where=s_loss != 0)
    rsi = 100 - (100 / (1 + rs))

    # 前 period 個值 NaN（資料不足）
    result = np.full(n, np.nan)
    result[1:] = rsi
    result[:period] = np.nan
    return _list_with_none(result)


def compute_macd(
    closes: list[float] | np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> dict[str, list[float | None]]:
    """MACD：(MACD line, Signal line, Histogram)。"""
    arr = _to_float_array(closes)
    n = len(arr)
    if n < slow:
        empty = [None] * n
        return {"macd": list(empty), "signal": list(empty), "hist": list(empty)}

    series = pd.Series(arr)
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = (ema_fast - ema_slow).to_numpy()
    signal_line = pd.Series(macd_line).ewm(span=signal_period, adjust=False).mean().to_numpy()
    hist = macd_line - signal_line

    # 前 slow-1 個值資料不足
    macd_line[: slow - 1] = np.nan
    signal_line[: slow + signal_period - 2] = np.nan
    hist[: slow + signal_period - 2] = np.nan

    return {
        "macd": _list_with_none(macd_line),
        "signal": _list_with_none(signal_line),
        "hist": _list_with_none(hist),
    }


def compute_kd(
    highs: list[float] | np.ndarray,
    lows: list[float] | np.ndarray,
    closes: list[float] | np.ndarray,
    period: int = 9,
) -> dict[str, list[float | None]]:
    """KD (Stochastic Oscillator)：%K + %D（台股慣例 K = 9-day, D = 3-day SMA of K）。"""
    h = _to_float_array(highs)
    low = _to_float_array(lows)
    c = _to_float_array(closes)
    n = len(c)
    if n < period:
        return {"k": [None] * n, "d": [None] * n}

    k_vals = np.full(n, np.nan)
    for i in range(period - 1, n):
        window_high = h[i - period + 1 : i + 1].max()
        window_low = low[i - period + 1 : i + 1].min()
        if window_high == window_low:
            k_vals[i] = 50.0
        else:
            k_vals[i] = 100 * (c[i] - window_low) / (window_high - window_low)

    # 台股慣例：D = 3-day SMA of K
    d_vals = pd.Series(k_vals).rolling(window=3, min_periods=3).mean().to_numpy()

    return {"k": _list_with_none(k_vals), "d": _list_with_none(d_vals)}


def compute_bbands(
    closes: list[float] | np.ndarray,
    period: int = 20,
    std_dev: float = 2.0,
) -> dict[str, list[float | None]]:
    """Bollinger Bands：上、中、下軌 + 帶寬。"""
    arr = _to_float_array(closes)
    n = len(arr)
    if n < period:
        return {
            "upper": [None] * n,
            "middle": [None] * n,
            "lower": [None] * n,
            "width": [None] * n,
        }
    series = pd.Series(arr)
    middle = series.rolling(window=period, min_periods=period).mean()
    std = series.rolling(window=period, min_periods=period).std(ddof=0)
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    width = upper - lower

    return {
        "upper": _list_with_none(upper.to_numpy()),
        "middle": _list_with_none(middle.to_numpy()),
        "lower": _list_with_none(lower.to_numpy()),
        "width": _list_with_none(width.to_numpy()),
    }


def compute_ma(closes: list[float] | np.ndarray, period: int) -> list[float | None]:
    """Simple Moving Average。"""
    arr = _to_float_array(closes)
    if len(arr) < period:
        return [None] * len(arr)
    series = pd.Series(arr)
    out = series.rolling(window=period, min_periods=period).mean().to_numpy()
    return _list_with_none(out)


# ── 主 entry：compute_indicators ──────────────────────────


def compute_indicators(ohlcv: list[dict[str, Any]]) -> dict[str, Any]:
    """從 OHLCV list 計算所有常用指標，回最新一筆 + 完整序列。

    Args:
        ohlcv: list of {date, open, high, low, close, volume}（由舊到新）。

    Returns:
        {
          "latest": {"rsi", "macd", "macd_signal", "macd_hist", "k", "d",
                     "bb_upper", "bb_middle", "bb_lower", "ma20", "ma60",
                     "close", "volume_avg_20"},
          "series": {... full lists ...},
          "stats": {"price_low", "price_high", "price_last", "cum_return_pct"}
        }
    """
    if not ohlcv:
        return {"latest": {}, "series": {}, "stats": {}, "rows": 0}

    closes = [r.get("close") for r in ohlcv]
    highs = [r.get("high") for r in ohlcv]
    lows = [r.get("low") for r in ohlcv]
    volumes = [r.get("volume") or 0 for r in ohlcv]

    rsi = compute_rsi(closes, 14)
    macd = compute_macd(closes)
    kd = compute_kd(highs, lows, closes, 9)
    bb = compute_bbands(closes, 20, 2.0)
    ma20 = compute_ma(closes, 20)
    ma60 = compute_ma(closes, 60)

    # 統計
    closes_arr = _to_float_array(closes)
    valid_closes = closes_arr[~np.isnan(closes_arr)]
    price_low = float(valid_closes.min()) if valid_closes.size else None
    price_high = float(valid_closes.max()) if valid_closes.size else None
    price_last = float(valid_closes[-1]) if valid_closes.size else None
    cum_return_pct = None
    if valid_closes.size >= 2 and valid_closes[0] > 0:
        cum_return_pct = float((valid_closes[-1] / valid_closes[0] - 1) * 100)

    volumes_arr = _to_float_array(volumes)
    volume_avg_20 = None
    if len(volumes_arr) >= 20:
        volume_avg_20 = float(np.nanmean(volumes_arr[-20:]))

    def _last(seq: list[float | None]) -> float | None:
        for v in reversed(seq):
            if v is not None:
                return v
        return None

    latest = {
        "rsi": _last(rsi),
        "macd": _last(macd["macd"]),
        "macd_signal": _last(macd["signal"]),
        "macd_hist": _last(macd["hist"]),
        "k": _last(kd["k"]),
        "d": _last(kd["d"]),
        "bb_upper": _last(bb["upper"]),
        "bb_middle": _last(bb["middle"]),
        "bb_lower": _last(bb["lower"]),
        "ma20": _last(ma20),
        "ma60": _last(ma60),
        "close": price_last,
        "volume_avg_20": volume_avg_20,
    }

    return {
        "latest": latest,
        "series": {
            "rsi": rsi,
            "macd": macd["macd"],
            "macd_signal": macd["signal"],
            "macd_hist": macd["hist"],
            "k": kd["k"],
            "d": kd["d"],
            "bb_upper": bb["upper"],
            "bb_middle": bb["middle"],
            "bb_lower": bb["lower"],
            "ma20": ma20,
            "ma60": ma60,
        },
        "stats": {
            "price_low": price_low,
            "price_high": price_high,
            "price_last": price_last,
            "cum_return_pct": cum_return_pct,
        },
        "rows": len(ohlcv),
    }


__all__ = [
    "compute_bbands",
    "compute_indicators",
    "compute_kd",
    "compute_ma",
    "compute_macd",
    "compute_rsi",
]
