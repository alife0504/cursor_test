"""SQLAlchemy 2.0 DeclarativeBase + 共用 mixin。

依 PLAN.md 第 20.2 章資料模型 + 第 15.5 章 UTC 時區 + 第 15.6 章 Decimal。

設計：
- Base 用 DeclarativeBase（SA 2.0 推薦）
- 所有 model `__tablename__` 用 snake_case 複數
- 共用 mixin：TimestampedMixin（created_at / updated_at）
- JSONB 統一用 PostgreSQL JSONB（不退化成 JSON）
- 金額：Numeric(24, 6) — 可表示 ±10^18，避免大型權證爆精度
- UUID：sqlalchemy.UUID(as_uuid=True) — PG-native uuid

注意：
- ORM 模型只負責「table 結構 + 欄位型別」的權威定義。
- TimescaleDB hypertable / retention policy / trigger 在 Alembic migration 用 op.execute() 顯式建立。
- 不在 model 自動建表（不用 Base.metadata.create_all）。Schema 必走 Alembic。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 統一命名規範 — Alembic autogenerate 時用一致的 index / fk 命名
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 DeclarativeBase。

    所有 model 繼承此類；metadata 帶命名規範。
    """

    metadata = metadata

    # Pydantic v2 ORM-mode 兼容（用 schema 層轉換時：from_attributes=True）
    def to_dict(self) -> dict[str, Any]:
        """轉成 dict（給 audit/log 用，遮蔽不在）。"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class TimestampedMixin:
    """共用：created_at / updated_at（UTC，trigger 會自動更新 updated_at）。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CreatedAtMixin:
    """只有 created_at（hypertable / append-only 表用）。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


def short_enum(*values: str, name: str) -> SAEnum:
    """專案統一 enum 工廠。

    決策：用 native_enum=False（背後是 VARCHAR + CHECK constraint），原因：
    1. 跨多個 model file 引用同一 name 的 enum 時，PG-native ENUM 容易在 DDL 階段
       發生「重複 CREATE TYPE」衝突；CHECK 模式不會。
    2. 加新 enum value 不需要 ALTER TYPE（避免 prod migration 高風險操作）。
    3. CHECK 模式對非 PostgreSQL 測試環境（如 sqlite 單元測試）相容。
    4. PG-native enum 的微小 IO 效能對 v1.0 規模不重要。

    若未來性能評估需切回 native enum，請統一改 base.py 此 helper，並在 baseline
    migration 用 op.execute() 補 CREATE TYPE / DROP TYPE。
    """
    return SAEnum(
        *values,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=50,
    )


__all__ = [
    "NAMING_CONVENTION",
    "Base",
    "CreatedAtMixin",
    "TimestampedMixin",
    "metadata",
    "short_enum",
]
