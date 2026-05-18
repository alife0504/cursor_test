"""Phase 18 — NotificationDispatcher（PLAN 第二十七章 Phase 18 E 節）。

設計目標：
- 一個 dispatch(event) 方法接受 NotifyEvent → 解析所有 target user/channel → 並行送
- 任一通道失敗：寫 notification_log(status='failed') + 寫 celery_dead_letters
- 不卡業務：FastAPI 端用 fire-and-forget（asyncio.create_task）；Celery 端用 dispatch_sync
- 加密欄位（line_token / telegram_bot_token）解密在 dispatcher 內統一處理（notifier 不碰）
- quiet hours：CRITICAL 仍發送；其他 level 在靜音時段內跳過

target 過濾邏輯：
- event.user_id != None → 只送給該 user
- event.user_id is None（系統廣播）→ 送給「訂閱了 event.event_type 的所有用戶」
- 該 user 的 enabled_events 為空 / None → 等同「全訂閱」
- 該 user 的 enabled_channels 為空 / None → 等同「全 channel 都送」
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from app.core.crypto import decrypt_str
from app.core.database import sync_rw_session
from app.models.dlq import CeleryDeadLetter
from app.models.notification import NotificationLog, NotificationSetting
from app.notifications.base import (
    NOTIFIER_REGISTRY,
    BaseNotifier,
    NotifyEvent,
    NotifyLevel,
    NotifyResult,
)

logger = logging.getLogger(__name__)


@dataclass
class _ResolvedTarget:
    """解析出來的單一發送目標。"""

    user_id: UUID
    notifier_name: str
    credentials: dict[str, Any]
    quiet_hours_start: str | None
    quiet_hours_end: str | None


def _parse_hhmm(s: str | None) -> time | None:
    if not s or len(s) != 5 or s[2] != ":":
        return None
    try:
        hh, mm = int(s[:2]), int(s[3:])
    except ValueError:
        return None
    if not (0 <= hh < 24 and 0 <= mm < 60):
        return None
    return time(hh, mm)


def _in_quiet_hours(now: time, start: time, end: time) -> bool:
    """[start, end) 區間判定，跨午夜也支援（如 22:00→07:00）。"""
    if start <= end:
        return start <= now < end
    return now >= start or now < end


class NotificationDispatcher:
    """事件 → 通知 分派器。

    主介面：
        await dispatch(event)        # async 場景
        dispatch_sync(event)          # sync 場景（celery）
        dispatch_in_background(event) # FastAPI 端 fire-and-forget

    依賴：
        sync_rw_session   — 讀 settings / 寫 log / 寫 DLQ（一致 sync 介面）
        DATA_ENCRYPTION_KEY — 透過 app.core.crypto 解密
        NOTIFIER_REGISTRY — line / telegram 兩個 plugin
    """

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
        clock: Any = None,
    ) -> None:
        """http_client：注入點（測試用）；不注入則每次 send 開短連線。

        clock：時間源（測試用 quiet hours）；不注入則用 datetime.now()。
        """
        self._client = http_client
        self._clock = clock or datetime.now

    # ════════════════ 公開 API ════════════════════════
    async def dispatch(self, event: NotifyEvent) -> list[NotifyResult]:
        """async 主入口。

        - 先在 thread 中查 DB（避免 block event loop）
        - 並行送到所有 target
        - log / DLQ 寫入也走 thread
        """
        targets = await asyncio.to_thread(self._resolve_targets, event)
        if not targets:
            return []

        return await asyncio.gather(
            *(self._send_one(t, event) for t in targets),
            return_exceptions=False,
        )

    def dispatch_sync(self, event: NotifyEvent) -> list[NotifyResult]:
        """sync 入口（celery worker / signal handler 用）。"""
        try:
            return asyncio.run(self.dispatch(event))
        except RuntimeError as exc:
            # 已在 event loop 中？不可能在 celery worker 發生，但 defensive
            logger.warning("NotificationDispatcher.dispatch_sync.loop_conflict error=%s", exc)
            return []

    def dispatch_in_background(self, event: NotifyEvent) -> asyncio.Task | None:
        """FastAPI 端用 — fire-and-forget。

        必須在 event loop 內呼叫。回傳 task；caller 通常不 await。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("dispatch_in_background.no_loop event=%s", event.event_type)
            return None
        return loop.create_task(self._dispatch_with_isolation(event))

    async def _dispatch_with_isolation(self, event: NotifyEvent) -> None:
        """fire-and-forget wrapper：抓住所有例外，避免污染主流程。"""
        try:
            await self.dispatch(event)
        except Exception as exc:
            logger.warning(
                "NotificationDispatcher.background.failed event=%s error=%s",
                event.event_type,
                exc,
            )

    # ════════════════ Target Resolution ═══════════════
    def _resolve_targets(self, event: NotifyEvent) -> list[_ResolvedTarget]:
        """從 DB 找出該收這個 event 的人 + 他們的 notifier credentials。"""
        resolved: list[_ResolvedTarget] = []
        with sync_rw_session() as s:
            stmt = select(NotificationSetting)
            if event.user_id is not None:
                stmt = stmt.where(NotificationSetting.user_id == event.user_id)
            rows = list(s.execute(stmt).scalars().all())

        for row in rows:
            if not self._user_subscribed(row, event):
                continue
            if self._in_quiet_hours_now(row) and event.level != NotifyLevel.CRITICAL:
                # 靜音時段內，跳過非 CRITICAL
                continue
            for target in self._build_targets_for_row(row):
                resolved.append(target)
        return resolved

    def _user_subscribed(self, row: NotificationSetting, event: NotifyEvent) -> bool:
        events = row.enabled_events
        if events is None or len(events) == 0:
            # 預設全訂閱
            return True
        return event.event_type in events

    def _in_quiet_hours_now(self, row: NotificationSetting) -> bool:
        start = _parse_hhmm(row.quiet_hours_start)
        end = _parse_hhmm(row.quiet_hours_end)
        if start is None or end is None:
            return False
        now = (
            self._clock().timetz().replace(tzinfo=None)
            if hasattr(self._clock(), "timetz")
            else self._clock().time()
        )
        return _in_quiet_hours(now, start, end)

    def _build_targets_for_row(
        self,
        row: NotificationSetting,
    ) -> list[_ResolvedTarget]:
        """把 settings row 拆成 (user, notifier, creds) 多筆。"""
        out: list[_ResolvedTarget] = []
        enabled = row.enabled_channels
        wanted = set(enabled) if enabled else None  # None = all

        # LINE
        if (wanted is None or "line" in wanted) and row.line_token_encrypted:
            try:
                token = decrypt_str(row.line_token_encrypted)
                out.append(
                    _ResolvedTarget(
                        user_id=row.user_id,
                        notifier_name="line",
                        credentials={"token": token},
                        quiet_hours_start=row.quiet_hours_start,
                        quiet_hours_end=row.quiet_hours_end,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "NotificationDispatcher.decrypt.line_failed user=%s error=%s",
                    row.user_id,
                    exc,
                )

        # Telegram
        if (
            (wanted is None or "telegram" in wanted)
            and row.telegram_bot_token_encrypted
            and row.telegram_chat_id
        ):
            try:
                bot_token = decrypt_str(row.telegram_bot_token_encrypted)
                out.append(
                    _ResolvedTarget(
                        user_id=row.user_id,
                        notifier_name="telegram",
                        credentials={
                            "bot_token": bot_token,
                            "chat_id": row.telegram_chat_id,
                        },
                        quiet_hours_start=row.quiet_hours_start,
                        quiet_hours_end=row.quiet_hours_end,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "NotificationDispatcher.decrypt.telegram_failed user=%s error=%s",
                    row.user_id,
                    exc,
                )

        return out

    # ════════════════ Send + Log ══════════════════════
    async def _send_one(
        self,
        target: _ResolvedTarget,
        event: NotifyEvent,
    ) -> NotifyResult:
        cls = NOTIFIER_REGISTRY.get(target.notifier_name)
        if cls is None:
            err = f"未知 notifier：{target.notifier_name}"
            logger.warning("NotificationDispatcher.unknown_notifier name=%s", target.notifier_name)
            await asyncio.to_thread(self._log_failure, target, event, err)
            return NotifyResult(success=False, error=err)

        notifier: BaseNotifier = cls(target.credentials, client=self._client)
        try:
            result = await notifier.send(
                event.title,
                event.body,
                level=event.level,
                metadata=event.metadata,
            )
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc!s}"[:500]
            logger.warning(
                "NotificationDispatcher.send_one.exception notifier=%s error=%s",
                target.notifier_name,
                exc,
            )
            await asyncio.to_thread(self._log_failure, target, event, err)
            await asyncio.to_thread(self._enqueue_dlq, target, event, err)
            return NotifyResult(success=False, error=err)

        if result.success:
            await asyncio.to_thread(self._log_success, target, event, result)
        else:
            await asyncio.to_thread(self._log_failure, target, event, result.error or "未知錯誤")
            await asyncio.to_thread(self._enqueue_dlq, target, event, result.error or "")
        return result

    # ── DB writes (sync) ─────────────────────────────
    @staticmethod
    def _redact_credentials_in_payload(event: NotifyEvent) -> dict[str, Any]:
        """寫 log 時的 payload — title/body 截斷，metadata 去敏感欄位。"""
        meta = dict(event.metadata or {})
        for k in list(meta.keys()):
            kl = k.lower()
            if any(s in kl for s in ("token", "password", "secret", "authorization", "cookie")):
                meta[k] = "***"
        return {
            "title": (event.title or "")[:200],
            "body": (event.body or "")[:500],
            "level": event.level.value
            if isinstance(event.level, NotifyLevel)
            else str(event.level),
            "metadata": meta,
        }

    def _log_success(
        self,
        target: _ResolvedTarget,
        event: NotifyEvent,
        result: NotifyResult,
    ) -> None:
        with sync_rw_session() as s:
            log = NotificationLog(
                user_id=target.user_id,
                channel=target.notifier_name,
                event_type=event.event_type,
                payload=self._redact_credentials_in_payload(event),
                status="sent",
                error_msg=None,
            )
            s.add(log)
            s.commit()

    def _log_failure(
        self,
        target: _ResolvedTarget,
        event: NotifyEvent,
        error: str,
    ) -> None:
        with sync_rw_session() as s:
            log = NotificationLog(
                user_id=target.user_id,
                channel=target.notifier_name,
                event_type=event.event_type,
                payload=self._redact_credentials_in_payload(event),
                status="failed",
                error_msg=(error or "")[:1000],
            )
            s.add(log)
            s.commit()

    def _enqueue_dlq(
        self,
        target: _ResolvedTarget,
        event: NotifyEvent,
        error: str,
    ) -> None:
        """通知失敗 → 寫 celery_dead_letters（task_name='notify'）。

        DLQ 寫入本身失敗：log 但不 raise（PLAN 已知陷阱）。
        """
        try:
            with sync_rw_session() as s:
                dlq = CeleryDeadLetter(
                    task_name="notify",
                    args=[event.event_type, target.notifier_name, str(target.user_id)],
                    kwargs={
                        "payload": self._redact_credentials_in_payload(event),
                    },
                    exception_type="NotifyError",
                    exception=(error or "")[:2000],
                    traceback=None,
                    retry_count=0,
                    resolved=False,
                )
                s.add(dlq)
                s.commit()
        except Exception as exc:
            logger.warning(
                "NotificationDispatcher.enqueue_dlq.write_failed error=%s",
                exc,
            )


# ════════════════ Module singleton ════════════════════
_DEFAULT_DISPATCHER: NotificationDispatcher | None = None


def get_dispatcher() -> NotificationDispatcher:
    """取得 process-level 共用 dispatcher。"""
    global _DEFAULT_DISPATCHER
    if _DEFAULT_DISPATCHER is None:
        _DEFAULT_DISPATCHER = NotificationDispatcher()
    return _DEFAULT_DISPATCHER


def set_dispatcher_for_test(dispatcher: NotificationDispatcher | None) -> None:
    """測試用：替換全域 dispatcher（傳 None 復原）。"""
    global _DEFAULT_DISPATCHER
    _DEFAULT_DISPATCHER = dispatcher


__all__ = [
    "NotificationDispatcher",
    "get_dispatcher",
    "set_dispatcher_for_test",
]
