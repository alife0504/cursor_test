"""Analyst 子類集合 — import 此 package 即觸發 4 個 stub 註冊到 ANALYST_REGISTRY。

依 PLAN.md 第 18.2 章 Plugin Pattern。

P12 階段 4 種 stub Analyst（market/fundamental/news/sentiment）；
P13 補真實 prompt + Tool call + 結構化輸出；
P14 補 sentiment 美股版本（目前 sentiment = TW only）。
"""

from __future__ import annotations

# side-effect imports：載入即註冊（不要刪）
from app.agents.analysts.fundamental_analyst import FundamentalAnalyst
from app.agents.analysts.market_analyst import MarketAnalyst
from app.agents.analysts.news_analyst import NewsAnalyst
from app.agents.analysts.sentiment_analyst import SentimentAnalyst

__all__ = [
    "FundamentalAnalyst",
    "MarketAnalyst",
    "NewsAnalyst",
    "SentimentAnalyst",
]
