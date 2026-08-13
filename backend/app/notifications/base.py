"""Phase 18 — Notifier 基底 + Registry + Event/Result DTO。

設計（PLAN 第 18.2 / 19.4 / 第二十七章 Phase 18 章節 B）：
- BaseNotifier：所有通知器抽象基底；持有「明文 credentials」+ httpx async client
- NOTIFIER_REGISTRY：name → class 的 plugin 註冊表
- NotifyEvent：dispatcher 餵給 notifier 的標準 DTO
- NotifyResult：notifier 回傳結果（成功 / 失敗 + 細節，給 log/audit 用）
- 信用度：notifier 內部不解密；解密由 dispatcher 統一在外層做，再用 from_credentials 建出實例
  → 加密 key 不會擴散到太多地方（PLAN 第 19.4 章：DATA_ENCRYPTION_KEY 與 SECRET_KEY 分離）

ClassVar[str] 是慣例：name = "line" / "telegram"，dispatcher 依此查表。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar
from uuid import UUID

import httpx


class NotifyLevel(StrEnum):
    """事件嚴重程度 — 影響 emoji 與 quiet-hours 行為。

    INFO：日常通知（分析完成）
    SUCCESS：好消息（訂單核准）
    WARN：注意（quota 80%、CB OPEN 試恢復）
    CRITICAL：必須立即處理（CB OPEN、quota 100%、audit chain broken）
        → quiet hours 仍會發送
    """

    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


@dataclass
class NotifyEvent:
    """dispatcher 接收的事件 DTO（領域事件 → 通知）。

    event_type：標準命名，與 schemas/notifications.ALLOWED_EVENTS 一致。
    user_id：None = 系統廣播（給所有訂閱的人）；非 None = 該 user 專屬。
    title / body：使用者看到的中文訊息（已格式化好）。
    level：影響 emoji + quiet-hours bypass。
    metadata：額外資料（trace_id、symbol、cost、breaker_name 等），不會直接顯示。
    """

    event_type: str
    title: str
    body: str
    user_id: UUID | None = None
    level: NotifyLevel = NotifyLevel.INFO
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotifyResult:
    """notifier 回傳的結果。

    success：是否成功送達
    status_code：HTTP 回應碼（無則 None）
    response_excerpt：response body 前 200 字（log/audit 用，遮蔽過）
    error：失敗訊息（中文 + 英文 exception class），最多 500 字
    """

    success: bool
    status_code: int | None = None
    response_excerpt: str | None = None
    error: str | None = None


class BaseNotifier(abc.ABC):
    """所有通知器的抽象基底。

    子類別必須宣告 ClassVar[str] name / display_name_zh，並用 @register_notifier 註冊。
    """

    name: ClassVar[str]
    display_name_zh: ClassVar[str]
    # 各 channel 訊息長度上限（截斷用）
    max_message_length: ClassVar[int] = 1000

    def __init__(
        self,
        credentials: dict[str, Any],
        *,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """credentials 已是「明文」dict（dispatcher 解密後傳入）。

        client：注入 httpx client（測試用）；若 None 則 send() 時建立短連線。
        timeout：HTTP 預設 timeout（秒）。
        """
        self.credentials = credentials
        self.timeout = timeout
        self._injected_client = client

    # ── 給子類別共用：取得 client（context-manager）─────
    def _client(self) -> httpx.AsyncClient:
        """回傳可用的 httpx.AsyncClient；若有注入則直接用。"""
        if self._injected_client is not None:
            return self._injected_client
        return httpx.AsyncClient(timeout=self.timeout)

    # ── 子類別必實作 ─────────────────────────────────
    @abc.abstractmethod
    async def send(
        self,
        title: str,
        body: str,
        level: NotifyLevel = NotifyLevel.INFO,
        metadata: dict[str, Any] | None = None,
    ) -> NotifyResult:
        """送一則通知。實作者必須處理截斷、escape、circuit breaker。"""

    async def health_check(self) -> bool:
        """快速健康檢查 — 預設用 send() 送一則探測訊息。

        子類別可覆寫成更輕量的方式（如 LINE 的 GET /api/status）。
        """
        try:
            r = await self.send(
                "健康檢查",
                "tradingagents-tw probe",
                level=NotifyLevel.INFO,
            )
            return r.success
        except Exception:
            return False

    # ── 工具：擷取 response 內容前 N 字（log 用，去敏感）─
    @staticmethod
    def _excerpt(text: str | bytes | None, *, limit: int = 200) -> str | None:
        if text is None:
            return None
        if isinstance(text, bytes):
            try:
                text = text.decode("utf-8", errors="replace")
            except Exception:
                return None
        return text[:limit]


# ════════════════ Registry ════════════════════════

NOTIFIER_REGISTRY: dict[str, type[BaseNotifier]] = {}


def register_notifier(cls: type[BaseNotifier]) -> type[BaseNotifier]:
    """class decorator：把 notifier 加進 registry。"""
    name = getattr(cls, "name", None)
    if not name:
        raise ValueError(f"{cls.__name__} 必須宣告 ClassVar `name`")
    NOTIFIER_REGISTRY[name] = cls
    return cls


__all__ = [
    "NOTIFIER_REGISTRY",
    "BaseNotifier",
    "NotifyEvent",
    "NotifyLevel",
    "NotifyResult",
    "register_notifier",
]
