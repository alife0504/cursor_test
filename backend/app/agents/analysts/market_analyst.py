"""MarketAnalyst — 技術面分析師（TW + US）。

P12 stub：只回固定文字，不呼叫 LLM。
P13 將實作：拉 OHLCV → 計算 MA/RSI/MACD → LLM prompt 產出技術面解讀。
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.agents.base_analyst import BaseAnalyst, register_analyst
from app.agents.state import AgentState
from app.core.logging_config import get_logger
from app.data_sources.base import DataKind, MarketRegion

logger = get_logger(__name__)


@register_analyst
class MarketAnalyst(BaseAnalyst):
    """技術面分析師。

    支援：TW + US
    依賴資料：OHLCV
    """

    name: ClassVar[str] = "market"
    display_name_zh: ClassVar[str] = "技術面分析師"
    supported_regions: ClassVar[list[MarketRegion]] = [MarketRegion.TW, MarketRegion.US]
    required_data_kinds: ClassVar[list[DataKind]] = [DataKind.OHLCV]

    async def analyze(self, state: AgentState) -> dict[str, Any]:
        """P12 stub — 回固定文字，不呼叫 LLM。

        P13 將實作真實 prompt + Tool call。
        """
        symbol = state.get("symbol", "?")
        text = (
            f"[stub] {self.display_name_zh} 對 {symbol} 的技術面分析。\n"
            "本內容為 Phase 12 框架測試輸出，尚未接 LLM。\n"
            "P13 完成後此處會輸出：MA20/MA60 趨勢、RSI、MACD、量價背離、近期支撐/壓力位。"
        )
        logger.info("analyst.stub.market", symbol=symbol)
        return {"analyses": {self.name: text}}


__all__ = ["MarketAnalyst"]
