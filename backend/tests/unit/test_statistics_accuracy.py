"""statistics_service.score_analyses PIT 正確性單元測試。

重點：
- BUY/SELL 命中方向正確
- 報酬視窗未過完 → pending（不硬湊未來）
- 無價格 / 容差窗外缺口 → no_data
- 進出場容差窗選 bar 正確
- 彙總 hit_rate / avg_return 正確
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.services.statistics_service import score_analyses

pytestmark = pytest.mark.unit


def _dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 1, 0, tzinfo=UTC)


def _series(start: date, closes: list[float]) -> list[tuple[date, Decimal]]:
    """自 start 起連續日曆天的 (date, close)。"""
    return [(start + timedelta(days=i), Decimal(str(c))) for i, c in enumerate(closes)]


D0 = date(2026, 1, 1)


def test_buy_hit_when_price_rises() -> None:
    # D0=100，30 天後 110 → BUY 命中
    prices = {"AAA": _series(D0, [100.0 + i * 0.5 for i in range(40)])}
    a = [{"id": "1", "symbol": "AAA", "signal": "BUY", "confidence": 0.7, "created_at": _dt(D0)}]
    out = score_analyses(a, prices, horizon_days=30)
    row = out["rows"][0]
    assert row["status"] == "scored"
    assert row["entry_price"] == 100.0
    assert row["hit"] is True
    assert row["actual_return"] > 0
    assert out["buy"]["scored"] == 1 and out["buy"]["hits"] == 1
    assert out["buy"]["hit_rate"] == 1.0


def test_buy_miss_when_price_falls() -> None:
    prices = {"AAA": _series(D0, [100.0 - i * 0.5 for i in range(40)])}
    a = [{"id": "1", "symbol": "AAA", "signal": "BUY", "confidence": 0.7, "created_at": _dt(D0)}]
    out = score_analyses(a, prices, horizon_days=30)
    assert out["rows"][0]["hit"] is False
    assert out["buy"]["hits"] == 0 and out["buy"]["hit_rate"] == 0.0


def test_sell_hit_when_price_falls() -> None:
    # SELL：跌 → 命中
    prices = {"BBB": _series(D0, [100.0 - i * 0.5 for i in range(40)])}
    a = [{"id": "2", "symbol": "BBB", "signal": "SELL", "confidence": 0.6, "created_at": _dt(D0)}]
    out = score_analyses(a, prices, horizon_days=30)
    row = out["rows"][0]
    assert row["hit"] is True
    assert row["actual_return"] < 0
    assert out["sell"]["hits"] == 1 and out["sell"]["hit_rate"] == 1.0


def test_sell_miss_when_price_rises() -> None:
    prices = {"BBB": _series(D0, [100.0 + i * 0.5 for i in range(40)])}
    a = [{"id": "2", "symbol": "BBB", "signal": "SELL", "confidence": 0.6, "created_at": _dt(D0)}]
    out = score_analyses(a, prices, horizon_days=30)
    assert out["rows"][0]["hit"] is False
    assert out["sell"]["hits"] == 0


def test_pending_when_window_not_elapsed() -> None:
    """只有 D0 前後 10 天資料、horizon=30 → 出場日尚未到 → pending，不計分。"""
    prices = {"AAA": _series(D0, [100.0 + i for i in range(10)])}
    a = [{"id": "1", "symbol": "AAA", "signal": "BUY", "confidence": 0.8, "created_at": _dt(D0)}]
    out = score_analyses(a, prices, horizon_days=30)
    assert out["rows"][0]["status"] == "pending"
    assert out["pending"] == 1
    assert out["buy"]["scored"] == 0  # 未過完不得計分（PIT）


def test_no_data_when_symbol_missing() -> None:
    a = [{"id": "1", "symbol": "ZZZ", "signal": "BUY", "confidence": 0.8, "created_at": _dt(D0)}]
    out = score_analyses(a, {}, horizon_days=30)
    assert out["rows"][0]["status"] == "no_data"
    assert out["no_data"] == 1


def test_horizon_counts_trading_days_not_calendar() -> None:
    """horizon 用「交易日」(bar)計數而非日曆天：日期間有假日缺口不影響 bar 數。"""
    # 5 根 bar，日期不連續（含週末/假日跳空）；horizon=3 → 出場＝進場後第 3 根 bar（index 3）。
    ds = [
        D0,
        D0 + timedelta(days=1),
        D0 + timedelta(days=4),  # 跳過週末
        D0 + timedelta(days=5),
        D0 + timedelta(days=6),
    ]
    closes = [Decimal(c) for c in ("100", "101", "102", "103", "110")]
    prices = {"AAA": list(zip(ds, closes, strict=True))}
    a = [{"id": "1", "symbol": "AAA", "signal": "BUY", "confidence": 0.5, "created_at": _dt(D0)}]
    out = score_analyses(a, prices, horizon_days=3)
    row = out["rows"][0]
    assert row["status"] == "scored"
    assert row["entry_date"] == D0.isoformat()  # index 0
    assert row["exit_date"] == (D0 + timedelta(days=5)).isoformat()  # index 3（非 D0+3 日曆）
    assert abs(row["actual_return"] - (103.0 / 100.0 - 1)) < 1e-9


def test_exit_is_nth_trading_bar_after_entry() -> None:
    """出場＝進場後第 N 個交易 bar（index）；缺一天不影響 bar 計數。"""
    full = _series(D0, [100.0 + i for i in range(41)])
    bars = [b for b in full if b[0] != D0 + timedelta(days=30)]  # 挖掉一天 → index 30 = D0+31
    prices = {"AAA": bars}
    a = [{"id": "1", "symbol": "AAA", "signal": "BUY", "confidence": 0.5, "created_at": _dt(D0)}]
    out = score_analyses(a, prices, horizon_days=30)
    row = out["rows"][0]
    assert row["status"] == "scored"
    assert row["exit_date"] == (D0 + timedelta(days=31)).isoformat()


def test_aggregate_hit_rate_and_avg_return() -> None:
    """兩檔 BUY：一命中(+10%)一失誤(-10%) → hit_rate=0.5、avg_return=0。"""
    # 31 根連續 bar；進場 index0=100、出場 index30=110/90（horizon=30 交易日）。
    up_c = [Decimal("100")] * 30 + [Decimal("110")]
    dn_c = [Decimal("100")] * 30 + [Decimal("90")]
    ds = [D0 + timedelta(days=i) for i in range(31)]
    prices = {
        "UP": list(zip(ds, up_c, strict=True)),
        "DN": list(zip(ds, dn_c, strict=True)),
    }
    a = [
        {"id": "1", "symbol": "UP", "signal": "BUY", "confidence": 0.7, "created_at": _dt(D0)},
        {"id": "2", "symbol": "DN", "signal": "BUY", "confidence": 0.7, "created_at": _dt(D0)},
    ]
    out = score_analyses(a, prices, horizon_days=30)
    assert out["buy"]["scored"] == 2
    assert out["buy"]["hits"] == 1
    assert out["buy"]["hit_rate"] == 0.5
    assert abs(out["buy"]["avg_return"]) < 1e-9  # (+0.1 -0.1)/2 = 0
    assert out["overall"]["hit_rate"] == 0.5
