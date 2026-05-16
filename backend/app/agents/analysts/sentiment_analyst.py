"""SentimentAnalyst — 籌碼/情緒面分析師（TW only）。

P12 stub。
P13 將實作：三大法人買賣超 + 融資融券 + 月營收年增 → LLM 評估市場情緒與大戶動向。

設計選擇：sentiment_analyst 為 TW only（依 PLAN 10.5）。
- 三大法人 / 融資融券是台股獨有資料（美股無公開等同資料）。
- US Sentiment 在 v1.1 才補（可用 13F filing + put/call ratio 等）。
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.agents.base_analyst import BaseAnalyst, register_analyst
from app.agents.state import AgentState
from app.core.logging_config import get_logger
from app.data_sources.base import DataKind, MarketRegion

logger = get_logger(__name__)


@register_analyst
class SentimentAnalyst(BaseAnalyst):
    """籌碼/情緒面分析師（台股 only）。

    支援：TW only
    依賴資料：INSTITUTIONAL（三大法人）+ MARGIN（融資融券）+ MONTHLY_REVENUE
    """

    name: ClassVar[str] = "sentiment"
    display_name_zh: ClassVar[str] = "籌碼面分析師"
    supported_regions: ClassVar[list[MarketRegion]] = [MarketRegion.TW]
    required_data_kinds: ClassVar[list[DataKind]] = [
        DataKind.INSTITUTIONAL,
        DataKind.MARGIN,
        DataKind.MONTHLY_REVENUE,
    ]

    async def analyze(self, state: AgentState) -> dict[str, Any]:
        """P12 stub — 回固定文字。"""
        symbol = state.get("symbol", "?")
        text = (
            f"[stub] {self.display_name_zh} 對 {symbol} 的籌碼面分析。\n"
            "本內容為 Phase 12 框架測試輸出，尚未接 LLM。\n"
            "P13 完成後此處會輸出：近 30 日外資/投信/自營商買賣超、融資融券變化、月營收年增趨勢。"
        )
        logger.info("analyst.stub.sentiment", symbol=symbol)
        return {"analyses": {self.name: text}}


__all__ = ["SentimentAnalyst"]
