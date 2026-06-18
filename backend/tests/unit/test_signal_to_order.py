"""signal_to_pending_order 單元測試 — PLAN 第 10 / 15 章。

不依賴 DB（純 in-memory 物件建構）。
"""

from __future__ import annotations

import uuid as _uuid
from decimal import Decimal

import pytest

from app.agents.managers.orders_decision import (
    DEFAULT_NOTIONAL_USD,
    calculate_qty,
    signal_to_pending_order,
)

pytestmark = pytest.mark.unit


def _signal(action: str, **extras: object) -> dict:
    base = {
        "action": action,
        "confidence": 75,
        "target_price_low": Decimal("100"),
        "target_price_high": Decimal("120"),
        "stop_loss": Decimal("90"),
    }
    base.update(extras)
    return base


def test_hold_returns_none() -> None:
    out = signal_to_pending_order(
        _signal("HOLD"),
        analysis_id=_uuid.uuid4(),
        user_id=_uuid.uuid4(),
        symbol="2330",
        market="TWSE",
    )
    assert out is None


def test_buy_creates_pending_order() -> None:
    user_id = _uuid.uuid4()
    analysis_id = _uuid.uuid4()
    order = signal_to_pending_order(
        _signal("BUY"),
        analysis_id=analysis_id,
        user_id=user_id,
        symbol="2330",
        market="TWSE",
    )
    assert order is not None
    assert order.user_id == user_id
    assert order.analysis_id == analysis_id
    assert order.symbol == "2330"
    assert order.market == "TWSE"
    assert order.side == "BUY"
    assert order.qty > 0
    assert order.target_price == Decimal("100")
    assert order.stop_loss == Decimal("90")
    assert order.take_profit == Decimal("120")
    assert order.status == "PENDING"
    assert order.version == 1


def test_sell_creates_short_pending_order() -> None:
    """SELL 也應建單（同 schema，side=SELL）。"""
    order = signal_to_pending_order(
        _signal("SELL", target_price_low=Decimal("200")),
        analysis_id=_uuid.uuid4(),
        user_id=_uuid.uuid4(),
        symbol="AAPL",
        market="NASDAQ",
    )
    assert order is not None
    assert order.side == "SELL"
    assert order.target_price == Decimal("200")


def test_qty_calculated_from_target_price() -> None:
    """DEFAULT_NOTIONAL_USD / target_price = qty（floor）。"""
    # 100 USD/股，預算 10000 → 100 股
    qty = calculate_qty(Decimal("100"))
    assert qty == int(DEFAULT_NOTIONAL_USD / Decimal("100"))

    # target_price None → 至少 1 股（保留訂單骨架）
    assert calculate_qty(None) == 1
    # target_price 0 / 負數 → 1 股
    assert calculate_qty(Decimal("0")) == 1
    assert calculate_qty(Decimal("-1")) == 1


def test_qty_tw_rounds_to_whole_lots() -> None:
    """台股以「整張」(1000 股) 為單位：無條件捨去到整張、至少 1 張。"""
    # 100000 / 50 = 2000 → 2 張 = 2000 股
    assert calculate_qty(Decimal("50"), market="TWSE") == 2000
    assert calculate_qty(Decimal("50"), market="TPEX") == 2000
    # 高價股 100000 / 600 ≈ 166 股 → 不足一張 → 補到 1 張
    assert calculate_qty(Decimal("600"), market="TWSE") == 1000
    # 缺價 → 至少 1 張（骨架單）
    assert calculate_qty(None, market="TWSE") == 1000
    # 整張保證可被 1000 整除
    assert calculate_qty(Decimal("123"), market="TWSE") % 1000 == 0


def test_qty_us_per_share_unchanged() -> None:
    """美股仍以「股」為單位、至少 1 股（行為不變）。"""
    assert calculate_qty(Decimal("100"), market="NASDAQ") == 100  # 10000 / 100
    assert calculate_qty(None, market="NASDAQ") == 1


def test_pending_order_status_pending_and_uuid() -> None:
    order = signal_to_pending_order(
        _signal("BUY"),
        analysis_id=_uuid.uuid4(),
        user_id=_uuid.uuid4(),
        symbol="0050",
        market="TWSE",
    )
    assert order is not None
    assert order.status == "PENDING"
    assert isinstance(order.id, _uuid.UUID)


def test_invalid_action_raises_value_error() -> None:
    with pytest.raises(ValueError):
        signal_to_pending_order(
            {"action": "WAT"},
            analysis_id=_uuid.uuid4(),
            user_id=_uuid.uuid4(),
            symbol="2330",
            market="TWSE",
        )


def test_empty_signal_returns_none() -> None:
    """None / 空 dict → 不建單。"""
    assert (
        signal_to_pending_order(
            None,
            analysis_id=_uuid.uuid4(),
            user_id=_uuid.uuid4(),
            symbol="2330",
            market="TWSE",
        )
        is None
    )
