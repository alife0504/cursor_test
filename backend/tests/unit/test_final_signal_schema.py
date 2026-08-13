"""FinalSignal 跨欄位驗證單元測試（schemas.py model_validator）。

不依賴 DB / LLM；純 Pydantic 驗證。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.agents.schemas import FinalSignal

pytestmark = pytest.mark.unit


def _base(**extra: Any) -> dict[str, Any]:
    d: dict[str, Any] = {
        "action": "BUY",
        "confidence": 70,
        "time_horizon": "中期(1-3月)",
        "position_size_pct": Decimal("10"),
        "reasoning_zh": "理" * 200,
        "risk_factors": ["風險一"],
        "debate_winner": "bull",
    }
    d.update(extra)
    return d


def test_valid_buy_signal() -> None:
    s = FinalSignal(
        **_base(
            target_price_low=Decimal("100"),
            target_price_high=Decimal("120"),
            stop_loss=Decimal("90"),
        )
    )
    assert s.action == "BUY"
    assert s.stop_loss == Decimal("90")


def test_target_low_greater_than_high_rejected() -> None:
    with pytest.raises(ValidationError):
        FinalSignal(
            **_base(
                target_price_low=Decimal("120"),
                target_price_high=Decimal("100"),
            )
        )


def test_buy_stop_loss_above_target_rejected() -> None:
    """BUY 的停損高於目標價 = 不自洽，應擋下。"""
    with pytest.raises(ValidationError):
        FinalSignal(
            **_base(
                action="BUY",
                target_price_low=Decimal("100"),
                target_price_high=Decimal("120"),
                stop_loss=Decimal("130"),
            )
        )


def test_sell_stop_loss_below_target_rejected() -> None:
    """SELL 的停損低於目標價 = 不自洽，應擋下。"""
    with pytest.raises(ValidationError):
        FinalSignal(
            **_base(
                action="SELL",
                target_price_low=Decimal("80"),
                target_price_high=Decimal("100"),
                stop_loss=Decimal("70"),
            )
        )


def test_sell_valid_stop_above_target() -> None:
    s = FinalSignal(
        **_base(
            action="SELL",
            target_price_low=Decimal("80"),
            target_price_high=Decimal("100"),
            stop_loss=Decimal("110"),
        )
    )
    assert s.action == "SELL"


def test_hold_no_price_constraint() -> None:
    """HOLD 可不給價位，不受方向約束。"""
    s = FinalSignal(**_base(action="HOLD"))
    assert s.action == "HOLD"


def test_position_pct_with_percent_sign_coerced() -> None:
    s = FinalSignal(**_base(position_size_pct="15%"))
    assert s.position_size_pct == Decimal("15")
