"""Phase 11 — /api/v1/exports/* router。

GET /api/v1/exports/{report_id}?format=pdf|md|xlsx
- format=pdf  → Playwright render → application/pdf
- format=md   → text/markdown; charset=utf-8
- format=xlsx → openpyxl bytes
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.api.dependencies import get_current_user
from app.core.database import get_rw_session
from app.core.errors import ValidationError
from app.core.validators import validate_uuid
from app.schemas.exports import ALLOWED_EXPORT_FORMATS, EXPORT_MIME_TYPES
from app.services.exports_service import ExportsService

if TYPE_CHECKING:
    from app.models.user import User


router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


@router.get("/{report_id}", summary="匯出分析報告（pdf / md / xlsx）")
async def export_report(
    report_id: str,
    request: Request,
    format: str = Query(default="pdf", max_length=10),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_rw_session),
):
    fmt = format.lower().strip()
    if fmt not in ALLOWED_EXPORT_FORMATS:
        raise ValidationError(
            message_zh=f"不支援的匯出格式 {format}（允許：{sorted(ALLOWED_EXPORT_FORMATS)}）",
            field="format",
        )

    service = ExportsService(session)
    uid = validate_uuid(report_id)

    if fmt == "md":
        content_str = await service.export_md(user, uid)
        return Response(
            content=content_str.encode("utf-8"),
            media_type=EXPORT_MIME_TYPES["md"],
            headers={"Content-Disposition": f'attachment; filename="report-{uid}.md"'},
        )

    if fmt == "xlsx":
        content_bytes = await service.export_xlsx(user, uid)
        return Response(
            content=content_bytes,
            media_type=EXPORT_MIME_TYPES["xlsx"],
            headers={"Content-Disposition": f'attachment; filename="report-{uid}.xlsx"'},
        )

    # pdf
    content_bytes = await service.export_pdf(user, uid)
    return Response(
        content=content_bytes,
        media_type=EXPORT_MIME_TYPES["pdf"],
        headers={"Content-Disposition": f'attachment; filename="report-{uid}.pdf"'},
    )


__all__ = ["router"]
