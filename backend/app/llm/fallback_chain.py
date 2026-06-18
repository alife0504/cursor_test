"""LLM Fallback Chain — 主 provider 失敗自動切下一個。

依 PLAN.md 第 14.4 章：

    LLM_FALLBACK_CHAIN = {
        "google":    ["openai", "anthropic"],
        "openai":    ["google", "anthropic"],
        "anthropic": ["google", "openai"],
    }

設計重點：
- `LLMFallbackChain` 是 `BaseLLMProvider` 的 **包裝器**（不繼承），但提供同樣的
  `generate(system, user, ...)` 介面，讓 Analyst 可以無痛從 single provider 換成 chain。
- 每個 provider 自帶 `cb`（CircuitBreaker）；CB OPEN 直接跳過該 provider。
- `generate_with_chain()` 額外回傳 `used_provider` 字串，方便 cost tracking / log。
- 主 provider 失敗 / 全部失敗 → raise `ExternalServiceError(name="llm_fallback_chain", ...)`。

`generate(system, user, ...)` 為 BaseLLMProvider 相容介面：
- 回 `LLMResponse`（caller 不需知道用了哪個 provider）
- 內部把 used_provider 寫到 `self.last_used_provider`（供 caller 查詢 cost 與 log 用）
- `self.name` 動態回 last_used_provider 或 primary（讓 record_llm_usage 寫對 provider）
- `self.default_model` 動態回 last_used_provider 的 default_model
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.errors import ExternalServiceError
from app.core.logging_config import get_logger

if TYPE_CHECKING:
    from app.llm.base_provider import BaseLLMProvider, LLMResponse

logger = get_logger(__name__)


# 第 14.4 章 fallback chain 定義
FALLBACK_CHAIN: dict[str, list[str]] = {
    "google": ["openai", "anthropic"],
    "openai": ["google", "anthropic"],
    "anthropic": ["google", "openai"],
}


def provider_for_model(model: str | None) -> str | None:
    """依 model id 前綴推斷對應 provider（per-agent 跨 provider 模型路由用）。

    gemini* → google；gpt*/o1*/o3* → openai；claude* → anthropic；無法判斷 → None。
    """
    if not model:
        return None
    m = model.lower().removeprefix("models/")
    if m.startswith("gemini") or m.startswith("text-embedding"):
        return "google"
    if m.startswith(("gpt", "o1", "o3", "o4", "chatgpt")):
        return "openai"
    if m.startswith("claude"):
        return "anthropic"
    return None


class LLMFallbackChain:
    """LLM Provider Fallback Chain（PLAN 14.4）。

    Usage：
        chain = LLMFallbackChain({"google": gp, "openai": op, ...}, primary="google")
        resp = await chain.generate(system, user)
        # chain.last_used_provider → "google" or "openai" or "anthropic"

    若需要明確指定 primary（每次呼叫不同）：
        resp, used = await chain.generate_with_chain("anthropic", system, user)
    """

    def __init__(
        self,
        providers: dict[str, BaseLLMProvider],
        *,
        primary: str = "google",
    ) -> None:
        """Args:
        providers: name → provider 實例。空 dict 會在第一次呼叫時 raise。
        primary: 預設 primary provider name；可在 generate_with_chain 覆寫。
        """
        if not providers:
            raise ValueError("LLMFallbackChain 至少需要一個 provider")
        self.providers: dict[str, BaseLLMProvider] = providers
        self.primary: str = primary
        # 每次 generate 後更新（供外部讀，記錄 cost 用）
        self.last_used_provider: str | None = None
        # 最近一次實際送出的 model id（per-agent 覆寫 / fallback 後可能 != default_model）；
        # record_llm_usage 用它寫對「實際使用的模型」而非 provider 預設。
        self.last_used_model: str | None = None

    @property
    def name(self) -> str:
        """為了相容 BaseLLMProvider 介面（讓 record_llm_usage 寫對 provider）。

        最近一次成功 generate 用的 provider；尚未呼叫 → primary。
        """
        return self.last_used_provider or self.primary

    @property
    def default_model(self) -> str:
        """動態回 last_used_provider 的 default_model（或 primary）。"""
        name = self.last_used_provider or self.primary
        p = self.providers.get(name)
        return getattr(p, "default_model", "unknown") if p else "unknown"

    # ── 主要介面：generate_with_chain（回 used_provider）────

    async def generate_with_chain(
        self,
        primary: str,
        system: str,
        user: str,
        *,
        tools: list[Any] | None = None,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> tuple[LLMResponse, str]:
        """嘗試 primary 後 fallback；回 (LLMResponse, used_provider_name)。

        - CB OPEN 的 provider 直接跳過。
        - 失敗的 provider 會 record_failure（推進 CB）。
        - 成功的 provider 會 record_success（reset CB）。

        Raises:
            ExternalServiceError(name="llm_fallback_chain"): 所有 provider 都失敗（或被跳過）。
        """
        chain_order = [primary, *FALLBACK_CHAIN.get(primary, [])]
        last_exc: BaseException | None = None
        last_skipped: list[str] = []

        for provider_name in chain_order:
            provider = self.providers.get(provider_name)
            if provider is None:
                # 該 provider 未配置（API key 缺）→ 跳過
                last_skipped.append(provider_name)
                logger.debug(
                    "llm_fallback.provider_unavailable",
                    provider=provider_name,
                )
                continue

            cb = getattr(provider, "cb", None)
            if cb is not None and str(cb.state) == "OPEN":
                logger.warning(
                    "llm_fallback.cb_open_skip",
                    provider=provider_name,
                    state=str(cb.state),
                )
                last_skipped.append(provider_name)
                continue

            # 指定的 model 若不屬於本 provider（fallback 到別家）→ 用該 provider 預設模型，
            # 避免把 gpt-* 丟給 Gemini 這種無意義呼叫。
            pm = provider_for_model(model)
            effective_model = model if (pm is None or pm == provider_name) else None

            try:
                resp = await provider.generate(
                    system=system,
                    user=user,
                    tools=tools,
                    model=effective_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as exc:
                last_exc = exc
                if cb is not None:
                    try:
                        await cb.record_failure()
                    except Exception as cb_exc:  # pragma: no cover
                        logger.warning(
                            "llm_fallback.cb_record_failure_failed",
                            provider=provider_name,
                            error=str(cb_exc),
                        )
                logger.warning(
                    "llm_fallback.provider_failed",
                    provider=provider_name,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                continue

            # 成功
            if cb is not None:
                try:
                    await cb.record_success()
                except Exception as cb_exc:  # pragma: no cover
                    logger.warning(
                        "llm_fallback.cb_record_success_failed",
                        provider=provider_name,
                        error=str(cb_exc),
                    )
            self.last_used_provider = provider_name
            # 記錄實際送出的 model（effective_model 為 None 表示用該 provider 預設）
            self.last_used_model = effective_model or getattr(provider, "default_model", None)
            logger.info(
                "llm_fallback.success",
                provider=provider_name,
                primary=primary,
                used_fallback=provider_name != primary,
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
            )
            return resp, provider_name

        # 所有 provider 都 fail / 跳過
        raise ExternalServiceError(
            message_zh=f"所有 LLM provider 皆失敗（chain={chain_order}, skipped={last_skipped}）",
            name="llm_fallback_chain",
            primary=primary,
            chain=chain_order,
            skipped=last_skipped,
            reason=str(last_exc) if last_exc else "all_skipped",
        )

    # ── BaseLLMProvider 相容介面：generate(...) ────

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
        """BaseLLMProvider 相容介面 — 用 self.primary 作 primary。

        Analyst 可以無痛從 GeminiProvider 換成 LLMFallbackChain。
        used_provider 寫到 self.last_used_provider；caller 透過 chain.name 拿到。

        per-agent 模型：若給 model，依其 provider 當 primary（gpt→openai、claude→anthropic、
        gemini→google）；無法判斷則用 self.primary。
        """
        primary = provider_for_model(model) or self.primary
        resp, _used = await self.generate_with_chain(
            primary,
            system,
            user,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp

    # ── health_check：所有 provider OR 取（至少一個就 True）────

    async def health_check(self) -> bool:
        """至少一個 provider health 即視為 chain 健康。"""
        for name, p in self.providers.items():
            try:
                ok = await p.health_check()
            except Exception as exc:  # pragma: no cover
                logger.warning("llm_fallback.health_check_failed", provider=name, error=str(exc))
                ok = False
            if ok:
                return True
        return False

    # ── helper：給外部 query 用 ────

    def get(self, name: str) -> BaseLLMProvider | None:
        """取得單一 provider（測試用）。"""
        return self.providers.get(name)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<LLMFallbackChain primary={self.primary} "
            f"providers={list(self.providers.keys())} "
            f"last_used={self.last_used_provider}>"
        )


__all__ = ["FALLBACK_CHAIN", "LLMFallbackChain", "provider_for_model"]
