"""Data source 抽象層 + 註冊機制 + Fallback chain。

公開介面：
- BaseDataSource (ABC)
- DataKind enum
- MarketRegion enum
- register_data_source 裝飾器
- DATA_SOURCE_REGISTRY 全域 dict
- DataSourceFallback (主源 → 備源 → 24h 快取)
- get_tw_sources / get_us_sources（in tw/__init__.py / us/__init__.py）

詳見 PLAN.md 第 18.2 章 Plugin Pattern + 第 14.3 章 Circuit Breaker。
"""

from __future__ import annotations

from app.data_sources.base import (
    DATA_SOURCE_REGISTRY,
    BaseDataSource,
    DataKind,
    MarketRegion,
    register_data_source,
)
from app.data_sources.fallback import DataSourceFallback

__all__ = [
    "DATA_SOURCE_REGISTRY",
    "BaseDataSource",
    "DataKind",
    "DataSourceFallback",
    "MarketRegion",
    "register_data_source",
]
