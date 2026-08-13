"""Verifier 純函數核心單元測試（未掛進 graph）。"""

from __future__ import annotations

import json

import pytest

from app.agents.verifier import Verifier, verify_signal

pytestmark = pytest.mark.unit


def _bullish() -> dict[str, str]:
    return {
        "market": json.dumps({"short_term_view": "看多"}),
        "fundamental": json.dumps({"long_term_view": "看多"}),
        "news": json.dumps({"sentiment": "正面"}),
        "sentiment": json.dumps({"market_sentiment": "樂觀"}),
        "chip": json.dumps({"institutional_flow": "大量買超"}),
    }


def _bearish() -> dict[str, str]:
    return {
        "market": json.dumps({"short_term_view": "看空"}),
        "fundamental": json.dumps({"long_term_view": "看空"}),
        "news": json.dumps({"sentiment": "負面"}),
        "sentiment": json.dumps({"market_sentiment": "悲觀"}),
        "chip": json.dumps({"institutional_flow": "大量賣超"}),
    }


def _buy(**extra: object) -> dict[str, object]:
    base = {
        "action": "BUY",
        "confidence": 70,
        "target_price_low": "100",
        "target_price_high": "120",
        "stop_loss": "90",
    }
    base.update(extra)
    return base


def test_pass_when_buy_matches_bullish_data() -> None:
    r = verify_signal(_buy(), _bullish())
    assert r.verdict == "pass"
    assert r.final_action == "BUY"
    assert r.final_confidence == 70  # 不調整
    assert r.net_direction > 0


def test_buy_against_strong_bearish_is_overridden_to_hold() -> None:
    r = verify_signal(_buy(), _bearish())
    assert r.verdict == "override_hold"
    assert r.final_action == "HOLD"
    assert r.final_confidence < 70
    assert any(f.code == "ACTION_DATA_CONFLICT" for f in r.flags)


def test_news_sentiment_not_counted_as_direction_vote() -> None:
    # 回歸：NewsAnalyst 的 sentiment 與情緒面 market_sentiment 同源於新聞，不應各投一票被
    # 重複計數。僅有極端新聞語氣、其餘中性 → net 必須為 0（新聞語氣不計方向票）。
    analyses = {
        "news": json.dumps({"sentiment": "極度正面"}),
        "sentiment": json.dumps({"market_sentiment": "中性"}),
    }
    r = verify_signal(_buy(), analyses)
    assert r.net_direction == 0


def test_price_incoherent_buy_stop_above_target() -> None:
    r = verify_signal(_buy(stop_loss="130"), _bullish())
    assert any(f.code == "PRICE_INCOHERENT" for f in r.flags)
    assert r.final_action == "HOLD"


def test_low_coverage_penalizes_confidence() -> None:
    analyses = {
        "market": json.dumps({"short_term_view": "看多"}),
        "fundamental": "⚠️ 資料不足：缺財報",
        "news": "⚠️ 資料不足：缺新聞",
        "sentiment": "⚠️ 資料不足：缺籌碼",
    }
    r = verify_signal(_buy(), analyses)
    assert r.evidence_coverage == 0.25
    assert any(f.code == "LOW_EVIDENCE_COVERAGE" for f in r.flags)
    assert r.final_confidence < 70


def test_confidence_is_monotonic_never_increases() -> None:
    # 即使資料極度看多，BUY 的信心也不會被調高
    r = verify_signal(_buy(confidence=55), _bullish())
    assert r.final_confidence <= 55


def test_baserate_weak_flags_buy() -> None:
    r = verify_signal(_buy(), _bullish(), base_rates={"forward_up_prob": 0.30})
    assert any(f.code == "BASERATE_WEAK" for f in r.flags)


def test_baserate_skipped_when_absent() -> None:
    r = verify_signal(_buy(), _bullish())
    assert any(f.code == "BASERATE_SKIPPED" for f in r.flags)


async def test_verifier_node_writes_back_adjusted_signal() -> None:
    node = Verifier(llm=None)
    state = {"signal": _buy(), "analyses": _bearish()}
    out = await node.verify(state)
    sig = out["signal"]
    assert sig["action"] == "HOLD"  # 被保守翻轉
    assert "verification" in sig
    assert sig["verification"]["verdict"] == "override_hold"
