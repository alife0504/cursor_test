"""Alembic env.py — 用 SQLAlchemy 2.0 async + ta_migration 帳號。

依 PLAN.md 第 17.7 章 + 第 19.1 章帳號分離。

設計：
- 連線用 ta_migration（CREATEDB + DDL 權限）
- async 模式（與 backend SQLAlchemy 2.0 async 一致）
- 支援 ALEMBIC_DATABASE_URL 環境變數覆寫（測試 / CI 用）
- target_metadata 由 app.models.base.Base 提供（autogenerate 用）
- include_object 排除 timescaledb 內部表（_timescaledb_*）

注意：
- Alembic autogenerate 無法處理 TimescaleDB hypertable / retention policy；
  baseline migration 內全部用 op.execute() 顯式建立。
- 後續 migration 若需 autogenerate，請在執行後手動加 hypertable / index。
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 把 backend/ 加入 sys.path，方便 import app.*
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.models.base import Base  # noqa: E402

# Alembic Config 物件
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata = ORM 模型的 metadata（autogenerate 用）
# 必須 import 全部 model 才會註冊到 Base.metadata
from app.models import (  # noqa: E402, F401
    analysis,
    audit,
    dlq,
    idempotency,
    news,
    notification,
    order,
    price,
    quota,
    stock,
    tw_specific,
    user,
    watchlist,
)

target_metadata = Base.metadata


def _get_url() -> str:
    """優先 ALEMBIC_DATABASE_URL，否則用 settings.postgres_dsn_migration。

    Alembic 內部走 async engine（asyncpg dialect），與 backend 一致。
    """
    override = os.getenv("ALEMBIC_DATABASE_URL")
    if override:
        return override
    return settings.postgres_dsn_migration


# 以「手寫 raw-SQL migration 建立、無對應 ORM model」的表：不在 Base.metadata 中，若不排除，
# autogenerate 會判成 drop_table → 一次疏忽即永久刪除交易日曆 / 稽核鏈尾錨（audit_checkpoints
# 已 REVOKE UPDATE/DELETE 為不可竄改設計，被 drop 等同湮滅稽核能力）。明確保護，絕不誤刪。
_RAW_SQL_TABLES: frozenset[str] = frozenset({"trading_calendar", "audit_checkpoints"})


def _include_object(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    """排除 timescaledb 內部 schema 表 + 無 ORM model 的 raw-SQL 表，避免 autogenerate 誤判 drop。"""
    if type_ == "table" and name.startswith("_timescaledb"):
        return False
    if type_ == "table" and name in ("hypertable", "chunk"):
        return False
    # 無 ORM model 的手寫表：排除以防 autogenerate 產生 drop_table 的資料遺失地雷
    if type_ == "table" and name in _RAW_SQL_TABLES:
        return False
    # timescaledb_information 是 view schema
    schema = getattr(obj, "schema", None)
    return not (schema and schema.startswith("_timescaledb"))


def run_migrations_offline() -> None:
    """Offline mode — 印 SQL 不連 DB。"""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """同步 callback（給 async 包裝用）。"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include_object,
        compare_type=True,
        compare_server_default=True,
        # TimescaleDB hypertable 的 chunks 用 inherits — 不讓 autogenerate 處理
        include_schemas=False,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Online async mode — 連 DB 跑 migration。"""
    cfg = config.get_section(config.config_ini_section, {}) or {}
    cfg["sqlalchemy.url"] = _get_url()

    connectable = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Online entry — 跑 async 版本。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
