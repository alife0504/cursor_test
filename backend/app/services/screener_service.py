"""Phase 10 — ScreenerService。

依 PLAN.md 第 17.4 章 cursor pagination + 第 19.2 章 sort whitelist。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cursor import Cursor, clamp_limit
from app.core.validators import validate_sort_field, validate_sort_order
from app.repos.screener_repo import ScreenerRepository
from app.schemas.screener import SCREENER_SORT_FIELDS, ScreenerFilters


@dataclass(slots=True)
class ScreenerPage:
    items: list[dict[str, Any]]
    next_cursor_kwargs: dict[str, Any] | None
    limit: int


class ScreenerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ScreenerRepository(session)

    async def screen(
        self,
        filters: ScreenerFilters,
        *,
        sort_by: str = "symbol",
        sort_order: str = "asc",
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ScreenerPage:
        sort_by = validate_sort_field(sort_by, allowed=set(SCREENER_SORT_FIELDS))
        sort_order = validate_sort_order(sort_order)
        page_size = clamp_limit(limit)
        decoded = Cursor.decode(cursor) if cursor else {}
        after_symbol = decoded.get("after_symbol") if isinstance(decoded, dict) else None

        rows = await self.repo.screen(
            filters,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=page_size + 1,
            after_symbol=after_symbol,
        )
        has_more = len(rows) > page_size
        items = rows[:page_size]
        next_cursor_kwargs: dict[str, Any] | None = None
        if has_more and items:
            next_cursor_kwargs = {"after_symbol": items[-1]["symbol"]}
        return ScreenerPage(items=items, next_cursor_kwargs=next_cursor_kwargs, limit=page_size)


__all__ = ["ScreenerPage", "ScreenerService"]
