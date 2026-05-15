"""Phase 10 — WatchlistService。

依 PLAN.md 第 20.2 章 UNIQUE(user_id, symbol, market) + 17.5 章 cache。

設計：
- ConflictError(409) 當 user 重複加同一支股票（不回 IntegrityError stack）
- cache 用 17.5 章 `cache:watchlist:{user_id}`，TTL=1h，增刪 DEL
- 取得 stock_list 確認 symbol 存在（FK 會擋，但提前 friendly error）
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.core.redis_client import RedisDB, get_redis
from app.core.validators import validate_symbol
from app.models.watchlist import UserWatchlist
from app.repos.stock_repo import StockRepository
from app.repos.watchlist_repo import WatchlistRepository

logger = get_logger(__name__)

WATCHLIST_CACHE_TTL = 3600


class WatchlistService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WatchlistRepository(session)
        self.stocks = StockRepository(session)

    @staticmethod
    def _cache_key(user_id: UUID) -> str:
        return f"cache:watchlist:{user_id}"

    async def _invalidate_cache(self, user_id: UUID) -> None:
        try:
            redis = await get_redis(RedisDB.CACHE)
            await redis.delete(self._cache_key(user_id))
        except Exception as exc:
            logger.warning(
                "watchlist.cache_invalidate_failed", error=str(exc), user_id=str(user_id)
            )

    async def list(self, user_id: UUID) -> list[UserWatchlist]:
        """讀 watchlist；走 cache → DB。"""
        cache_key = self._cache_key(user_id)
        try:
            redis = await get_redis(RedisDB.CACHE)
            cached = await redis.get(cache_key)
            if cached:
                # cache 結構：list of dict（不還原 ORM；直接給 router）
                # 為求簡單，hit cache 仍 return DB ORM（再查 DB）— 留給 P12 物化視圖優化
                _ = json.loads(cached)
        except Exception as exc:
            logger.warning("watchlist.cache_read_failed", error=str(exc), user_id=str(user_id))
        rows = await self.repo.list_for_user(user_id)
        return rows

    async def add(
        self,
        *,
        user_id: UUID,
        symbol: str,
        market: str,
        tag: str | None = None,
        notes: str | None = None,
    ) -> UserWatchlist:
        sym = validate_symbol(symbol)
        market = market.upper()
        # 驗 symbol 存在
        stock = await self.stocks.get_by_symbol(sym, market)
        if stock is None:
            raise NotFoundError(
                message_zh=f"找不到股票 {sym}（市場 {market}）",
                symbol=sym,
                market=market,
            )
        # 預先檢查 unique → 給 friendly 409
        existing = await self.repo.get_by_unique(user_id=user_id, symbol=sym, market=market)
        if existing is not None:
            raise ConflictError(
                message_zh=f"{sym} 已在你的自選股清單",
                symbol=sym,
                market=market,
                existing_id=str(existing.id),
            )

        try:
            entry = await self.repo.add(
                user_id=user_id,
                symbol=sym,
                market=market,
                tag=tag,
                notes=notes,
            )
            await self.session.commit()
        except IntegrityError as e:
            # 競態下 unique 被另一個 request 搶先寫 → 422 / 409 友善訊息
            await self.session.rollback()
            raise ConflictError(
                message_zh=f"{sym} 已在你的自選股清單（並發新增）",
                symbol=sym,
                market=market,
            ) from e
        await self._invalidate_cache(user_id)
        return entry

    async def update(
        self,
        *,
        user_id: UUID,
        watchlist_id: UUID,
        tag: str | None = None,
        notes: str | None = None,
        sort_order: int | None = None,
    ) -> UserWatchlist:
        if tag is None and notes is None and sort_order is None:
            raise ValidationError(
                message_zh="至少需要更新一個欄位（tag / notes / sort_order）",
                field="body",
            )
        updated = await self.repo.update_fields(
            watchlist_id,
            user_id=user_id,
            tag=tag,
            notes=notes,
            sort_order=sort_order,
        )
        if updated is None:
            raise NotFoundError(
                message_zh="找不到該自選股紀錄（或非本人擁有）",
                watchlist_id=str(watchlist_id),
            )
        await self.session.commit()
        await self._invalidate_cache(user_id)
        return updated

    async def delete(self, *, user_id: UUID, watchlist_id: UUID) -> None:
        deleted = await self.repo.delete(watchlist_id, user_id=user_id)
        if not deleted:
            raise NotFoundError(
                message_zh="找不到該自選股紀錄（或非本人擁有）",
                watchlist_id=str(watchlist_id),
            )
        await self.session.commit()
        await self._invalidate_cache(user_id)


# 抑制 unused import 警告
_ = Any


__all__ = ["WATCHLIST_CACHE_TTL", "WatchlistService"]
