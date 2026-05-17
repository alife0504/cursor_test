"""Manager 子模組 — 綜合分析師 + 辯論 → FinalSignal + 訂單建立。"""

from app.agents.managers.orders_decision import (
    DEFAULT_NOTIONAL_USD,
    calculate_qty,
    signal_to_pending_order,
)
from app.agents.managers.research_manager import ResearchManager

__all__ = [
    "DEFAULT_NOTIONAL_USD",
    "ResearchManager",
    "calculate_qty",
    "signal_to_pending_order",
]
