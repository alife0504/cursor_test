"""Phase 18 — LINE Notify Adapter（PLAN 第二十七章 Phase 18 C 節）。

LINE Notify API：
- POST https://notify-api.line.me/api/notify
- Header: Authorization: Bearer {token}
- Body (form): message=<text>，最長 1000 字
- 回傳 200 {"status":200,"message":"ok"}；超過配額 200/429 視 LINE 而定

注意（v7.0 補）：
- LINE Notify 服務在 2025/04 已被官方標示為棄用；本實作仍照 PLAN 介面寫，
  方便：(1) 既有 token 仍可用一段時間；(2) 之後改 LINE Messaging API 只要新增一個
  notifier class，不影響 dispatcher。
- 真打測試需 user 自備 token；自動化測試用 httpx mock transport（pytest-httpx）。

credentials 欄位：
    {"token": "<LINE_NOTIFY_ACCESS_TOKEN>"}
"""

from __future__ import annotations

import logging
from typing import Any

from app.notifications.base import (
    BaseNotifier,
    NotifyLevel,
    NotifyResult,
    register_notifier,
)

logger = logging.getLogger(__name__)

LEVEL_EMOJI: dict[NotifyLevel, str] = {
    NotifyLevel.INFO: "ℹ️",
    NotifyLevel.SUCCESS: "✅",
    NotifyLevel.WARN: "⚠️",
    NotifyLevel.CRITICAL: "🚨",
}


@register_notifier
class LINENotifier(BaseNotifier):
    """LINE Notify。"""

    name = "line"
    display_name_zh = "LINE Notify"
    BASE_URL = "https://notify-api.line.me/api/notify"
    max_message_length = 1000

    def _validate_credentials(self) -> str:
        token = self.credentials.get("token") or self.credentials.get("line_token")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("LINE notifier 缺少 'token' credentials")
        return token

    def _format_message(
        self,
        title: str,
        body: str,
        level: NotifyLevel,
        metadata: dict[str, Any] | None,
    ) -> str:
        emoji = LEVEL_EMOJI.get(level, "ℹ️")
        message = f"{emoji} {title}\n\n{body}"
        if metadata:
            trace_id = metadata.get("trace_id")
            if trace_id:
                message += f"\n\n[trace_id: {trace_id}]"
        return message[: self.max_message_length]

    async def send(
        self,
        title: str,
        body: str,
        level: NotifyLevel = NotifyLevel.INFO,
        metadata: dict[str, Any] | None = None,
    ) -> NotifyResult:
        token = self._validate_credentials()
        message = self._format_message(title, body, level, metadata)

        headers = {"Authorization": f"Bearer {token}"}
        data = {"message": message}

        try:
            if self._injected_client is not None:
                resp = await self._injected_client.post(
                    self.BASE_URL,
                    headers=headers,
                    data=data,
                )
            else:
                # 短連線，避免長住 socket
                async with self._client() as client:
                    resp = await client.post(self.BASE_URL, headers=headers, data=data)

            text = resp.text if hasattr(resp, "text") else ""
            ok = resp.status_code == 200
            return NotifyResult(
                success=ok,
                status_code=resp.status_code,
                response_excerpt=self._excerpt(text),
                error=None if ok else f"LINE Notify 回應 HTTP {resp.status_code}",
            )
        except Exception as exc:
            logger.warning("LINENotifier.send.failed error=%s", exc)
            return NotifyResult(
                success=False,
                status_code=None,
                response_excerpt=None,
                error=f"LINE 發送失敗：{type(exc).__name__}: {exc!s}"[:500],
            )


__all__ = ["LEVEL_EMOJI", "LINENotifier"]
