"""中立型風險分析師（還原原版 neutral_debator）。"""

from __future__ import annotations

from typing import ClassVar

from app.agents.risk_mgmt.base import BaseRiskAnalyst


class NeutralRiskAnalyst(BaseRiskAnalyst):
    stance: ClassVar[str] = "neutral"
    system_prompt_name: ClassVar[str] = "risk_neutral_system"
    arguments_key: ClassVar[str] = "neutral_arguments"


__all__ = ["NeutralRiskAnalyst"]
