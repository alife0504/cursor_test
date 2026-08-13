"""per-agent 模型路由單元測試。"""

from __future__ import annotations

import pytest

from app.agents.state import resolve_agent_model
from app.llm.fallback_chain import provider_for_model

pytestmark = pytest.mark.unit


def test_provider_for_model_by_prefix() -> None:
    assert provider_for_model("gemini-2.0-flash") == "google"
    assert provider_for_model("models/text-embedding-004") == "google"
    assert provider_for_model("gpt-4o-mini") == "openai"
    assert provider_for_model("o1-preview") == "openai"
    assert provider_for_model("claude-haiku-3-5") == "anthropic"
    assert provider_for_model("claude-sonnet-4-20250514") == "anthropic"
    assert provider_for_model("unknown-model-x") is None
    assert provider_for_model(None) is None
    assert provider_for_model("") is None


def test_resolve_agent_model_override_then_default() -> None:
    state = {
        "llm_model": "gemini-2.0-flash",
        "agent_models": {"market": "gpt-4o-mini", "manager": "claude-haiku-3-5"},
    }
    # 有覆寫 → 用覆寫
    assert resolve_agent_model(state, "market") == "gpt-4o-mini"  # type: ignore[arg-type]
    assert resolve_agent_model(state, "manager") == "claude-haiku-3-5"  # type: ignore[arg-type]
    # 無覆寫 → 用 llm_model 預設
    assert resolve_agent_model(state, "news") == "gemini-2.0-flash"  # type: ignore[arg-type]


def test_resolve_agent_model_empty() -> None:
    assert resolve_agent_model({"llm_model": "x"}, "market") == "x"  # type: ignore[arg-type]
    assert resolve_agent_model({}, "market") is None  # type: ignore[arg-type]
