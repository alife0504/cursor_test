"""統一 API Response Envelope。

依 PLAN.md 第 17.3 章規範：
- 成功：{"data": ..., "meta": {trace_id, version, timestamp}, "pagination": {...}}
- 失敗：{"error": {code, message, trace_id, details}}

所有 response body 走這兩個 envelope，前端可統一解析。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

# ════════════════ Pydantic Models（給 Swagger 用） ════════════════


class MetaInfo(BaseModel):
    """Response meta 區段：trace_id / version / timestamp。"""

    model_config = ConfigDict(populate_by_name=True)

    trace_id: str = Field(description="本次 request 唯一識別碼（同 X-Request-ID header）")
    version: str = Field(default="v1")
    timestamp: str = Field(description="ISO 8601 UTC 時間")


class PaginationInfo(BaseModel):
    """Cursor-based 分頁資訊（依第 17.4 章）。"""

    model_config = ConfigDict(populate_by_name=True)

    next_cursor: str | None = Field(default=None, description="下一頁 cursor，無更多資料時為 null")
    limit: int = Field(default=50, description="本次回應的最大筆數")
    has_more: bool = Field(default=False)


class ErrorInfo(BaseModel):
    """Error envelope 內容。"""

    model_config = ConfigDict(populate_by_name=True)

    code: str
    message: str
    trace_id: str
    details: dict[str, Any] | None = Field(default=None)


class SuccessEnvelope(BaseModel):
    """成功回應的 envelope（Swagger / docs 用）。"""

    data: Any
    meta: MetaInfo
    pagination: PaginationInfo | None = Field(default=None)


class ErrorEnvelope(BaseModel):
    """失敗回應的 envelope。"""

    error: ErrorInfo


# ════════════════ Helper functions（給 router 直接呼叫） ════════════════


def _serialize_value(v: Any) -> Any:
    """JSON-serializable 轉換：Decimal → str、datetime → ISO 8601。"""
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, datetime):
        # 強制 UTC ISO 8601
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _serialize_value(val) for k, val in v.items()}
    if isinstance(v, list | tuple):
        return [_serialize_value(x) for x in v]
    return v


def envelope_success(
    data: Any,
    *,
    trace_id: str,
    pagination: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """成功回應 envelope。

    Args:
        data: 主資料（dict / list / 任何 JSON-serializable）
        trace_id: 本次 request 的 trace_id（從 RequestIDMiddleware）
        pagination: 分頁資訊（可選，含 next_cursor / limit / has_more）

    Returns:
        envelope dict，可直接給 FastAPI 回。
    """
    body: dict[str, Any] = {
        "data": _serialize_value(data),
        "meta": {
            "trace_id": trace_id,
            "version": "v1",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    }
    if pagination is not None:
        body["pagination"] = pagination
    return body


def envelope_error(
    code: str,
    message: str,
    *,
    trace_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """失敗回應 envelope。

    Args:
        code: 錯誤代碼（依第 17.2 章 AppError.code）
        message: 繁中錯誤訊息
        trace_id: 本次 request 的 trace_id
        details: 額外結構化資訊（如 field, allowed_values）

    Returns:
        envelope dict。
    """
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "trace_id": trace_id,
        }
    }
    if details:
        body["error"]["details"] = _serialize_value(details)
    return body


__all__ = [
    "ErrorEnvelope",
    "ErrorInfo",
    "MetaInfo",
    "PaginationInfo",
    "SuccessEnvelope",
    "envelope_error",
    "envelope_success",
]


# 標記 settings 已 import 但本檔暫不直接用（避免 ruff 警告）
_ = settings
