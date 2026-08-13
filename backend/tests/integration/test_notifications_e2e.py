"""Phase 18 — Notification dispatcher 端到端整合測試（PLAN 第二十七章 P18 O 節）。

涵蓋：
1. 分析完成事件 → 訂閱用戶收到通知
2. 訂單核准事件 → 訂閱用戶收到通知
3. CB OPEN 事件 → CRITICAL 廣播
4. LLM quota 80% → 收到 WARN
5. 未訂閱該事件 → 不發送
6. notifier 失敗 → 寫入 DLQ

策略：
- 用 httpx.MockTransport 攔截外部 HTTP（不真打 Discord/Telegram）
- 直接呼叫 dispatcher.dispatch（不跑完整 analysis worker）
- 驗收 notification_log + celery_dead_letters DB 狀態

跑：cd backend && uv run pytest tests/integration/test_notifications_e2e.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, select

from app.core.crypto import encrypt_str
from app.models.dlq import CeleryDeadLetter
from app.models.notification import NotificationLog, NotificationSetting
from app.notifications import (
    NotificationDispatcher,
    NotifyEvent,
    NotifyLevel,
)

pytestmark = pytest.mark.integration


# ════════════════════════════════════════════════════════
# helpers
# ════════════════════════════════════════════════════════


def _make_mock_transport(*, succeed: bool = True) -> httpx.MockTransport:
    """httpx MockTransport — succeed=True 回 200，False 回 500。"""

    def handler(request: httpx.Request) -> httpx.Response:
        if succeed:
            if "telegram" in request.url.host:
                return httpx.Response(200, json={"ok": True, "result": {}})
            return httpx.Response(200, json={"status": 200, "message": "ok"})
        return httpx.Response(500, text="internal error (mock)")

    return httpx.MockTransport(handler)


def _make_mock_client(*, succeed: bool = True) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=_make_mock_transport(succeed=succeed), timeout=2.0)


async def _seed_notification_settings(
    db_session_maker,
    user_id: Any,
    *,
    enabled_events: list[str] | None = None,
    enabled_channels: list[str] | None = None,
    with_discord: bool = True,
    with_telegram: bool = False,
) -> None:
    """寫一筆 settings；discord webhook / telegram token 用 encrypt_str 預先加密。"""
    async with db_session_maker() as s:
        existing = (
            await s.execute(
                select(NotificationSetting).where(NotificationSetting.user_id == user_id)
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = NotificationSetting(user_id=user_id)
            s.add(existing)
        if with_discord:
            existing.discord_webhook_encrypted = encrypt_str(
                "https://discord.com/api/webhooks/123456789/FAKE_DISCORD_WEBHOOK_TOKEN"
            )
        if with_telegram:
            existing.telegram_bot_token_encrypted = encrypt_str("99:FAKE_BOT_TOKEN")
            existing.telegram_chat_id = "-1001234567890"
        existing.enabled_events = enabled_events
        existing.enabled_channels = enabled_channels
        await s.commit()


async def _cleanup_for_user(db_session_maker, user_id) -> None:
    async with db_session_maker() as s:
        await s.execute(delete(NotificationLog).where(NotificationLog.user_id == user_id))
        await s.execute(delete(NotificationSetting).where(NotificationSetting.user_id == user_id))
        await s.commit()


async def _wait_for_logs(db_session_maker, user_id, *, min_count: int, timeout: float = 3.0):
    """polling 等 NotificationLog 寫進 DB。"""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        async with db_session_maker() as s:
            rows = list(
                (await s.execute(select(NotificationLog).where(NotificationLog.user_id == user_id)))
                .scalars()
                .all()
            )
        if len(rows) >= min_count:
            return rows
        await asyncio.sleep(0.1)
    return rows


# ════════════════════════════════════════════════════════
# 1. analysis.completed → 訂閱 user 收到
# ════════════════════════════════════════════════════════


async def test_analysis_completed_dispatches_to_subscriber(
    make_test_user, db_session_maker
) -> None:
    user, _ = await make_test_user(role="VIEWER", must_change=False)
    await _seed_notification_settings(
        db_session_maker, user.id, enabled_events=["analysis.completed"]
    )

    mock_client = _make_mock_client(succeed=True)
    dispatcher = NotificationDispatcher(http_client=mock_client)
    try:
        results = await dispatcher.dispatch(
            NotifyEvent(
                event_type="analysis.completed",
                user_id=user.id,
                title="分析完成 — 2330",
                body="action=BUY confidence=0.78",
                level=NotifyLevel.SUCCESS,
                metadata={"trace_id": "abc", "symbol": "2330"},
            )
        )
        assert len(results) == 1
        assert results[0].success is True

        logs = await _wait_for_logs(db_session_maker, user.id, min_count=1)
        assert len(logs) >= 1
        assert logs[0].status == "sent"
        assert logs[0].event_type == "analysis.completed"
        assert logs[0].channel == "discord"
    finally:
        await mock_client.aclose()
        await _cleanup_for_user(db_session_maker, user.id)


# ════════════════════════════════════════════════════════
# 2. order.approved → 收到
# ════════════════════════════════════════════════════════


async def test_order_approved_dispatches(make_test_user, db_session_maker) -> None:
    user, _ = await make_test_user(role="VIEWER", must_change=False)
    await _seed_notification_settings(db_session_maker, user.id, enabled_events=["order.approved"])
    mock_client = _make_mock_client(succeed=True)
    dispatcher = NotificationDispatcher(http_client=mock_client)
    try:
        results = await dispatcher.dispatch(
            NotifyEvent(
                event_type="order.approved",
                user_id=user.id,
                title="訂單已核准 — 2330 BUY 100",
                body="reviewer=admin@example.com",
                level=NotifyLevel.SUCCESS,
            )
        )
        assert results[0].success is True
        logs = await _wait_for_logs(db_session_maker, user.id, min_count=1)
        assert logs[0].status == "sent"
    finally:
        await mock_client.aclose()
        await _cleanup_for_user(db_session_maker, user.id)


# ════════════════════════════════════════════════════════
# 3. CB OPEN → CRITICAL 廣播（user_id=None）
# ════════════════════════════════════════════════════════


async def test_cb_open_dispatches_critical(make_test_user, db_session_maker) -> None:
    user, _ = await make_test_user(role="ADMIN", must_change=False)
    await _seed_notification_settings(
        db_session_maker,
        user.id,
        enabled_events=["system.alert"],
    )
    mock_client = _make_mock_client(succeed=True)
    dispatcher = NotificationDispatcher(http_client=mock_client)
    try:
        results = await dispatcher.dispatch(
            NotifyEvent(
                event_type="system.alert",
                user_id=None,  # 系統廣播
                title="🚨 CB OPEN — finmind",
                body="failure_count=5 threshold=5",
                level=NotifyLevel.CRITICAL,
                metadata={"breaker_name": "finmind"},
            )
        )
        # 廣播應有至少 1 個 target（這個 admin）
        assert len(results) >= 1
        logs = await _wait_for_logs(db_session_maker, user.id, min_count=1)
        assert any(log.event_type == "system.alert" for log in logs)
    finally:
        await mock_client.aclose()
        await _cleanup_for_user(db_session_maker, user.id)


# ════════════════════════════════════════════════════════
# 4. LLM quota 80% → WARN
# ════════════════════════════════════════════════════════


async def test_llm_quota_80_dispatches_warning(make_test_user, db_session_maker) -> None:
    user, _ = await make_test_user(role="VIEWER", must_change=False)
    await _seed_notification_settings(db_session_maker, user.id, enabled_events=["system.alert"])
    mock_client = _make_mock_client(succeed=True)
    dispatcher = NotificationDispatcher(http_client=mock_client)
    try:
        results = await dispatcher.dispatch(
            NotifyEvent(
                event_type="system.alert",
                user_id=user.id,
                title="⚠️ LLM 月配額已達 80%",
                body="used=$40.00 / limit=$50.00",
                level=NotifyLevel.WARN,
                metadata={"quota_kind": "warning_80pct"},
            )
        )
        assert results[0].success is True
        logs = await _wait_for_logs(db_session_maker, user.id, min_count=1)
        assert logs[0].status == "sent"
    finally:
        await mock_client.aclose()
        await _cleanup_for_user(db_session_maker, user.id)


# ════════════════════════════════════════════════════════
# 5. 未訂閱該事件 → 不發送
# ════════════════════════════════════════════════════════


async def test_user_unsubscribed_event_not_sent(make_test_user, db_session_maker) -> None:
    user, _ = await make_test_user(role="VIEWER", must_change=False)
    # 只訂閱 analysis.completed，不訂閱 order.approved
    await _seed_notification_settings(
        db_session_maker, user.id, enabled_events=["analysis.completed"]
    )
    mock_client = _make_mock_client(succeed=True)
    dispatcher = NotificationDispatcher(http_client=mock_client)
    try:
        results = await dispatcher.dispatch(
            NotifyEvent(
                event_type="order.approved",  # 未訂閱
                user_id=user.id,
                title="不該收到",
                body="...",
                level=NotifyLevel.SUCCESS,
            )
        )
        assert results == []
        # log 應該為空
        async with db_session_maker() as s:
            logs = list(
                (await s.execute(select(NotificationLog).where(NotificationLog.user_id == user.id)))
                .scalars()
                .all()
            )
        assert len(logs) == 0
    finally:
        await mock_client.aclose()
        await _cleanup_for_user(db_session_maker, user.id)


# ════════════════════════════════════════════════════════
# 6. notifier 失敗 → 寫 DLQ
# ════════════════════════════════════════════════════════


async def test_notification_failure_writes_dlq(make_test_user, db_session_maker) -> None:
    user, _ = await make_test_user(role="VIEWER", must_change=False)
    await _seed_notification_settings(
        db_session_maker, user.id, enabled_events=["analysis.completed"]
    )
    # 用 succeed=False 的 mock client → Discord 回 500 → notifier 回 NotifyResult(success=False)
    mock_client = _make_mock_client(succeed=False)
    dispatcher = NotificationDispatcher(http_client=mock_client)
    try:
        results = await dispatcher.dispatch(
            NotifyEvent(
                event_type="analysis.completed",
                user_id=user.id,
                title="分析完成 — 2330",
                body="...",
                level=NotifyLevel.SUCCESS,
            )
        )
        assert results[0].success is False

        logs = await _wait_for_logs(db_session_maker, user.id, min_count=1)
        assert logs[0].status == "failed"
        assert logs[0].error_msg is not None

        # DLQ 應該有一筆 task_name='notify'
        async with db_session_maker() as s:
            dlq_rows = list(
                (
                    await s.execute(
                        select(CeleryDeadLetter).where(CeleryDeadLetter.task_name == "notify")
                    )
                )
                .scalars()
                .all()
            )
        assert len(dlq_rows) >= 1
        # 清掉
        async with db_session_maker() as s:
            await s.execute(delete(CeleryDeadLetter).where(CeleryDeadLetter.task_name == "notify"))
            await s.commit()
    finally:
        await mock_client.aclose()
        await _cleanup_for_user(db_session_maker, user.id)
