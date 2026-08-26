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


def test_gap_beyond_tolerance_is_no_data() -> None:
    """出場目標日附近（容差窗）無 bar，但更遠處有資料 → 視為資料缺口 no_data，不亂抓遠 bar。"""
    # 進場段 D0..D0+2，之後跳到 D0+60 才有資料（target=D0+30 附近容差 14 天內無 bar）
    bars = _series(D0, [100.0, 101.0, 102.0])
    bars += [(D0 + timedelta(days=60 + i), Decimal("200")) for i in range(5)]
    prices = {"AAA": bars}
    a = [{"id": "1", "symbol": "AAA", "signal": "BUY", "confidence": 0.8, "created_at": _dt(D0)}]
    out = score_analyses(a, prices, horizon_days=30)
    assert out["rows"][0]["status"] == "no_data"
    assert out["no_data"] == 1


def test_exit_picks_first_bar_at_or_after_target_within_tolerance() -> None:
    """出場取 target 起容差窗內「第一根」；holiday 讓 target 當天無 bar 也能取次日。"""
    # D0..D0+40 每日都有，但把 D0+30 當天挖掉（假日）→ 應取 D0+31
    full = _series(D0, [100.0 + i for i in range(41)])
    bars = [b for b in full if b[0] != D0 + timedelta(days=30)]
    prices = {"AAA": bars}
    a = [{"id": "1", "symbol": "AAA", "signal": "BUY", "confidence": 0.5, "created_at": _dt(D0)}]
    out = score_analyses(a, prices, horizon_days=30)
    row = out["rows"][0]
    assert row["status"] == "scored"
    assert row["exit_date"] == (D0 + timedelta(days=31)).isoformat()


def test_aggregate_hit_rate_and_avg_return() -> None:
    """兩檔 BUY：一命中(+10%)一失誤(-10%) → hit_rate=0.5、avg_return=0。"""
    # 精準造 +10% / -10%：進場 100，出場(D0+30 那根) 110 / 90
    prices = {
        "UP": [(D0, Decimal("100")), (D0 + timedelta(days=30), Decimal("110"))],
        "DN": [(D0, Decimal("100")), (D0 + timedelta(days=30), Decimal("90"))],
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
