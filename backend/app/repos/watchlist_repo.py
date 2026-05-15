"""Phase 10 — WatchlistRepository。

依 PLAN.md 第 17.3 章 envelope + 第 20.2 章 UNIQUE(user_id, symbol, market)。

設計：
- list_for_user → 不分頁（單一 user 通常 < 100 支，先實作簡單列表；後續需要再加 cursor）
- add 時用 ON CONFLICT (uq_user_watchlist_user_symbol_market) DO NOTHING + RETURNING
  讓 service 能準確判斷「新增 or 重複」 → 重複 → ConflictError(409)
- update 走部分欄位 update
- delete 走硬刪除（watchlist 不留 audit；audit log 在 middleware 層記）
- count_for_user：給 sort_order = max+1 用
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import and_, delete, func, select, update

from app.models.watchlist import UserWatchlist
from app.repos.base import BaseRepository

if TYPE_CHECKING:
    pass


class WatchlistRepository(BaseRepository):
    """user_watchlist 表 CRUD。"""

    async def list_for_user(self, user_id: UUID) -> list[UserWatchlist]:
        """列出某 user 全部 watchlist；依 sort_order asc 再 created_at asc。"""
        stmt = (
            select(UserWatchlist)
            .where(UserWatchlist.user_id == user_id)
            .order_by(UserWatchlist.sort_order.asc(), UserWatchlist.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_user(self, user_id: UUID) -> int:
        stmt = select(func.count()).where(UserWatchlist.user_id == user_id)
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def get_by_id(self, watchlist_id: UUID, *, user_id: UUID) -> UserWatchlist | None:
        """取得 watchlist；必須屬於指定 user（防越權）。"""
        stmt = select(UserWatchlist).where(
            and_(
                UserWatchlist.id == watchlist_id,
                UserWatchlist.user_id == user_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_unique(
        self,
        *,
        user_id: UUID,
        symbol: str,
        market: str,
    ) -> UserWatchlist | None:
        """走 UNIQUE(user_id, symbol, market) 查單筆 — service 層 conflict 判斷用。"""
        stmt = select(UserWatchlist).where(
            and_(
                UserWatchlist.user_id == user_id,
                UserWatchlist.symbol == symbol,
                UserWatchlist.market == market,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(
        self,
        *,
        user_id: UUID,
        symbol: str,
        market: str,
        tag: str | None = None,
        notes: str | None = None,
        sort_order: int | None = None,
    ) -> UserWatchlist:
        """建立 watchlist 紀錄；UNIQUE 衝突由 caller 預先檢查（get_by_unique）。

        不在這層 catch IntegrityError — service 層用 try/except 包裝 → ConflictError。
        """
        if sort_order is None:
            sort_order = await self.count_for_user(user_id)
        entry = UserWatchlist(
            user_id=user_id,
            symbol=symbol,
            market=market,
            tag=tag,
            notes=notes,
            sort_order=sort_order,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def update_fields(
        self,
        watchlist_id: UUID,
        *,
        user_id: UUID,
        tag: str | None = None,
        notes: str | None = None,
        sort_order: int | None = None,
    ) -> UserWatchlist | None:
        """部分更新；只能更新自己擁有的 row。"""
        values: dict[str, object] = {}
        if tag is not None:
            values["tag"] = tag
        if notes is not None:
            values["notes"] = notes
        if sort_order is not None:
            values["sort_order"] = sort_order
        if not values:
            # 沒給任何更新欄位 — 直接回 current row
            return await self.get_by_id(watchlist_id, user_id=user_id)
        stmt = (
            update(UserWatchlist)
            .where(
                and_(
                    UserWatchlist.id == watchlist_id,
                    UserWatchlist.user_id == user_id,
                )
            )
            .values(**values)
            .returning(UserWatchlist)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, watchlist_id: UUID, *, user_id: UUID) -> bool:
        """刪除指定 watchlist；只能刪自己擁有的 row。回 True/False 表示是否真的刪到。"""
        stmt = (
            delete(UserWatchlist)
            .where(
                and_(
                    UserWatchlist.id == watchlist_id,
                    UserWatchlist.user_id == user_id,
                )
            )
            .returning(UserWatchlist.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None


__all__ = ["WatchlistRepository"]
