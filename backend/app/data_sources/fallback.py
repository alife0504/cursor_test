"""Data source fallback chain — 主源 fail → 備源 → 24h stale 快取。

依 PLAN.md 第 14.3 章（Circuit Breaker）+ 第 14.4 章（Fallback Chain）+ 11 章風險矩陣。

行為：
1. 依 priority 排序 sources
2. 對每個 source，若 cb.state == OPEN 直接跳過（不浪費 quota）
3. 嘗試 fetch；成功 → cb.record_success 並 return
4. 失敗 → cb.record_failure，log warning，嘗試下一個
5. 全部失敗 → 嘗試 Redis 24h stale cache（caller 須提供 callback；本檔不耦合 Redis）
6. 仍無 → raise ExternalServiceError（含 last_exc）

關於 stale cache：
- 為避免本檔耦合 Redis，cache callback 由 caller 提供（function/coroutine）
- callback 簽名：`async def(kind: str, **params) -> Any | None`
- 設計上 P5 還沒整合 Redis cache，傳 None 即可（直接 raise）
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import TYPE_CHECKING, Any

from app.core.circuit_breaker import CircuitState
from app.core.errors import ExternalServiceError
from app.core.logging_config import get_logger
from app.data_sources.base import BaseDataSource, DataKind

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger(__name__)

# 區分「來源尚未回應」與「來源回了空」：不能用 None（None 本身可能是合法空回應）
_EMPTY_SENTINEL: Any = object()


def _is_empty_result(result: Any) -> bool:
    """判斷資料源回應是否為「空」（無資料），以決定是否 failover 到下一來源。

    - None → 空
    - pandas DataFrame（有 .empty）→ 依 .empty
    - list/tuple/dict/set → 長度為 0 即空
    - 其他型別（單一物件）→ 視為非空（有效回應）
    """
    if result is None:
        return True
    empty_attr = getattr(result, "empty", None)
    if isinstance(empty_attr, bool):  # pandas DataFrame/Series
        return empty_attr
    if isinstance(result, (list, tuple, dict, set)):
        return len(result) == 0
    return False


# Stale cache callback：(kind, params) → cached value 或 None
StaleCacheLoader = Callable[..., Awaitable[Any | None]]


class DataSourceFallback:
    """從 N 個 source 依序嘗試，第一個成功的回傳。

    Usage:
        fb = DataSourceFallback(sources=[FinMindSource(s), TWSESource(s)])
        df = await fb.fetch_ohlcv("2330", start, end)
    """

    def __init__(
        self,
        sources: list[BaseDataSource],
        *,
        stale_cache_loader: StaleCacheLoader | None = None,
    ) -> None:
        if not sources:
            raise ValueError("DataSourceFallback 至少需要 1 個 source")
        # 依 priority 升序排（priority 越小越優先）
        self.sources: list[BaseDataSource] = sorted(sources, key=lambda s: s.priority)
        self.stale_cache_loader = stale_cache_loader
        # 記錄最近一次成功取得資料的 source name（供 caller 標正確 source 欄位）
        self.last_used_source: str | None = None

    # ── 對應 BaseDataSource 每個 fetch_* 方法 ─────────────

    async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        return await self._call(
            kind=DataKind.OHLCV,
            method_name="fetch_ohlcv",
            args=(symbol, start, end),
            cache_params={"symbol": symbol, "start": start, "end": end},
        )

    async def fetch_company_info(self, symbol: str) -> dict[str, Any]:
        return await self._call(
            kind=DataKind.COMPANY_INFO,
            method_name="fetch_company_info",
            args=(symbol,),
            cache_params={"symbol": symbol},
        )

    async def fetch_financial(
        self,
        symbol: str,
        *,
        year: int | None = None,
        quarter: int | None = None,
    ) -> list[dict[str, Any]]:
        return await self._call(
            kind=DataKind.FINANCIAL,
            method_name="fetch_financial",
            args=(symbol,),
            kwargs={"year": year, "quarter": quarter},
            cache_params={"symbol": symbol, "year": year, "quarter": quarter},
        )

    async def fetch_news(
        self, symbol: str | None = None, *, since: date | None = None
    ) -> list[dict[str, Any]]:
        return await self._call(
            kind=DataKind.NEWS,
            method_name="fetch_news",
            args=(symbol,),
            kwargs={"since": since},
            cache_params={"symbol": symbol, "since": since},
        )

    async def fetch_announcement(
        self, symbol: str, *, since: date | None = None
    ) -> list[dict[str, Any]]:
        return await self._call(
            kind=DataKind.ANNOUNCEMENT,
            method_name="fetch_announcement",
            args=(symbol,),
            kwargs={"since": since},
            cache_params={"symbol": symbol, "since": since},
        )

    async def fetch_institutional(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        return await self._call(
            kind=DataKind.INSTITUTIONAL,
            method_name="fetch_institutional",
            args=(symbol, start, end),
            cache_params={"symbol": symbol, "start": start, "end": end},
        )

    async def fetch_margin(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        return await self._call(
            kind=DataKind.MARGIN,
            method_name="fetch_margin",
            args=(symbol, start, end),
            cache_params={"symbol": symbol, "start": start, "end": end},
        )

    async def fetch_monthly_revenue(
        self, symbol: str, *, year: int | None = None
    ) -> list[dict[str, Any]]:
        return await self._call(
            kind=DataKind.MONTHLY_REVENUE,
            method_name="fetch_monthly_revenue",
            args=(symbol,),
            kwargs={"year": year},
            cache_params={"symbol": symbol, "year": year},
        )

    # ── 內部 dispatcher ───────────────────────────────────

    async def _call(
        self,
        *,
        kind: DataKind,
        method_name: str,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        cache_params: dict[str, Any] | None = None,
    ) -> Any:
        """對 self.sources 中支援此 kind 的 source 依序嘗試。"""
        kwargs = kwargs or {}
        cache_params = cache_params or {}

        # 過濾支援此 kind 的 source
        candidates = [s for s in self.sources if s.supports(kind)]
        if not candidates:
            raise ExternalServiceError(
                message_zh=f"無任何 source 支援 {kind.value}",
                kind=kind.value,
            )

        last_exc: Exception | None = None
        skipped_open: list[str] = []
        tried: list[str] = []
        # 空結果不視為終點：記下第一個空回應，續試下一來源（本地庫缺/落後時能 failover 到 API）；
        # 全部來源皆空才回空。避免「本地源回 []→被當成功→API 永不被詢問」的 lag bug。
        first_empty: Any = _EMPTY_SENTINEL
        first_empty_source: str | None = None

        for source in candidates:
            if source.cb.state == CircuitState.OPEN:
                skipped_open.append(source.name)
                logger.warning(
                    "fallback.skipped_open_breaker",
                    source=source.name,
                    kind=kind.value,
                )
                continue

            method = getattr(source, method_name)
            tried.append(source.name)
            try:
                result = await method(*args, **kwargs)
                await source.cb.record_success()
                if _is_empty_result(result):
                    # 空結果（本地庫無此標的/落後）→ 不當終點，續試下一來源
                    if first_empty is _EMPTY_SENTINEL:
                        first_empty = result
                        first_empty_source = source.name
                    logger.info(
                        "fallback.empty_result_try_next",
                        source=source.name,
                        kind=kind.value,
                    )
                    continue
                self.last_used_source = source.name  # 供 caller 標正確 source 欄位
                if tried[0] != source.name or skipped_open:
                    logger.info(
                        "fallback.recovered_via_secondary",
                        used=source.name,
                        tried=tried,
                        skipped_open=skipped_open,
                        kind=kind.value,
                    )
                return result
            except NotImplementedError:
                # 此 source 雖然在 candidates，但實際沒實作（防呆）
                logger.debug(
                    "fallback.method_not_implemented",
                    source=source.name,
                    method=method_name,
                )
                continue
            except Exception as e:
                last_exc = e
                await source.cb.record_failure()
                logger.warning(
                    "fallback.source_failed",
                    source=source.name,
                    kind=kind.value,
                    error=type(e).__name__,
                    message=str(e),
                )
                continue

        # 所有來源皆回空（無例外）→ 回第一個空結果（全空是合法的「查無資料」）
        if first_empty is not _EMPTY_SENTINEL:
            self.last_used_source = first_empty_source
            logger.info(
                "fallback.all_sources_empty",
                tried=tried,
                skipped_open=skipped_open,
                kind=kind.value,
            )
            return first_empty

        # 全部 source 都掛 / 全 OPEN → 嘗試 stale cache
        if self.stale_cache_loader is not None:
            try:
                cached = await self.stale_cache_loader(kind=kind.value, **cache_params)
            except Exception as cache_err:
                logger.warning("fallback.stale_cache_loader_failed", error=str(cache_err))
                cached = None
            if cached is not None:
                logger.warning(
                    "fallback.using_stale_cache",
                    kind=kind.value,
                    tried=tried,
                    skipped_open=skipped_open,
                )
                return cached

        # 完全失敗 → raise
        raise ExternalServiceError(
            message_zh=(
                f"所有 {kind.value} 資料源均失敗（嘗試 {tried}，跳過 OPEN: {skipped_open}）"
            ),
            kind=kind.value,
            tried=tried,
            skipped_open=skipped_open,
            last_exception=str(last_exc) if last_exc else "none",
        )


__all__ = ["DataSourceFallback", "StaleCacheLoader"]
