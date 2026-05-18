"""Repository 基類。

依 PLAN.md 第 18.1 章後端分層 + 第 17.9 章。

設計原則：
- 每個 repo 接收 AsyncSession（從 router/service depend 注入）
- 寫操作 → 由 caller 控制 transaction（unit-of-work 模式：caller 用 `async with session.begin():`）
- repo 本身只 add / execute；不主動 commit
- 例外：upsert_many / bulk 寫 → 提供 commit=True 參數（單 step 場景方便）
- 區分 BaseRepository（read+write）與 ReadOnlyRepository（強型別表達只讀）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """所有 repo 的基類。子類繼承並注入 AsyncSession。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def commit(self) -> None:
        await self.session.commit()

    async def flush(self) -> None:
        await self.session.flush()

    async def rollback(self) -> None:
        await self.session.rollback()


class ReadOnlyRepository(BaseRepository):
    """強型別表達只讀（給 LangGraph Tool / Agent 用，session 來自 ta_agent_ro 帳號）。

    P5 階段：本類別不強制檢查 session role（PG 層由 GRANT 控制），
    但定義出明確的型別語義，方便 P10+ 上線時用 type-check / linter 限制。
    """


__all__ = ["BaseRepository", "ReadOnlyRepository"]
