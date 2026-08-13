"""LangGraph Agents — TradingAgents-TW v7.0 Phase 12 起。

依 PLAN.md 第 14.9 章 LangGraph State 控制 + 第 18.2 章 Plugin Pattern。

模組結構：
- state：`AgentState` TypedDict（debate_history / analyses / signal / ...）
- base_analyst：`BaseAnalyst` ABC + `ANALYST_REGISTRY`
- analysts/：4 種台股 Analyst stub（market/fundamental/news/sentiment）
- tools/：`ToolRegistry`（全部用 ta_agent_ro session，防 prompt injection）
- state_trim：超量 debate_history 摘要壓縮
- graph_builder：`build_graph(symbol, market)` 組裝 StateGraph

P12 = 框架；P13 補真實 prompt + Bull/Bear/Manager；P14 補美股 Analyst + Fallback Chain。
"""

from __future__ import annotations
