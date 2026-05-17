"""完整 US pipeline 整合測試 — Phase 14 條 T（≥ 3 個測試）。

策略：mock LLM + ToolRegistry → build_graph("AAPL", "NASDAQ") → ainvoke → 驗證
- sentiment 不在 analyses（US 不支援）
- 3 個 analyst（market / fundamental / news）都跑完
- pending_order：signal=BUY → signal_to_pending_order 建單成功
- 不會呼叫 institutional tool（強制塞 sentiment 應 raise，但 graph 過濾應不會塞）

並驗證 P14 美股 prompt 模板被使用（render_template 呼叫 us 版）。
"""

from __future__ import annotations

import asyncio
import json
import uuid as _uuid
from decimal import Decimal
from typing import Any, ClassVar

import pytest

from app.agents.analysts.sentiment_analyst import SentimentAnalyst
from app.agents.graph_builder import build_graph, build_initial_state
from app.agents.managers.orders_decision import signal_to_pending_order
from app.agents.state import make_initial_state
from app.core.errors import ValidationError
from app.llm.base_provider import LLMResponse, TokenUsage

pytestmark = pytest.mark.integration


# ── valid payload（schema 對齊 P13）───────────────

VALID_MARKET = {
    "summary": "X" * 200,
    "trend": "上升",
    "support_levels": ["180.0"],
    "resistance_levels": ["220.0"],
    "key_indicators": {"RSI": "62", "MACD": "黃金交叉", "MA20": "195"},
    "risk_factors": ["FOMC 升息預期"],
    "short_term_view": "看多",
    "confidence": 70,
}
VALID_FUNDAMENTAL = {
    "summary": "X" * 200,
    "valuation": "合理",
    "financial_strength": "強",
    "growth_outlook": "AI 與 Services 高速成長，自由現金流穩定",
    "key_ratios": {"PE": "28", "ROE": "150%", "FCF": "100B"},
    "risk_factors": ["供應鏈"],
    "long_term_view": "看多",
    "confidence": 78,
}
VALID_NEWS = {
    "summary": "X" * 200,
    "sentiment": "正面",
    "key_topics": ["AI", "iPhone 15"],
    "supporting_articles": [],
    "impact_assessment": "整體新聞偏正面，預期短線情緒支撐",
    "confidence": 65,
}
VALID_BULL = {
    "points": ["技術面強", "基本面佳", "新聞正面"],
    "confidence": 80,
    "evidence_from": ["market", "fundamental", "news"],
}
VALID_BEAR = {
    "points": ["評價偏高", "宏觀利率高", "中國市場疲弱"],
    "confidence": 55,
    "evidence_from": ["fundamental", "news"],
}
VALID_FINAL = {
    "action": "BUY",
    "confidence": 75,
    "target_price_low": "200",
    "target_price_high": "240",
    "stop_loss": "180",
    "time_horizon": "中期(1-3月)",
    "position_size_pct": "10",
    "reasoning_zh": "X" * 250,
    "risk_factors": ["宏觀利率", "中國市場", "美元走強"],
    "debate_winner": "bull",
}


class _ScriptedLLM:
    name: ClassVar[str] = "fake-us"
    default_model: ClassVar[str] = "fake-us-1.0"
    pricing: ClassVar[dict] = {}

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._mapping = [
            ("技術面分析師", VALID_MARKET),
            ("基本面分析師", VALID_FUNDAMENTAL),
            ("新聞情緒分析師", VALID_NEWS),
            ("看多（Bull）研究員", VALID_BULL),
            ("看空（Bear）研究員", VALID_BEAR),
            ("首席投資策略長", VALID_FINAL),
        ]

    async def generate(self, system: str, user: str, **kw) -> LLMResponse:
        payload: dict[str, Any] = VALID_FINAL
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
            model="fake-us-1.0",
            finish_reason="stop",
        )


