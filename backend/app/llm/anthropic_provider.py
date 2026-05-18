"""AnthropicProvider — Anthropic Claude Haiku 3.5 預設。

依 PLAN.md 第 14.4 章 LLM Fallback Chain + 第 19.3 章 cost tracking。

設計：
- 直接用 `anthropic.AsyncAnthropic` SDK（不繞 langchain-anthropic），取 `response.usage`。
- Pricing 表（2026-05 來源：https://www.anthropic.com/pricing）：
    claude-haiku-3-5：input $0.80/1M, output $4.00/1M
    claude-sonnet-4：input $3.00/1M, output $15.00/1M
- Anthropic SDK API：messages.create()；system 是獨立 param、user 走 messages list
  （與 OpenAI Chat API 不同；底層 protocol 差異大）。
- model name pin 到具體日期版（PLAN 14 已知陷阱：Anthropic model name 變動快）。

P14 加入；註冊 name="anthropic"。
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
class AnthropicProvider(BaseLLMProvider):
    """Anthropic provider（預設 claude-haiku-3-5-20241022）。"""

    name: ClassVar[str] = "anthropic"
    default_model: ClassVar[str] = "claude-haiku-3-5-20241022"

    # Pricing：(input_per_1k_usd, output_per_1k_usd)
    # 來源：https://www.anthropic.com/pricing（2026-05 抓取）
    pricing: ClassVar[dict[str, tuple[Decimal, Decimal]]] = {
        # Claude Haiku 3.5: $0.80/1M input, $4.00/1M output
        "claude-haiku-3-5-20241022": (Decimal("0.0008"), Decimal("0.004")),
        # Claude Sonnet 4: $3.00/1M input, $15.00/1M output
        "claude-sonnet-4-20250514": (Decimal("0.003"), Decimal("0.015")),
        # 舊 alias / fallback（同價）
        "claude-3-5-haiku-latest": (Decimal("0.0008"), Decimal("0.004")),
        "claude-3-5-sonnet-latest": (Decimal("0.003"), Decimal("0.015")),
    }

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._client: Any = None
        self.cb: CircuitBreaker = get_or_create_breaker("llm.anthropic")

    @property
    def client(self) -> Any:
        """Lazy 建 AsyncAnthropic client（單例）。"""
        if self._client is not None:
            return self._client
        api_key = (
            self.settings.ANTHROPIC_API_KEY.get_secret_value()
            if self.settings.ANTHROPIC_API_KEY
            else None
        )
        if not api_key:
            raise ExternalServiceError(
                message_zh="未設定 ANTHROPIC_API_KEY，無法呼叫 Anthropic API",
                provider="anthropic",
            )
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:  # pragma: no cover
            raise ExternalServiceError(
                message_zh="anthropic SDK 未安裝；請執行 uv sync",
                provider="anthropic",
            ) from e
        self._client = AsyncAnthropic(api_key=api_key)
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
        """呼叫 Anthropic messages.create API。

        注意：Anthropic 介面把 system 放 top-level（不在 messages list 內）。
        """
        actual_model = model or self.default_model
        try:
            resp = await self.client.messages.create(
                model=actual_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:
            logger.error(
                "llm.anthropic.call_failed",
                model=actual_model,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise ExternalServiceError(
                message_zh=f"Anthropic API 呼叫失敗：{exc}",
                provider="anthropic",
                model=actual_model,
            ) from exc

        # 解析 token usage
        usage_obj = getattr(resp, "usage", None)
        input_tokens = int(getattr(usage_obj, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage_obj, "output_tokens", 0) or 0)
        total_tokens = input_tokens + output_tokens
        cost = self.calc_cost(actual_model, input_tokens, output_tokens)

        # Anthropic content：list[ContentBlock]，每個 block 有 .type 與 .text（text type）
        content_parts: list[str] = []
        raw_blocks = getattr(resp, "content", None) or []
        for block in raw_blocks:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                t = getattr(block, "text", "") or ""
                content_parts.append(t)
        content = "\n".join(content_parts)

        finish_reason = getattr(resp, "stop_reason", None)

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
        """探活：發一個極小 message（max_tokens=1）。

        注意：Anthropic 沒有 GET 端點可以 ping（不像 OpenAI 的 models.list）；
        最便宜的健康檢查還是發一個 1-token message。失敗 / 無 key → False。
        """
        if not self.settings.ANTHROPIC_API_KEY:
            logger.warning("llm.anthropic.health.no_api_key")
            return False
        try:
            await self.client.messages.create(
                model=self.default_model,
                max_tokens=1,
                messages=[{"role": "user", "content": "."}],
                timeout=5,
            )
            return True
        except Exception as exc:
            logger.warning("llm.anthropic.health.failed", error=str(exc))
            return False


__all__ = ["AnthropicProvider"]
