"""MarketAnalyst 整合測試 — Phase 13 條 R（≥ 4 個測試）。

策略：mock LLM + mock ToolRegistry → 驗 analyst 邏輯。
不打真 LLM、不打真 DB（用 fake session）。
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, ClassVar

import pytest

from app.agents.analysts.market_analyst import MarketAnalyst
from app.agents.schemas import MarketAnalysisResult
from app.llm.base_provider import LLMResponse, TokenUsage

pytestmark = pytest.mark.integration


# ── Mock fixtures ───────────────────────────────────────


VALID_MARKET_PAYLOAD: dict[str, Any] = {
    "summary": "X" * 200,
    "trend": "上升",
    "support_levels": ["850.0"],
    "resistance_levels": ["1000.0"],
    "key_indicators": {
        "RSI": "65 偏多",
        "MACD": "黃金交叉",
        "MA20": "835 上升",
    },
    "risk_factors": ["量縮", "外資賣超"],
    "short_term_view": "看多",
    "confidence": 70,
}


class _FakeLLM:
    name: ClassVar[str] = "fake"
    default_model: ClassVar[str] = "fake-1.0"
    pricing: ClassVar[dict] = {}

    def __init__(self, response_payload: dict[str, Any] | None = None) -> None:
        self.response_payload = response_payload or VALID_MARKET_PAYLOAD
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system, user, **kw) -> LLMResponse:
        self.calls.append((system, user))
        content = (
            "繁中綜述：技術面偏多，本檔近期 MA20 上揚。\n\n"
            f"```json\n{json.dumps(self.response_payload, ensure_ascii=False)}\n```"
        )
        return LLMResponse(
            content=content,
            tool_calls=[],
            usage=TokenUsage(
                input_tokens=500,
                output_tokens=300,
                total_tokens=800,
                cost_usd=Decimal("0.0005"),
            ),
            model="fake-1.0",
            finish_reason="stop",
        )


class _FakeTools:
    """模擬 ToolRegistry — 只提供 market_analyst 需要的 method。"""

    def __init__(
        self,
        ohlcv: list[dict[str, Any]] | None = None,
        company: dict[str, Any] | None = None,
    ) -> None:
        self._ohlcv = ohlcv if ohlcv is not None else _synthetic_ohlcv()
        self._company = company or {
            "name": "台積電",
            "industry": "半導體",
            "market": "TWSE",
        }
        self.get_ohlcv_calls: list[tuple[str, int]] = []

    async def get_ohlcv(self, symbol: str, days_back: int = 60) -> list[dict[str, Any]]:
        self.get_ohlcv_calls.append((symbol, days_back))
        return self._ohlcv

    async def get_company_info(self, symbol: str) -> dict[str, Any]:
        return self._company


def _synthetic_ohlcv(n: int = 60) -> list[dict[str, Any]]:
    return [
        {
            "date": f"2026-{((i // 28) + 1):02d}-{(i % 28) + 1:02d}",
            "open": 100.0 + i * 0.5,
            "high": 102.0 + i * 0.5,
            "low": 98.0 + i * 0.5,
            "close": 101.0 + i * 0.5,
            "volume": 1_000_000 + i * 1000,
            "turnover": (101.0 + i * 0.5) * 1_000_000,
            "source": "stub",
        }
        for i in range(n)
    ]


# ── Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_market_analyst_returns_valid_schema(monkeypatch) -> None:
    """成功路徑：mock 回 schema-valid JSON → 應產出 analyses[market] 為 JSON。"""
    llm = _FakeLLM()
    tools = _FakeTools()
    analyst = MarketAnalyst(llm=llm, tools=tools)
    # disable rw_session usage in tests（避免依賴 DB）
    monkeypatch.setattr(
        "app.agents.analysts.market_analyst.rw_session",
        _NoopSession,
        raising=True,
    )

    state = {"symbol": "2330", "market_code": "TWSE", "region": "TW", "analysis_id": None}
    result = await analyst.analyze(state)

    assert "analyses" in result
    assert "market" in result["analyses"]
    # JSON 應可反序列化回 schema
    payload = json.loads(result["analyses"]["market"])
    parsed = MarketAnalysisResult.model_validate(payload)
    assert parsed.short_term_view == "看多"
    assert result["llm_usage_total_tokens"] == 800


@pytest.mark.asyncio
async def test_market_analyst_uses_ohlcv_tool(monkeypatch) -> None:
    """應呼叫 tools.get_ohlcv 抓資料（days_back=60）。"""
    llm = _FakeLLM()
    tools = _FakeTools()
    monkeypatch.setattr("app.agents.analysts.market_analyst.rw_session", _NoopSession)

    state = {"symbol": "2330", "market_code": "TWSE", "region": "TW", "analysis_id": None}
    await MarketAnalyst(llm=llm, tools=tools).analyze(state)

    assert len(tools.get_ohlcv_calls) == 1
    sym, days = tools.get_ohlcv_calls[0]
    assert sym == "2330"
    assert days == 60


@pytest.mark.asyncio
async def test_market_analyst_records_usage_in_state(monkeypatch) -> None:
    """state.llm_usage_total_tokens 應正確累積。"""
    llm = _FakeLLM()
    tools = _FakeTools()
    monkeypatch.setattr("app.agents.analysts.market_analyst.rw_session", _NoopSession)

    state = {
        "symbol": "2330",
        "market_code": "TWSE",
        "region": "TW",
        "analysis_id": None,
        "llm_usage_total_tokens": 1000,
    }
    result = await MarketAnalyst(llm=llm, tools=tools).analyze(state)
    # 原本 1000 + 本次 800 = 1800
    assert result["llm_usage_total_tokens"] == 1800


@pytest.mark.asyncio
async def test_market_analyst_handles_no_data(monkeypatch) -> None:
    """tools.get_ohlcv 回空 list → 應 raise ExternalServiceError（不 silent）。"""
    from app.core.errors import ExternalServiceError

    llm = _FakeLLM()
    tools = _FakeTools(ohlcv=[])
    monkeypatch.setattr("app.agents.analysts.market_analyst.rw_session", _NoopSession)
    state = {"symbol": "2330", "market_code": "TWSE", "region": "TW", "analysis_id": None}
    with pytest.raises(ExternalServiceError, match="OHLCV"):
        await MarketAnalyst(llm=llm, tools=tools).analyze(state)


@pytest.mark.asyncio
async def test_market_analyst_stub_when_no_llm() -> None:
    """無 llm → 應回 stub（向下相容 P12 測試）。"""
    state = {"symbol": "2330", "market_code": "TWSE", "region": "TW"}
    result = await MarketAnalyst(llm=None, tools=None).analyze(state)
    assert "[stub]" in result["analyses"]["market"]


# ── helpers ────────────────────────────────────────────


class _NoopSession:
    """假的 async context manager — yield 空物件，避開實際 DB connection。"""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    def add(self, *args, **kwargs):
        pass

    async def flush(self):
        pass

    async def commit(self):
        pass
