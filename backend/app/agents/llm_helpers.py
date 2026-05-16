"""LLM 結構化輸出 helper + cost recording。

依 PLAN.md 第 14.4 章（LLM 介面）+ 第 20.3 章（schema 規範）+ 第 19.3 章（cost tracking）。

主要函式：
- `extract_json_block(text)` — 從 LLM 回應中抓 ```json``` 區塊（容錯處理多種格式）。
- `llm_call_with_schema(llm, system, user, schema)` — 跑 LLM 並用 Pydantic schema 驗證輸出；
  失敗時自動重試（最多 max_retries=2 次，附帶 ValidationError 訊息要求 repair）。
- `record_llm_usage(...)` — 寫一筆 llm_usage（hypertable on created_at）。

設計：
- LLM 結構化輸出在 Gemini / GPT / Claude 的最穩做法是「明確要求 JSON + 驗證 + 重試」，
  不依賴 Provider-specific structured output（langchain v0.3 在 Gemini 上仍偶有抖動）。
- repair retry 時把 user prompt 截斷（不無限累加）避免 token 爆。
- record_llm_usage 用 async session（caller 提供）；celery context 改用 sync_rw_session helper。
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.core.logging_config import get_logger
from app.models.quota import LLMUsage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Session

    from app.llm.base_provider import BaseLLMProvider, TokenUsage

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


# ── extract_json_block ──────────────────────────────────


_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*\n(.+?)\n```", re.DOTALL)


def extract_json_block(text: str) -> dict[str, Any] | list[Any]:
    """從 LLM 回應萃取 JSON block。

    支援格式：
      1. ```json\n{...}\n```（最常見 fence）
      2. ```{...}```（無 lang 標記）
      3. 直接 {...} 在文末（無 fence）
      4. 多個 block → 取最後一個（通常是最終輸出）

    Raises:
        ValueError: 找不到任何合法 JSON。
    """
    # 1. 嘗試 code fence
    matches = _FENCE_RE.findall(text)
    if matches:
        for candidate in reversed(matches):  # 取最後一個合法的
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    # 2. 嘗試找最後一個 top-level JSON object / array
    #    用 stack 配對 {} 或 [] — 從文末倒推
    for opener, closer in (("{", "}"), ("[", "]")):
        end = text.rfind(closer)
        if end == -1:
            continue
        depth = 0
        for i in range(end, -1, -1):
            ch = text[i]
            if ch == closer:
                depth += 1
            elif ch == opener:
                depth -= 1
                if depth == 0:
                    candidate = text[i : end + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    raise ValueError("LLM 回應中找不到合法 JSON 區塊")


# ── llm_call_with_schema ─────────────────────────────────


_MAX_USER_PROMPT_CHARS = 16000  # ~4k token；防 repair 越加越長


async def llm_call_with_schema(
    llm: BaseLLMProvider,
    system: str,
    user: str,
    schema: type[T],
    *,
    tools: list[Any] | None = None,
    model: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.3,
    max_retries: int = 2,
) -> tuple[T, TokenUsage]:
    """跑 LLM 並用 Pydantic schema 驗證結果；驗證失敗時自動 repair retry。

    Args:
        llm: BaseLLMProvider 實例。
        system: System prompt。
        user: User prompt。
        schema: 預期的 Pydantic Model class。
        max_retries: 額外重試次數（總共最多 max_retries+1 次呼叫）。

    Returns:
        (parsed model, accumulated TokenUsage)。

    Raises:
        ValidationError: 重試後仍無法符合 schema。
        ValueError: LLM 回應始終無法解析 JSON。
    """
    from app.llm.base_provider import TokenUsage as _TU

    # 把 schema 描述附在 system 末尾（不在每次重試重複加）
    schema_hint = (
        "\n\n## 最後輸出必須為以下 JSON Schema（合法 JSON，置於 ```json``` 區塊）\n"
        f"{json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)}"
    )
    system_with_schema = system + schema_hint

    current_user = user
    if len(current_user) > _MAX_USER_PROMPT_CHARS:
        logger.warning(
            "llm_helpers.user_prompt.truncated",
            original=len(current_user),
            truncated_to=_MAX_USER_PROMPT_CHARS,
        )
        current_user = current_user[:_MAX_USER_PROMPT_CHARS]

    total_in = 0
    total_out = 0
    total_cost = Decimal("0")
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        resp = await llm.generate(
            system=system_with_schema,
            user=current_user,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        total_in += resp.usage.input_tokens
        total_out += resp.usage.output_tokens
        total_cost += resp.usage.cost_usd

        try:
            parsed_json = extract_json_block(resp.content)
        except ValueError as e:
            last_error = e
            logger.warning(
                "llm_helpers.no_json",
                attempt=attempt + 1,
                error=str(e),
                content_preview=resp.content[:300],
            )
            if attempt < max_retries:
                # 提示 LLM 必須包 ```json```
                current_user = (
                    user[: _MAX_USER_PROMPT_CHARS - 800]
                    + "\n\n[REPAIR] 上次回應中找不到 ```json``` 區塊，"
                    "請務必把最終輸出包在 ```json ... ``` 區塊內。"
                )
                continue
            raise

        try:
            parsed: T = schema.model_validate(parsed_json)
        except ValidationError as e:
            last_error = e
            logger.warning(
                "llm_helpers.schema_invalid",
                attempt=attempt + 1,
                errors=e.error_count(),
                first_error=str(e.errors()[0]) if e.errors() else None,
            )
            if attempt < max_retries:
                err_str = str(e)[:1500]  # 控制長度
                current_user = (
                    user[: _MAX_USER_PROMPT_CHARS - 2000]
                    + f"\n\n[REPAIR] 上次輸出 schema 驗證失敗，錯誤如下：\n{err_str}\n"
                    "請依錯誤訊息修正後重新輸出符合 schema 的 JSON。"
                )
                continue
            raise

        usage_total = _TU(
            input_tokens=total_in,
            output_tokens=total_out,
            total_tokens=total_in + total_out,
            cost_usd=total_cost,
        )
        logger.info(
            "llm_helpers.success",
            schema=schema.__name__,
            attempts=attempt + 1,
            total_tokens=usage_total.total_tokens,
        )
        return parsed, usage_total

    # 理論上不會到這（每次迭代都會 return 或 raise）
    raise RuntimeError(
        f"llm_call_with_schema 異常結束，last_error={last_error}",
    )


# ── record_llm_usage ────────────────────────────────────


async def record_llm_usage(
    session: AsyncSession,
    *,
    analysis_id: str | UUID | None,
    user_id: str | UUID | None,
    provider: str,
    model: str,
    usage: TokenUsage,
    purpose: str | None = None,
    latency_ms: int | None = None,
    succeeded: bool = True,
    error_msg: str | None = None,
) -> None:
    """寫一筆 LLMUsage 到 DB（async session）。

    Args:
        session: async session（建議用 rw_session，需 ta_service_rw）。
        analysis_id: 對應 analysis_reports.id；可為 None（embedding 等獨立呼叫）。
        usage: TokenUsage 統計（含 cost）。
        purpose: analyst / debate / summary / embedding 等分類。

    本函數不 commit；caller 控制 transaction 邊界。
    """
    row = LLMUsage(
        user_id=_uuid_or_none(user_id),
        analysis_id=_uuid_or_none(analysis_id),
        provider=provider[:30],
        model=model[:100],
        purpose=purpose[:50] if purpose else None,
        prompt_tokens=int(usage.input_tokens),
        completion_tokens=int(usage.output_tokens),
        total_tokens=int(usage.total_tokens),
        cost_usd=Decimal(usage.cost_usd),
        latency_ms=latency_ms,
        succeeded=succeeded,
        error_msg=error_msg[:500] if error_msg else None,
    )
    session.add(row)
    await session.flush()
    logger.info(
        "llm_helpers.usage_recorded",
        provider=provider,
        model=model,
        purpose=purpose,
        total_tokens=row.total_tokens,
        cost_usd=str(row.cost_usd),
    )


def record_llm_usage_sync(
    session: Session,
    *,
    analysis_id: str | UUID | None,
    user_id: str | UUID | None,
    provider: str,
    model: str,
    usage: TokenUsage,
    purpose: str | None = None,
    latency_ms: int | None = None,
    succeeded: bool = True,
    error_msg: str | None = None,
) -> None:
    """同步版（celery task context 用）— 行為與 async 版一致。"""
    row = LLMUsage(
        user_id=_uuid_or_none(user_id),
        analysis_id=_uuid_or_none(analysis_id),
        provider=provider[:30],
        model=model[:100],
        purpose=purpose[:50] if purpose else None,
        prompt_tokens=int(usage.input_tokens),
        completion_tokens=int(usage.output_tokens),
        total_tokens=int(usage.total_tokens),
        cost_usd=Decimal(usage.cost_usd),
        latency_ms=latency_ms,
        succeeded=succeeded,
        error_msg=error_msg[:500] if error_msg else None,
    )
    session.add(row)
    session.flush()


def _uuid_or_none(v: str | UUID | None) -> UUID | None:
    if v is None:
        return None
    if isinstance(v, UUID):
        return v
    try:
        return UUID(str(v))
    except (ValueError, TypeError):
        return None


__all__ = [
    "extract_json_block",
    "llm_call_with_schema",
    "record_llm_usage",
    "record_llm_usage_sync",
]
