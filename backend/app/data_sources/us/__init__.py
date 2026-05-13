"""US 資料源 — Phase 6 註冊 4 個 source。

import 此 module 即透過 @register_data_source 的 side-effect 註冊到
`DATA_SOURCE_REGISTRY`。

`get_us_sources(settings)` 回傳依 DataKind 分組的 source list（供 fallback 使用）。
"""

from __future__ import annotations

from app.core.config import Settings
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion
from app.data_sources.us.alpha_vantage_source import AlphaVantageSource
from app.data_sources.us.finnhub_source import FinnhubSource
from app.data_sources.us.sec_edgar_source import SECEdgarSource
from app.data_sources.us.yfinance_source import YFinanceSource


def get_us_sources(settings: Settings) -> dict[DataKind, list[BaseDataSource]]:
    """產生所有 US source 實例並依 DataKind 分組（依 priority 排序）。"""
    sources: list[BaseDataSource] = [
        YFinanceSource(settings),
        AlphaVantageSource(settings),
        FinnhubSource(settings),
        SECEdgarSource(settings),
    ]
    grouped: dict[DataKind, list[BaseDataSource]] = {}
    for src in sources:
        if MarketRegion.US not in src.supported_regions:
            continue
        for kind in src.supported_kinds:
            grouped.setdefault(kind, []).append(src)
    # 排序：priority 越小越優先
    for lst in grouped.values():
        lst.sort(key=lambda s: s.priority)
    return grouped


__all__ = [
    "AlphaVantageSource",
    "FinnhubSource",
    "SECEdgarSource",
    "YFinanceSource",
    "get_us_sources",
]
