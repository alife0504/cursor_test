"""Phase 11 — NotificationService：settings + 測試發送 + log。

依 PLAN.md 第 19.4 章 secret 加密 + 第 20.x。

注意：實際發送 (LINE / Telegram) 在 P14+ 才接，本 service 只負責：
- settings CRUD（line_token 進 DB 前 Fernet 加密）
- test：寫一筆 NotificationLog（不真打）
- list_logs
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.crypto import decrypt_str, encrypt_str, mask_token
from app.core.errors import ValidationError
from app.repos.audit_repo import AuditRepository
from app.repos.notification_repo import NotificationRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.notification import NotificationLog, NotificationSetting
    from app.models.user import User


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NotificationRepository(session)
        self.audit_repo = AuditRepository(session)

    async def get_settings(self, user: User) -> NotificationSetting | None:
        return await self.repo.get_settings(user.id)

    async def update_settings(
        self,
        user: User,
        *,
        patch: dict[str, Any],
        request_id: str | None = None,
    ) -> NotificationSetting:
        """部分更新；line_token / telegram_bot_token 進 DB 前先 Fernet 加密。

        - line_token / telegram_bot_token=None → 不變
        - line_token / telegram_bot_token="" → 清空
        - 其他值 → 加密寫入對應 *_encrypted 欄位
        """
        normalized: dict[str, Any] = {}
        for k, v in patch.items():
            if k == "line_token":
                if v is None:
                    continue
                if v == "":
                    normalized["line_token_encrypted"] = None
                else:
                    normalized["line_token_encrypted"] = encrypt_str(v)
            elif k == "telegram_bot_token":
                if v is None:
                    continue
                if v == "":
                    normalized["telegram_bot_token_encrypted"] = None
                else:
                    normalized["telegram_bot_token_encrypted"] = encrypt_str(v)
            else:
                if v is not None:
                    normalized[k] = v

        row = await self.repo.upsert_settings(user.id, patch=normalized)
        await self.audit_repo.append(
            actor_id=user.id,
            action="notification.settings.updated",
            entity_type="notification_setting",
            entity_id=str(row.id),
            details={"fields": sorted(normalized.keys())},
            request_id=request_id,
        )
        await self.session.commit()
        return row

    async def send_test(
        self,
        user: User,
        *,
        channel: str,
        message: str,
        dry_run: bool = True,
        request_id: str | None = None,
    ) -> NotificationLog:
        """測試發送。

        dry_run=True（預設）：只驗 credentials 可解密 → 寫 log，不真打外部。
        dry_run=False：透過 dispatcher 真打 LINE / Telegram。

        失敗時寫 failed + 中文錯誤訊息。
        """
        from app.notifications import NotifyEvent, NotifyLevel, get_dispatcher

        settings = await self.repo.get_settings(user.id)
        status = "queued"
        error_msg: str | None = None
        if channel == "line":
            token_enc = getattr(settings, "line_token_encrypted", None) if settings else None
            if not token_enc:
                status = "failed"
                error_msg = "尚未設定 LINE token"
            else:
                try:
                    decrypt_str(token_enc)
                    status = "sent" if dry_run else "queued"
                except ValidationError as e:
                    status = "failed"
                    error_msg = e.get_message()
        elif channel == "telegram":
            bot_enc = getattr(settings, "telegram_bot_token_encrypted", None) if settings else None
            chat_id = getattr(settings, "telegram_chat_id", None) if settings else None
            if not bot_enc or not chat_id:
                status = "failed"
                error_msg = "尚未設定 Telegram bot_token 或 chat_id"
            else:
                try:
                    decrypt_str(bot_enc)
                    status = "sent" if dry_run else "queued"
                except ValidationError as e:
                    status = "failed"
                    error_msg = e.get_message()
        elif channel == "email":
            if not (settings and settings.email_enabled):
                status = "failed"
                error_msg = "Email 通知未啟用"
            else:
                status = "sent"
        else:
            status = "failed"
            error_msg = f"不支援的 channel：{channel}"

        # 真打模式：dispatcher 後台送（不影響 audit log）
        if not dry_run and error_msg is None and channel in ("line", "telegram"):
            try:
                dispatcher = get_dispatcher()
                dispatcher.dispatch_in_background(
                    NotifyEvent(
                        event_type="test",
                        user_id=user.id,
                        title="TradingAgents-TW 測試通知",
                        body=message,
                        level=NotifyLevel.INFO,
                        metadata={"trace_id": request_id or "-"},
                    )
                )
            except Exception as exc:
                # dispatcher 啟動失敗不擋 test endpoint；走 log
                error_msg = f"dispatcher 啟動失敗：{type(exc).__name__}"[:300]
                status = "failed"

        log = await self.repo.add_log(
            user_id=user.id,
            channel=channel,
            event_type="test",
            payload={"message": message[:500]},
            status=status,
            error_msg=error_msg,
        )
        await self.audit_repo.append(
            actor_id=user.id,
            action="notification.test",
            entity_type="notification_log",
            entity_id=str(log.id),
            details={"channel": channel, "status": status},
            request_id=request_id,
        )
        await self.session.commit()
        return log

    async def list_logs(
        self,
        user: User,
        *,
        limit: int = 50,
        before_sent_at=None,
    ) -> list[NotificationLog]:
        user_filter: UUID | None = None if user.role.upper() == "ADMIN" else user.id
        return await self.repo.list_logs(
            user_id=user_filter,
            limit=limit,
            before_sent_at=before_sent_at,
        )

    # ── 給 router 用：把 ORM 物件序列化成 response，遮蔽 token ──
    @staticmethod
    def serialize_settings(row: NotificationSetting | None, user_id: UUID) -> dict[str, Any]:
        """轉 ORM → response dict（line_token / telegram_bot_token 永遠遮蔽）。

        P18：新增 line_token_set / telegram_bot_token_set 旗標，方便前端判斷
        「已設定」與否，不需顯示真實 token。
        """
        if row is None:
            return {
                "user_id": str(user_id),
                "line_token_masked": None,
                "line_token_set": False,
                "telegram_bot_token_set": False,
                "telegram_chat_id": None,
                "email_enabled": False,
                "enabled_channels": None,
                "enabled_events": None,
                "quiet_hours_start": None,
                "quiet_hours_end": None,
                "updated_at": None,
            }
        return {
            "user_id": str(row.user_id),
            "line_token_masked": mask_token(row.line_token_encrypted),
            "line_token_set": bool(row.line_token_encrypted),
            "telegram_bot_token_set": bool(row.telegram_bot_token_encrypted),
            "telegram_chat_id": row.telegram_chat_id,
            "email_enabled": bool(row.email_enabled),
            "enabled_channels": row.enabled_channels,
            "enabled_events": row.enabled_events,
            "quiet_hours_start": row.quiet_hours_start,
            "quiet_hours_end": row.quiet_hours_end,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


__all__ = ["NotificationService"]
