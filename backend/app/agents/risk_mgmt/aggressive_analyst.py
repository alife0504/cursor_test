"""積極型風險分析師（還原原版 aggressive_debator）。"""

from __future__ import annotations

from typing import ClassVar

from app.agents.risk_mgmt.base import BaseRiskAnalyst


class AggressiveRiskAnalyst(BaseRiskAnalyst):
    stance: ClassVar[str] = "aggressive"
    system_prompt_name: ClassVar[str] = "risk_aggressive_system"
    arguments_key: ClassVar[str] = "aggressive_arguments"


__all__ = ["AggressiveRiskAnalyst"]
