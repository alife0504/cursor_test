"""Agent schemas unit tests — Phase 13 條 P（≥ 8 個測試）。

驗證每個 Pydantic schema 的 validation 嚴格性、enum 邊界、Decimal 序列化。
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.agents.schemas import (
    BearArgument,
    BullArgument,
    ChipAnalysisResult,
    FinalSignal,
    FundamentalAnalysisResult,
    MarketAnalysisResult,
    NewsAnalysisResult,
    NewsSupportingArticle,
    SentimentAnalysisResult,
)

pytestmark = pytest.mark.unit


# ── MarketAnalysisResult ───────────────────────────────


def _valid_market_payload(**overrides):
    base = {
        "summary": "X" * 150,
        "trend": "上升",
        "support_levels": [Decimal("850.0")],
        "resistance_levels": [Decimal("1000.0")],
        "key_indicators": {"RSI": "65", "MACD": "黃金交叉", "MA20": "835"},
        "risk_factors": ["量縮", "外資賣超"],
        "short_term_view": "看多",
        "confidence": 70,
    }
    base.update(overrides)
    return base


def test_market_result_validates() -> None:
    r = MarketAnalysisResult(**_valid_market_payload())
    assert r.trend == "上升"
    assert r.confidence == 70


def test_market_result_rejects_invalid_trend() -> None:
    with pytest.raises(ValidationError):
        MarketAnalysisResult(**_valid_market_payload(trend="不可能值"))


def test_market_result_rejects_short_summary() -> None:
    with pytest.raises(ValidationError):
        MarketAnalysisResult(**_valid_market_payload(summary="太短"))


def test_market_result_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValidationError):
        MarketAnalysisResult(**_valid_market_payload(confidence=150))
    with pytest.raises(ValidationError):
        MarketAnalysisResult(**_valid_market_payload(confidence=-1))


# ── FundamentalAnalysisResult ──────────────────────────


def test_fundamental_result_validates() -> None:
    r = FundamentalAnalysisResult(
        summary="X" * 150,
        valuation="合理",
        financial_strength="強",
        growth_outlook="未來兩年預期雙位數營收成長，主要受 AI 需求推動",
        key_ratios={"PE": "15", "PB": "3.2", "ROE": "20%"},
        risk_factors=["景氣循環"],
        long_term_view="看多",
        confidence=80,
    )
    assert r.valuation == "合理"


def test_fundamental_rejects_invalid_strength() -> None:
    with pytest.raises(ValidationError):
        FundamentalAnalysisResult(
            summary="X" * 150,
            valuation="合理",
            financial_strength="極強",  # 非允許值
            growth_outlook="未來兩年預期雙位數營收成長，主要受 AI 需求推動",
            key_ratios={"PE": "15", "PB": "3", "ROE": "20"},
            risk_factors=["a"],
            long_term_view="看多",
            confidence=80,
        )


# ── NewsAnalysisResult ─────────────────────────────────


def test_news_result_supporting_articles_format() -> None:
    r = NewsAnalysisResult(
        summary="X" * 150,
        sentiment="正面",
        key_topics=["AI", "毛利"],
        supporting_articles=[
            NewsSupportingArticle(
                title="標題1",
                url="https://example.com/a",
                published_at="2026-05-01T10:00:00",
                score=0.9,
            )
        ],
        impact_assessment="短線預期正面影響股價",
        confidence=70,
    )
    assert r.supporting_articles[0].score == 0.9


def test_news_result_score_must_be_0_to_1() -> None:
    with pytest.raises(ValidationError):
        NewsSupportingArticle(
            title="x",
            url="https://e.com",
            published_at="2026-05-01",
            score=1.5,
        )


# ── NewsAnalysisResult macro 欄位 ──────────────────────


def test_news_result_macro_fields_default_and_enum() -> None:
    # macro 欄位有預設值：未提供時可省略
    r = NewsAnalysisResult(
        summary="X" * 150,
        sentiment="正面",
        key_topics=["AI"],
        impact_assessment="短線情緒偏正向，須留意獲利了結賣壓。",
        confidence=60,
    )
    assert r.macro_context == ""
    assert r.macro_bias == "未提供"

    # macro_bias 非法值應擋
    with pytest.raises(ValidationError):
        NewsAnalysisResult(
            summary="X" * 150,
            sentiment="正面",
            key_topics=[],
            impact_assessment="x" * 10,
            macro_bias="超級偏多",  # 非合法
            confidence=60,
        )


# ── ChipAnalysisResult（原籌碼面，v1.1 正名）─────────────


def test_chip_result_enums() -> None:
    r = ChipAnalysisResult(
        summary="X" * 150,
        institutional_flow="大量買超",
        foreign_position_change="外資連 5 個交易日買超合計 12000 張",
        margin_trading_signal="看多",
        retail_sentiment="正常",
        risk_factors=["融券回補"],
        confidence=65,
    )
    assert r.institutional_flow == "大量買超"

    with pytest.raises(ValidationError):
        ChipAnalysisResult(
            summary="X" * 150,
            institutional_flow="超大買超",  # 非合法
            foreign_position_change="x" * 20,
            margin_trading_signal="看多",
            retail_sentiment="正常",
            risk_factors=["a"],
            confidence=50,
        )


# ── SentimentAnalysisResult（v1.1 新設：情緒面）─────────


def test_sentiment_result_emotion_schema() -> None:
    r = SentimentAnalysisResult(
        summary="X" * 150,
        market_sentiment="樂觀",
        sentiment_score="0.42",  # 字串應被 coerce 成 Decimal
        buzz_level="中",
        momentum="轉強",
        key_drivers=["法說會樂觀展望"],
        contrarian_flag=False,
        risk_factors=[],
        confidence=60,
    )
    assert str(r.market_sentiment) == "樂觀"
    assert float(r.sentiment_score) == pytest.approx(0.42)

    # sentiment_score 超出 [-1, 1] 應擋
    with pytest.raises(ValidationError):
        SentimentAnalysisResult(
            summary="X" * 150,
            market_sentiment="樂觀",
            sentiment_score="1.5",
            buzz_level="中",
            momentum="持平",
            key_drivers=[],
            confidence=50,
        )

    # market_sentiment 非法值應擋
    with pytest.raises(ValidationError):
        SentimentAnalysisResult(
            summary="X" * 150,
            market_sentiment="超級樂觀",  # 非合法
            sentiment_score="0.1",
            buzz_level="中",
            momentum="持平",
            key_drivers=[],
            confidence=50,
        )


# ── BullArgument / BearArgument ────────────────────────


def test_bull_argument_min_points() -> None:
    with pytest.raises(ValidationError):
        BullArgument(
            points=["僅一點"],  # < 3
            confidence=80,
            evidence_from=["market"],
        )
    ok = BullArgument(
        points=["技術面強", "基本面佳", "新聞正面"],
        confidence=80,
        evidence_from=["market", "fundamental", "news"],
    )
    assert len(ok.points) == 3


def test_bear_argument_evidence_from_enum() -> None:
    with pytest.raises(ValidationError):
        BearArgument(
            points=["a", "b", "c"],
            confidence=50,
            evidence_from=["unknown_source"],  # 非合法值
        )


# ── FinalSignal ────────────────────────────────────────


def _valid_final_payload(**overrides):
    base = {
        "action": "BUY",
        "confidence": 80,
        "target_price_low": Decimal("900"),
        "target_price_high": Decimal("1000"),
        "stop_loss": Decimal("850"),
        "time_horizon": "中期(1-3月)",
        "position_size_pct": Decimal("20"),
        "reasoning_zh": "X" * 250,
        "risk_factors": ["景氣循環", "外資賣超"],
        "debate_winner": "bull",
    }
    base.update(overrides)
    return base


def test_final_signal_action_enum() -> None:
    s = FinalSignal(**_valid_final_payload())
    assert s.action == "BUY"
    with pytest.raises(ValidationError):
        FinalSignal(**_valid_final_payload(action="WAIT"))


def test_final_signal_confidence_range() -> None:
    with pytest.raises(ValidationError):
        FinalSignal(**_valid_final_payload(confidence=101))


def test_final_signal_decimal_serialized_as_string() -> None:
    s = FinalSignal(**_valid_final_payload())
    d = s.model_dump(mode="json")
    assert d["target_price_low"] == "900"
    assert d["position_size_pct"] == "20"
    # 反序列化回來不該爆
    j = json.loads(s.model_dump_json())
    assert j["stop_loss"] == "850"


def test_final_signal_accepts_str_target_price_from_llm() -> None:
    """LLM 常會回 '900.5' 字串 → 應自動轉 Decimal。"""
    s = FinalSignal(**_valid_final_payload(target_price_low="900.5", target_price_high="1000.0"))
    assert s.target_price_low == Decimal("900.5")


def test_final_signal_accepts_null_string_for_optional_decimal() -> None:
    """LLM 偶爾會回 'null' 字串而非 null → 應視為 None。"""
    s = FinalSignal(**_valid_final_payload(stop_loss="null", target_price_low="N/A"))
    assert s.stop_loss is None
    assert s.target_price_low is None


def test_final_signal_reasoning_min_length() -> None:
    with pytest.raises(ValidationError):
        FinalSignal(**_valid_final_payload(reasoning_zh="太短"))


def test_final_signal_debate_winner_enum() -> None:
    with pytest.raises(ValidationError):
        FinalSignal(**_valid_final_payload(debate_winner="draw"))
