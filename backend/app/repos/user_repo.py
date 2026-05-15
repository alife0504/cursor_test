"""Phase 8 — User / UserSession / PasswordResetToken repositories。

依 PLAN.md 第 19.1 章認證授權 + 第 13.4 章 onboarding。

設計：
- 所有 method 都 take `AsyncSession`（caller 傳，這層不開新 session）
- caller 負責 commit / rollback（service 層才開 transaction）
- lockout / session 上限的並發控制用 SELECT ... FOR UPDATE
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, select, update

from app.models.user import PasswordResetToken, User, UserSession

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

MAX_SESSIONS_PER_USER = 5
LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)
PASSWORD_RESET_TOKEN_TTL = timedelta(minutes=30)
PASSWORD_RESET_RATE_WINDOW = timedelta(hours=1)
PASSWORD_RESET_RATE_LIMIT = 3


def hash_refresh_token(token: str) -> str:
    """sha256 hash 一個 refresh token（DB 存 hash，不存原始 token）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_reset_token(token: str) -> str:
    """sha256 hash 一個 password-reset token（DB 存 hash）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────
# UserRepository
# ─────────────────────────────────────────────────────────


class UserRepository:
    """User table 的 CRUD wrapper（lockout / 密碼更新 / 軟刪除）。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── 查詢 ────────────────────────────────────────
    async def get_by_email(self, email: str) -> User | None:
        """大小寫不敏感查 email（functional index ix_users_email_lower）。"""
        if not email:
            return None
        stmt = select(User).where(func.lower(User.email) == email.strip().lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_update(self, user_id: UUID) -> User | None:
        """row-level lock 取 user（用於 lockout / session 並發控制）。"""
        stmt = select(User).where(User.id == user_id).with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── 密碼 ────────────────────────────────────────
    async def update_password(
        self,
        user_id: UUID,
        new_hash: str,
        *,
        clear_must_change: bool = True,
    ) -> None:
        """改密碼；可選擇是否清掉 must_change_password。"""
        values: dict[str, object] = {"password_hash": new_hash}
        if clear_must_change:
            values["must_change_password"] = False
        stmt = update(User).where(User.id == user_id).values(**values)
        await self.session.execute(stmt)

    # ── lockout ─────────────────────────────────────
    def is_locked(self, user: User) -> bool:
        """判斷 user 是否還在鎖定中。"""
        if user.locked_until is None:
            return False
        return user.locked_until > datetime.now(UTC)

    async def increment_failed_attempts(self, user_id: UUID) -> int:
        """+1 失敗次數，回傳更新後的數值。"""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(failed_attempts=User.failed_attempts + 1)
            .returning(User.failed_attempts)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def reset_failed_attempts(
        self,
        user_id: UUID,
        *,
        last_login_at: datetime | None = None,
        last_login_ip: str | None = None,
    ) -> None:
        """登入成功後清 failed_attempts + locked_until + 更新 last_login_*。"""
        values: dict[str, object] = {
            "failed_attempts": 0,
            "locked_until": None,
        }
        if last_login_at is not None:
            values["last_login_at"] = last_login_at
        if last_login_ip is not None:
            values["last_login_ip"] = last_login_ip
        stmt = update(User).where(User.id == user_id).values(**values)
        await self.session.execute(stmt)

    async def lock(self, user_id: UUID, until: datetime) -> None:
        """鎖到指定時間。"""
        stmt = update(User).where(User.id == user_id).values(locked_until=until)
        await self.session.execute(stmt)

    # ── onboarding ──────────────────────────────────
    async def mark_onboarded(self, user_id: UUID) -> None:
        stmt = update(User).where(User.id == user_id).values(onboarding_completed=True)
        await self.session.execute(stmt)

    # ── Phase 10 — admin CRUD ──────────────────────────
    async def list_page(
        self,
        *,
        after_id: UUID | None = None,
        limit: int = 50,
        include_deleted: bool = False,
    ) -> list[User]:
        """Cursor pagination — order by id asc。"""
        stmt = select(User)
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))
        if after_id is not None:
            stmt = stmt.where(User.id > after_id)
        stmt = stmt.order_by(User.id.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str | None,
        role: str,
        preferred_timezone: str,
        preferred_language: str,
        must_change_password: bool,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            preferred_timezone=preferred_timezone,
            preferred_language=preferred_language,
            must_change_password=must_change_password,
            onboarding_completed=False,
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_fields(
        self,
        user_id: UUID,
        *,
        full_name: str | None = None,
        role: str | None = None,
        preferred_timezone: str | None = None,
        preferred_language: str | None = None,
        is_active: bool | None = None,
    ) -> User | None:
        values: dict[str, object] = {}
        if full_name is not None:
            values["full_name"] = full_name
        if role is not None:
            values["role"] = role
        if preferred_timezone is not None:
            values["preferred_timezone"] = preferred_timezone
        if preferred_language is not None:
            values["preferred_language"] = preferred_language
        if is_active is not None:
            values["is_active"] = is_active
        if not values:
            return await self.get_by_id(user_id)
        stmt = update(User).where(User.id == user_id).values(**values).returning(User)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete(self, user_id: UUID) -> bool:
        """軟刪除：is_active=false + deleted_at=now()。回 True 若有行被改。"""
        stmt = (
            update(User)
            .where(and_(User.id == user_id, User.deleted_at.is_(None)))
            .values(is_active=False, deleted_at=func.now())
            .returning(User.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None


# ─────────────────────────────────────────────────────────
# UserSessionRepository
# ─────────────────────────────────────────────────────────


class UserSessionRepository:
    """user_sessions 表 — refresh JWT 一個 row（含 jti / hash / 黑名單比對）。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: UUID,
        jti: str,
        refresh_token: str,
        expires_at: datetime,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> UserSession:
        """建立 session 紀錄；refresh_token 會被 sha256 hash 後存。"""
        record = UserSession(
            user_id=user_id,
            jti=jti,
            refresh_token_hash=hash_refresh_token(refresh_token),
            expires_at=expires_at,
            ip=ip,
            user_agent=user_agent,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_jti(self, jti: str) -> UserSession | None:
        stmt = select(UserSession).where(UserSession.jti == jti)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self, user_id: UUID) -> list[UserSession]:
        """列出 user 仍有效（未過期 + 未撤銷）的 session，照 issued_at 由舊到新。"""
        now = datetime.now(UTC)
        stmt = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked.is_(False),
                UserSession.expires_at > now,
            )
            .order_by(UserSession.issued_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def revoke_oldest_if_over_limit(
        self,
        user_id: UUID,
        *,
        max_sessions: int = MAX_SESSIONS_PER_USER,
    ) -> list[UserSession]:
        """若 user 的 active session 超過 max_sessions，撤銷最舊的幾個。

        回傳被撤銷的 sessions（caller 可拿來加入 blacklist）。
        """
        active = await self.list_active(user_id)
        if len(active) <= max_sessions:
            return []
        excess = active[: len(active) - max_sessions]
        now = datetime.now(UTC)
        for s in excess:
            s.revoked = True
            s.revoked_at = now
        await self.session.flush()
        return excess

    async def revoke(self, jti: str) -> UserSession | None:
        """撤銷指定 jti。"""
        sess = await self.get_by_jti(jti)
        if sess is None:
            return None
        sess.revoked = True
        sess.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return sess

    async def revoke_all_for_user(
        self,
        user_id: UUID,
        *,
        except_jti: str | None = None,
    ) -> list[UserSession]:
        """撤銷 user 全部 active session；可選保留一個（例如改密碼後保留當前 session）。"""
        now = datetime.now(UTC)
        active = await self.list_active(user_id)
        revoked: list[UserSession] = []
        for s in active:
            if except_jti and s.jti == except_jti:
                continue
            s.revoked = True
            s.revoked_at = now
            revoked.append(s)
        await self.session.flush()
        return revoked


# ─────────────────────────────────────────────────────────
# PasswordResetTokenRepository
# ─────────────────────────────────────────────────────────


class PasswordResetTokenRepository:
    """password_reset_tokens 表 — 一次性 token + 限速 3/hr/IP。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: UUID,
        token: str,
        expires_at: datetime,
        ip: str | None = None,
    ) -> PasswordResetToken:
        record = PasswordResetToken(
            user_id=user_id,
            token_hash=hash_reset_token(token),
            expires_at=expires_at,
            ip=ip,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_token(self, token: str) -> PasswordResetToken | None:
        token_hash = hash_reset_token(token)
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_used(self, record: PasswordResetToken) -> None:
        record.used = True
        record.used_at = datetime.now(UTC)
        await self.session.flush()

    async def count_recent_for_ip(
        self,
        ip: str,
        *,
        window: timedelta = PASSWORD_RESET_RATE_WINDOW,
    ) -> int:
        """限速用：查同一 IP 在 window 內已發起幾次重置。"""
        if not ip:
            return 0
        since = datetime.now(UTC) - window
        stmt = select(func.count()).where(
            PasswordResetToken.ip == ip,
            PasswordResetToken.created_at >= since,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)


__all__ = [
    "LOCKOUT_DURATION",
    "LOCKOUT_THRESHOLD",
    "MAX_SESSIONS_PER_USER",
    "PASSWORD_RESET_RATE_LIMIT",
    "PASSWORD_RESET_RATE_WINDOW",
    "PASSWORD_RESET_TOKEN_TTL",
    "PasswordResetTokenRepository",
    "UserRepository",
    "UserSessionRepository",
    "hash_refresh_token",
    "hash_reset_token",
]
