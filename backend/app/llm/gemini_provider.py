"""GeminiProvider — Google Gemini 2.0 Flash 預設。

依 PLAN.md 第 14.4 章 + 第 20.4 章（Gemini embedding 也是預設）。

設計：
- 用 `langchain-google-genai.ChatGoogleGenerativeAI` 封裝 API call。
- Pricing 表（2026-05 來源：https://ai.google.dev/pricing）：
    gemini-2.0-flash：input $0.10/1M, output $0.40/1M
    gemini-1.5-pro：input $1.25/1M, output $5.00/1M（large context）
- token 計數延用 tiktoken gpt-4 encoder（誤差 ~10%，PLAN 14.9 已知陷阱）。
- health_check：判斷 `GOOGLE_API_KEY` 是否設定（不打 API，避免 startup 燒 quota）。

P14 補 fallback chain（先試 google，失敗轉 openai → anthropic）。
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
class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider（預設 gemini-2.0-flash）。"""

    name: ClassVar[str] = "google"
    default_model: ClassVar[str] = "gemini-2.5-flash"

    # Pricing：(input_per_1k_usd, output_per_1k_usd)
    # 來源：https://ai.google.dev/pricing（2026-05 抓取）
    # 注意：原表是 per 1M tokens；這裡換算 per 1k（除以 1000）
    pricing: ClassVar[dict[str, tuple[Decimal, Decimal]]] = {
        # gemini-2.0-flash：$0.10/1M input, $0.40/1M output
        "gemini-2.0-flash": (Decimal("0.0001"), Decimal("0.0004")),
        # gemini-1.5-flash：$0.075/1M input, $0.30/1M output
        "gemini-1.5-flash": (Decimal("0.000075"), Decimal("0.0003")),
        # gemini-1.5-pro：$1.25/1M input, $5.00/1M output
        "gemini-1.5-pro": (Decimal("0.00125"), Decimal("0.005")),
        # gemini-2.5-flash：$0.30/1M input, $2.50/1M output
        "gemini-2.5-flash": (Decimal("0.0003"), Decimal("0.0025")),
        # gemini-2.5-flash-lite：$0.10/1M input, $0.40/1M output
        "gemini-2.5-flash-lite": (Decimal("0.0001"), Decimal("0.0004")),
        # gemini-3.5-flash（若 API 已開放；暫沿用 2.5-flash 定價估算）
        "gemini-3.5-flash": (Decimal("0.0003"), Decimal("0.0025")),
    }

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._client_cache: dict[str, Any] = {}
        # P14：CircuitBreaker — 與 fallback_chain 共用 registry（key = "llm.google"）
        self.cb: CircuitBreaker = get_or_create_breaker("llm.google")

    def _build_client(self, model: str, temperature: float, max_tokens: int) -> Any:
        """Lazy 建 ChatGoogleGenerativeAI client（按 model 快取）。"""
        key = f"{model}:{temperature}:{max_tokens}"
        if key in self._client_cache:
            return self._client_cache[key]

        api_key = (
            self.settings.GOOGLE_API_KEY.get_secret_value()
            if self.settings.GOOGLE_API_KEY
            else None
        )
        if not api_key:
            raise ExternalServiceError(
                message_zh="未設定 GOOGLE_API_KEY，無法呼叫 Gemini API",
                provider="google",
            )

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as e:  # pragma: no cover
            raise ExternalServiceError(
                message_zh="langchain-google-genai 未安裝；請執行 uv sync",
                provider="google",
            ) from e

        client = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        self._client_cache[key] = client
        return client

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
        """呼叫 Gemini API。

        注意：P12 階段 graph 跑的是 stub Analyst，本方法只在
        state_trim summary 或 P13+ Analyst 中真實被呼叫。
        """
        actual_model = model or self.default_model
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
        except ImportError as e:  # pragma: no cover
            raise ExternalServiceError(
                message_zh="langchain-core 未安裝",
                provider="google",
            ) from e

        client = self._build_client(actual_model, temperature, max_tokens)
        if tools:
            client = client.bind_tools(tools)

        messages: list[Any] = [SystemMessage(content=system), HumanMessage(content=user)]

        try:
            ai_msg = await client.ainvoke(messages)
        except Exception as exc:
            logger.error(
                "llm.gemini.call_failed",
                model=actual_model,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise ExternalServiceError(
                message_zh=f"Gemini API 呼叫失敗：{exc}",
                provider="google",
                model=actual_model,
            ) from exc

        # 解析 token usage：langchain 在 ai_msg.usage_metadata 提供（v0.3+）
        usage_meta = getattr(ai_msg, "usage_metadata", None) or {}
        input_tokens = int(usage_meta.get("input_tokens", 0) or 0)
        output_tokens = int(usage_meta.get("output_tokens", 0) or 0)
        total_tokens = int(usage_meta.get("total_tokens", input_tokens + output_tokens) or 0)

        # fallback：若 metadata 缺漏，用 tiktoken 粗估
        if total_tokens == 0:
            input_tokens = await self.count_tokens(system + user)
            output_tokens = await self.count_tokens(str(getattr(ai_msg, "content", "") or ""))
            total_tokens = input_tokens + output_tokens

        cost = self.calc_cost(actual_model, input_tokens, output_tokens)

        # tool_calls：langchain 0.3 起放在 ai_msg.tool_calls
        tool_calls_raw = getattr(ai_msg, "tool_calls", None) or []
        tool_calls = [
            {"name": tc.get("name"), "arguments": tc.get("args") or tc.get("arguments") or {}}
            for tc in tool_calls_raw
            if isinstance(tc, dict)
        ]

        content_str = ""
        raw_content = getattr(ai_msg, "content", "") or ""
        if isinstance(raw_content, str):
            content_str = raw_content
        elif isinstance(raw_content, list):
            # langchain 有時回 list[dict]（多模態）
            content_str = "\n".join(
                str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in raw_content
            )
        else:
            content_str = str(raw_content)

        return LLMResponse(
            content=content_str,
            tool_calls=tool_calls,
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost,
            ),
            model=actual_model,
            finish_reason=str(
                (getattr(ai_msg, "response_metadata", {}) or {}).get("finish_reason", "stop")
            ),
        )

    async def health_check(self) -> bool:
        """探活：檢查 API key 設定 + langchain 套件可 import。

        不打 API（避免 startup 燒免費 quota）。實際 API 連通由第一次 call 驗證。
        """
        if not self.settings.GOOGLE_API_KEY:
            logger.warning("llm.gemini.health.no_api_key")
            return False
        try:
            import langchain_google_genai  # noqa: F401
        except ImportError:  # pragma: no cover
            logger.warning("llm.gemini.health.missing_package")
            return False
        return True


__all__ = ["GeminiProvider"]
