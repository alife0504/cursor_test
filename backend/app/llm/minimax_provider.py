"""MiniMax provider（MiniMax-M3，國際版 api.minimax.io）。

MiniMax 提供 OpenAI 相容的 Chat Completions 端點，故直接沿用 `OpenAIProvider` 的
請求/回應解析邏輯，只覆寫：API key、base_url、預設模型、定價與 circuit breaker。

注意（M3 是推理模型）：
- 回應可能包含 `<think>...</think>` 推理區塊，且**思考 token 計入 output**；
  JSON 解析前需剝除 think 區塊（見 `app.agents.llm_helpers.extract_json_block`），
  額度不足時會 finish_reason='length' 被截斷（`llm_helpers` 會自動加大額度重試）。
- 支援極長上下文（標準檔 ≤512K input）。
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar

from app.core.circuit_breaker import CircuitBreaker, get_or_create_breaker
from app.core.errors import ExternalServiceError
from app.core.logging_config import get_logger
from app.llm.openai_provider import OpenAIProvider

if TYPE_CHECKING:
    from app.core.config import Settings

logger = get_logger(__name__)


class MiniMaxProvider(OpenAIProvider):
    """MiniMax provider（預設 MiniMax-M3）。OpenAI 相容，沿用父類 generate()。"""

    name: ClassVar[str] = "minimax"
    default_model: ClassVar[str] = "MiniMax-M3"

    # Pricing：(input_per_1k_usd, output_per_1k_usd)
    # 來源：MiniMax 官方定價（2026-08 抓取）標準檔（input ≤512K）：
    #   $0.30/1M input、$1.20/1M output（含官方「永久 5 折」後之價）。
    #   超過 512K input 之長上下文檔為 $0.60/$2.40（此處以標準檔計價，成本僅供追蹤參考）。
    pricing: ClassVar[dict[str, tuple[Decimal, Decimal]]] = {
        "MiniMax-M3": (Decimal("0.0003"), Decimal("0.0012")),
        "MiniMax-M2": (Decimal("0.0003"), Decimal("0.0012")),
    }

    def __init__(self, settings: Settings) -> None:
        # 跳過 OpenAIProvider.__init__ 的 breaker 設定，改用 minimax 自己的
        super().__init__(settings)
        self._client = None
        self.cb: CircuitBreaker = get_or_create_breaker("llm.minimax")

    @property
    def client(self) -> Any:
        """Lazy 建 AsyncOpenAI client，指向 MiniMax 相容端點（單例）。"""
        if self._client is not None:
            return self._client
        api_key = (
            self.settings.MINIMAX_API_KEY.get_secret_value()
            if self.settings.MINIMAX_API_KEY
            else None
        )
        if not api_key:
            raise ExternalServiceError(
                message_zh="未設定 MINIMAX_API_KEY，無法呼叫 MiniMax API",
                provider="minimax",
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as e:  # pragma: no cover
            raise ExternalServiceError(
                message_zh="openai SDK 未安裝；請執行 uv sync",
                provider="minimax",
            ) from e
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.settings.MINIMAX_BASE_URL,
        )
        return self._client

    async def health_check(self) -> bool:
        """探活：對 MiniMax 端點送一則極短 chat（models.list 不一定支援）。"""
        if not self.settings.MINIMAX_API_KEY:
            logger.warning("llm.minimax.health.no_api_key")
            return False
        try:
            resp = await self.client.chat.completions.create(
                model=self.settings.MINIMAX_DEFAULT_MODEL or self.default_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=16,
                timeout=10,
            )
            return bool(resp and resp.choices)
        except Exception as exc:
            logger.warning("llm.minimax.health.failed", error=str(exc))
            return False


__all__ = ["MiniMaxProvider"]
