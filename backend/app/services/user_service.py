"""Phase 10 — UserService（admin CRUD + self-update + reset-password）。

依 PLAN.md 第 19.1 章認證授權 + 第 19.4 章 secret 管理。

設計：
- list / create / update / soft_delete 全部走 admin only（RBAC 在 router 層 Depends）
- self_update 走 user 自己更新（限制不能改 role / is_active）
- reset_password 由 admin 為某 user 重設密碼：撤銷該 user 全部 session
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cursor import Cursor, clamp_limit
from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.repos.user_repo import UserRepository, UserSessionRepository


@dataclass(slots=True)
class UserListPage:
    items: list[User]
    next_cursor_kwargs: dict[str, Any] | None
    limit: int


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sessions = UserSessionRepository(session)

    async def list_users(
        self,
        *,
        cursor: str | None,
        limit: int | None,
        include_deleted: bool = False,
    ) -> UserListPage:
        page_size = clamp_limit(limit)
        decoded = Cursor.decode(cursor) if cursor else {}
        after_id: UUID | None = None
        after_raw = decoded.get("after_id") if isinstance(decoded, dict) else None
        if after_raw:
            try:
                after_id = UUID(str(after_raw))
            except (ValueError, TypeError):
                after_id = None

        rows = await self.users.list_page(
            after_id=after_id,
            limit=page_size + 1,
            include_deleted=include_deleted,
        )
        has_more = len(rows) > page_size
        items = rows[:page_size]
        next_cursor_kwargs: dict[str, Any] | None = None
        if has_more and items:
            next_cursor_kwargs = {"after_id": str(items[-1].id)}
        return UserListPage(items=items, next_cursor_kwargs=next_cursor_kwargs, limit=page_size)

    async def get_user(self, user_id: UUID) -> User:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError(message_zh="找不到該使用者", user_id=str(user_id))
        return user

    async def create_user(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None,
        role: str,
        preferred_timezone: str,
        preferred_language: str,
        must_change_password: bool,
    ) -> User:
        existing = await self.users.get_by_email(email)
        if existing is not None:
            raise ConflictError(
                message_zh="此 email 已存在",
                email=email,
            )
        user = await self.users.create(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            preferred_timezone=preferred_timezone,
            preferred_language=preferred_language,
            must_change_password=must_change_password,
        )
        await self.session.commit()
        return user

    async def update_user(
        self,
        user_id: UUID,
        *,
        full_name: str | None = None,
        role: str | None = None,
        preferred_timezone: str | None = None,
        preferred_language: str | None = None,
        is_active: bool | None = None,
    ) -> User:
        updated = await self.users.update_fields(
            user_id,
            full_name=full_name,
            role=role,
            preferred_timezone=preferred_timezone,
            preferred_language=preferred_language,
            is_active=is_active,
        )
        if updated is None:
            raise NotFoundError(message_zh="找不到該使用者", user_id=str(user_id))
        await self.session.commit()
        return updated

    async def mark_onboarded(self, user_id: UUID) -> None:
        """把使用者 onboarding_completed 設為 true（首次導覽完成）。"""
        await self.users.mark_onboarded(user_id)
        await self.session.commit()

    async def soft_delete_user(self, user_id: UUID) -> None:
        ok = await self.users.soft_delete(user_id)
        if not ok:
            raise NotFoundError(message_zh="找不到該使用者（或已刪除）", user_id=str(user_id))
        # 撤銷該 user 全部 active sessions
        await self.sessions.revoke_all_for_user(user_id)
        await self.session.commit()

    async def reset_password(
        self,
        user_id: UUID,
        *,
        new_password: str,
        must_change_password: bool = True,
    ) -> None:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError(message_zh="找不到該使用者", user_id=str(user_id))
        new_hash = hash_password(new_password)
        await self.users.update_password(
            user_id, new_hash, clear_must_change=not must_change_password
        )
        if must_change_password:
            # update_password 在 must_change=False 時才會把 must_change 設 False；
            # 反過來：我們希望強制改密 → 直接走 fields update
            await self.users.update_fields(
                user_id,
                # 這裡用既有 update_fields 不能改 must_change_password；
                # 直接走 SQL update
            )
            from sqlalchemy import update as sa_update

            from app.models.user import User as UserModel

            await self.session.execute(
                sa_update(UserModel)
                .where(UserModel.id == user_id)
                .values(must_change_password=True)
            )
        # 撤銷全部 session
        await self.sessions.revoke_all_for_user(user_id)
        await self.session.commit()


__all__ = ["UserListPage", "UserService"]
