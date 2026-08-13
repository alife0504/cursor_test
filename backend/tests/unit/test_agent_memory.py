"""AgentMemory 單元測試 — 純函數 + 優雅降級（不依賴 Qdrant/嵌入）。"""

from __future__ import annotations

import pytest

from app.agents.memory import AgentMemory, build_situation_text

pytestmark = pytest.mark.unit


def test_build_situation_text_includes_symbol_and_analysts() -> None:
    s = build_situation_text("2330", {"market": '{"trend":"上升"}', "news": "利多消息"})
    assert "2330" in s
    assert "market" in s
    assert "news" in s


def test_build_situation_text_empty_analyses() -> None:
    s = build_situation_text("2454", {})
    assert "2454" in s


async def test_retrieve_graceful_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """無嵌入能力（_embed→None）時，retrieve 應回 "" 而非拋出。"""

    async def _no_embed(self: AgentMemory, text: str) -> None:
        return None

    monkeypatch.setattr(AgentMemory, "_embed", _no_embed)
    out = await AgentMemory().retrieve(symbol="2330", region="", situation="x")
    assert out == ""


async def test_store_graceful_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """無 Qdrant（_ensure→False）時，store 應 no-op 不拋出。"""

    async def _no_ensure(self: AgentMemory) -> bool:
        return False

    monkeypatch.setattr(AgentMemory, "_ensure", _no_ensure)
    # 不應拋出任何例外
    await AgentMemory().store(
        symbol="2330", region="", situation="x", decision={"action": "BUY", "confidence": 70}
    )
