"""technical indicators unit tests — Phase 13 條 O（≥ 8 個測試）。

不依賴外部資料；用合成序列驗證 RSI / MACD / KD / BBANDS / MA 的正確性與容錯。
"""

from __future__ import annotations

import math

import pytest

from app.agents.indicators import (
    compute_bbands,
    compute_indicators,
    compute_kd,
    compute_ma,
    compute_macd,
    compute_rsi,
)

pytestmark = pytest.mark.unit


# ── RSI ────────────────────────────────────────────────


def test_rsi_known_values() -> None:
    """連續上漲 → RSI 應趨近 100；連續下跌 → 接近 0。"""
    up = list(range(1, 50))
    rsi = compute_rsi(up, period=14)
    last = [v for v in rsi if v is not None][-1]
    assert last > 90, f"連續上漲 RSI 應 > 90，實際 {last}"

    down = list(range(50, 1, -1))
    rsi_d = compute_rsi(down, period=14)
    last_d = [v for v in rsi_d if v is not None][-1]
    assert last_d < 10, f"連續下跌 RSI 應 < 10，實際 {last_d}"


def test_rsi_handles_short_series() -> None:
    """資料少於 period+1 → 全 None。"""
    rsi = compute_rsi([1, 2, 3], period=14)
    assert all(v is None for v in rsi)
    assert len(rsi) == 3


# ── MACD ───────────────────────────────────────────────


def test_macd_signal_crossover_detected() -> None:
    """簡單上升序列：MACD line 應上穿 signal（hist > 0）。"""
    closes = [float(x) for x in range(1, 60)]
    m = compute_macd(closes)
    last_hist = [v for v in m["hist"] if v is not None][-1]
    assert last_hist > 0, f"上升序列最後 hist 應 > 0，實際 {last_hist}"


def test_macd_handles_short_series() -> None:
    """資料 < slow（26）→ 全 None。"""
    m = compute_macd([1.0, 2.0, 3.0])
    assert all(v is None for v in m["macd"])


# ── KD ─────────────────────────────────────────────────


def test_kd_overbought() -> None:
    """收盤接近高點 → K 接近 100。"""
    n = 30
    highs = [100.0 + i * 0.5 for i in range(n)]
    lows = [98.0 + i * 0.5 for i in range(n)]
    closes = [99.9 + i * 0.5 for i in range(n)]  # 接近 high
    kd = compute_kd(highs, lows, closes, period=9)
    k_last = [v for v in kd["k"] if v is not None][-1]
    assert k_last > 80, f"收盤近高點 K 應 > 80，實際 {k_last}"


def test_kd_handles_flat_window() -> None:
    """window high==low → K 應為 50（避免除以 0）。"""
    flat = [10.0] * 12
    kd = compute_kd(flat, flat, flat, period=9)
    # 第 period 個（index 8）起應為 50
    k = kd["k"]
    assert k[8] == 50.0


# ── BBANDS ─────────────────────────────────────────────


def test_bbands_band_width_positive() -> None:
    """有正常波動 → upper > middle > lower。"""
    closes = [100 + (-1) ** i * 2 for i in range(30)]  # 震盪序列
    bb = compute_bbands(closes, period=20, std_dev=2.0)
    valid_upper = [v for v in bb["upper"] if v is not None]
    assert valid_upper, "應有有效值"
    last_u = valid_upper[-1]
    last_m = [v for v in bb["middle"] if v is not None][-1]
    last_l = [v for v in bb["lower"] if v is not None][-1]
    assert last_u > last_m > last_l


# ── MA ─────────────────────────────────────────────────


def test_ma_simple() -> None:
    """SMA 5：[1,2,3,4,5] 平均 = 3.0。"""
    ma = compute_ma([1, 2, 3, 4, 5], period=5)
    assert ma[-1] == 3.0
    # 前 4 個 None
    assert all(v is None for v in ma[:4])


# ── 整合 compute_indicators ──────────────────────────


def test_compute_indicators_empty_input() -> None:
    """空 list 不該爆。"""
    out = compute_indicators([])
    assert out["rows"] == 0
    assert out["latest"] == {}
    assert out["stats"] == {}


def test_compute_indicators_with_realistic_data() -> None:
    """合成 60 日 OHLCV → 應產出 RSI / MACD / KD / MA20 / MA60 等指標。"""
    rows = []
    for i in range(60):
        base = 100.0 + i * 0.5  # 上升趨勢
        rows.append(
            {
                "date": f"2026-01-{(i % 28) + 1:02d}",
                "open": base - 1,
                "high": base + 1,
                "low": base - 2,
                "close": base,
                "volume": 1_000_000 + i * 1000,
            }
        )
    out = compute_indicators(rows)
    latest = out["latest"]
    assert latest["rsi"] is not None and latest["rsi"] > 50
    assert latest["macd"] is not None
    assert latest["ma20"] is not None
    assert latest["ma60"] is not None
    assert out["stats"]["cum_return_pct"] is not None
    assert out["rows"] == 60


def test_compute_indicators_handles_nan_values() -> None:
    """部分 close 為 None → 不該爆，should produce floats where possible."""
    rows = [
        {"close": 100, "high": 101, "low": 99, "volume": 1000},
        {"close": None, "high": None, "low": None, "volume": 1000},
        {"close": 102, "high": 103, "low": 101, "volume": 1000},
    ]
    out = compute_indicators(rows)
    # 不應爆；應該有 rows=3
    assert out["rows"] == 3
    # 大部分 indicator 為 None（資料太少）
    assert out["latest"]["rsi"] is None  # 14-period 不足


def test_compute_indicators_str_decimal_input() -> None:
    """ohlcv 用 str（DB 來的 Decimal 字串）應自動轉 float。"""
    rows = [
        {"close": "100.50", "high": "101.00", "low": "99.00", "volume": 1000} for _ in range(30)
    ]
    out = compute_indicators(rows)
    assert out["stats"]["price_last"] == 100.5
    assert out["latest"]["ma20"] is not None


def test_indicators_no_lookahead() -> None:
    """RSI[t] 不應使用 closes[t+1:]（避免 lookahead bias）。"""
    closes = list(range(1, 50))
    rsi_full = compute_rsi(closes, period=14)
    # 截斷後重算，截斷點之前的值應相同
    rsi_short = compute_rsi(closes[:30], period=14)
    for i in range(len(rsi_short)):
        if rsi_short[i] is None or rsi_full[i] is None:
            continue
        assert math.isclose(rsi_short[i], rsi_full[i], rel_tol=1e-9), (
            f"RSI[{i}] 截斷與全量不一致：short={rsi_short[i]} full={rsi_full[i]}"
        )
