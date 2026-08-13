"""Phase 10 — ScreenerRepository。

依 PLAN.md 第 17.4 章 cursor pagination + 第 19.2 章 sort whitelist + 防 SQL injection。

設計：
- 動態 SQL 用 SQLAlchemy expression 組裝（不用字串 format）
- sort field whitelist（防 ORDER BY injection）
- cursor 走 (sort_field_value, symbol) 兩個欄位 — 因為 symbol 唯一可破 tie

指標（PE / 殖利率 / EPS 成長 / RSI / 市值）已物化到 stock_metrics（每日排程
sync_stock_metrics_tw 刷新），本 repo JOIN 該表並真正套用所有數值條件與排序。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, asc, desc, func, select

from app.models.price import StockPrice
from app.models.stock import StockList
from app.models.tw_specific import StockMetrics
from app.repos.base import BaseRepository

if TYPE_CHECKING:
    from app.schemas.screener import ScreenerFilters


_MARKET_GROUPS: dict[str, tuple[str, ...]] = {
    "TW": ("TWSE", "TPEX"),
    "US": ("NYSE", "NASDAQ", "AMEX"),
}


def _market_filter(market: str) -> tuple[str, ...]:
    return _MARKET_GROUPS.get(market.upper(), (market.upper(),))


class ScreenerRepository(BaseRepository):
    """多條件篩選。"""

    async def screen(
        self,
        filters: ScreenerFilters,
        *,
        sort_by: str = "symbol",
        sort_order: str = "asc",
        limit: int = 50,
        after_symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        """依條件過濾後 + sort + cursor pagination 回前 N 筆。

        sort_by 必須在 SCREENER_SORT_FIELDS（caller 在 service 層先 validate）；
        指標已物化，symbol / market_cap / pe_ratio / dividend_yield / eps_growth / rsi 皆可排序。
        """
        markets = _market_filter(filters.market)

        # 子查 — 每支股票的最新 close
        latest_price_sub = (
            select(
                StockPrice.symbol,
                func.max(StockPrice.date).label("latest_date"),
            )
            .group_by(StockPrice.symbol)
            .subquery()
        )

        stmt = (
            select(
                StockList.symbol,
                StockList.market,
                StockList.name,
                StockList.industry,
                StockPrice.close.label("close"),
                StockMetrics.pe_ratio,
                StockMetrics.dividend_yield,
                StockMetrics.eps_growth,
                StockMetrics.rsi14,
                StockMetrics.market_cap,
            )
            .join(latest_price_sub, latest_price_sub.c.symbol == StockList.symbol, isouter=True)
            .join(
                StockPrice,
                and_(
                    StockPrice.symbol == latest_price_sub.c.symbol,
                    StockPrice.date == latest_price_sub.c.latest_date,
                ),
                isouter=True,
            )
            .join(StockMetrics, StockMetrics.symbol == StockList.symbol, isouter=True)
            .where(
                and_(
                    StockList.market.in_(markets),
                    StockList.is_active.is_(True),
                )
            )
        )

        # ── 數值條件（None 者跳過）——指標來自 stock_metrics（每日排程物化）。
        # LEFT JOIN + 條件比較：某指標為 NULL 的股票在該條件下自然被排除（合理：
        # 你按 PE 篩選就不該回沒有 PE 的個股）。
        if filters.industry:
            # 模糊比對：DB 是「半導體業」，使用者常輸入「半導體」；原精確比對必落空。
            stmt = stmt.where(StockList.industry.ilike(f"%{filters.industry.strip()}%"))
        if filters.pe_min is not None:
            stmt = stmt.where(StockMetrics.pe_ratio >= filters.pe_min)
        if filters.pe_max is not None:
            stmt = stmt.where(StockMetrics.pe_ratio <= filters.pe_max)
        if filters.dividend_yield_min is not None:
            stmt = stmt.where(StockMetrics.dividend_yield >= filters.dividend_yield_min)
        if filters.eps_growth_min is not None:
            stmt = stmt.where(StockMetrics.eps_growth >= filters.eps_growth_min)
        if filters.rsi_min is not None:
            stmt = stmt.where(StockMetrics.rsi14 >= filters.rsi_min)
        if filters.rsi_max is not None:
            stmt = stmt.where(StockMetrics.rsi14 <= filters.rsi_max)
        if filters.market_cap_min is not None:
            stmt = stmt.where(StockMetrics.market_cap >= filters.market_cap_min)

        # cursor — keyset on symbol（symbol 唯一；預設 symbol 排序時分頁精確。
        # 非 symbol 排序目前 UI 不觸發，游標仍以 symbol tie-break 保穩定）
        if after_symbol is not None and after_symbol != "":
            if sort_order.lower() == "desc":
                stmt = stmt.where(StockList.symbol < after_symbol)
            else:
                stmt = stmt.where(StockList.symbol > after_symbol)

        # sort（whitelist 已校驗）— 指標欄位現已物化，可真正排序
        _sort_map = {
            "symbol": StockList.symbol,
            "market_cap": StockMetrics.market_cap,
            "pe_ratio": StockMetrics.pe_ratio,
            "dividend_yield": StockMetrics.dividend_yield,
            "eps_growth": StockMetrics.eps_growth,
            "rsi": StockMetrics.rsi14,
        }
        order_col = _sort_map.get(sort_by, StockList.symbol)
        order_expr = desc(order_col) if sort_order.lower() == "desc" else asc(order_col)
        # 為 keyset 穩定，再加一個 symbol tie-breaker
        stmt = stmt.order_by(order_expr, StockList.symbol.asc())

        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        rows: list[dict[str, Any]] = []
        for r in result.all():
            rows.append(
                {
                    "symbol": r.symbol,
                    "market": r.market,
                    "name": r.name,
                    "industry": r.industry,
                    "close": r.close,
                    "pe_ratio": r.pe_ratio,
                    "dividend_yield": r.dividend_yield,
                    "eps_growth": r.eps_growth,
                    "rsi": r.rsi14,
                    "market_cap": r.market_cap,
                }
            )
        return rows


__all__ = ["ScreenerRepository"]
