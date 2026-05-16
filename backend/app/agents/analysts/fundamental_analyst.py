"""FundamentalAnalyst — 基本面分析師（TW + US）。

P12 stub。
P13 將實作：拉財報（IS/BS/CF）+ 月營收（TW only） → LLM 解析 EPS / 毛利率 / ROE / 營收年增。
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.agents.base_analyst import BaseAnalyst, register_analyst
from app.agents.state import AgentState
from app.core.logging_config import get_logger
from app.data_sources.base import DataKind, MarketRegion

logger = get_logger(__name__)


@register_analyst
class FundamentalAnalyst(BaseAnalyst):
    """基本面分析師。

    支援：TW + US
    依賴資料：FINANCIAL（IS/BS/CF）+ COMPANY_INFO + （TW only）MONTHLY_REVENUE
    """

    name: ClassVar[str] = "fundamental"
    display_name_zh: ClassVar[str] = "基本面分析師"
    supported_regions: ClassVar[list[MarketRegion]] = [MarketRegion.TW, MarketRegion.US]
    required_data_kinds: ClassVar[list[DataKind]] = [
        DataKind.FINANCIAL,
        DataKind.COMPANY_INFO,
    ]

    async def analyze(self, state: AgentState) -> dict[str, Any]:
        """P12 stub — 回固定文字。

        P13 將實作真實 prompt + Tool call。
        """
        symbol = state.get("symbol", "?")
        text = (
            f"[stub] {self.display_name_zh} 對 {symbol} 的基本面分析。\n"
            "本內容為 Phase 12 框架測試輸出，尚未接 LLM。\n"
            "P13 完成後此處會輸出：近 4 季 EPS / 毛利率 / ROE / 營收年增 / 自由現金流。"
        )
        logger.info("analyst.stub.fundamental", symbol=symbol)
        return {"analyses": {self.name: text}}


__all__ = ["FundamentalAnalyst"]
