"""Phase 8 — AuthService：login / refresh / logout / change-password / password-reset。

依 PLAN.md 第 19.1 章認證授權 + 第 13.4 章 onboarding + 第 19.4 章 secret 管理。

設計：
- service 層開 transaction（async with session.begin()）
- repo 層只負責 SQL
- audit log 用 _audit_minimal.append_audit（P9 改 AuditRepository）
- token blacklist 用 Redis db3；ws ticket 用 Redis db5
- lockout / 5 sessions 上限 / password history / CSRF 全部在這層處理
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.csrf import generate_csrf_token, verify_csrf_token
from app.core.errors import AuthError, ForbiddenError, LockedError, RateLimitError
from app.core.logging_config import get_logger
from app.core.password_policy import (
    PasswordHistoryService,
    validate_password,
)
from app.core.security import (
    JWTService,
    TokenBlacklist,
    constant_time_dummy_verify,
    hash_password,
    ttl_seconds_from_exp,
    verify_password,
)
from app.repos.user_repo import (
    LOCKOUT_DURATION,
    LOCKOUT_THRESHOLD,
    MAX_SESSIONS_PER_USER,
    PASSWORD_RESET_RATE_LIMIT,
    PASSWORD_RESET_RATE_WINDOW,
    PASSWORD_RESET_TOKEN_TTL,
    PasswordResetTokenRepository,
    UserRepository,
    UserSessionRepository,
    hash_refresh_token,
)
from app.services._audit_minimal import append_audit

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────
# DTO
# ─────────────────────────────────────────────────────────


@dataclass(slots=True)
class LoginResult:
    """login 成功的結果 — router 拿來組 response cookies + body。"""

    access_token: str
    refresh_token: str
    csrf_token: str
    refresh_expires_at: datetime
    access_ttl_seconds: int
    next_action: str
    user: User


@dataclass(slots=True)
class RefreshResult:
    access_token: str
    refresh_token: str
    csrf_token: str
    refresh_expires_at: datetime
    access_ttl_seconds: int


# ─────────────────────────────────────────────────────────
# AuthService
# ─────────────────────────────────────────────────────────


class AuthService:
    """整合 jwt / blacklist / user / session / audit 的高階服務。"""

    def __init__(
        self,
        *,
        session: AsyncSession,
        jwt_service: JWTService,
        blacklist: TokenBlacklist,
    ) -> None:
        self.session = session
        self.jwt = jwt_service
        self.blacklist = blacklist
        self.user_repo = UserRepository(session)
        self.session_repo = UserSessionRepository(session)
        self.reset_repo = PasswordResetTokenRepository(session)
        self.history = PasswordHistoryService(session)

    # ════════════════ login ════════════════

    async def login(
        self,
        *,
        email: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
        request_id: str | None = None,
    ) -> LoginResult:
        """登入 — 含 lockout、session 上限、audit log、next_action 判斷。

        Phase 12 audit fix #2/#3：用 PG advisory lock (per email/user_id) 防止並發 burst 繞過
        lockout 與 session 上限。lock 在 transaction commit 時自動釋放。
        """
        # Phase 12 audit fix #2: 並發 lockout race
        # PG advisory lock 以 email 為 key — 並發 login 同 email 會排隊，避免 burst dictionary attack
        # 可繞過 5 次門檻；email 用 hashtext() 摺成 int4
        from sqlalchemy import text as sql_text

        await self.session.execute(
            sql_text("SELECT pg_advisory_xact_lock(hashtext(:e))"),
            {"e": email.lower()},
        )

        user = await self.user_repo.get_by_email(email)

        # 1) user 不存在 → dummy verify 抵抗 timing attack
        if user is None or not user.is_active or user.deleted_at is not None:
            constant_time_dummy_verify()
            await append_audit(
                self.session,
                actor_id=None,
                action="auth.login_failed",
                entity_type="user",
                entity_id=email,
                details={"reason": "user_not_found_or_inactive"},
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
            )
            await self.session.commit()
            raise AuthError(message_zh="帳號或密碼錯誤")

        # 2) 仍鎖定中 → 423
        if self.user_repo.is_locked(user):
            await append_audit(
                self.session,
                actor_id=user.id,
                action="auth.login_locked",
                entity_type="user",
                entity_id=str(user.id),
                details={
                    "locked_until": user.locked_until.isoformat() if user.locked_until else None
                },
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
            )
            await self.session.commit()
            raise LockedError(
                message_zh="帳號已鎖定，請於 15 分鐘後再試或請管理員解鎖",
                locked_until=user.locked_until.isoformat() if user.locked_until else None,
            )

        # 3) 比對密碼
        if not verify_password(password, user.password_hash):
            new_count = await self.user_repo.increment_failed_attempts(user.id)
            if new_count >= LOCKOUT_THRESHOLD:
                lock_until = datetime.now(UTC) + LOCKOUT_DURATION
                await self.user_repo.lock(user.id, lock_until)
                await append_audit(
                    self.session,
                    actor_id=user.id,
                    action="auth.login_locked",
                    entity_type="user",
                    entity_id=str(user.id),
                    details={
                        "failed_attempts": new_count,
                        "locked_until": lock_until.isoformat(),
                    },
                    ip=ip,
                    user_agent=user_agent,
                    request_id=request_id,
                )
                await self.session.commit()
                raise LockedError(
                    message_zh="連續登入失敗，帳號已鎖定 15 分鐘",
                    locked_until=lock_until.isoformat(),
                )
            await append_audit(
                self.session,
                actor_id=user.id,
                action="auth.login_failed",
                entity_type="user",
                entity_id=str(user.id),
                details={"failed_attempts": new_count, "reason": "wrong_password"},
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
            )
            await self.session.commit()
            raise AuthError(message_zh="帳號或密碼錯誤")

        # 4) 成功 — 簽 access + refresh、建 session、清 failed_attempts、撤銷超量舊 session
        now = datetime.now(UTC)
        access_token, _ = self.jwt.create_access_token(user.id, user.role)
        refresh_token, refresh_jti, refresh_exp = self.jwt.create_refresh_token(user.id)

        await self.session_repo.create(
            user_id=user.id,
            jti=refresh_jti,
            refresh_token=refresh_token,
            expires_at=refresh_exp,
            ip=ip,
            user_agent=user_agent,
        )

        revoked_excess = await self.session_repo.revoke_oldest_if_over_limit(
            user.id, max_sessions=MAX_SESSIONS_PER_USER
        )
        # 撤銷的舊 session 放進 JWT blacklist（jti TTL 用剩餘秒）
        for old in revoked_excess:
            ttl = max(0, int((old.expires_at - now).total_seconds()))
            await self.blacklist.add(old.jti, ttl)

        await self.user_repo.reset_failed_attempts(
            user.id,
            last_login_at=now,
            last_login_ip=ip,
        )

        # next_action 判斷（priority: change_password > onboarding > dashboard）
        if user.must_change_password:
            next_action = "change_password"
        elif not user.onboarding_completed:
            next_action = "onboarding"
        else:
            next_action = "dashboard"

        await append_audit(
            self.session,
            actor_id=user.id,
            action="auth.login",
            entity_type="user",
            entity_id=str(user.id),
            details={
                "next_action": next_action,
                "revoked_excess_sessions": len(revoked_excess),
            },
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
        )
        await self.session.commit()

        csrf_token = generate_csrf_token()
        return LoginResult(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            refresh_expires_at=refresh_exp,
            access_ttl_seconds=int(self.jwt.ACCESS_TTL.total_seconds()),
            next_action=next_action,
            user=user,
        )

    # ════════════════ refresh ════════════════

    async def refresh(
        self,
        *,
        refresh_token: str,
        csrf_header: str | None,
        csrf_cookie: str | None,
        ip: str | None,
        user_agent: str | None,
        request_id: str | None = None,
    ) -> RefreshResult:
        """換新 access + refresh — rotation：舊 jti 進 blacklist + revoke。"""

        # CSRF 必須帶且相符
        if not verify_csrf_token(csrf_header, csrf_cookie):
            raise ForbiddenError(message_zh="CSRF token 驗證失敗")

        if not refresh_token:
            raise AuthError(message_zh="缺少 refresh token")

        payload = self.jwt.decode(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthError(message_zh="Token 類型錯誤（不是 refresh token）")

        jti = str(payload.get("jti") or "")
        sub = str(payload.get("sub") or "")
        if not jti or not sub:
            raise AuthError(message_zh="Token 內容不完整")

        if await self.blacklist.is_blacklisted(jti):
            raise AuthError(message_zh="Token 已被撤銷")

        existing = await self.session_repo.get_by_jti(jti)
        # Phase 12 audit fix #5: refresh token reuse detection
        # 若 session 已 revoked（已 rotation 過或被 logout），但對方又送來 = 強烈洩漏訊號
        # OWASP refresh-token rotation：偵測到 reuse → 撤銷該 user 全部 active session（family revoke）
        if existing is not None and existing.revoked:
            try:
                user_uuid = UUID(sub)
                revoked_sessions = await self.session_repo.revoke_all_for_user(user_uuid)
                revoked_count = len(revoked_sessions)
                logger.critical(
                    "auth.refresh.token_reuse_detected",
                    user_id=sub,
                    jti=jti,
                    revoked_sessions=revoked_count,
                )
                await append_audit(
                    self.session,
                    actor_id=user_uuid,
                    action="auth.token_reuse_detected",
                    entity_type="user",
                    entity_id=sub,
                    details={
                        "jti": jti,
                        "revoked_sessions": revoked_count,
                        "reason": "refresh_token_reuse",
                    },
                    ip=ip,
                    user_agent=user_agent,
                    request_id=request_id,
                )
                await self.session.commit()
            except (ValueError, TypeError):
                # sub 非 UUID 不應發生（前面已驗）— 但保險起見不擋 401 流程
                logger.warning("auth.refresh.reuse_detected_but_bad_sub", sub=sub)
            raise AuthError(message_zh="Token 已被撤銷（偵測到重複使用，已強制全部登出）")
        if existing is None:
            raise AuthError(message_zh="Session 不存在或已撤銷")
        if existing.refresh_token_hash != hash_refresh_token(refresh_token):
            # token 內容被改過
            raise AuthError(message_zh="Token 不一致")

        # 載入 user 並檢查 active
        user = await self.user_repo.get_by_id(UUID(sub))
        if user is None or not user.is_active or user.deleted_at is not None:
            raise AuthError(message_zh="帳號已停用")

        # rotation: 撤銷舊 + 加 blacklist + 簽新
        existing.revoked = True
        existing.revoked_at = datetime.now(UTC)
        await self.blacklist.add(jti, ttl_seconds_from_exp(int(payload["exp"])))

        access_token, _ = self.jwt.create_access_token(user.id, user.role)
        new_refresh_token, new_refresh_jti, new_refresh_exp = self.jwt.create_refresh_token(user.id)
        await self.session_repo.create(
            user_id=user.id,
            jti=new_refresh_jti,
            refresh_token=new_refresh_token,
            expires_at=new_refresh_exp,
            ip=ip,
            user_agent=user_agent,
        )

        await append_audit(
            self.session,
            actor_id=user.id,
            action="auth.refresh",
            entity_type="user",
            entity_id=str(user.id),
            details={"old_jti": jti, "new_jti": new_refresh_jti},
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
        )
        await self.session.commit()

        return RefreshResult(
            access_token=access_token,
            refresh_token=new_refresh_token,
            csrf_token=generate_csrf_token(),
            refresh_expires_at=new_refresh_exp,
            access_ttl_seconds=int(self.jwt.ACCESS_TTL.total_seconds()),
        )

    # ════════════════ logout ════════════════

    async def logout(
        self,
        *,
        refresh_token: str | None,
        actor_id_from_access: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """logout — 撤銷 refresh session + access blacklist。

        若 refresh_token 缺失或失效，仍視為登出成功（不洩漏訊息給攻擊者）。
        """
        if not refresh_token:
            return

        try:
            payload = self.jwt.decode(refresh_token)
        except AuthError:
            return

        # Phase 12 audit fix #4: logout 只接受 refresh token；access token 不應寫 blacklist
        # （避免攻擊者把 access token 灌入 blacklist db3 佔記憶體並令正常 access 失效）
        if payload.get("type") != "refresh":
            logger.info(
                "auth.logout.wrong_token_type",
                got_type=payload.get("type"),
                jti=payload.get("jti"),
            )
            return

        jti = str(payload.get("jti") or "")
        if not jti:
            return

        sess = await self.session_repo.get_by_jti(jti)
        if sess is not None and not sess.revoked:
            sess.revoked = True
            sess.revoked_at = datetime.now(UTC)
        await self.blacklist.add(jti, ttl_seconds_from_exp(int(payload["exp"])))

        actor_id = None
        sub = payload.get("sub")
        if sub:
            try:
                actor_id = UUID(str(sub))
            except (ValueError, TypeError):
                actor_id = None
        elif actor_id_from_access:
            try:
                actor_id = UUID(actor_id_from_access)
            except (ValueError, TypeError):
                actor_id = None

        await append_audit(
            self.session,
            actor_id=actor_id,
            action="auth.logout",
            entity_type="user",
            entity_id=str(actor_id) if actor_id else None,
            details={"jti": jti},
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
        )
        await self.session.commit()

    # ════════════════ change password ════════════════

    async def change_password(
        self,
        *,
        user_id,
        old_password: str,
        new_password: str,
        current_refresh_jti: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """改密碼 — 驗舊 + 4 類字元 + 不可包含 email + 最近 5 次不可重複。

        成功後：撤銷所有「其他」refresh session（保留當前 jti 不撤）。
        """
        user = await self.user_repo.get_by_id(user_id)
        if user is None or not user.is_active or user.deleted_at is not None:
            raise AuthError(message_zh="帳號不存在或已停用")

        if not verify_password(old_password, user.password_hash):
            await append_audit(
                self.session,
                actor_id=user.id,
                action="auth.password_change_failed",
                entity_type="user",
                entity_id=str(user.id),
                details={"reason": "wrong_old_password"},
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
            )
            await self.session.commit()
            raise AuthError(message_zh="舊密碼錯誤")

        if old_password == new_password:
            raise AuthError(message_zh="新密碼不可與舊密碼相同")

        validate_password(new_password, user_email=user.email)

        if await self.history.is_recent(user.id, new_password):
            raise AuthError(message_zh="新密碼不可與最近 5 次重複")

        new_hash = hash_password(new_password)
        # 先存舊密碼到 history
        await self.history.add(user.id, user.password_hash)
        await self.user_repo.update_password(user.id, new_hash, clear_must_change=True)

        # 撤銷其他 active session（保留當前 jti）
        revoked = await self.session_repo.revoke_all_for_user(
            user.id, except_jti=current_refresh_jti
        )
        now = datetime.now(UTC)
        for s in revoked:
            ttl = max(0, int((s.expires_at - now).total_seconds()))
            await self.blacklist.add(s.jti, ttl)

        await append_audit(
            self.session,
            actor_id=user.id,
            action="auth.password_changed",
            entity_type="user",
            entity_id=str(user.id),
            details={"revoked_other_sessions": len(revoked)},
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
        )
        await self.session.commit()

    # ════════════════ password reset (request) ════════════════

    async def password_reset_request(
        self,
        *,
        email: str,
        ip: str,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> str | None:
        """發起密碼重置。回 plain token（dev/test 直接回；prod 寄信由 P18）。

        為避免 email 列舉，無論 email 是否存在都回相同 envelope。但會限速 3/hr/IP。
        """
        # 限速：3/hr/IP（無論 email 是否存在都計入）
        recent = await self.reset_repo.count_recent_for_ip(ip)
        if recent >= PASSWORD_RESET_RATE_LIMIT:
            raise RateLimitError(
                message_zh=f"密碼重置請求過於頻繁（{PASSWORD_RESET_RATE_LIMIT}/小時）",
                window_hours=PASSWORD_RESET_RATE_WINDOW.total_seconds() / 3600,
            )

        user = await self.user_repo.get_by_email(email)

        if user is None or not user.is_active or user.deleted_at is not None:
            # 仍寫一筆 audit 記錄（含 IP）做限速 + 觀察用
            await append_audit(
                self.session,
                actor_id=None,
                action="auth.password_reset_requested",
                entity_type="user",
                entity_id=email,
                details={"result": "user_not_found_or_inactive"},
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
            )
            await self.session.commit()
            return None

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + PASSWORD_RESET_TOKEN_TTL
        await self.reset_repo.create(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
            ip=ip,
        )

        await append_audit(
            self.session,
            actor_id=user.id,
            action="auth.password_reset_requested",
            entity_type="user",
            entity_id=str(user.id),
            details={"expires_at": expires_at.isoformat()},
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
        )
        await self.session.commit()
        return token

    # ════════════════ password reset (confirm) ════════════════

    async def password_reset_confirm(
        self,
        *,
        token: str,
        new_password: str,
        ip: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """確認重置 — 驗 token、用 + 撤銷所有 session、寫 audit。"""
        record = await self.reset_repo.get_by_token(token)
        if record is None:
            raise AuthError(message_zh="重置連結無效")
        if record.used:
            raise AuthError(message_zh="重置連結已使用過")
        if record.expires_at <= datetime.now(UTC):
            raise AuthError(message_zh="重置連結已過期")

        user = await self.user_repo.get_by_id(record.user_id)
        if user is None or not user.is_active or user.deleted_at is not None:
            raise AuthError(message_zh="帳號已停用")

        validate_password(new_password, user_email=user.email)
        if await self.history.is_recent(user.id, new_password):
            raise AuthError(message_zh="新密碼不可與最近 5 次重複")

        new_hash = hash_password(new_password)
        await self.history.add(user.id, user.password_hash)
        await self.user_repo.update_password(user.id, new_hash, clear_must_change=True)

        # 一次性：mark used
        await self.reset_repo.mark_used(record)

        # 撤銷該 user 全部 session
        revoked = await self.session_repo.revoke_all_for_user(user.id)
        now = datetime.now(UTC)
        for s in revoked:
            ttl = max(0, int((s.expires_at - now).total_seconds()))
            await self.blacklist.add(s.jti, ttl)

        await append_audit(
            self.session,
            actor_id=user.id,
            action="auth.password_reset_confirmed",
            entity_type="user",
            entity_id=str(user.id),
            details={"revoked_sessions": len(revoked)},
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
        )
        await self.session.commit()


__all__ = [
    "AuthService",
    "LoginResult",
    "RefreshResult",
]
