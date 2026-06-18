"""Phase 18 — 通知 Adapter 套件（PLAN 第 18.2 / 第二十七章 Phase 18）。

公開元件：
- BaseNotifier：所有通知器的抽象基底
- NOTIFIER_REGISTRY / register_notifier：plugin pattern 註冊表
- NotifyEvent / NotifyResult：dispatcher 與 notifier 間的 DTO
- DiscordNotifier / TelegramNotifier：兩個內建 adapter（LINE Notify 已停服，改 Discord Webhook）
- NotificationDispatcher：依用戶 settings 過濾、發送、失敗 DLQ
"""

from __future__ import annotations

from app.notifications.base import (
    NOTIFIER_REGISTRY,
    BaseNotifier,
    NotifyEvent,
    NotifyLevel,
    NotifyResult,
    register_notifier,
)
from app.notifications.discord_notifier import DiscordNotifier
from app.notifications.dispatcher import NotificationDispatcher, get_dispatcher
from app.notifications.telegram_notifier import TelegramNotifier

__all__ = [
    "NOTIFIER_REGISTRY",
    "BaseNotifier",
    "DiscordNotifier",
    "NotificationDispatcher",
    "NotifyEvent",
    "NotifyLevel",
    "NotifyResult",
    "TelegramNotifier",
    "get_dispatcher",
    "register_notifier",
]
