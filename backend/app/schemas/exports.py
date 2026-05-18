"""Phase 11 — /api/v1/exports/* schemas（PDF / MD / XLSX）。"""

from __future__ import annotations

ALLOWED_EXPORT_FORMATS = {"pdf", "md", "xlsx"}

EXPORT_MIME_TYPES = {
    "pdf": "application/pdf",
    "md": "text/markdown; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


__all__ = ["ALLOWED_EXPORT_FORMATS", "EXPORT_MIME_TYPES"]
