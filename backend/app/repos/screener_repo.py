"""Phase 10 — ScreenerRepository。

依 PLAN.md 第 17.4 章 cursor pagination + 第 19.2 章 sort whitelist + 防 SQL injection。

設計：
- 動態 SQL 用 SQLAlchemy expression 組裝（不用字串 format）
- sort field whitelist（防 ORDER BY injection）
- cursor 走 (sort_field_value, symbol) 兩個欄位 — 因為 symbol 唯一可破 tie

注意：本 Phase v1 — 真正的 PE / Yield / EPS / RSI 還沒在 PG 物化（Phase 12 後做），
這裡先以「stock_list + 最新 stock_prices.close」demo，
filter pe_min/pe_max/... 為 future-proof 介面（傳入但忽略也合法）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, asc, desc, distinct, func, select, tuple_

from app.models.price import StockPrice
from app.models.stock import StockList
from app.repos.base import BaseRepository
from app.schemas.screener import SCREENER_SORT_FIELDS

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

        sort_by 必須在 SCREENER_SORT_FIELDS（caller 在 service 層先 validate）。
        本 v1 因 PE / Yield 還沒物化，sort 只實作 symbol / market_cap（其它 fall back to symbol）。
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
            .where(
                and_(
                    StockList.market.in_(markets),
                    StockList.is_active.is_(True),
                )
            )
        )

        if filters.industry:
            stmt = stmt.where(StockList.industry == filters.industry)

        # cursor — keyset on symbol（單欄即可，symbol 是唯一鍵）
        if after_symbol is not None and after_symbol != "":
            if sort_order.lower() == "desc":
                stmt = stmt.where(StockList.symbol < after_symbol)
            else:
                stmt = stmt.where(StockList.symbol > after_symbol)

        # sort（whitelist 已校驗）
        order_col = StockList.symbol  # 預設 / fallback
        if sort_by == "symbol":
            order_col = StockList.symbol
        elif sort_by == "market_cap":
            # 暫無 market_cap 欄位 — 用 close 代替（v1 demo）
            order_col = StockPrice.close
        # 其他 PE / yield / eps / RSI — 還沒物化 → fall back symbol
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
                    "pe_ratio": None,
                    "dividend_yield": None,
                    "eps_growth": None,
                    "rsi": None,
                    "market_cap": None,
                }
            )
        return rows


# 抑制未用 import（保留給未來指標欄位）
_ = (distinct, tuple_, SCREENER_SORT_FIELDS)


__all__ = ["ScreenerRepository"]
