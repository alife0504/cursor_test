"""Data source 抽象基類 + 註冊機制。

依 PLAN.md 第 18.2 章（Plugin Pattern）+ 第 10.4 章資料來源對照表。

設計：
- BaseDataSource：所有 source（FinMind / TWSE / yfinance / SEC EDGAR ...）的共同介面
- DataKind：source 可提供的資料種類列舉（OHLCV / FINANCIAL / NEWS ...）
- MarketRegion：source 支援的市場區域（TW / US）
- DATA_SOURCE_REGISTRY：全域 dict[name -> class]（不是 instance！避免單例化問題）
- @register_data_source：類別裝飾器自動把 subclass 註冊到 registry
- 每個 source 在 __init__ 時 lazy 註冊自己的 CircuitBreaker（per source name）

抽象方法都帶預設 `NotImplementedError`，subclass 只要 override 自己支援的 kind。
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import httpx
from aiolimiter import AsyncLimiter

from app.core.circuit_breaker import CircuitBreaker, get_or_create_breaker
from app.core.http_client import get_async_client
from app.core.logging_config import get_logger

if TYPE_CHECKING:
    import pandas as pd

    from app.core.config import Settings

logger = get_logger(__name__)


class DataKind(StrEnum):
    """資料來源可提供的資料類別（PLAN 10.4 對照表）。"""

    OHLCV = "ohlcv"
    """日 K 線（OHLCV + 成交金額）"""
    COMPANY_INFO = "company_info"
    """公司基本資料（產業、資本額、地址、員工數...）"""
    FINANCIAL = "financial"
    """財務報表（IS / BS / CF，季 / 年）"""
    NEWS = "news"
    """個股 / 大盤新聞"""
    ANNOUNCEMENT = "announcement"
    """重大訊息 / 公開資訊觀測站公告"""
    INSTITUTIONAL = "institutional"
    """三大法人買賣超（台股 only）"""
    MARGIN = "margin"
    """融資融券（台股 only）"""
    MONTHLY_REVENUE = "monthly_revenue"
    """月營收（台股 only，第 10 號公報）"""


class MarketRegion(StrEnum):
    """市場區域。"""

    TW = "TW"
    US = "US"


class BaseDataSource:
    """所有資料來源的共同基類（不繼承 ABC：不強制 abstractmethod，但抽象方法預設 raise NotImplementedError）。

    Subclass 需要：
    1. 設定 class-level metadata：name / priority / supported_regions / supported_kinds
    2. （可選）設定 rate_limit_per_sec
    3. 用 @register_data_source 裝飾
    4. Override 自己支援的 fetch_* 方法（其他保留預設 NotImplementedError）

    Attributes:
        name: source 唯一識別碼（也是 circuit breaker 的 key），如 "finmind"
        priority: fallback 排序權重（越小越優先；主源 10、備源 20）
        supported_regions: 支援的市場
        supported_kinds: 支援的資料類別
        rate_limit_per_sec: 每秒最大 request 數（None = 無限制）
    """

    # ── Subclass 必填 / 可覆寫 ────────────────────────────
    name: str = "base"
    priority: int = 100
    supported_regions: tuple[MarketRegion, ...] = ()
    supported_kinds: tuple[DataKind, ...] = ()
    rate_limit_per_sec: float | None = None
    base_url: str = ""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        # Circuit Breaker（per source name）— 全域共用 registry
        self.cb: CircuitBreaker = get_or_create_breaker(self.name)

        # Async rate limiter（None = 不限速）
        self.limiter: AsyncLimiter | None = None
        if self.rate_limit_per_sec is not None and self.rate_limit_per_sec > 0:
            # AsyncLimiter(max_rate, time_period) — 「time_period 秒內最多 max_rate 次」
            # 但 max_rate < 1 會被 floor 到 0 capacity → 永遠 acquire 失敗。
            # 因此 < 1 的 rate 換算成「1 次 / N 秒」：
            #   rate=0.5/sec → 1 次 / 2.0 秒 = AsyncLimiter(1, 2.0)
            #   rate=2.0/sec → 2 次 / 1.0 秒 = AsyncLimiter(2, 1.0)
            if self.rate_limit_per_sec >= 1.0:
                self.limiter = AsyncLimiter(self.rate_limit_per_sec, 1.0)
            else:
                period_sec = 1.0 / self.rate_limit_per_sec
                self.limiter = AsyncLimiter(1, period_sec)

        # 預先建一個 client，但給每個 source 自己的 base_url / headers
        self._client: httpx.AsyncClient | None = None

    # ── 抽象方法（subclass 視能力 override；不支援的留 NotImplementedError）─

    async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """抓 OHLCV，標準化欄位：date / open / high / low / close / volume (+ optional turnover)。"""
        raise NotImplementedError(f"{self.name} does not support OHLCV")

    async def fetch_company_info(self, symbol: str) -> dict[str, Any]:
        """抓公司基本資料。"""
        raise NotImplementedError(f"{self.name} does not support COMPANY_INFO")

    async def fetch_financial(
        self,
        symbol: str,
        *,
        year: int | None = None,
        quarter: int | None = None,
    ) -> list[dict[str, Any]]:
        """抓財務報表。回傳 list of dict（每筆 = 1 個 statement）。"""
        raise NotImplementedError(f"{self.name} does not support FINANCIAL")

    async def fetch_news(
        self, symbol: str | None = None, *, since: date | None = None
    ) -> list[dict[str, Any]]:
        """抓新聞。symbol=None 表示抓大盤 / 全部。"""
        raise NotImplementedError(f"{self.name} does not support NEWS")

    async def fetch_announcement(
        self, symbol: str, *, since: date | None = None
    ) -> list[dict[str, Any]]:
        """抓重大訊息。"""
        raise NotImplementedError(f"{self.name} does not support ANNOUNCEMENT")

    async def fetch_institutional(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """抓三大法人買賣超（台股 only）。"""
        raise NotImplementedError(f"{self.name} does not support INSTITUTIONAL")

    async def fetch_margin(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """抓融資融券（台股 only）。"""
        raise NotImplementedError(f"{self.name} does not support MARGIN")

    async def fetch_monthly_revenue(
        self, symbol: str, *, year: int | None = None
    ) -> list[dict[str, Any]]:
        """抓月營收（台股 only）。"""
        raise NotImplementedError(f"{self.name} does not support MONTHLY_REVENUE")

    # ── 共用 helper ────────────────────────────────────

    def supports(self, kind: DataKind) -> bool:
        """是否支援此資料類別。"""
        return kind in self.supported_kinds

    async def health_check(self) -> bool:
        """探活：預設 = base_url GET（child class 可覆寫指向更輕量端點）。"""
        if not self.base_url:
            return True
        try:
            async with self._get_client() as client:
                resp = await client.get(self.base_url, timeout=5.0)
                return resp.status_code < 500
        except Exception as e:
            logger.warning("data_source.health_check_failed", name=self.name, error=str(e))
            return False

    def _get_client(self) -> httpx.AsyncClient:
        """取得 httpx.AsyncClient（每次建新的；caller 用 async with 控制生命週期）。

        注意：不重用 client instance，因為要在多個 task 並發時避免共用 race。
        Pool 在 httpx 內部已經處理連線重用。
        """
        return get_async_client(name=self.name, base_url=self.base_url)

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name={self.name} "
            f"priority={self.priority} regions={self.supported_regions}>"
        )


# ── Registry ─────────────────────────────────────────────
# 全域 class registry（不是 instance）— 啟動時透過 import side-effect 註冊
DATA_SOURCE_REGISTRY: dict[str, type[BaseDataSource]] = {}


def register_data_source(
    cls: type[BaseDataSource],
) -> type[BaseDataSource]:
    """類別裝飾器：把 BaseDataSource subclass 註冊到 DATA_SOURCE_REGISTRY。

    Usage:
        @register_data_source
        class FinMindSource(BaseDataSource):
            name = "finmind"
            ...

    Raises:
        ValueError: name 已被註冊或 name 為空 / 仍為 "base"
    """
    if not cls.name or cls.name == "base":
        raise ValueError(
            f"register_data_source: class {cls.__name__} 必須設定 class-level `name` "
            "（且不可為 'base'）"
        )
    if cls.name in DATA_SOURCE_REGISTRY:
        existing = DATA_SOURCE_REGISTRY[cls.name]
        if existing is not cls:
            raise ValueError(
                f"register_data_source: name='{cls.name}' 已被 {existing.__name__} 註冊"
            )
        return cls
    DATA_SOURCE_REGISTRY[cls.name] = cls
    logger.debug("data_source.registered", name=cls.name, cls=cls.__name__)
    return cls


__all__ = [
    "DATA_SOURCE_REGISTRY",
    "BaseDataSource",
    "DataKind",
    "MarketRegion",
    "register_data_source",
]
