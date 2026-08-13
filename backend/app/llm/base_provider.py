"""BaseLLMProvider — LLM 統一抽象介面。

依 PLAN.md 第 14.4 章 LLM Fallback Chain + 第 18.2 章 Plugin Pattern。

設計：
- `BaseLLMProvider` ABC：所有 provider（Google / OpenAI / Anthropic）共同介面。
- `LLMResponse`：統一回應結構（content + tool_calls + usage）。
- `TokenUsage`：token 與 cost 統計（cost 計算依各 provider 自己的 pricing）。
- `LLM_PROVIDER_REGISTRY`：{name: class}，由 `@register_llm_provider` 自動填。
- token 計數預設用 `tiktoken`（gpt-4 encoder）粗估，誤差 ~10%（PLAN 14.9 已知陷阱）。

P12 階段：只實作 GoogleProvider。P14 補 OpenAI / Anthropic + Fallback Chain。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.logging_config import get_logger

if TYPE_CHECKING:
    from app.core.config import Settings

logger = get_logger(__name__)


# ── pydantic 模型 ────────────────────────────────────────


class TokenUsage(BaseModel):
    """單次 LLM 呼叫的 token 使用量 + 成本。"""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)
    total_tokens: int = Field(ge=0, default=0)
    cost_usd: Decimal = Field(default=Decimal("0"))
    """成本（美元，4 位小數）。"""

    @classmethod
    def zero(cls) -> TokenUsage:
        return cls(input_tokens=0, output_tokens=0, total_tokens=0, cost_usd=Decimal("0"))


class LLMResponse(BaseModel):
    """LLM 回應統一結構。"""

    model_config = ConfigDict(frozen=True)

    content: str
    """主要文字內容（可能為空若全部是 tool_calls）。"""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    """[{name, arguments}, ...]；P13 起 Analyst 用。"""
    usage: TokenUsage
    model: str
    """實際使用的模型 ID。"""
    finish_reason: str | None = None
    """e.g. "stop" / "length" / "tool_calls"。"""


# ── BaseLLMProvider ─────────────────────────────────────


class BaseLLMProvider(ABC):
    """LLM Provider 抽象基類。

    子類需設定：
    - `name`：registry key（"google" / "openai" / "anthropic"）
    - `default_model`：未指定 model 時的預設值
    - `pricing`：{model_id: (input_per_1k_usd, output_per_1k_usd)}（cost 計算用）

    子類 override：
    - `generate()`：主呼叫；回 `LLMResponse`
    - `health_check()`：startup 探活；回 bool（True = 連得到）
    """

    name: ClassVar[str] = "base"
    default_model: ClassVar[str] = ""
    pricing: ClassVar[dict[str, tuple[Decimal, Decimal]]] = {}
    """{model_id: (input_per_1k_usd, output_per_1k_usd)}。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
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
        """主呼叫。

        Args:
            system: System prompt（角色、規則）。
            user: User prompt（實際請求內容）。
            tools: 可選的 langchain BaseTool list（P13+ 才接 tool calling）。
            model: 覆寫 `default_model`。
            max_tokens: 輸出 token 上限。
            temperature: 0.0~1.0；越低越保守。

        Returns:
            `LLMResponse`。
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """探活：可選擇 ping API 或檢查 API key 存在。

        startup 時 fail-fast probe 用。
        """

    # ── 共用 helper：token 計數 ────────────────────
    async def count_tokens(self, text: str) -> int:
        """粗估 token 數（用 tiktoken gpt-4 encoder）。

        誤差 ~10%（Gemini / Claude tokenizer 不同；參考 PLAN 14.9 已知陷阱）。
        Provider 子類可 override 改用各家精準 tokenizer。
        """
        try:
            import tiktoken
        except ImportError:  # pragma: no cover
            # tiktoken 未裝 → 退化用字元數 / 4 估算
            return max(1, len(text) // 4)
        try:
            enc = tiktoken.encoding_for_model("gpt-4")
        except Exception:  # pragma: no cover
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))

    def calc_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Decimal:
        """依 pricing 表算 cost。Provider 子類若無 pricing 表 → 回 0 + warning。"""
        prices = self.pricing.get(model)
        if not prices:
            logger.warning("llm.cost.unknown_model", provider=self.name, model=model)
            return Decimal("0")
        ip, op = prices
        cost = (Decimal(input_tokens) * ip + Decimal(output_tokens) * op) / Decimal("1000")
        # quantize 到 6 位小數（與 DB analysis_reports.total_cost_usd 一致）
        return cost.quantize(Decimal("0.000001"))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} name={self.name!r} default_model={self.default_model!r}>"


# ── REGISTRY ───────────────────────────────────────────

LLM_PROVIDER_REGISTRY: dict[str, type[BaseLLMProvider]] = {}


def register_llm_provider(cls: type[BaseLLMProvider]) -> type[BaseLLMProvider]:
    """類別裝飾器：把子類註冊進 `LLM_PROVIDER_REGISTRY`。"""
    name = getattr(cls, "name", None)
    if not name or name == "base":
        raise ValueError(f"LLM Provider {cls.__name__} 必須設定 `name`（非空且不為 'base'）")
    if name in LLM_PROVIDER_REGISTRY and LLM_PROVIDER_REGISTRY[name] is not cls:
        logger.warning(
            "llm.register.duplicate",
            name=name,
            old=LLM_PROVIDER_REGISTRY[name].__name__,
            new=cls.__name__,
        )
    LLM_PROVIDER_REGISTRY[name] = cls
    logger.debug("llm.registered", name=name, cls=cls.__name__)
    return cls


def get_llm_provider(name: str, settings: Settings) -> BaseLLMProvider:
    """依名稱取得 provider 實例。

    Raises:
        KeyError: name 不在 registry。
    """
    cls = LLM_PROVIDER_REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"未註冊的 LLM provider: {name}；可用：{list(LLM_PROVIDER_REGISTRY.keys())}")
    return cls(settings)


__all__ = [
    "LLM_PROVIDER_REGISTRY",
    "BaseLLMProvider",
    "LLMResponse",
    "TokenUsage",
    "get_llm_provider",
    "register_llm_provider",
]
