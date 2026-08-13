"""Phase 10 — schemas 共用基底。

依 PLAN.md 第 17.3 章 envelope / 第 17.5 章 Decimal as str。

設計：
- BaseSchema：所有 response model 繼承；
  - from_attributes=True 讓 SQLAlchemy ORM 物件可直接 model_validate
  - Pydantic v2 在 model_dump(mode="json") 預設把 Decimal 序列化為 str，符合 17.5 章規範
  - datetime 一律 ISO 8601（router 統一 model_dump(mode="json")）
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """所有 P10 response payload 的共用基底。"""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


__all__ = ["BaseSchema"]
