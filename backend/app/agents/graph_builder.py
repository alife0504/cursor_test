"""LangGraph 圖建構 — `build_graph(symbol, market)`。

依 PLAN.md 第 14.9 章 + 第 18.2 章 Plugin Pattern。

設計：
- 接受 `symbol` + `market` → 自動判 region → 依 ANALYST_REGISTRY 篩出可用 Analyst。
- 圖結構（P12）：entry → analyst_1 → analyst_2 → ... → manager → END
  - analyst 之間 sequential（簡化版；P13 改為 parallel + Bull/Bear 辯論）
  - manager：P12 為 placeholder（只彙整 analyses 為 report_md）；P13 才接 LLM 結構化輸出
- 不上 checkpointer（P12/P13 跑 in-memory；P14 才用 Redis checkpointer）
- 過濾邏輯：region 不支援的 Analyst 直接 skip（如 US symbol 跳過 sentiment）
- 若 `analyst_types` 指定 → 進一步 intersect（白名單）

注意：本模組 import time 不會載入 langgraph，避免測試環境沒裝套件時整支 import 失敗。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.agents.analysts import (  # noqa: F401  side-effect: 觸發 register_analyst
    FundamentalAnalyst,
    MarketAnalyst,
    NewsAnalyst,
    SentimentAnalyst,
)
from app.agents.base_analyst import ANALYST_REGISTRY, BaseAnalyst, get_analysts_for_region
from app.agents.state import AgentState, make_initial_state
from app.core.logging_config import get_logger
from app.core.market_dispatcher import detect_region, market_to_region

if TYPE_CHECKING:
    from app.agents.tools import ToolRegistry
    from app.llm.base_provider import BaseLLMProvider

logger = get_logger(__name__)


# ── placeholder manager（P12 用，P13 補真實 LLM 結構化輸出）─────


async def placeholder_manager(state: AgentState) -> dict[str, Any]:
    """P12 manager stub — 把 analyses dict 彙整成 Markdown report_md。

    P13 改為：吃 debate_history + bull/bear arguments → LLM 結構化輸出
    {signal, confidence, target_price, stop_loss, reasoning, report_md}。
    """
    analyses = state.get("analyses") or {}
    symbol = state.get("symbol", "?")
    market = state.get("market_code", "?")
    started_at = state.get("started_at", "")

    lines: list[str] = [
        f"# {symbol} ({market}) 分析報告 [stub]",
        "",
        "> Phase 12 框架測試報告。實際 LLM 分析將在 Phase 13/14 完成。",
        f"> 啟動時間：{started_at}",
        "",
    ]
    for name, text in analyses.items():
        display = name
        cls = ANALYST_REGISTRY.get(name)
        if cls is not None:
            display = getattr(cls, "display_name_zh", name)
        lines.extend([f"## {display}", "", str(text), ""])

    if not analyses:
        lines.append("（無 Analyst 結果 — region 可能不支援任何 Analyst）")

    report_md = "\n".join(lines)
    signal = {
        "action": "HOLD",
        "confidence": 50,
        "reasoning": "[stub] Phase 12 框架測試，未進行真實判斷",
    }
    logger.info(
        "graph.manager.placeholder",
        symbol=symbol,
        market=market,
        analyses_count=len(analyses),
    )
    return {"signal": signal, "report_md": report_md}


# ── build_graph ───────────────────────────────────────


def build_graph(
    symbol: str,
    market: str | Any,
    *,
    analyst_types: list[str] | None = None,
    debate_rounds: int = 1,
    llm: BaseLLMProvider | None = None,
    tools: ToolRegistry | None = None,
    checkpointer: Any = None,
) -> Any:
    """組裝並回傳 compiled `StateGraph`。

    Args:
        symbol: 股票代號（推斷 region）。
        market: Market enum 或 str（"TWSE" / "NASDAQ" / ...）。
        analyst_types: 若給 → 過濾只用其中的 Analyst；None → 全部支援的。
        debate_rounds: P13 才用（Bull/Bear 輪次）。
        llm: BaseLLMProvider 實例（注入給 Analyst）。
        tools: ToolRegistry 實例（注入給 Analyst）。
        checkpointer: langgraph checkpointer（P12 預設 None；P14 加 Redis）。

    Returns:
        compiled graph（可呼叫 `.ainvoke(initial_state)`）。

    Raises:
        ImportError: langgraph 未安裝。
    """
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as e:
        raise ImportError("langgraph 未安裝；請執行 `cd backend && uv sync`") from e

    # 1. 決定 region（detect_region 對 symbol，market_to_region 對 market；
    #    兩者應一致，若不一致以 detect_region(symbol) 為準並警告）
    region_by_symbol = detect_region(symbol)
    try:
        region_by_market = market_to_region(market)
        if region_by_market != region_by_symbol:
            logger.warning(
                "graph.region.mismatch",
                symbol=symbol,
                market=str(market),
                by_symbol=region_by_symbol.value,
                by_market=region_by_market.value,
            )
    except Exception as exc:  # pragma: no cover
        logger.debug("graph.market_to_region.failed", market=str(market), error=str(exc))

    region = region_by_symbol

    # 2. 過濾 Analyst class
    analyst_classes = get_analysts_for_region(region, analyst_types=analyst_types)
    if not analyst_classes:
        logger.warning(
            "graph.no_analysts",
            symbol=symbol,
            region=region.value,
            requested=analyst_types,
        )

    # 3. 實例化（依 registry 順序）
    analysts: list[BaseAnalyst] = [cls(llm=llm, tools=tools) for cls in analyst_classes]

    # 4. 建 StateGraph
    graph = StateGraph(AgentState)

    if not analysts:
        # 沒任何 analyst → 直接 entry → manager → END
        graph.add_node("manager", placeholder_manager)
        graph.set_entry_point("manager")
        graph.add_edge("manager", END)
    else:
        for analyst in analysts:
            graph.add_node(analyst.name, analyst.analyze)
        graph.add_node("manager", placeholder_manager)

        # sequential：entry → analyst[0] → analyst[1] → ... → manager → END
        graph.set_entry_point(analysts[0].name)
        for i in range(len(analysts) - 1):
            graph.add_edge(analysts[i].name, analysts[i + 1].name)
        graph.add_edge(analysts[-1].name, "manager")
        graph.add_edge("manager", END)

    compiled = graph.compile(checkpointer=checkpointer)

    logger.info(
        "graph.built",
        symbol=symbol,
        market=str(market),
        region=region.value,
        analysts=[a.name for a in analysts],
        debate_rounds=debate_rounds,
        checkpointer=type(checkpointer).__name__ if checkpointer else None,
    )
    return compiled


# ── helper：建立初始 state（合 detect_region + ISO time）────


def build_initial_state(
    *,
    symbol: str,
    market: str,
    analysis_id: str,
    trace_id: str,
    analyst_types: list[str] | None = None,
    llm_model: str = "gemini-2.0-flash",
    debate_rounds: int = 1,
) -> AgentState:
    """組裝初始 state（給 celery task 用）。

    自動填：region / started_at；analyst_types None → 空 list（表示全部）。
    """
    region = detect_region(symbol)
    return make_initial_state(
        symbol=symbol,
        market=market,
        region=region.value,
        analyst_types=list(analyst_types or []),
        llm_model=llm_model,
        debate_rounds=debate_rounds,
        trace_id=trace_id,
        analysis_id=analysis_id,
        started_at=datetime.now(tz=UTC).isoformat(),
    )


__all__ = [
    "build_graph",
    "build_initial_state",
    "placeholder_manager",
]
