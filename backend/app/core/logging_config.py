"""structlog 設定 — JSON output + 敏感欄位遮蔽 + trace_id 自動帶入。

依 PLAN.md 第 17.1 章 logging 規範。

使用方式：
    from app.core.logging_config import configure_logging, get_logger
    configure_logging()
    log = get_logger()
    log.info("user.login", user_id=user.id)  # 自動帶 trace_id
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.contextvars import merge_contextvars
from structlog.processors import (
    JSONRenderer,
    StackInfoRenderer,
    TimeStamper,
    UnicodeDecoder,
    add_log_level,
    format_exc_info,
)
from structlog.types import EventDict, Processor

from app.core.config import settings

# 敏感欄位清單（依第 17.1 章）
_SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "token",
        "authorization",
        "auth",
        "line_token",
        "telegram_token",
        "refresh_token",
        "access_token",
        "csrf",
        "csrf_token",
        "cookie",
        "secret_key",
        "data_encryption_key",
        "qdrant_api_key",
        "google_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "finmind_token",
        "alpha_vantage_api_key",
        "finnhub_api_key",
        "telegram_bot_token",
        "line_notify_token",
    }
)

_MASK = "***REDACTED***"


def _mask_sensitive_processor(_logger: Any, _method_name: str, event_dict: EventDict) -> EventDict:
    """遮蔽敏感欄位（不分大小寫比對 key）。"""
    for key in list(event_dict.keys()):
        key_lower = key.lower()
        if key_lower in _SENSITIVE_FIELDS or any(
            s in key_lower for s in ("password", "secret", "token", "api_key")
        ):
            event_dict[key] = _MASK
    return event_dict


def _drop_color_message_processor(
    _logger: Any, _method_name: str, event_dict: EventDict
) -> EventDict:
    """uvicorn 預設加 color_message 欄位，drop 掉避免 JSON 雜訊。"""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging() -> None:
    """在 lifespan startup 跑一次。"""
    # stdlib logging 設定（uvicorn / fastapi 自身用）
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL),
    )
    # 把第三方 logger 也納入 structlog
    for noisy in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        logging.getLogger(noisy).handlers.clear()
        logging.getLogger(noisy).propagate = True

    # 注意：不用 stdlib.add_logger_name（PrintLoggerFactory 沒 .name 屬性）
    # 改用：呼叫 get_logger("...") 時用 .bind(logger="...") 自帶
    shared_processors: list[Processor] = [
        merge_contextvars,  # 自動帶入 contextvars（含 trace_id）
        add_log_level,
        TimeStamper(fmt="iso", utc=True, key="ts"),
        StackInfoRenderer(),
        format_exc_info,
        UnicodeDecoder(),
        _drop_color_message_processor,
        _mask_sensitive_processor,
    ]

    if settings.LOG_FORMAT == "json":
        shared_processors.append(JSONRenderer(sort_keys=False))
    else:
        # console（dev 友善）
        shared_processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True, exception_formatter=structlog.dev.plain_traceback
            )
        )

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.LOG_LEVEL)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """取得 structlog logger（同步、bound）。"""
    return structlog.get_logger(name) if name else structlog.get_logger()


__all__ = ["configure_logging", "get_logger"]
