"""llm_helpers unit tests — Phase 13 條 Q（≥ 5 個測試）。

驗證：
- extract_json_block：多種 markdown 格式
- llm_call_with_schema：成功 / repair retry / 用盡 retry
- cost calculation 基本邏輯
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

import pytest
from pydantic import BaseModel, Field, ValidationError

from app.agents.llm_helpers import (
    extract_json_block,
    llm_call_with_schema,
)
from app.llm.base_provider import LLMResponse, TokenUsage

pytestmark = pytest.mark.unit


# ── extract_json_block ─────────────────────────────────


def test_extract_json_block_handles_code_fences() -> None:
    text = """
這是一些前文。

```json
{"a": 1, "b": "x"}
```
"""
    result = extract_json_block(text)
    assert result == {"a": 1, "b": "x"}


def test_extract_json_block_handles_no_lang_fence() -> None:
    text = """前文
```
{"key": "value"}
```
"""
    result = extract_json_block(text)
    assert result == {"key": "value"}


def test_extract_json_block_handles_inline_json_no_fence() -> None:
    text = '前文敘述。\n\n最終結果：{"action": "BUY", "confidence": 80}'
    result = extract_json_block(text)
    assert result == {"action": "BUY", "confidence": 80}


def test_extract_json_block_picks_last_block_when_multiple() -> None:
    """多個 fence → 取最後一個合法的。"""
    text = """
```json
{"intermediate": true}
```
最終：
```json
{"final": true}
```
"""
    result = extract_json_block(text)
    assert result == {"final": True}


def test_extract_json_block_raises_when_no_json() -> None:
    with pytest.raises(ValueError, match="JSON"):
        extract_json_block("這段裡完全沒有 JSON 區塊")


# ── llm_call_with_schema ───────────────────────────────


class _DummyModel(BaseModel):
    action: str = Field(min_length=1)
    confidence: int = Field(ge=0, le=100)


class _FakeLLM:
    """可控 mock LLM — 預先指定每次 generate 回什麼。"""

    name: ClassVar[str] = "fake"
    default_model: ClassVar[str] = "fake-1.0"
    pricing: ClassVar[dict] = {}

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def generate(
        self,
        system: str,
        user: str,
        *,
        tools=None,
        model=None,
        max_tokens=2048,
        temperature=0.3,
    ) -> LLMResponse:
        self.calls.append((system, user))
        content = self.responses.pop(0) if self.responses else "{}"
        return LLMResponse(
            content=content,
            tool_calls=[],
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost_usd=Decimal("0.001"),
            ),
            model="fake-1.0",
            finish_reason="stop",
        )


@pytest.mark.asyncio
async def test_schema_validation_succeeds_first_try() -> None:
    llm = _FakeLLM(['```json\n{"action": "BUY", "confidence": 80}\n```'])
    result, usage = await llm_call_with_schema(llm, "sys", "usr", _DummyModel)
    assert result.action == "BUY"
    assert result.confidence == 80
    assert usage.total_tokens == 150
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_schema_validation_retries_on_failure() -> None:
    """第一次回 invalid（confidence 超過 100）→ 第二次回正確。"""
    llm = _FakeLLM(
        [
            '```json\n{"action": "BUY", "confidence": 150}\n```',  # invalid
            '```json\n{"action": "BUY", "confidence": 50}\n```',  # ok
        ]
    )
    result, usage = await llm_call_with_schema(llm, "sys", "usr", _DummyModel, max_retries=2)
    assert result.confidence == 50
    # 累計 token = 兩次 150
    assert usage.total_tokens == 300
    assert len(llm.calls) == 2
    # 第二次 user prompt 應含 [REPAIR]
    assert "[REPAIR]" in llm.calls[1][1]


@pytest.mark.asyncio
async def test_schema_validation_gives_up_after_max_retries() -> None:
    """全部都 invalid → 用盡 retry 後 raise ValidationError。"""
    llm = _FakeLLM(
        [
            '```json\n{"action": "BUY", "confidence": 200}\n```',
            '```json\n{"action": "BUY", "confidence": 200}\n```',
            '```json\n{"action": "BUY", "confidence": 200}\n```',
        ]
    )
    with pytest.raises(ValidationError):
        await llm_call_with_schema(llm, "sys", "usr", _DummyModel, max_retries=2)
    # 用了 1 + 2 = 3 次
    assert len(llm.calls) == 3


@pytest.mark.asyncio
async def test_no_json_block_triggers_repair() -> None:
    llm = _FakeLLM(
        [
            "完全沒有 JSON 的純文字回應",  # 無 JSON
            '```json\n{"action": "HOLD", "confidence": 50}\n```',  # 第二次有
        ]
    )
    result, _ = await llm_call_with_schema(llm, "sys", "usr", _DummyModel, max_retries=2)
    assert result.action == "HOLD"
    # 第二次 user 應含 [REPAIR]
    assert "[REPAIR]" in llm.calls[1][1]


# ── cost calculation ────────────────────────────────────


def test_cost_calculation_for_gemini_flash() -> None:
    """驗 GeminiProvider.calc_cost 對 gemini-2.0-flash 模型的數字正確。"""
    from app.llm.gemini_provider import GeminiProvider

    # gemini-2.0-flash: input $0.0001/1k, output $0.0004/1k
    # 1000 in + 500 out → 0.1 cents + 0.2 cents = 0.0003 USD
    # 不過 Decimal('1') 與 1 等價，所以直接呼叫類別方法
    cost = GeminiProvider.calc_cost(
        GeminiProvider.__new__(GeminiProvider),
        "gemini-2.0-flash",
        1000,
        500,
    )
    assert cost == Decimal("0.000300")
