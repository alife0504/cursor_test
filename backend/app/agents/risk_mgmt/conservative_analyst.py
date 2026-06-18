"""保守型風險分析師（還原原版 conservative_debator）。"""

from __future__ import annotations

from typing import ClassVar

from app.agents.risk_mgmt.base import BaseRiskAnalyst


class ConservativeRiskAnalyst(BaseRiskAnalyst):
    stance: ClassVar[str] = "conservative"
    system_prompt_name: ClassVar[str] = "risk_conservative_system"
    arguments_key: ClassVar[str] = "conservative_arguments"


__all__ = ["ConservativeRiskAnalyst"]
