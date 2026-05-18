"""Researcher 子模組 — Bull/Bear 辯論。

P13 起：
- BullResearcher / BearResearcher 多輪辯論
- 每輪都吃所有 analyst 結論 + 對方上一輪論點
- 累積到 state.bull_arguments / state.bear_arguments + state.debate_history
"""

from app.agents.researchers.bear_researcher import BearResearcher
from app.agents.researchers.bull_researcher import BullResearcher

__all__ = ["BearResearcher", "BullResearcher"]
