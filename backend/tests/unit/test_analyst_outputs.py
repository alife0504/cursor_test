"""build_analyst_outputs 單元測試（v1.0.2 新增）。

用「真實 Pydantic schema 的 model_dump_json()」當輸入，確保轉換與 analyst
實際序列化形狀對齊（防 schema drift）。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.agents.analyst_outputs import build_analyst_outputs
from app.agents.schemas import (
    FundamentalAnalysisResult,
    MarketAnalysisResult,
    NewsAnalysisResult,
    SentimentAnalysisResult,
)

pytestmark = pytest.mark.unit

_SUMMARY = "這是一段足夠長的技術面綜述，用來滿足 schema 對 summary 最少 100 字的限制。" * 3


def _market(view: str = "看多", conf: int = 78) -> str:
    return MarketAnalysisResult(
        summary=_SUMMARY,
        trend="上升",
        support_levels=[Decimal("100.5")],
        resistance_levels=[Decimal("120.0")],
        key_indicators={"RSI": "62", "MACD": "正", "MA20": "上彎"},
        risk_factors=["大盤系統性風險"],
        short_term_view=view,  # type: ignore[arg-type]
        confidence=conf,
    ).model_dump_json()


def test_market_structured_maps_score_signal_points() -> None:
    out = build_analyst_outputs({"market": _market(view="看多", conf=78)})
    m = out["market"]
    assert m["type"] == "market"
    assert m["score"] == 78
    assert m["signal"] == "BUY"  # 看多 → BUY
    assert m["report_md"].startswith("這是一段")  # summary 進 report_md
    # key_points 應含趨勢 / 短線觀點 / 指標
    joined = " ".join(m["key_points"])
    assert "技術趨勢：上升" in joined
    assert "短線觀點：看多" in joined
    assert "RSI：62" in joined
    # metrics 帶原始結構
    assert m["metrics"]["trend"] == "上升"


def test_market_view_bear_maps_sell() -> None:
    out = build_analyst_outputs({"market": _market(view="看空")})
    assert out["market"]["signal"] == "SELL"


def test_fundamental_long_term_view_maps_signal() -> None:
    raw = FundamentalAnalysisResult(
        summary=_SUMMARY,
        valuation="低估",
        financial_strength="強",
        growth_outlook="未來兩年營收年增 20% 以上，受惠 AI 需求。",
        key_ratios={"PE": "15", "ROE": "22%", "殖利率": "3.1%"},
        risk_factors=["匯率波動"],
        long_term_view="看多",
        confidence=80,
    ).model_dump_json()
    f = build_analyst_outputs({"fundamental": raw})["fundamental"]
    assert f["signal"] == "BUY"
    assert f["score"] == 80
    assert any("評價：低估" in p for p in f["key_points"])
    assert any("PE：15" in p for p in f["key_points"])


def test_news_has_no_trade_signal() -> None:
    raw = NewsAnalysisResult(
        summary=_SUMMARY,
        sentiment="正面",
        key_topics=["法說會釋出樂觀展望"],
        supporting_articles=[],
        impact_assessment="短線情緒偏多，但須留意獲利了結賣壓。",
        confidence=65,
    ).model_dump_json()
    n = build_analyst_outputs({"news": raw})["news"]
    # 新聞情緒不是交易訊號
    assert "signal" not in n or n["signal"] is None
    assert any("市場情緒：正面" in p for p in n["key_points"])
    assert any("焦點：" in p for p in n["key_points"])


def test_sentiment_margin_signal_maps() -> None:
    raw = SentimentAnalysisResult(
        summary=_SUMMARY,
        institutional_flow="大量買超",
        foreign_position_change="外資連三日買超合計 1.2 萬張。",
        margin_trading_signal="看空",
        retail_sentiment="過熱",
        risk_factors=["融資餘額偏高"],
        confidence=55,
    ).model_dump_json()
    s = build_analyst_outputs({"sentiment": raw})["sentiment"]
    assert s["signal"] == "SELL"  # margin_trading_signal=看空
    assert any("法人動向：大量買超" in p for p in s["key_points"])


def test_stub_plain_text_falls_back_to_report_md() -> None:
    out = build_analyst_outputs({"market": "[stub] 技術面分析（無 LLM 注入）"})
    m = out["market"]
    assert m["type"] == "market"
    assert "[stub]" in m["report_md"]
    # 純文字不應硬湊 key_points
    assert not m.get("key_points")


def test_invalid_json_string_falls_back() -> None:
    out = build_analyst_outputs({"market": "{壞掉的 json"})
    assert "壞掉" in out["market"]["report_md"]


def test_dict_input_supported() -> None:
    """測試直接傳 dict（非 JSON 字串）也能解析。"""
    out = build_analyst_outputs(
        {"news": {"summary": "x" * 50, "sentiment": "中性", "confidence": 50}}
    )
    assert out["news"]["score"] == 50
    assert any("市場情緒：中性" in p for p in out["news"]["key_points"])


def test_empty_input_returns_empty_dict() -> None:
    assert build_analyst_outputs({}) == {}
    assert build_analyst_outputs(None) == {}


def test_unknown_analyst_uses_generic() -> None:
    out = build_analyst_outputs(
        {"macro": {"summary": "總經分析摘要", "confidence": 70, "key_points": ["升息趨緩"]}}
    )
    assert out["macro"]["score"] == 70
    assert out["macro"]["report_md"] == "總經分析摘要"
    assert "升息趨緩" in out["macro"]["key_points"]
