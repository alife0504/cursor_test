"""Analyst 子類集合 — import 此 package 即觸發 5 個 Analyst 註冊到 ANALYST_REGISTRY。

依 PLAN.md 第 18.2 章 Plugin Pattern。

v1.1 陣容（market/fundamental/news/sentiment/chip）：
- market / fundamental：技術面 / 基本面（TW + US）。
- news：新聞/公告 + 總經脈絡（TW + US）。
- sentiment：情緒面（新聞情緒聚合，TW only）。
- chip：籌碼面（三大法人/融資券/月營收，TW only；前身為誤植的 sentiment）。
"""

from __future__ import annotations

# side-effect imports：載入即註冊（不要刪）
from app.agents.analysts.chip_analyst import ChipAnalyst
from app.agents.analysts.fundamental_analyst import FundamentalAnalyst
from app.agents.analysts.market_analyst import MarketAnalyst
from app.agents.analysts.news_analyst import NewsAnalyst
from app.agents.analysts.sentiment_analyst import SentimentAnalyst

__all__ = [
    "ChipAnalyst",
    "FundamentalAnalyst",
    "MarketAnalyst",
    "NewsAnalyst",
    "SentimentAnalyst",
]
