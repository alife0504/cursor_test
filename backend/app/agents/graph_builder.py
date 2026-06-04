"""LangGraph 圖建構 — `build_graph(symbol, market)`。

依 PLAN.md 第 14.9 章 + 第 18.2 章 Plugin Pattern。

P12（前一版）：entry → analyst_1 → ... → placeholder_manager → END
P13（本版）：entry → analyst_1 → ... → bull → bear → (conditional: 再 bull or → manager) → END
              ↑ debate_rounds 控制 bull/bear 循環次數

設計：
- analyst 之間 sequential（簡化版；parallel 留 P14）。
- Bull/Bear 透過 conditional edge 控制輪次（多輪互相反駁）。
- Manager 是最終的「真實 manager」（取代 P12 的 placeholder_manager）。
- 若 debate_rounds=0：跳過 Bull/Bear，直接 manager（保留向下相容）。
- analyst_types=[] 或無支援 Analyst → manager-only graph（report 含「無 Analyst」說明）。
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
from app.agents.managers import ResearchManager
from app.agents.researchers import BearResearcher, BullResearcher
from app.agents.state import AgentState, make_initial_state
from app.agents.streaming import (
    EVENT_ANALYST_COMPLETED,
    EVENT_DEBATE_ARGUMENT,
    EVENT_SYNTHESIS_COMPLETED,
    publish_event,
)
from app.core.errors import ExternalServiceError
from app.core.logging_config import get_logger
from app.core.market_dispatcher import detect_region, market_to_region

if TYPE_CHECKING:
    from app.agents.tools import ToolRegistry
    from app.llm.base_provider import BaseLLMProvider

logger = get_logger(__name__)


# ── streaming wrapper（P14：每個 node 完成後 publish redis pubsub event）─────


def _stream_wrap(node_func: Any, *, event: str, node_name: str) -> Any:
    """把 graph node 包成「執行 + publish event」。

    Args:
        node_func: 原始 node coroutine（吃 state → dict）。
        event: 對應的 streaming event 名稱（analyst_completed / debate_argument / synthesis_completed）。
        node_name: 寫進 data 的識別名。

    Returns:
        async 包裝後的 coroutine（與原 node 介面相容）。
    """

    async def _wrapped(state: AgentState) -> dict[str, Any]:
        # 優雅降級：analyst node 若因「資料源不足」(ExternalServiceError) 失敗，
        # 不讓單一 analyst 缺資料炸掉整張圖 —— 標記為「略過」並續跑其餘 analyst /
        # 辯論 / manager。非 analyst node（bull/bear/manager）或非資料類例外仍如實拋出。
        degraded_reason: str | None = None
        try:
            result = await node_func(state)
        except ExternalServiceError as exc:
            if event != EVENT_ANALYST_COMPLETED:
                raise  # 只對 analyst node 降級；manager/researcher 的外部錯誤仍應失敗
            degraded_reason = str(exc)
            display = node_name
            cls = ANALYST_REGISTRY.get(node_name)
            if cls is not None:
                display = getattr(cls, "display_name_zh", node_name)
            logger.warning(
                "graph.analyst.degraded",
                node=node_name,
                analysis_id=str(state.get("analysis_id") or ""),
                reason=degraded_reason,
            )
            result = {
                "analyses": {
                    node_name: (
                        f"⚠️ 資料不足：{degraded_reason}。"
                        f"「{display}」因缺少必要資料而略過，未納入最終決策；"
                        "待資料源建置後重試即可取得完整分析。"
                    )
                }
            }
        analysis_id = state.get("analysis_id")
        if analysis_id:
            # 從 result 取摘要（避免送整段 analyses[name]，太大）
            data: dict[str, Any] = {"node": node_name}
            if degraded_reason is not None:
                data["degraded"] = True
                data["reason"] = degraded_reason
            if event == EVENT_ANALYST_COMPLETED:
                analyses = result.get("analyses") or {}
                # 取本 analyst 寫入 key 的長度做摘要
                content = analyses.get(node_name) or ""
                data["result_length"] = len(content) if isinstance(content, str) else 0
                data["preview"] = content[:200] if isinstance(content, str) else ""
            elif event == EVENT_DEBATE_ARGUMENT:
                # round 數從 result 嘗試取
                history = result.get("debate_history") or []
                if history:
                    last = history[-1]
                    data["role"] = last.get("role")
                    data["round"] = last.get("round")
                    content = last.get("content") or ""
                    data["preview"] = content[:200] if isinstance(content, str) else ""
            elif event == EVENT_SYNTHESIS_COMPLETED:
                signal = result.get("signal") or {}
                data["action"] = signal.get("action")
                data["confidence"] = signal.get("confidence")
                report = result.get("report_md") or ""
                data["report_length"] = len(report) if isinstance(report, str) else 0
            try:
                await publish_event(analysis_id, event, data)
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "graph.stream.publish_failed",
                    analysis_id=str(analysis_id),
                    event_name=event,
                    node=node_name,
                    error=str(exc),
                )
        return result

    _wrapped.__name__ = getattr(node_func, "__name__", node_name)  # type: ignore[attr-defined]
    return _wrapped


# ── placeholder manager（向下相容 P12 測試）─────


async def placeholder_manager(state: AgentState) -> dict[str, Any]:
    """P12 stub manager — 只在沒注入 llm 時用。

    P13 起預設改用真實 ResearchManager；本函數保留供 stub graph 測試。
    """
    analyses = state.get("analyses") or {}
    symbol = state.get("symbol", "?")
    market = state.get("market_code", "?")
    started_at = state.get("started_at", "")

    lines: list[str] = [
        f"# {symbol} ({market}) 分析報告 [stub]",
        "",
        "> Phase 12 框架測試報告（無 LLM 注入時的 fallback）。",
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
        debate_rounds: Bull/Bear 辯論輪次（0 = 跳過辯論直接 manager）。
        llm: BaseLLMProvider 實例（注入給 Analyst / Researcher / Manager）。
            * None → 用 placeholder_manager（P12 stub 模式，僅單測用）。
        tools: ToolRegistry 實例（注入給 Analyst）。
        checkpointer: langgraph checkpointer（None；P14 加 Redis）。

    Returns:
        compiled graph。

    Raises:
        ImportError: langgraph 未安裝。
    """
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as e:
        raise ImportError("langgraph 未安裝；請執行 `cd backend && uv sync`") from e

    # 1. 決定 region
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

    # 3. 實例化 Analyst
    analysts: list[BaseAnalyst] = [cls(llm=llm, tools=tools) for cls in analyst_classes]

    # 4. 建 StateGraph
    graph = StateGraph(AgentState)

    # 5. 決定 manager 模式：有 llm → 真實 ResearchManager；無 llm → placeholder
    use_real_manager = llm is not None
    manager_node_name = "manager"
    if use_real_manager:
        manager_instance = ResearchManager(llm=llm)
        graph.add_node(
            manager_node_name,
            _stream_wrap(
                manager_instance.synthesize,
                event=EVENT_SYNTHESIS_COMPLETED,
                node_name=manager_node_name,
            ),
        )
    else:
        graph.add_node(manager_node_name, placeholder_manager)

    # 6. 加 analyst nodes（P14：每個 node 加 streaming wrapper publish event）
    if not analysts:
        # 沒任何 analyst → 直接 entry → manager → END
        graph.set_entry_point(manager_node_name)
        graph.add_edge(manager_node_name, END)
    else:
        for analyst in analysts:
            graph.add_node(
                analyst.name,
                _stream_wrap(
                    analyst.analyze,
                    event=EVENT_ANALYST_COMPLETED,
                    node_name=analyst.name,
                ),
            )

        # 7. 加 bull/bear node（僅在 use_real_manager 且 debate_rounds > 0 時）
        has_debate = use_real_manager and debate_rounds > 0
        if has_debate:
            bull = BullResearcher(llm=llm)
            bear = BearResearcher(llm=llm)
            graph.add_node(
                "bull",
                _stream_wrap(bull.argue, event=EVENT_DEBATE_ARGUMENT, node_name="bull"),
            )
            graph.add_node(
                "bear",
                _stream_wrap(bear.argue, event=EVENT_DEBATE_ARGUMENT, node_name="bear"),
            )

        # 8. 連 edge
        graph.set_entry_point(analysts[0].name)
        for i in range(len(analysts) - 1):
            graph.add_edge(analysts[i].name, analysts[i + 1].name)

        if has_debate:
            # analyst[-1] → bull → bear → (conditional: bull 再來 or manager)
            graph.add_edge(analysts[-1].name, "bull")
            graph.add_edge("bull", "bear")

            def _decide_next(s: AgentState) -> str:
                """達到 debate_rounds 後 → manager，否則繼續 bull。"""
                rounds_done = len(s.get("bear_arguments") or [])
                return manager_node_name if rounds_done >= debate_rounds else "bull"

            graph.add_conditional_edges(
                "bear",
                _decide_next,
                {"bull": "bull", manager_node_name: manager_node_name},
            )
        else:
            graph.add_edge(analysts[-1].name, manager_node_name)

        graph.add_edge(manager_node_name, END)

    compiled = graph.compile(checkpointer=checkpointer)

    logger.info(
        "graph.built",
        symbol=symbol,
        market=str(market),
        region=region.value,
        analysts=[a.name for a in analysts],
        debate_rounds=debate_rounds,
        use_real_manager=use_real_manager,
        has_debate=use_real_manager and debate_rounds > 0 and bool(analysts),
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
