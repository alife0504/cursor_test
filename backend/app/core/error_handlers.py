"""FastAPI exception handlers — 統一用 envelope_error 回。

依 PLAN.md 第 17.2-17.3 章：
- AppError → 對應 http_status + envelope
- RequestValidationError → 422 + 結構化 details
- HTTPException (FastAPI 內建) → 對應 status + envelope
- Exception (兜底) → 500，**不洩漏 stack trace 給 client**，trace_id 進 log
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.errors import AppError
from app.core.logging_config import get_logger
from app.core.request_id import get_current_trace_id
from app.core.response_envelope import envelope_error

logger = get_logger(__name__)


# ── HTTPException code 對應 ──────────────────────────────

_HTTP_STATUS_TO_CODE = {
    400: "BAD_REQUEST",
    401: "AUTH_ERROR",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    423: "LOCKED",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


# ── Handlers ─────────────────────────────────────────────


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """AppError → envelope_error。"""
    trace_id = getattr(request.state, "trace_id", None) or get_current_trace_id()
    logger.warning(
        "app_error",
        code=exc.code,
        message=exc.get_message(),
        path=request.url.path,
        method=request.method,
        details=exc.details,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=envelope_error(
            code=exc.code,
            message=exc.get_message(),
            trace_id=trace_id,
            details=exc.details if exc.details else None,
        ),
    )


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pydantic 驗證錯誤 → 422 + 結構化 details。"""
    trace_id = getattr(request.state, "trace_id", None) or get_current_trace_id()

    # 從 exc.errors() 萃取對 user 友善的欄位
    field_errors = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        field_errors.append(
            {
                "field": loc or "(body)",
                "type": err.get("type", "unknown"),
                "message": err.get("msg", ""),
            }
        )

    logger.info(
        "validation_error",
        path=request.url.path,
        method=request.method,
        field_count=len(field_errors),
    )
    return JSONResponse(
        status_code=422,
        content=envelope_error(
            code="VALIDATION_ERROR",
            message="輸入驗證失敗",
            trace_id=trace_id,
            details={"errors": field_errors},
        ),
    )


async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """FastAPI / Starlette HTTPException → envelope。

    FastAPI HTTPException 繼承自 StarletteHTTPException，所以註冊 Starlette 版即可攔截兩種。
    這也能攔到 Starlette 路由系統內建 raise 的 404 / 405。
    """
    trace_id = getattr(request.state, "trace_id", None) or get_current_trace_id()
    code = _HTTP_STATUS_TO_CODE.get(exc.status_code, f"HTTP_{exc.status_code}")
    # detail 可能是 dict / str / list；str 直接用，dict 進 details
    if isinstance(exc.detail, str):
        message = exc.detail
        details = None
    else:
        message = "請求發生錯誤"
        details = {"detail": exc.detail} if exc.detail else None

    return JSONResponse(
        status_code=exc.status_code,
        content=envelope_error(
            code=code,
            message=message,
            trace_id=trace_id,
            details=details,
        ),
        headers=getattr(exc, "headers", None) or None,
    )


async def _handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    """兜底：所有未捕捉的 Exception → 500 + trace_id（**不洩漏 stack trace**）。"""
    trace_id = getattr(request.state, "trace_id", None) or get_current_trace_id()
    logger.exception(
        "unexpected_error",
        path=request.url.path,
        method=request.method,
        exc_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content=envelope_error(
            code="INTERNAL_ERROR",
            message="系統發生錯誤，請稍後再試或聯絡管理員",
            trace_id=trace_id,
        ),
    )


# ── 註冊 ────────────────────────────────────────────────


def register_exception_handlers(app: FastAPI) -> None:
    """在 app 啟動時呼叫一次。"""
    app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    # 註冊 Starlette HTTPException（FastAPI HTTPException 繼承自此），
    # 也涵蓋 Starlette 路由系統內建 raise 的 404 / 405
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)  # type: ignore[arg-type]
    # Exception 兜底（最後一層）
    app.add_exception_handler(Exception, _handle_unexpected_exception)


__all__ = ["register_exception_handlers"]
