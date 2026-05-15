"""StockRepository — stock_list / stock_info CRUD。

依 PLAN.md 第 15.3 章「N+1 防護」+ 第 17.9 章「stock_list seed P2 起前端搜尋必需」。

提供：
- list_active(market): 取得所有 is_active=true 的股票（前端下拉用）
- get_by_symbol(symbol, market): 單股
- search_by_name(query, limit): 模糊搜尋（依 GIN(name gin_trgm_ops)）
- upsert_many(items): bulk upsert（給 seeders / data pipeline）
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging_config import get_logger
from app.models.stock import StockList
from app.repos.base import BaseRepository

logger = get_logger(__name__)


class StockRepository(BaseRepository):
    async def list_active(self, market: str | None = None) -> list[StockList]:
        stmt = select(StockList).where(StockList.is_active.is_(True))
        if market is not None:
            stmt = stmt.where(StockList.market == market)
        stmt = stmt.order_by(StockList.market, StockList.symbol)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_page(
        self,
        *,
        markets: list[str] | None = None,
        keyword: str | None = None,
        after_symbol: str | None = None,
        limit: int = 50,
    ) -> list[StockList]:
        """Phase 10 — cursor pagination 列表。

        Args:
            markets: stock_list.market enum 過濾（如 ["TWSE","TPEX"]）；None → 不限
            keyword: symbol prefix 或 name ILIKE 子串
            after_symbol: cursor — 取 symbol > after_symbol（asc 排序）
            limit: 最多筆數

        排序：symbol asc（keyset 用）。
        """
        stmt = select(StockList).where(StockList.is_active.is_(True))
        if markets:
            stmt = stmt.where(StockList.market.in_(markets))
        if keyword:
            q = keyword.strip()
            if q:
                like = f"%{q}%"
                symbol_prefix = f"{q}%"
                stmt = stmt.where(
                    (StockList.symbol.ilike(symbol_prefix)) | (StockList.name.ilike(like))
                )
        if after_symbol:
            stmt = stmt.where(StockList.symbol > after_symbol)
        stmt = stmt.order_by(StockList.symbol.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_symbol(self, symbol: str, market: str) -> StockList | None:
        stmt = select(StockList).where(and_(StockList.symbol == symbol, StockList.market == market))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_by_name(self, query: str, *, limit: int = 20) -> list[StockList]:
        """模糊搜尋 — 同時匹配 symbol 字頭與 name 子串。

        使用 ILIKE 即可；GIN(name gin_trgm_ops) index 由 PG planner 自動採用
        （PLAN 第 20.2 章）。
        """
        q = query.strip()
        if not q:
            return []
        like = f"%{q}%"
        symbol_prefix = f"{q}%"
        stmt = (
            select(StockList)
            .where(
                StockList.is_active.is_(True),
                # symbol 字頭 or name 子串
                (StockList.symbol.ilike(symbol_prefix)) | (StockList.name.ilike(like)),
            )
            .order_by(StockList.symbol)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_many(self, items: list[dict[str, Any]], *, commit: bool = False) -> int:
        """ON CONFLICT (symbol) DO UPDATE — bulk upsert。

        Args:
            items: list[dict]，每筆至少含 symbol / market / name；其他欄位可選。
            commit: 是否在這裡 commit；False 由 caller 控制 transaction。

        Returns:
            實際寫入 / 更新筆數（PG `xmax` 0 vs > 0 不分開算，直接回 len(items)）。
        """
        if not items:
            return 0

        # 預設未填欄位給 None；保留 PK = symbol
        stmt = pg_insert(StockList).values(items)
        update_cols = {
            "market": stmt.excluded.market,
            "name": stmt.excluded.name,
            "short_name": stmt.excluded.short_name,
            "industry": stmt.excluded.industry,
            "listed_at": stmt.excluded.listed_at,
            "is_active": stmt.excluded.is_active,
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_=update_cols,
        )
        await self.session.execute(stmt)
        if commit:
            await self.session.commit()
        return len(items)


__all__ = ["StockRepository"]
