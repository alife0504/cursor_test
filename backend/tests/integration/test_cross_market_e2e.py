"""Cross-market e2e — 2330 + AAPL 都跑通（mock LLM）。

Phase 14 條 U（≥ 2 個測試）。

策略：複用 _ScriptedLLM + _FakeTools 風格；不打 LLM API、不打 DB（rw_session noop）。
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any, ClassVar

import pytest

from app.agents.graph_builder import build_graph, build_initial_state
from app.llm.base_provider import LLMResponse, TokenUsage

pytestmark = pytest.mark.integration


_VALID_MARKET = {
    "summary": "X" * 200,
    "trend": "上升",
    "support_levels": ["100"],
    "resistance_levels": ["120"],
    "key_indicators": {"RSI": "60", "MACD": "黃金交叉", "MA20": "110"},
    "risk_factors": ["量縮"],
    "short_term_view": "看多",
    "confidence": 70,
}
_VALID_FUND = {
    "summary": "X" * 200,
    "valuation": "合理",
    "financial_strength": "強",
    "growth_outlook": "雙位數成長預期，未來兩年動能不弱，AI 與 HPC 推動營收動能持續",
    "key_ratios": {"PE": "20", "PB": "3", "ROE": "15%"},
    "risk_factors": ["景氣"],
    "long_term_view": "看多",
    "confidence": 75,
}
_VALID_NEWS = {
    "summary": "X" * 200,
    "sentiment": "正面",
    "key_topics": ["AI"],
    "supporting_articles": [],
    "impact_assessment": "整體新聞偏正面，預期短線支撐",
    "confidence": 65,
}
_VALID_SENT = {
    "summary": "X" * 200,
    "institutional_flow": "大量買超",
    "foreign_position_change": "外資連 5 日買超合計 8000 張",
    "margin_trading_signal": "看多",
    "retail_sentiment": "正常",
    "risk_factors": ["融券壓力"],
    "confidence": 70,
}
_VALID_BULL = {
    "points": ["技術強", "基本面佳", "新聞正面"],
    "confidence": 78,
    "evidence_from": ["market", "fundamental", "news"],
}
_VALID_BEAR = {
    "points": ["估值偏高", "宏觀利率", "外資高位"],
    "confidence": 55,
    "evidence_from": ["fundamental", "news"],
}
_VALID_FINAL = {
    "action": "BUY",
    "confidence": 75,
    "target_price_low": "100",
    "target_price_high": "120",
    "stop_loss": "90",
    "time_horizon": "中期(1-3月)",
    "position_size_pct": "10",
    "reasoning_zh": "X" * 250,
    "risk_factors": ["景氣", "宏觀", "外資"],
    "debate_winner": "bull",
}


class _ScriptedLLM:
    name: ClassVar[str] = "fake-cross"
    default_model: ClassVar[str] = "fake-cross-1.0"

    def __init__(self) -> None:
        self._mapping = [
            ("技術面分析師", _VALID_MARKET),
            ("基本面分析師", _VALID_FUND),
            ("新聞情緒分析師", _VALID_NEWS),
            ("籌碼面分析師", _VALID_SENT),
            ("看多（Bull）研究員", _VALID_BULL),
            ("看空（Bear）研究員", _VALID_BEAR),
            ("首席投資策略長", _VALID_FINAL),
        ]

    async def generate(self, system: str, user: str, **kw) -> LLMResponse:
        payload: dict[str, Any] = _VALID_FINAL
        for key, val in self._mapping:
            if key in system:
                payload = val
                break
        content = f"中文綜述。\n\n```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
        return LLMResponse(
            content=content,
            tool_calls=[],
            usage=TokenUsage(
                input_tokens=300,
                output_tokens=150,
                total_tokens=450,
                cost_usd=Decimal("0.0002"),
            ),
            model="fake-cross-1.0",
            finish_reason="stop",
        )


class _FakeTools:
    """all-region stub。"""

    async def get_ohlcv(self, symbol, days_back=60):
        return [
            {
                "date": f"2026-{(i // 28 + 1):02d}-{(i % 28 + 1):02d}",
                "open": 100 + i * 0.1,
                "high": 102 + i * 0.1,
                "low": 98 + i * 0.1,
                "close": 101 + i * 0.1,
                "volume": 1_000_000,
                "source": "fake",
            }
            for i in range(60)
        ]

    async def get_company_info(self, symbol):
        return {"name": "Test Co", "industry": "Tech", "market": "TWSE", "capital": "1B"}

    async def get_financial(self, symbol, quarters_back=4):
        rows = []
        for q in range(4):
            for stype in ("IS", "BS", "CF"):
                rows.append(
                    {
                        "fiscal_year": 2025,
                        "fiscal_quarter": 4 - q,
                        "statement_type": stype,
                        "revenue": 1_000_000 if stype == "IS" else None,
                        "net_income": 100_000 if stype == "IS" else None,
                        "eps": 5.0 if stype == "IS" else None,
                        "cogs": 500_000 if stype == "IS" else None,
                        "operating_income": 400_000 if stype == "IS" else None,
                        "total_equity": 5_000_000 if stype == "BS" else None,
                        "operating_cash_flow": 200_000 if stype == "CF" else None,
                        "capex": -50_000 if stype == "CF" else None,
                    }
                )
        return rows

    async def get_news(self, symbol, days_back=7, max_items=20):
        return [
            {
                "id": "n1",
                "title": "正面新聞",
                "summary": "x",
                "source": "fake",
                "url": "https://example.com/n1",
                "sentiment": "positive",
                "sentiment_score": "0.8",
                "published_at": "2026-05-10T10:00:00",
            }
        ]

    async def get_announcements(self, symbol, days_back=30):
        return []

    async def get_institutional(self, symbol, days_back=30):
        return [
            {
                "date": "2026-05-10",
                "foreign_buy": 1000,
                "foreign_sell": 500,
                "foreign_net": 500,
                "trust_buy": 200,
                "trust_sell": 100,
                "trust_net": 100,
                "dealer_buy": 50,
                "dealer_sell": 30,
                "dealer_net": 20,
            }
        ]

    async def get_margin(self, symbol, days_back=30):
        return [
            {
                "date": "2026-05-10",
                "margin_balance": 100000,
                "margin_buy": 1000,
                "margin_sell": 800,
                "short_balance": 5000,
                "short_buy": 50,
                "short_sell": 30,
            }
        ]

    async def get_monthly_revenue(self, symbol, months_back=12):
        return [
            {
                "year": 2026,
                "month": 4,
                "revenue": 200_000,
                "revenue_yoy": "15",
                "revenue_mom": "5",
                "ytd_yoy": "10",
            },
        ]


@pytest.fixture
def patched_rw_session(monkeypatch):
    class _NoopSession:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        def add(self, *a, **kw):
            pass

        async def flush(self):
            pass

        async def commit(self):
            pass

    targets = [
        "app.agents.analysts.market_analyst.rw_session",
        "app.agents.analysts.fundamental_analyst.rw_session",
        "app.agents.analysts.news_analyst.rw_session",
        "app.agents.analysts.sentiment_analyst.rw_session",
        "app.agents.researchers.bull_researcher.rw_session",
        "app.agents.researchers.bear_researcher.rw_session",
        "app.agents.managers.research_manager.rw_session",
    ]
    for t in targets:
        monkeypatch.setattr(t, _NoopSession, raising=True)


@pytest.fixture
def patched_streaming(monkeypatch):
    async def _noop_async(*a, **kw):
        return True

    monkeypatch.setattr("app.agents.graph_builder.publish_event", _noop_async)


def test_2330_full_pipeline_end_to_end_mock_llm(patched_rw_session, patched_streaming) -> None:
    """台股 2330 完整跑：4 analyst + 1 round + manager。"""
    llm = _ScriptedLLM()
    tools = _FakeTools()
    g = build_graph("2330", "TWSE", debate_rounds=1, llm=llm, tools=tools)
    state = build_initial_state(
        symbol="2330",
        market="TWSE",
        analysis_id="00000000-0000-0000-0000-000000000c01",
        trace_id="cross-tw",
        debate_rounds=1,
    )
    final = asyncio.run(g.ainvoke(state, config={"recursion_limit": 25}))
    analyses = final.get("analyses") or {}
    assert {"market", "fundamental", "news", "sentiment"}.issubset(analyses.keys())
    assert (final.get("signal") or {}).get("action") in {"BUY", "HOLD", "SELL"}


def test_aapl_full_pipeline_end_to_end_mock_llm(patched_rw_session, patched_streaming) -> None:
    """美股 AAPL 完整跑：3 analyst（無 sentiment）+ 1 round + manager。"""
    llm = _ScriptedLLM()
    tools = _FakeTools()
    g = build_graph("AAPL", "NASDAQ", debate_rounds=1, llm=llm, tools=tools)
    state = build_initial_state(
        symbol="AAPL",
        market="NASDAQ",
        analysis_id="00000000-0000-0000-0000-000000000c02",
        trace_id="cross-us",
        debate_rounds=1,
    )
    final = asyncio.run(g.ainvoke(state, config={"recursion_limit": 25}))
    analyses = final.get("analyses") or {}
    assert "sentiment" not in analyses
    assert {"market", "fundamental", "news"}.issubset(analyses.keys())
    assert (final.get("signal") or {}).get("action") in {"BUY", "HOLD", "SELL"}
