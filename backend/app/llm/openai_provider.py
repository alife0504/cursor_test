"""OpenAIProvider — OpenAI GPT-4o-mini 預設。

依 PLAN.md 第 14.4 章 LLM Fallback Chain + 第 19.3 章 cost tracking。

設計：
- 直接用 `openai.AsyncOpenAI` SDK（不繞 langchain-openai），讓 token usage 直接取自
  `response.usage`，cost 計算更精準。
- Pricing 表（2026-05 來源：https://openai.com/api/pricing/）：
    gpt-4o-mini：input $0.15/1M, output $0.60/1M
    gpt-4o：    input $2.50/1M, output $10.00/1M
- health_check：嘗試 `models.list(timeout=5)`；失敗 / 無 key → False。
- circuit breaker：與 fallback_chain 配合，內建 `self.cb`（用 get_or_create_breaker）。

P14 加入；註冊 name="openai"。
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar

from app.core.circuit_breaker import CircuitBreaker, get_or_create_breaker
from app.core.errors import ExternalServiceError
from app.core.logging_config import get_logger
from app.llm.base_provider import (
    BaseLLMProvider,
    LLMResponse,
    TokenUsage,
    register_llm_provider,
)

if TYPE_CHECKING:
    from app.core.config import Settings

logger = get_logger(__name__)


@register_llm_provider
class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider（預設 gpt-4o-mini）。"""

    name: ClassVar[str] = "openai"
    default_model: ClassVar[str] = "gpt-4o-mini"

    # Pricing：(input_per_1k_usd, output_per_1k_usd)
    # 來源：https://openai.com/api/pricing/（2026-05 抓取）
    pricing: ClassVar[dict[str, tuple[Decimal, Decimal]]] = {
        # gpt-4o-mini：$0.15/1M input, $0.60/1M output
        "gpt-4o-mini": (Decimal("0.00015"), Decimal("0.0006")),
        # gpt-4o：$2.50/1M input, $10.00/1M output
        "gpt-4o": (Decimal("0.0025"), Decimal("0.01")),
        # gpt-4o-2024-08-06：等同 gpt-4o
        "gpt-4o-2024-08-06": (Decimal("0.0025"), Decimal("0.01")),
    }

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._client: Any = None
        # CircuitBreaker — 與 fallback_chain 共用 registry（key = "llm.openai"）
        self.cb: CircuitBreaker = get_or_create_breaker("llm.openai")

    @property
    def client(self) -> Any:
        """Lazy 建 AsyncOpenAI client（單例）。"""
        if self._client is not None:
            return self._client
        api_key = (
            self.settings.OPENAI_API_KEY.get_secret_value()
            if self.settings.OPENAI_API_KEY
            else None
        )
        if not api_key:
            raise ExternalServiceError(
                message_zh="未設定 OPENAI_API_KEY，無法呼叫 OpenAI API",
                provider="openai",
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as e:  # pragma: no cover
            raise ExternalServiceError(
                message_zh="openai SDK 未安裝；請執行 uv sync",
                provider="openai",
            ) from e
        self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    async def generate(
        self,
        system: str,
        user: str,
        *,
        tools: list[Any] | None = None,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """呼叫 OpenAI Chat Completions API。

        tools：暫不接 OpenAI function calling（與 fallback chain 在不同 provider 間
        protocol 差異大；P14 先用 prompt-driven JSON output）。
        """
        actual_model = model or self.default_model
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            resp = await self.client.chat.completions.create(
                model=actual_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            logger.error(
                "llm.openai.call_failed",
                model=actual_model,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise ExternalServiceError(
                message_zh=f"OpenAI API 呼叫失敗：{exc}",
                provider="openai",
                model=actual_model,
            ) from exc

        # 解析 token usage
        usage_obj = getattr(resp, "usage", None)
        input_tokens = int(getattr(usage_obj, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage_obj, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage_obj, "total_tokens", input_tokens + output_tokens) or 0)
        cost = self.calc_cost(actual_model, input_tokens, output_tokens)

        # 內容
        choice = resp.choices[0] if resp.choices else None
        content = ""
        finish_reason: str | None = None
        if choice is not None:
            msg = getattr(choice, "message", None)
            if msg is not None:
                content = getattr(msg, "content", "") or ""
            finish_reason = getattr(choice, "finish_reason", None)

        return LLMResponse(
            content=content,
            tool_calls=[],
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost,
            ),
            model=actual_model,
            finish_reason=str(finish_reason) if finish_reason else None,
        )

    async def health_check(self) -> bool:
        """探活：嘗試 models.list(timeout=5)。

        無 API key → False；其他 import / API 異常 → False（不 raise）。
        """
        if not self.settings.OPENAI_API_KEY:
            logger.warning("llm.openai.health.no_api_key")
            return False
        try:
            await self.client.models.list(timeout=5)
            return True
        except Exception as exc:
            logger.warning("llm.openai.health.failed", error=str(exc))
            return False


__all__ = ["OpenAIProvider"]
