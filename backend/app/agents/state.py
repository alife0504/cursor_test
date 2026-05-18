"""LangGraph AgentState — TypedDict 形式的圖狀態定義。

依 PLAN.md 第 14.9 章 LangGraph State 控制 + 第 14.4 章 LLM Fallback。

設計重點：
- 「累積欄位」用 `Annotated[list, add]` 讓 LangGraph 自動 reduce（多 node 寫入時不 overwrite）
- 「終結欄位」（signal / report_md）只在 manager / final node 寫一次，故不需 reduce
- `analyses: dict[str, str]` 由 graph_builder 預先放空 dict 並 each analyst 在 analyze() 結果中
  以 `{"analyses": {name: text}}` 的 partial 回傳——langgraph 預設行為會 shallow merge dict。
  但「以防萬一」我們提供 `merge_dict` reducer，可讀性更佳，且避免不同版本 langgraph 行為差異。

P12 階段 stub Analyst 只填 `analyses[name]`；
P13 起 Bull/Bear/Manager 會寫 debate_history / bull_arguments / bear_arguments / signal。
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

# ── reducer：用於 dict 累積（多 analyst 同時寫 analyses[name]）──────


def merge_dict(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """淺合併兩個 dict — 右側值覆蓋左側同 key。

    LangGraph reducer 要求是 pure function：不可 mutate 輸入。
    """
    base: dict[str, Any] = dict(left) if left else {}
    if right:
        base.update(right)
    return base


# ── AgentState ─────────────────────────────────────────


class AgentState(TypedDict, total=False):
    """LangGraph 共用狀態。

    所有 Analyst / Researcher / Manager 都讀寫此 state。
    `total=False` 讓欄位非必填（langgraph 預設 partial update 模式）。

    欄位分組：
    1. 輸入（caller 設定）：symbol / market / region / debate_rounds / llm_model / analyst_types
    2. 累積欄位（多 node 寫，reducer 自動合併）：analyses / debate_history /
       bull_arguments / bear_arguments
    3. 終結欄位（最後一個 node 寫）：signal / report_md
    4. metadata：trace_id / analysis_id / started_at / llm_usage_total_tokens
    """

    # ── 輸入 ─────────────────────────────────────────
    symbol: str
    """股票代號（如 "2330" / "AAPL"）。"""
    market_code: str
    """市場（TWSE / TPEX / NASDAQ / NYSE / AMEX）。

    注意：本欄位名稱故意與 ANALYST_REGISTRY 的 "market" key 區分，
    避免 langgraph 報 "node name conflicts with state key" 錯誤。
    DB 模型 (analysis_reports.market) 與 API schema 仍叫 market。
    """
    region: str
    """區域（TW / US）— detect_region 結果，避免重複解析。"""
    debate_rounds: int
    """Bull/Bear 辯論輪次（P13 才使用）。"""
    llm_model: str
    """LLM 模型 ID（gemini-2.0-flash / gpt-4o-mini / claude-3-5-haiku 等）。"""
    analyst_types: list[str]
    """請求啟用的 Analyst 名稱（如 ["market", "fundamental"]）。"""

    # ── 累積欄位（多 node 可寫；reducer 合併）─────────
    analyses: Annotated[dict[str, str], merge_dict]
    """{analyst_name: analysis_text}；每個 Analyst 在 analyze() 結束時寫入自己的 key。"""

    debate_history: Annotated[list[dict[str, Any]], add]
    """[{round, role, content, tokens?}, ...]。P13 Bull/Bear/Manager 才會累積。

    超過 6 筆會在 state_trim 階段壓縮：[summary] + 最近 6 筆。
    """

    bull_arguments: Annotated[list[str], add]
    """Bull researcher 每輪論點（P13）。"""
    bear_arguments: Annotated[list[str], add]
    """Bear researcher 每輪論點（P13）。"""

    # ── 終結欄位（manager / final 才寫一次）─────────
    signal: dict[str, Any] | None
    """{action: "BUY"/"SELL"/"HOLD"/..., confidence: 0~100, reasoning: str,
       target_price?, stop_loss?, take_profit?}。"""

    report_md: str | None
    """繁中 Markdown 最終報告。"""

    # ── metadata ─────────────────────────────────────
    trace_id: str
    """跨 process trace ID（HTTP → celery → WS 全鏈路）。"""
    analysis_id: str
    """analysis_reports.id（UUID 字串）。"""
    started_at: str
    """ISO 8601 (UTC)。"""
    llm_usage_total_tokens: int
    """累計 token 數（cost 計算 + 月配額判斷依據）。"""


# ── 工廠函數 ───────────────────────────────────────────


def make_initial_state(
    *,
    symbol: str,
    market: str,
    region: str,
    analyst_types: list[str],
    llm_model: str,
    debate_rounds: int,
    trace_id: str,
    analysis_id: str,
    started_at: str,
) -> AgentState:
    """建立初始 state（所有累積欄位 = 空容器，終結欄位 = None）。

    Caller 必須提供所有輸入欄位；不依賴 default 避免欄位漏設。

    Args:
        market: 交易所代碼（TWSE / TPEX / NASDAQ / ...）。
          注意 state 內部欄位名為 `market_code`（避開 langgraph node name 衝突）。
    """
    state: AgentState = {
        "symbol": symbol,
        "market_code": market,
        "region": region,
        "debate_rounds": debate_rounds,
        "llm_model": llm_model,
        "analyst_types": list(analyst_types),
        "analyses": {},
        "debate_history": [],
        "bull_arguments": [],
        "bear_arguments": [],
        "signal": None,
        "report_md": None,
        "trace_id": trace_id,
        "analysis_id": analysis_id,
        "started_at": started_at,
        "llm_usage_total_tokens": 0,
    }
    return state


__all__ = ["AgentState", "make_initial_state", "merge_dict"]
