"""Phase 18 — Telegram Bot Adapter（PLAN 第二十七章 Phase 18 D 節）。

Telegram Bot API：
- POST https://api.telegram.org/bot<TOKEN>/sendMessage
- Body (JSON): {"chat_id": "...", "text": "...", "parse_mode": "MarkdownV2"}
- 回傳 200 {"ok":true,"result":{...}}；錯誤 400/401/403/429

MarkdownV2 特殊字元 escape（PLAN「已知陷阱」）：
  _ * [ ] ( ) ~ ` > # + - = | { } . !

credentials 欄位：
    {"bot_token": "<TG_BOT_TOKEN>", "chat_id": "<CHAT_ID>"}
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


# MarkdownV2 必須 escape 的字元（每個都要前置一個反斜線）
_MD2_ESCAPE = set("_*[]()~`>#+-=|{}.!")


def escape_markdown_v2(text: str) -> str:
    """Telegram MarkdownV2 escape。"""
    return "".join(("\\" + c) if c in _MD2_ESCAPE else c for c in text)


LEVEL_EMOJI: dict[NotifyLevel, str] = {
    NotifyLevel.INFO: "ℹ️",
    NotifyLevel.SUCCESS: "✅",
    NotifyLevel.WARN: "⚠️",
    NotifyLevel.CRITICAL: "🚨",
}


@register_notifier
class TelegramNotifier(BaseNotifier):
    """Telegram Bot sendMessage adapter。"""

    name = "telegram"
    display_name_zh = "Telegram Bot"
    BASE_URL_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"
    max_message_length = 4096  # Telegram 限制 4096

    def _validate_credentials(self) -> tuple[str, str]:
        token = self.credentials.get("bot_token")
        chat_id = self.credentials.get("chat_id")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Telegram notifier 缺少 'bot_token' credentials")
        if not isinstance(chat_id, str) or not chat_id.strip():
            raise ValueError("Telegram notifier 缺少 'chat_id' credentials")
        return token, chat_id

    def _format_text(
        self,
        title: str,
        body: str,
        level: NotifyLevel,
        metadata: dict[str, Any] | None,
    ) -> str:
        emoji = LEVEL_EMOJI.get(level, "ℹ️")
        # title 用 bold（在 escape 前後加 *）；body 原樣 escape
        text = f"{emoji} *{escape_markdown_v2(title)}*\n\n{escape_markdown_v2(body)}"
        if metadata:
            trace_id = metadata.get("trace_id")
            if trace_id:
                text += f"\n\n_{escape_markdown_v2(f'trace_id: {trace_id}')}_"
        return text[: self.max_message_length]

    async def send(
        self,
        title: str,
        body: str,
        level: NotifyLevel = NotifyLevel.INFO,
        metadata: dict[str, Any] | None = None,
    ) -> NotifyResult:
        token, chat_id = self._validate_credentials()
        text = self._format_text(title, body, level, metadata)
        url = self.BASE_URL_TEMPLATE.format(token=token)
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True,
        }

        try:
            if self._injected_client is not None:
                resp = await self._injected_client.post(url, json=payload)
            else:
                async with self._client() as client:
                    resp = await client.post(url, json=payload)

            text_body = resp.text if hasattr(resp, "text") else ""
            ok = resp.status_code == 200
            return NotifyResult(
                success=ok,
                status_code=resp.status_code,
                response_excerpt=self._excerpt(text_body),
                error=None if ok else f"Telegram 回應 HTTP {resp.status_code}",
            )
        except Exception as exc:
            logger.warning("TelegramNotifier.send.failed error=%s", exc)
            return NotifyResult(
                success=False,
                status_code=None,
                response_excerpt=None,
                error=f"Telegram 發送失敗：{type(exc).__name__}: {exc!s}"[:500],
            )


__all__ = ["LEVEL_EMOJI", "TelegramNotifier", "escape_markdown_v2"]
