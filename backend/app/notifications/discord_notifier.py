"""Discord Webhook Adapter — 取代已停服的 LINE Notify。

Discord Webhook API：
- POST {webhook_url}（webhook URL 本身即含 id/token，無需額外 Authorization header）
- Body (JSON): {"content": "<text>", "username": "..."}；content 最長 2000 字
- 成功回傳 204 No Content（帶 ?wait=true 時為 200）

credentials 欄位：
    {"webhook_url": "https://discord.com/api/webhooks/<id>/<token>"}

備註：LINE Notify 已於 2025/03 官方停止服務，故以 Discord Webhook 取代——
免 OAuth、個人在頻道設定即可建立 webhook，與既有 plugin 介面完全相容。
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

# 合法的 Discord Webhook 網址前綴（含 canary / ptb 與舊網域 discordapp.com）
_VALID_PREFIXES = (
    "https://discord.com/api/webhooks/",
    "https://discordapp.com/api/webhooks/",
    "https://canary.discord.com/api/webhooks/",
    "https://ptb.discord.com/api/webhooks/",
)


@register_notifier
class DiscordNotifier(BaseNotifier):
    """Discord Webhook。"""

    name = "discord"
    display_name_zh = "Discord"
    max_message_length = 2000  # Discord content 上限
    username = "TradingAgents-TW"

    def _validate_credentials(self) -> str:
        url = self.credentials.get("webhook_url") or self.credentials.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("Discord notifier 缺少 'webhook_url' credentials")
        url = url.strip()
        if not url.startswith(_VALID_PREFIXES):
            raise ValueError("webhook_url 不是合法的 Discord Webhook 網址")
        return url

    def _format_message(
        self,
        title: str,
        body: str,
        level: NotifyLevel,
        metadata: dict[str, Any] | None,
    ) -> str:
        emoji = LEVEL_EMOJI.get(level, "ℹ️")
        message = f"{emoji} **{title}**\n\n{body}"
        if metadata:
            trace_id = metadata.get("trace_id")
            if trace_id:
                message += f"\n\n`trace_id: {trace_id}`"
        return message[: self.max_message_length]

    async def send(
        self,
        title: str,
        body: str,
        level: NotifyLevel = NotifyLevel.INFO,
        metadata: dict[str, Any] | None = None,
    ) -> NotifyResult:
        webhook_url = self._validate_credentials()
        content = self._format_message(title, body, level, metadata)
        payload = {"content": content, "username": self.username}

        try:
            if self._injected_client is not None:
                resp = await self._injected_client.post(webhook_url, json=payload)
            else:
                # 短連線，避免長住 socket
                async with self._client() as client:
                    resp = await client.post(webhook_url, json=payload)

            text = resp.text if hasattr(resp, "text") else ""
            # Discord 成功回 204（無 body）；帶 ?wait=true 時 200
            ok = resp.status_code in (200, 204)
            return NotifyResult(
                success=ok,
                status_code=resp.status_code,
                response_excerpt=self._excerpt(text),
                error=None if ok else f"Discord Webhook 回應 HTTP {resp.status_code}",
            )
        except Exception as exc:
            logger.warning("DiscordNotifier.send.failed error=%s", exc)
            return NotifyResult(
                success=False,
                status_code=None,
                response_excerpt=None,
                error=f"Discord 發送失敗：{type(exc).__name__}: {exc!s}"[:500],
            )


__all__ = ["LEVEL_EMOJI", "DiscordNotifier"]
