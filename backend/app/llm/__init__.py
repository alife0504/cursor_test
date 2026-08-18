"""LLM Provider abstraction — TradingAgents-TW v7.0 Phase 12 起。

依 PLAN.md 第 14.4 章 LLM Fallback + 第 18.2 章 Plugin Pattern。

模組結構：
- base_provider：`BaseLLMProvider` + `LLMResponse` + `TokenUsage`
- gemini_provider：`GeminiProvider`（Gemini 2.0 Flash 預設）
- openai_provider：`OpenAIProvider`（gpt-4o-mini，P14 加）
- anthropic_provider：`AnthropicProvider`（claude-haiku-3-5，P14 加）
- fallback_chain：`LLMFallbackChain`（P14 加，依 14.4 章 chain map）
- LLM_PROVIDER_REGISTRY：`{name: class}`，提供 `register_llm_provider`、`get_llm_provider`

`get_llm_chain(settings)`：建構並回 `LLMFallbackChain`（依 .env 設定哪些 provider 可用）。

side-effect imports：載入此 package 即註冊所有 provider。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.logging_config import get_logger

# side-effect imports：載入即註冊（順序：google → openai → anthropic）
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base_provider import (
    LLM_PROVIDER_REGISTRY,
    BaseLLMProvider,
    LLMResponse,
    TokenUsage,
    get_llm_provider,
    register_llm_provider,
)
from app.llm.fallback_chain import FALLBACK_CHAIN, LLMFallbackChain
from app.llm.gemini_provider import GeminiProvider
from app.llm.minimax_provider import MiniMaxProvider
from app.llm.openai_provider import OpenAIProvider

if TYPE_CHECKING:
    from app.core.config import Settings

logger = get_logger(__name__)


def available_providers(settings: Settings) -> list[str]:
    """回傳目前已配置 API key（即可實際使用）的 provider name list。

    供前端標示／禁用「無對應金鑰」的模型選項，避免使用者選了 GPT/Claude 卻被
    fallback chain 靜默降級為預設 Gemini 而不自知。順序固定：google → openai → anthropic。
    """
    out: list[str] = []
    if settings.GOOGLE_API_KEY:
        out.append("google")
    if settings.OPENAI_API_KEY:
        out.append("openai")
    if settings.ANTHROPIC_API_KEY:
        out.append("anthropic")
    return out


def get_llm_chain(settings: Settings) -> LLMFallbackChain:
    """建構 `LLMFallbackChain` — 只把有 API key 的 provider 加進來。

    Args:
        settings: `app.core.config.Settings` 實例。

    Returns:
        `LLMFallbackChain`：primary = `settings.LLM_DEFAULT_PROVIDER`。

    Raises:
        ValueError: 沒有任何 provider 配置 API key（至少要一個）。

    Note:
        - `settings.LLM_DEFAULT_PROVIDER` 必須對應「有配置 key」的 provider；
          否則 fall back 到第一個可用 provider（log warning）。
        - 在 lifespan 中 caller 應對每個 provider 跑 health_check() 並 log。
    """
    providers: dict[str, BaseLLMProvider] = {}
    if settings.GOOGLE_API_KEY:
        providers["google"] = GeminiProvider(settings)
    if settings.OPENAI_API_KEY:
        providers["openai"] = OpenAIProvider(settings)
    if settings.ANTHROPIC_API_KEY:
        providers["anthropic"] = AnthropicProvider(settings)
    if settings.MINIMAX_API_KEY:
        providers["minimax"] = MiniMaxProvider(settings)

    if not providers:
        raise ValueError(
            "至少需配置一個 LLM provider 的 API key "
            "(GOOGLE_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY / MINIMAX_API_KEY)"
        )

    primary = settings.LLM_DEFAULT_PROVIDER
    if primary not in providers:
        fallback_primary = next(iter(providers))
        logger.warning(
            "llm_chain.primary_not_configured",
            requested=primary,
            available=list(providers.keys()),
            fallback_primary=fallback_primary,
        )
        primary = fallback_primary

    chain = LLMFallbackChain(providers, primary=primary)
    logger.info(
        "llm_chain.built",
        primary=primary,
        providers=list(providers.keys()),
    )
    return chain


__all__ = [
    "FALLBACK_CHAIN",
    "LLM_PROVIDER_REGISTRY",
    "AnthropicProvider",
    "BaseLLMProvider",
    "GeminiProvider",
    "LLMFallbackChain",
    "LLMResponse",
    "OpenAIProvider",
    "TokenUsage",
    "available_providers",
    "get_llm_chain",
    "get_llm_provider",
    "register_llm_provider",
]
