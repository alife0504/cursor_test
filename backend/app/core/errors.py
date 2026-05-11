"""AppError 階層 — 業務錯誤類別。

依 PLAN.md 第 17.2 章 Error 階層設計。
"""

from __future__ import annotations

from typing import Any, ClassVar


class AppError(Exception):
    """業務錯誤基類。

    用法：
        raise NotFoundError(message_zh="用戶不存在", user_id=str(user_id))
    """

    code: ClassVar[str] = "INTERNAL_ERROR"
    message_zh: ClassVar[str] = "系統發生錯誤"
    http_status: ClassVar[int] = 500

    def __init__(self, message_zh: str | None = None, **details: Any) -> None:
        # 允許覆寫預設訊息（subclass 可給更具體的）
        self.message_zh_override = message_zh
        self.details: dict[str, Any] = details
        super().__init__(self.get_message())

    def get_message(self) -> str:
        return self.message_zh_override or self.message_zh


class ValidationError(AppError):
    code: ClassVar[str] = "VALIDATION_ERROR"
    message_zh: ClassVar[str] = "輸入驗證失敗"
    http_status: ClassVar[int] = 422


class NotFoundError(AppError):
    code: ClassVar[str] = "NOT_FOUND"
    message_zh: ClassVar[str] = "資源不存在"
    http_status: ClassVar[int] = 404


class AuthError(AppError):
    code: ClassVar[str] = "AUTH_ERROR"
    message_zh: ClassVar[str] = "認證失敗"
    http_status: ClassVar[int] = 401


class ForbiddenError(AppError):
    code: ClassVar[str] = "FORBIDDEN"
    message_zh: ClassVar[str] = "權限不足"
    http_status: ClassVar[int] = 403


class ConflictError(AppError):
    code: ClassVar[str] = "CONFLICT"
    message_zh: ClassVar[str] = "資源狀態衝突"
    http_status: ClassVar[int] = 409


class RateLimitError(AppError):
    code: ClassVar[str] = "RATE_LIMITED"
    message_zh: ClassVar[str] = "請求頻率過高，請稍後再試"
    http_status: ClassVar[int] = 429


class ExternalServiceError(AppError):
    code: ClassVar[str] = "EXTERNAL_SERVICE_ERROR"
    message_zh: ClassVar[str] = "外部服務暫時無法存取"
    http_status: ClassVar[int] = 503


class TooLargeError(AppError):
    code: ClassVar[str] = "PAYLOAD_TOO_LARGE"
    message_zh: ClassVar[str] = "請求內容過大"
    http_status: ClassVar[int] = 413


class LockedError(AppError):
    code: ClassVar[str] = "LOCKED"
    message_zh: ClassVar[str] = "帳號已鎖定"
    http_status: ClassVar[int] = 423


class QuotaExceededError(AppError):
    code: ClassVar[str] = "QUOTA_EXCEEDED"
    message_zh: ClassVar[str] = "配額已用盡"
    http_status: ClassVar[int] = 402


class IdempotencyConflictError(AppError):
    code: ClassVar[str] = "IDEMPOTENCY_CONFLICT"
    message_zh: ClassVar[str] = "Idempotency-Key 已存在但 request 內容不同"
    http_status: ClassVar[int] = 409


__all__ = [
    "AppError",
    "AuthError",
    "ConflictError",
    "ExternalServiceError",
    "ForbiddenError",
    "IdempotencyConflictError",
    "LockedError",
    "NotFoundError",
    "QuotaExceededError",
    "RateLimitError",
    "TooLargeError",
    "ValidationError",
]