class _FakeUSTools:
    """fake ToolRegistry — 美股版（無 institutional / margin / monthly_revenue）。"""

    async def get_ohlcv(self, symbol, days_back=60):
        return [
            {
                "date": f"2026-{(i // 28 + 1):02d}-{(i % 28 + 1):02d}",
                "open": 200 + i * 0.3,
                "high": 202 + i * 0.3,
                "low": 198 + i * 0.3,
                "close": 201 + i * 0.3,
                "volume": 20_000_000 + i * 5000,
                "source": "fake-us",
            }
            for i in range(60)
        ]

    async def get_company_info(self, symbol):
        return {
            "name": "Apple Inc.",
            "industry": "Consumer Electronics",
            "market": "NASDAQ",
            "capital": "3000000000000",
        }

    async def get_financial(self, symbol, quarters_back=4):
        rows = []
        for q in range(4):
            for stype in ("IS", "BS", "CF"):
                rows.append(
                    {
                        "fiscal_year": 2025,
                        "fiscal_quarter": 4 - q,
                        "statement_type": stype,
                        "revenue": 80_000_000_000 + q * 1_000_000_000 if stype == "IS" else None,
                        "net_income": 20_000_000_000 if stype == "IS" else None,
                        "eps": 1.5 if stype == "IS" else None,
                        "cogs": 40_000_000_000 if stype == "IS" else None,
                        "operating_income": 30_000_000_000 if stype == "IS" else None,
                        "total_equity": 60_000_000_000 if stype == "BS" else None,
                        "operating_cash_flow": 25_000_000_000 if stype == "CF" else None,
                        "capex": -3_000_000_000 if stype == "CF" else None,
                    }
                )
        return rows

    async def get_news(self, symbol, days_back=7, max_items=20):
        return [
            {
                "id": "n1",
                "title": "Apple announces AI features",
                "summary": "positive coverage",
                "source": "Reuters",
                "url": "https://example.com/n1",
                "sentiment": "positive",
                "sentiment_score": "0.80",
                "published_at": "2026-05-10T10:00:00",
            }
        ]

    async def get_announcements(self, symbol, days_back=30):
        return []

    async def get_institutional(self, symbol, days_back=30):
        # 美股不應呼叫此方法；call → raise
        raise AssertionError(
            "get_institutional 不應該被美股 pipeline 呼叫（sentiment_analyst 不在 graph）"
        )

    async def get_margin(self, symbol, days_back=30):
        raise AssertionError("get_margin 不應該被美股 pipeline 呼叫")

    async def get_monthly_revenue(self, symbol, months_back=12):
        # FundamentalAnalyst 對美股不會呼叫（已 region check）
        raise AssertionError("get_monthly_revenue 不應該被美股 pipeline 呼叫（region=US 已過濾）")


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
    """publish_event 改 noop（避免測試環境 redis 不可達）。"""

    async def _noop_async(*a, **kw):
        return True

    def _noop_sync(*a, **kw):
        return True

    monkeypatch.setattr("app.agents.graph_builder.publish_event", _noop_async)
    monkeypatch.setattr("app.agents.streaming.publish_event", _noop_async, raising=True)
    monkeypatch.setattr("app.agents.streaming.publish_event_sync", _noop_sync, raising=True)


def test_aapl_completes_with_mock_llm(patched_rw_session, patched_streaming) -> None:
    """AAPL 完整跑：3 analyst + bull/bear + manager。"""
    llm = _ScriptedLLM()
    tools = _FakeUSTools()
    g = build_graph("AAPL", "NASDAQ", debate_rounds=1, llm=llm, tools=tools)
    state = build_initial_state(
        symbol="AAPL",
        market="NASDAQ",
        analysis_id="00000000-0000-0000-0000-000000000b01",
        trace_id="trace-us-1",
        debate_rounds=1,
    )
    final = asyncio.run(g.ainvoke(state, config={"recursion_limit": 25}))
    analyses = final.get("analyses") or {}
    # 美股 3 個 analyst
    assert {"market", "fundamental", "news"}.issubset(analyses.keys())
    # 不含 sentiment
    assert "sentiment" not in analyses
    # signal + report_md
    signal = final.get("signal") or {}
    assert signal.get("action") in {"BUY", "HOLD", "SELL"}
    assert isinstance(final.get("report_md"), str) and len(final["report_md"]) > 100


def test_us_sentiment_analyst_raises_on_us_region(patched_rw_session) -> None:
    """強制塞 sentiment_analyst.analyze(state with region=US) → raise ValidationError。"""

    class _FakeTools:
        async def get_company_info(self, *a, **kw):
            return {"name": "Apple", "industry": "Tech", "market": "NASDAQ"}

        async def get_institutional(self, *a, **kw):
            return []

        async def get_margin(self, *a, **kw):
            return []

        async def get_monthly_revenue(self, *a, **kw):
            return []

    class _DummyLLM:
        name = "x"
        default_model = "x"

        async def generate(self, *a, **kw):
            raise AssertionError("不該呼叫到 LLM；region check 先 raise")

    sa = SentimentAnalyst(llm=_DummyLLM(), tools=_FakeTools())
    state = make_initial_state(
        symbol="AAPL",
        market="NASDAQ",
        region="US",
        analyst_types=["sentiment"],
        llm_model="fake",
        debate_rounds=0,
        trace_id="t",
        analysis_id="00000000-0000-0000-0000-000000000b02",
        started_at="2026-05-17T08:00:00+00:00",
    )
    with pytest.raises(ValidationError):
        asyncio.run(sa.analyze(state))


def test_us_pending_order_created_for_buy_signal() -> None:
    """final signal=BUY → signal_to_pending_order 建單，market=NASDAQ。"""
    order = signal_to_pending_order(
        VALID_FINAL,
        analysis_id=_uuid.uuid4(),
        user_id=_uuid.uuid4(),
        symbol="AAPL",
        market="NASDAQ",
    )
    assert order is not None
    assert order.market == "NASDAQ"
    assert order.side == "BUY"
    assert order.qty > 0
    assert order.target_price == Decimal("200")
    assert order.take_profit == Decimal("240")
    assert order.stop_loss == Decimal("180")
