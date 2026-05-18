"""跨市場 Dispatcher — 依 symbol 自動派送 TW / US 資料源。

依 PLAN.md 第 10 章（跨市場架構）+ 第 10.2 章（Symbol 驗證 regex）+ 第 18.2 章（Plugin Pattern）。

設計：
- `Market` enum：實際交易所（TWSE / TPEX / NYSE / NASDAQ / AMEX）
- `MarketRegion`：粗分為 TW / US（直接 re-export from data_sources.base）
- `detect_region(symbol)`：用 regex 區分 TW / US
- `validate_symbol_exists()`：在 stock_list 存在性驗證
- `MarketDispatcher`：保管「TW source dict」+「US source dict」，提供 get_sources_for()

Symbol regex（涵蓋實際樣態）：
- TW：一般股 2330 / ETF 0050/006208/00878 / 特別股 2884A / 權證 030001/043333P
- US：一般股 AAPL / Class B 股 BRK.B / 短代號 F、T

注意：Market enum 與 data_sources.base.MarketRegion 不同層級
（前者是「交易所」，後者是「TW vs US」）。market_to_region() 做轉換。
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import TYPE_CHECKING

from app.core.errors import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind, MarketRegion

if TYPE_CHECKING:
    from app.repos.stock_repo import StockRepository

logger = get_logger(__name__)


class Market(StrEnum):
    """交易所識別（PLAN 10.1）。"""

    TWSE = "TWSE"
    """上市（台灣證券交易所）"""
    TPEX = "TPEX"
    """上櫃（櫃買中心）"""
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"
    AMEX = "AMEX"


# 屬於 TW 區域的市場
TW_MARKETS: frozenset[Market] = frozenset({Market.TWSE, Market.TPEX})
US_MARKETS: frozenset[Market] = frozenset({Market.NASDAQ, Market.NYSE, Market.AMEX})


# ── Symbol regex ─────────────────────────────────────────
# Phase 12 audit fix #10：與 validators.py 統一單一 pattern。
# 涵蓋 PLAN 10.2「實際樣態」：
# - 4 碼：一般股（2330 / 0050）、特別股（2884A、0050B）
# - 5 碼：常見 ETF（00878、00713）、含字母後綴變體
# - 6 碼：較長 ETF（006208）、權證 + 字母（030001、043333P）
TW_SYMBOL_PATTERN = re.compile(r"^[0-9]{4,6}[A-Z]?$")

# US 1~5 碼大寫字母 + 可選 .X 後綴（BRK.B / RDS.A / BF.B 等 dual class）
US_SYMBOL_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")


def detect_region(symbol: str) -> MarketRegion:
    """依 symbol 格式判斷市場區域。

    優先順序：TW pattern 在先（純數字優先），再 US。

    Raises:
        ValidationError: symbol 為空或不符合任一 pattern
    """
    if not symbol or not isinstance(symbol, str):
        raise ValidationError(message_zh="股票代號不可為空")
    s = symbol.strip()
    if not s:
        raise ValidationError(message_zh="股票代號不可為空")
    if TW_SYMBOL_PATTERN.match(s):
        return MarketRegion.TW
    if US_SYMBOL_PATTERN.match(s):
        return MarketRegion.US
    raise ValidationError(message_zh=f"無法識別股票代號 {s}")


def market_to_region(market: Market | str) -> MarketRegion:
    """Market enum → MarketRegion。"""
    m = Market(market) if isinstance(market, str) else market
    if m in TW_MARKETS:
        return MarketRegion.TW
    if m in US_MARKETS:
        return MarketRegion.US
    raise ValidationError(message_zh=f"未知市場 {m}")


async def validate_symbol_exists(
    symbol: str,
    market: Market | str,
    repo: StockRepository,
) -> bool:
    """驗證 symbol 在 stock_list 存在（防亂打字）。

    Raises:
        NotFoundError: 不在 stock_list
    """
    market_str = Market(market).value if isinstance(market, Market) else str(market)
    stock = await repo.get_by_symbol(symbol, market_str)
    if not stock:
        raise NotFoundError(
            message_zh=f"股票 {symbol} 不在系統清單",
            symbol=symbol,
            market=market_str,
        )
    return True


class MarketDispatcher:
    """跨市場 Dispatcher — 依 region + DataKind 回傳對應的 source list。

    Usage:
        dispatcher = MarketDispatcher(
            tw_sources=get_tw_sources(settings),
            us_sources=get_us_sources(settings),
        )
        sources = dispatcher.get_sources_for(MarketRegion.US, DataKind.OHLCV)
        fb = DataSourceFallback(sources)
        df = await fb.fetch_ohlcv("AAPL", start, end)
    """

    def __init__(
        self,
        tw_sources: dict[DataKind, list[BaseDataSource]],
        us_sources: dict[DataKind, list[BaseDataSource]],
    ) -> None:
        self.tw: dict[DataKind, list[BaseDataSource]] = tw_sources
        self.us: dict[DataKind, list[BaseDataSource]] = us_sources

    def get_sources_for(
        self,
        region: MarketRegion,
        kind: DataKind,
    ) -> list[BaseDataSource]:
        """取得 region + kind 對應的 source list（依 priority 由小到大）。"""
        bucket = self.tw if region == MarketRegion.TW else self.us
        return list(bucket.get(kind, []))

    def get_sources_for_symbol(self, symbol: str, kind: DataKind) -> list[BaseDataSource]:
        """便利方法：自動 detect_region 再查 sources。"""
        region = detect_region(symbol)
        return self.get_sources_for(region, kind)


__all__ = [
    "TW_MARKETS",
    "TW_SYMBOL_PATTERN",
    "US_MARKETS",
    "US_SYMBOL_PATTERN",
    "Market",
    "MarketDispatcher",
    "MarketRegion",
    "detect_region",
    "market_to_region",
    "validate_symbol_exists",
]
