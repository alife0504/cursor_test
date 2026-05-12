"""TW 資料源 — Phase 5 註冊 5 個 source。

import 此 module 即透過 @register_data_source 的 side-effect 註冊到
`DATA_SOURCE_REGISTRY`。

`get_tw_sources(settings)` 回傳依 DataKind 分組的 source list（供 fallback 使用）。
"""

from __future__ import annotations

from app.core.config import Settings
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion
from app.data_sources.tw.cnyes_rss_source import CnyesRSSSource
from app.data_sources.tw.finmind_source import FinMindSource
from app.data_sources.tw.mops_source import MOPSSource
from app.data_sources.tw.tpex_source import TPEXSource
from app.data_sources.tw.twse_openapi_source import TWSEOpenAPISource


def get_tw_sources(settings: Settings) -> dict[DataKind, list[BaseDataSource]]:
    """產生所有 TW source 實例並依 DataKind 分組（依 priority 排序）。"""
    sources: list[BaseDataSource] = [
        FinMindSource(settings),
        TWSEOpenAPISource(settings),
        TPEXSource(settings),
        MOPSSource(settings),
        CnyesRSSSource(settings),
    ]
    grouped: dict[DataKind, list[BaseDataSource]] = {}
    for src in sources:
        if MarketRegion.TW not in src.supported_regions:
            continue
        for kind in src.supported_kinds:
            grouped.setdefault(kind, []).append(src)
    # 排序：priority 越小越優先
    for lst in grouped.values():
        lst.sort(key=lambda s: s.priority)
    return grouped


__all__ = [
    "CnyesRSSSource",
    "FinMindSource",
    "MOPSSource",
    "TPEXSource",
    "TWSEOpenAPISource",
    "get_tw_sources",
]
