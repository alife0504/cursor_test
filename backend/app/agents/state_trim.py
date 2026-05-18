"""State trim — 防 debate_history 無限累積撐爆 state。

依 PLAN.md 第 14.9 章 LangGraph State 控制。

策略：
- `MAX_STATE_SIZE_BYTES = 500_000`：state 序列化後若超過此 size → trigger trim。
- `MAX_DEBATE_HISTORY = 6`：超過 6 筆 debate 時，把舊的部分 LLM 摘要，最近 6 筆保留。
  trim 後：`[{role: "summary", content: <摘要>}] + recent 6`。
- 序列化用 `json.dumps(state, default=str)`，含 Decimal / datetime / UUID。
- P12 階段 stub Analyst 不會產生 debate_history（P13 才有），但本模組已可獨立測試。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.logging_config import get_logger

if TYPE_CHECKING:
    from app.agents.state import AgentState
    from app.llm.base_provider import BaseLLMProvider

logger = get_logger(__name__)


MAX_STATE_SIZE_BYTES = 500_000
"""state 序列化後的軟上限。超過會觸發 trim。"""

MAX_DEBATE_HISTORY = 6
"""debate_history 保留最近幾筆（舊的部分壓縮成 summary）。"""

SUMMARY_PROMPT_SYSTEM = (
    "你是金融分析摘要助手。請將以下 Bull/Bear 辯論訊息精簡為一段繁體中文摘要，"
    "保留：每輪雙方核心論點、關鍵數據與結論傾向。不要超過 500 字。"
)


def _default_serializer(obj: object) -> str:
    """為 Decimal / datetime / UUID 等非 JSON 原生型別提供字串化。"""
    return str(obj)


def estimate_state_size(state: AgentState) -> int:
    """估算 state 序列化後的位元組數。

    用於 graph node 之後檢查是否需要 trim。
    """
    try:
        text = json.dumps(state, default=_default_serializer, ensure_ascii=False)
    except (TypeError, ValueError) as e:  # pragma: no cover
        # 不可序列化欄位 → 回保守值（觸發 trim）
        logger.warning("state.estimate.serialize_failed", error=str(e))
        return MAX_STATE_SIZE_BYTES + 1
    return len(text.encode("utf-8"))


async def trim_debate_history(
    state: AgentState,
    llm: BaseLLMProvider | None = None,
) -> AgentState:
    """壓縮過長的 debate_history。

    策略：
    - 若 len(debate_history) <= MAX_DEBATE_HISTORY → 不動。
    - 否則：把前面 (n - MAX_DEBATE_HISTORY) 筆給 LLM 摘要 → 變成
      `[{role: "summary", content: <摘要>}] + recent MAX_DEBATE_HISTORY 筆`。
    - 若沒提供 `llm`（測試環境 / P12 stub）→ 用 truncation fallback：
      把舊訊息 join 為文字字串塞進 summary（不打 LLM）。

    本函數回**新的 state**（不修改傳入的 dict，遵守 LangGraph reducer 原則）。
    """
    history = state.get("debate_history") or []
    if len(history) <= MAX_DEBATE_HISTORY:
        return state

    keep = history[-MAX_DEBATE_HISTORY:]
    drop = history[:-MAX_DEBATE_HISTORY]

    summary_text: str
    if llm is not None:
        try:
            user_msg = json.dumps(drop, ensure_ascii=False, default=_default_serializer)
            resp = await llm.generate(
                system=SUMMARY_PROMPT_SYSTEM,
                user=f"以下是要摘要的辯論紀錄（JSON）:\n{user_msg}",
                max_tokens=600,
                temperature=0.2,
            )
            summary_text = resp.content.strip() or "[摘要失敗：LLM 回空]"
        except Exception as exc:
            logger.warning("state.trim.llm_failed", error=str(exc))
            summary_text = _truncation_fallback(drop)
    else:
        summary_text = _truncation_fallback(drop)

    new_history: list[dict[str, object]] = [
        {"role": "summary", "content": summary_text, "trimmed_count": len(drop)}
    ]
    new_history.extend(keep)

    # 回新 state（dict-shallow copy）
    new_state: AgentState = dict(state)  # type: ignore[assignment]
    new_state["debate_history"] = new_history
    logger.info(
        "state.trimmed",
        original=len(history),
        kept=len(keep),
        summarized=len(drop),
        used_llm=llm is not None,
    )
    return new_state


def _truncation_fallback(drop: list[dict[str, object]]) -> str:
    """LLM 不可用時的退路：把丟掉的訊息 join 為短字串（保留 role + 前 200 字）。"""
    parts: list[str] = []
    for msg in drop[-20:]:  # 最多回顧 20 筆，避免字串爆炸
        role = str(msg.get("role", "?"))
        raw_content = msg.get("content", "")
        content = str(raw_content)
        if len(content) > 200:
            content = content[:200] + "…"
        parts.append(f"- [{role}] {content}")
    body = "\n".join(parts)
    return f"[摘要：以下為前 {len(drop)} 筆訊息的截斷預覽（無 LLM 摘要）]\n{body}"


__all__ = [
    "MAX_DEBATE_HISTORY",
    "MAX_STATE_SIZE_BYTES",
    "estimate_state_size",
    "trim_debate_history",
]
