"""backtest_service.run_backtest PIT / 指標正確性單元測試。

重點：
- buy_and_hold 權益比＝價格比（精準）
- 無前視：改「最後一天」收盤，不得改變先前任何一天的權益
- 策略只在持有日承受報酬（現金日報酬 0）
- 暖身視窗：曲線自 window_start 起、初始資本正確
- Sharpe/最大回撤/勝率 合理
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.backtest_service import STRATEGIES, run_backtest

pytestmark = pytest.mark.unit

D0 = date(2026, 1, 1)


def _dates(n: int) -> list[date]:
    return [D0 + timedelta(days=i) for i in range(n)]


def test_buy_and_hold_equity_ratio_equals_price_ratio() -> None:
    closes = [100.0, 110.0, 121.0, 133.1]  # 每日 +10%
    dates = _dates(len(closes))
    out = run_backtest(dates, closes, strategy="buy_and_hold", window_start=D0)
    assert out["curve"][0]["equity"] == 1_000_000.0
    # 末值 = 初值 * 133.1/100
    assert abs(out["curve"][-1]["equity"] - 1_000_000.0 * 1.331) < 1.0
    assert abs(out["metrics"]["total_return"] - 0.331) < 1e-6
    assert out["metrics"]["num_trades"] == 1


def test_no_lookahead_last_day_change_does_not_affect_earlier_equity() -> None:
    """改最後一天收盤，先前每一天的權益必須完全不變（無前視鐵證）。"""
    base = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 110.0]
    dates = _dates(len(base))
    for strat in STRATEGIES:
        a = run_backtest(dates, base, strategy=strat, window_start=D0)
        bumped = list(base)
        bumped[-1] = 999.0  # 只動最後一天
        b = run_backtest(dates, bumped, strategy=strat, window_start=D0)
        eq_a = [c["equity"] for c in a["curve"]]
        eq_b = [c["equity"] for c in b["curve"]]
        # 除最後一天外，全部相等
        assert eq_a[:-1] == eq_b[:-1], f"{strat} 有前視：改末日影響了先前權益"


def test_cash_days_earn_zero() -> None:
    """sma_cross 在暖身/未站上均線期間為現金 → 那些日報酬 0，權益持平。"""
    # 前 20 天下跌（不會站上長均線），權益應維持初始資本（現金）
    closes = [100.0 - i for i in range(25)]
    dates = _dates(len(closes))
    out = run_backtest(dates, closes, strategy="sma_cross", window_start=D0)
    # 下跌盤 SMA5<SMA20 全程持現金 → 權益不變
    assert out["curve"][-1]["equity"] == 1_000_000.0
    assert out["metrics"]["total_return"] == 0.0
    assert out["metrics"]["num_trades"] == 0


def test_warmup_window_start_after_history() -> None:
    """window_start 在序列中間 → 曲線自該日起、初始資本正確、暖身資料不列入曲線。"""
    closes = [100.0 + i for i in range(40)]
    dates = _dates(len(closes))
    ws = D0 + timedelta(days=20)
    out = run_backtest(dates, closes, strategy="buy_and_hold", window_start=ws)
    assert out["curve"][0]["date"] == ws.isoformat()
    assert out["curve"][0]["equity"] == 1_000_000.0
    # 曲線長度 = 從 index20 到 39 = 20 根
    assert out["trading_days"] == 20


def test_benchmark_always_buy_and_hold() -> None:
    closes = [100.0, 105.0, 110.0, 108.0, 115.0]
    dates = _dates(len(closes))
    out = run_backtest(dates, closes, strategy="rsi_mean_reversion", window_start=D0)
    # 基準線末值 = 初值 * 115/100
    assert abs(out["benchmark_curve"][-1]["equity"] - 1_000_000.0 * 1.15) < 1.0
    assert abs(out["benchmark_metrics"]["total_return"] - 0.15) < 1e-6


def test_drawdown_is_non_positive_and_tracks_peak() -> None:
    closes = [100.0, 120.0, 90.0, 95.0]  # 高點120後跌到90 = -25%
    dates = _dates(len(closes))
    out = run_backtest(dates, closes, strategy="buy_and_hold", window_start=D0)
    dds = [c["drawdown"] for c in out["curve"]]
    assert all(d <= 0.0 for d in dds)
    assert abs(out["metrics"]["max_drawdown"] - (-0.25)) < 1e-3


def test_rsi_enters_on_oversold_and_profits() -> None:
    """先重跌觸發 RSI<30 進場，之後反彈 → 應有交易且獲利。"""
    down = [100.0 - i * 3 for i in range(15)]  # 連跌 → RSI 低
    up = [down[-1] + i * 4 for i in range(1, 15)]  # 強彈
    closes = down + up
    dates = _dates(len(closes))
    out = run_backtest(dates, closes, strategy="rsi_mean_reversion", window_start=D0)
    assert out["metrics"]["num_trades"] >= 1
    # 反彈段持有 → 總報酬為正
    assert out["metrics"]["total_return"] > 0


def test_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError):
        run_backtest(_dates(3), [1.0, 2.0, 3.0], strategy="nope", window_start=D0)
