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
    """LLM 模型 ID（預設模型；gemini-2.5-flash / gpt-4o-mini / claude-haiku-4-5 等）。"""
    agent_models: dict[str, str]
    """各 agent 的模型覆寫（role → model id）；缺的 role 用 llm_model 預設。

    role 對應：market/fundamental/news/sentiment/chip（analyst）、bull/bear、manager、
    trader、aggressive/conservative/neutral（風險辯論）、risk_manager。
    """
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

    # ── 完整 agent 架構（trader + 風險團隊；還原原版）────
    investment_plan: str
    """ResearchManager 的研究計畫（文字綜述）；Trader / 風險團隊的輸入。"""
    trader_proposal: dict[str, Any] | None
    """Trader 的交易提案（TraderProposal.model_dump）。"""
    risk_debate_history: Annotated[list[dict[str, Any]], add]
    """[{stance, round, content}]；積極/保守/中立風險辯論累積。"""
    aggressive_arguments: Annotated[list[str], add]
    conservative_arguments: Annotated[list[str], add]
    neutral_arguments: Annotated[list[str], add]
    past_context: str
    """記憶系統注入：同標的歷史決策 + 跨標的教訓（RiskManager 用）。"""

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
    user_id: str
    """發起分析的用戶 ID（UUID 字串）。

    每筆 llm_usage 都要帶此 user_id 才能讓 QuotaService 按用戶彙總當月成本；
    缺此值 → 月配額（PLAN §19.3 L6）等同失效（所有 usage 落在 user_id=NULL）。
    """


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
    user_id: str = "",
    agent_models: dict[str, str] | None = None,
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
        "investment_plan": "",
        "trader_proposal": None,
        "risk_debate_history": [],
        "aggressive_arguments": [],
        "conservative_arguments": [],
        "neutral_arguments": [],
        "past_context": "",
        "signal": None,
        "report_md": None,
        "trace_id": trace_id,
        "analysis_id": analysis_id,
        "started_at": started_at,
        "llm_usage_total_tokens": 0,
        "user_id": user_id,
        "agent_models": dict(agent_models or {}),
    }
    return state


def resolve_agent_model(state: AgentState, role: str) -> str | None:
    """取某 agent 的模型：先看 agent_models[role]，否則回 llm_model 預設。

    回 None 表示讓 LLM chain 用其預設（caller 把 None 傳給 llm_call_with_schema 即可）。
    """
    models = state.get("agent_models") or {}
    return models.get(role) or state.get("llm_model") or None


__all__ = ["AgentState", "make_initial_state", "merge_dict", "resolve_agent_model"]
