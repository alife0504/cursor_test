"""NewsAnalyst — 新聞/公告面分析師（TW + US）。

P12 stub。
P13 將實作：抓近 7 日新聞 + 重大公告 → LLM 摘要 + sentiment 評分（positive/neutral/negative）。
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.agents.base_analyst import BaseAnalyst, register_analyst
from app.agents.state import AgentState
from app.core.logging_config import get_logger
from app.data_sources.base import DataKind, MarketRegion

logger = get_logger(__name__)


@register_analyst
class NewsAnalyst(BaseAnalyst):
    """新聞/公告分析師。

    支援：TW + US
    依賴資料：NEWS + ANNOUNCEMENT
    """

    name: ClassVar[str] = "news"
    display_name_zh: ClassVar[str] = "新聞/公告分析師"
    supported_regions: ClassVar[list[MarketRegion]] = [MarketRegion.TW, MarketRegion.US]
    required_data_kinds: ClassVar[list[DataKind]] = [
        DataKind.NEWS,
        DataKind.ANNOUNCEMENT,
    ]

    async def analyze(self, state: AgentState) -> dict[str, Any]:
        """P12 stub — 回固定文字。"""
        symbol = state.get("symbol", "?")
        text = (
            f"[stub] {self.display_name_zh} 對 {symbol} 的新聞/公告分析。\n"
            "本內容為 Phase 12 框架測試輸出，尚未接 LLM。\n"
            "P13 完成後此處會輸出：近 7 日新聞摘要、sentiment 分布、重大公告影響評估。"
        )
        logger.info("analyst.stub.news", symbol=symbol)
        return {"analyses": {self.name: text}}


__all__ = ["NewsAnalyst"]
