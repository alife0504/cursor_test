"""Service 層 — 業務邏輯協調器。

依 PLAN.md 第 18.1 章後端分層：
  API → Service → Domain → Repository → Infrastructure

Service 從 Repository 取資料、執行業務規則、發布事件，不直接接 HTTP。
"""

from __future__ import annotations

from app.services.data_pipeline_service import DataPipelineService

__all__ = ["DataPipelineService"]
