"""自動選股預篩選 — 純函式評分 + AnalysisCreateRequest 雙模式 schema 測試。

只測不碰 DB 的邏輯（select_candidates / target_count / 指標小工具 / schema 驗證）；
DB 撈取部分由整合測試覆蓋。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisCreateRequest
from app.services.screening_service import (
    Candidate,
    _percentile_ranks,
    _rsi,
    _rsi_health,
    _sma,
    select_candidates,
    target_count,
)

pytestmark = pytest.mark.unit


# ── target_count（等級 → 保留檔數，絕對數）──────────────


def test_target_count_absolute() -> None:
    # 預設 settings：low=600 / mid=300 / high=150
    assert target_count("low") == 600
    assert target_count("mid") == 300
    assert target_count("high") == 150


def test_target_count_unknown_falls_back_high() -> None:
    assert target_count("bogus") == target_count("high")


# ── _percentile_ranks ──────────────────────────────────


def test_percentile_ranks_best_is_one() -> None:
    ranks = _percentile_ranks([10.0, 30.0, 20.0])
    assert ranks[1] == 1.0  # 30 最大 → 1.0
    assert ranks[0] == 0.0  # 10 最小 → 0.0
    assert 0.0 < ranks[2] < 1.0


def test_percentile_ranks_none_is_worst() -> None:
    ranks = _percentile_ranks([None, 5.0])
    assert ranks[0] == 0.0
    assert ranks[1] == 1.0


# ── RSI 健康度 ─────────────────────────────────────────


def test_rsi_health_sweet_spot() -> None:
    assert _rsi_health(55.0) == 1.0


def test_rsi_health_penalises_extremes() -> None:
    assert _rsi_health(80.0) == pytest.approx(0.2)  # 超買
    assert _rsi_health(20.0) == pytest.approx(0.2)  # 超賣


def test_rsi_health_none() -> None:
    assert _rsi_health(None) is None


# ── 指標小工具 ─────────────────────────────────────────


def test_sma_needs_enough_bars() -> None:
    assert _sma([1.0, 2.0], 5) is None
    assert _sma([1.0, 2.0, 3.0], 3) == 2.0


def test_rsi_all_gains_is_high() -> None:
    closes = [float(i) for i in range(1, 20)]  # 一路上漲
    assert _rsi(closes, 14) == 100.0


# ── select_candidates（保證比例 + 評分排序）────────────


def _cand(symbol: str, turnover: float, last_close: float = 100.0) -> Candidate:
    return Candidate(
        symbol=symbol,
        market="TWSE",
        last_close=last_close,
        avg_turnover=turnover,
        ma20=last_close,
        ma60=last_close * 0.9,  # 站上季線
        ret20=0.05,
        rsi14=55.0,
        volatility=0.02,
        vol_ratio=1.2,
    )


def test_select_empty_returns_empty() -> None:
    assert select_candidates([], "low") == []


def test_select_returns_all_when_fewer_than_target_sorted() -> None:
    # 8 檔 < high(150) → 全數回傳，且依綜合評分排序（流動性等因子皆隨 index 遞增 → 0008 最前）
    cands = [_cand(f"{i:04d}", turnover=float(i) * 1_000) for i in range(1, 9)]
    kept = select_candidates(cands, "high")
    assert len(kept) == 8
    assert kept[0].symbol == "0008"  # 分數最高排最前


def test_select_caps_at_target_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """候選超過等級數量 → 只取分數最高的前 N。"""
    from app.core.config import settings as _s

    monkeypatch.setattr(_s, "SCREEN_COUNT_HIGH", 3, raising=False)
    cands = [_cand(f"{i:04d}", turnover=float(i) * 1_000) for i in range(1, 9)]
    kept = select_candidates(cands, "high")
    assert len(kept) == 3
    assert {c.symbol for c in kept} == {"0008", "0007", "0006"}


# ── AnalysisCreateRequest 雙模式 ───────────────────────


def test_request_symbol_mode_ok() -> None:
    req = AnalysisCreateRequest(symbol="2330")
    assert req.symbol == "2330"
    assert req.screen_level is None


def test_request_screen_mode_defaults_market_tw() -> None:
    req = AnalysisCreateRequest(screen_level="high")
    assert req.symbol is None
    assert req.screen_level == "high"
    assert req.market == "TW"  # 預設補 TW


def test_request_screen_mode_us() -> None:
    req = AnalysisCreateRequest(screen_level="mid", market="us")
    assert req.market == "US"  # 正規化大寫


def test_request_rejects_both() -> None:
    with pytest.raises(ValidationError):
        AnalysisCreateRequest(symbol="2330", screen_level="high")


def test_request_rejects_neither() -> None:
    with pytest.raises(ValidationError):
        AnalysisCreateRequest()


def test_request_rejects_bad_level() -> None:
    with pytest.raises(ValidationError):
        AnalysisCreateRequest(screen_level="extreme")


def test_request_rejects_bad_market() -> None:
    with pytest.raises(ValidationError):
        AnalysisCreateRequest(screen_level="low", market="JP")
