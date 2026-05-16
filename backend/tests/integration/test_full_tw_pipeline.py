"""完整 TW pipeline 整合測試 — Phase 13 條 S（≥ 3 個測試）。

策略：mock LLM + ToolRegistry → 跑 build_graph → ainvoke → 驗最終 state。
驗證 debate_history / signal / report_md 結構完整。
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


# 各 schema 的 fixture payload（會被 _ScriptedLLM 用）

VALID_MARKET = {
    "summary": "X" * 200,
    "trend": "上升",
    "support_levels": ["850.0"],
    "resistance_levels": ["1000.0"],
    "key_indicators": {"RSI": "65", "MACD": "黃金交叉", "MA20": "835"},
    "risk_factors": ["量縮"],
    "short_term_view": "看多",
    "confidence": 75,
}
VALID_FUNDAMENTAL = {
    "summary": "X" * 200,
    "valuation": "合理",
    "financial_strength": "強",
    "growth_outlook": "未來兩年雙位數成長，AI 與 HPC 需求推動營收",
    "key_ratios": {"PE": "15", "PB": "3.2", "ROE": "20%"},
    "risk_factors": ["景氣循環"],
    "long_term_view": "看多",
    "confidence": 80,
}
VALID_NEWS = {
    "summary": "X" * 200,
    "sentiment": "正面",
    "key_topics": ["AI", "毛利"],
    "supporting_articles": [],
    "impact_assessment": "短線正面影響預期偏正向",
    "confidence": 60,
}
VALID_SENTIMENT = {
    "summary": "X" * 200,
    "institutional_flow": "大量買超",
    "foreign_position_change": "外資連 5 日買超合計 12000 張",
    "margin_trading_signal": "看多",
    "retail_sentiment": "正常",
    "risk_factors": ["融券回補壓力"],
    "confidence": 70,
}
VALID_BULL = {
    "points": ["技術面強", "基本面佳", "新聞正面"],
    "confidence": 80,
    "evidence_from": ["market", "fundamental", "news"],
}
VALID_BEAR = {
    "points": ["評價偏高", "外資高位", "景氣轉冷"],
    "confidence": 55,
    "evidence_from": ["fundamental", "sentiment"],
}
VALID_FINAL = {
    "action": "BUY",
    "confidence": 75,
    "target_price_low": "900",
    "target_price_high": "1050",
    "stop_loss": "830",
    "time_horizon": "中期(1-3月)",
    "position_size_pct": "15",
    "reasoning_zh": "X" * 250,
    "risk_factors": ["景氣循環", "外資資金流向", "美中貿易"],
    "debate_winner": "bull",
}


class _ScriptedLLM:
    """根據 system prompt 內容自動回對應 schema 的 valid JSON。"""

    name: ClassVar[str] = "fake"
    default_model: ClassVar[str] = "fake-1.0"
    pricing: ClassVar[dict] = {}

    def __init__(self) -> None:
        self.calls: list[str] = []
        # role 對應 payload
        self._mapping = [
            ("技術面分析師", VALID_MARKET),
            ("基本面分析師", VALID_FUNDAMENTAL),
            ("新聞情緒分析師", VALID_NEWS),
            ("籌碼面分析師", VALID_SENTIMENT),
            ("看多（Bull）研究員", VALID_BULL),
            ("看空（Bear）研究員", VALID_BEAR),
            ("首席投資策略長", VALID_FINAL),
        ]

    async def generate(self, system: str, user: str, **kw) -> LLMResponse:
        payload: dict[str, Any] = VALID_FINAL  # default
        for key, val in self._mapping:
            if key in system:
                payload = val
                break
        self.calls.append(system[:30])
        content = f"中文綜述。\n\n```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
        return LLMResponse(
            content=content,
            tool_calls=[],
            usage=TokenUsage(
                input_tokens=400,
                output_tokens=200,
                total_tokens=600,
                cost_usd=Decimal("0.0003"),
            ),
            model="fake-1.0",
            finish_reason="stop",
        )


class _FakeTools:
    """fake ToolRegistry — 提供所有 8 個 method 的合理 stub 資料。"""

    async def get_ohlcv(self, symbol, days_back=60):
        return [
            {
                "date": f"2026-{(i // 28 + 1):02d}-{(i % 28 + 1):02d}",
                "open": 100 + i * 0.5,
                "high": 102 + i * 0.5,
                "low": 98 + i * 0.5,
                "close": 101 + i * 0.5,
                "volume": 1_000_000 + i * 1000,
                "source": "fake",
            }
            for i in range(60)
        ]

    async def get_company_info(self, symbol):
        return {"name": "台積電", "industry": "半導體", "market": "TWSE", "capital": "1000000000"}

    async def get_financial(self, symbol, quarters_back=4):
        rows = []
        for q in range(4):
            for stype in ("IS", "BS", "CF"):
                rows.append(
                    {
                        "fiscal_year": 2025,
                        "fiscal_quarter": 4 - q,
                        "statement_type": stype,
                        "revenue": 500_000 + q * 10_000 if stype == "IS" else None,
                        "net_income": 100_000 if stype == "IS" else None,
                        "eps": 10.0 if stype == "IS" else None,
                        "cogs": 250_000 if stype == "IS" else None,
                        "operating_income": 200_000 if stype == "IS" else None,
                        "total_equity": 1_000_000 if stype == "BS" else None,
                        "operating_cash_flow": 150_000 if stype == "CF" else None,
                        "capex": -50_000 if stype == "CF" else None,
                    }
                )
        return rows

    async def get_news(self, symbol, days_back=7, max_items=20):
        return [
            {
                "id": "n1",
                "title": "台積電獲 AI 訂單",
                "summary": "正面新聞",
                "source": "cnyes",
                "url": "https://example.com/n1",
                "sentiment": "positive",
                "sentiment_score": "0.85",
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
    """所有 analyst / researcher / manager 的 rw_session 都改 noop。"""

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


def test_2330_completes_with_stub_llm(patched_rw_session) -> None:
    """跑完整 graph（4 analyst + 1 round bull/bear + manager）→ signal + report_md 完整。"""
    llm = _ScriptedLLM()
    tools = _FakeTools()

    g = build_graph("2330", "TWSE", debate_rounds=1, llm=llm, tools=tools)
    state = build_initial_state(
        symbol="2330",
        market="TWSE",
        analysis_id="00000000-0000-0000-0000-000000000a01",
        trace_id="trace-13",
        analyst_types=None,
        llm_model="fake",
        debate_rounds=1,
    )
    final = asyncio.run(g.ainvoke(state, config={"recursion_limit": 25}))

    # 4 analyst 結果
    analyses = final.get("analyses") or {}
    assert set(analyses.keys()) >= {
        "market",
        "fundamental",
        "news",
        "sentiment",
    }, f"missing analysts: {set(analyses.keys())}"

    # signal + report_md
    signal = final.get("signal") or {}
    assert signal.get("action") in {"BUY", "HOLD", "SELL"}
    assert isinstance(final.get("report_md"), str) and len(final["report_md"]) > 100

    # debate_history 應有 2 筆（1 round = bull + bear）
    history = final.get("debate_history") or []
    assert len(history) == 2
    assert {h.get("role") for h in history} == {"bull", "bear"}


def test_debate_rounds_creates_correct_history_entries(patched_rw_session) -> None:
    """debate_rounds=2 → debate_history 應有 4 筆（bull-bear-bull-bear）。"""
    llm = _ScriptedLLM()
    tools = _FakeTools()

    g = build_graph("2330", "TWSE", debate_rounds=2, llm=llm, tools=tools)
    state = build_initial_state(
        symbol="2330",
        market="TWSE",
        analysis_id="00000000-0000-0000-0000-000000000a02",
        trace_id="trace-r2",
        analyst_types=["market", "fundamental"],
        llm_model="fake",
        debate_rounds=2,
    )
    final = asyncio.run(g.ainvoke(state, config={"recursion_limit": 25}))

    history = final.get("debate_history") or []
    # 2 rounds → 4 entries (bull-bear × 2)
    assert len(history) == 4
    roles = [h.get("role") for h in history]
    rounds = [h.get("round") for h in history]
    assert roles == ["bull", "bear", "bull", "bear"]
    assert rounds == [1, 1, 2, 2]


def test_us_pipeline_excludes_sentiment(patched_rw_session) -> None:
    """US 應跳過 sentiment（TW only），其餘 3 個 analyst 正常跑。"""
    llm = _ScriptedLLM()
    tools = _FakeTools()

    g = build_graph("AAPL", "NASDAQ", debate_rounds=1, llm=llm, tools=tools)
    state = build_initial_state(
        symbol="AAPL",
        market="NASDAQ",
        analysis_id="00000000-0000-0000-0000-000000000a03",
        trace_id="trace-us",
        debate_rounds=1,
    )
    final = asyncio.run(g.ainvoke(state, config={"recursion_limit": 25}))
    analyses = final.get("analyses") or {}
    assert "sentiment" not in analyses
    assert {"market", "fundamental", "news"}.issubset(analyses.keys())
