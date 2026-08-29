"""月營收動能（基本面）/ 籌碼動能（籌碼面）衍生算式單元測試。

這兩個衍生是「工具層資料豐富化」中我方保證正確的部分（純算術、PIT 安全）：
- 只用「已公告/已發生的過去資料」做統計，不偷看未來（PIT 由 caller 的 available_at<=pit 閘門保證）。
- LLM 對這些訊號的解讀屬決策層，不在本測試範圍。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.agents.analysts.chip_analyst import _derive_chip_momentum
from app.agents.analysts.fundamental_analyst import _derive_revenue_momentum

pytestmark = pytest.mark.unit


# ── 月營收動能 ──────────────────────────────────────


def _mo(*yoys: float | None) -> list[dict]:
    """由舊到新的月營收列（只放 revenue_yoy）。"""
    return [{"revenue_yoy": (str(y) if y is not None else None)} for y in yoys]


def test_revenue_momentum_empty_when_no_yoy() -> None:
    assert _derive_revenue_momentum([]) == {}
    assert _derive_revenue_momentum(_mo(None, None)) == {}


def test_revenue_momentum_consecutive_growth_streak() -> None:
    # 由舊到新：-2, 5, 8, 12 → 最新為正，連續正成長 3 個月（-2 打斷）
    out = _derive_revenue_momentum(_mo(-2, 5, 8, 12))
    assert out["yoy_latest"] == Decimal("12")
    assert out["streak_months"] == 3
    assert out["streak_dir"] == "成長"
    assert out["trend"] == "加速"  # 12 > 8


def test_revenue_momentum_decline_streak_and_deceleration() -> None:
    out = _derive_revenue_momentum(_mo(10, -3, -5, -8))
    assert out["streak_dir"] == "衰退"
    assert out["streak_months"] == 3
    assert out["trend"] == "減速"  # -8 < -5


def test_revenue_momentum_3m_avg() -> None:
    out = _derive_revenue_momentum(_mo(0, 6, 9, 15))
    # 近 3 月 = 6, 9, 15 → 平均 10
    assert out["yoy_3m_avg"] == Decimal("10")


# ── 籌碼動能 ──────────────────────────────────────


def _inst(*foreign_nets: int) -> list[dict]:
    """由舊到新的三大法人列（只放 foreign_net / trust_net=0）。"""
    return [{"foreign_net": fn, "trust_net": 0} for fn in foreign_nets]


def test_chip_momentum_empty_when_no_data() -> None:
    assert _derive_chip_momentum([], []) == {}


def test_chip_momentum_foreign_consecutive_buy_streak() -> None:
    # 由舊到新：-100, 200, 300, 500 → 最新買超，連續買超 3 日
    out = _derive_chip_momentum(_inst(-100, 200, 300, 500), [])
    assert out["foreign_streak"] == 3
    assert out["foreign_streak_dir"] == "買超"
    # 近 5 日淨額 = -100+200+300+500 = 900
    assert out["foreign_net_5d"] == Decimal("900")


def test_chip_momentum_foreign_consecutive_sell_streak() -> None:
    out = _derive_chip_momentum(_inst(100, -200, -300), [])
    assert out["foreign_streak"] == 2
    assert out["foreign_streak_dir"] == "賣超"


def test_chip_momentum_margin_trend() -> None:
    margin_up = [{"margin_balance": 1000}, {"margin_balance": 1500}]
    margin_down = [{"margin_balance": 2000}, {"margin_balance": 1200}]
    assert _derive_chip_momentum(_inst(1), margin_up)["margin_trend"] == "增加"
    assert _derive_chip_momentum(_inst(1), margin_down)["margin_trend"] == "減少"
