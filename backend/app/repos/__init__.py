"""Repository 層 — DB 抽象。

依 PLAN.md 第 18.1 章分層（API → Service → Domain → Repository → Infrastructure）+
第 17.9 章「Repository 基類 P2 建、P3+ 全部使用」。

公開：
- BaseRepository / ReadOnlyRepository
- StockRepository / OHLCVRepository / NewsRepository / FinancialsRepository
"""

from __future__ import annotations

from app.repos.base import BaseRepository, ReadOnlyRepository
from app.repos.financials_repo import FinancialsRepository
from app.repos.news_repo import NewsRepository
from app.repos.ohlcv_repo import OHLCVRepository
from app.repos.stock_repo import StockRepository

__all__ = [
    "BaseRepository",
    "FinancialsRepository",
    "NewsRepository",
    "OHLCVRepository",
    "ReadOnlyRepository",
    "StockRepository",
]
