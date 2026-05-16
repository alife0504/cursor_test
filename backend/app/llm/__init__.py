"""LLM Provider abstraction — TradingAgents-TW v7.0 Phase 12 起。

依 PLAN.md 第 14.4 章 LLM Fallback + 第 18.2 章 Plugin Pattern。

模組結構：
- base_provider：`BaseLLMProvider` + `LLMResponse` + `TokenUsage`
- gemini_provider：`GeminiProvider`（Gemini 2.0 Flash 預設）
- LLM_PROVIDER_REGISTRY：`{name: class}`，提供 `register_llm_provider`、`get_llm_provider`
- Fallback Chain：P14 才加（P12 預設只 google）

side-effect imports：載入此 package 即註冊所有 provider。
"""

from __future__ import annotations

from app.llm.base_provider import (
    LLM_PROVIDER_REGISTRY,
    BaseLLMProvider,
    LLMResponse,
    TokenUsage,
    get_llm_provider,
    register_llm_provider,
)

# side-effect import：載入即註冊
from app.llm.gemini_provider import GeminiProvider

__all__ = [
    "LLM_PROVIDER_REGISTRY",
    "BaseLLMProvider",
    "GeminiProvider",
    "LLMResponse",
    "TokenUsage",
    "get_llm_provider",
    "register_llm_provider",
]
