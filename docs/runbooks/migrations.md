# Migrations Runbook

> 目的：說明如何在 Phase 4 之後新增 / 應用 / 退回 Alembic migration。
> 對應 PLAN 第 17.7 章。

## TL;DR

```bash
# 新增 migration
make migration-new MSG="add ticker alias column"
# 編輯 backend/migrations/versions/<id>_add_ticker_alias_column.py

# 套用
make migration-up        # alembic upgrade head

# 退回一步
make migration-down      # alembic downgrade -1

# 看狀態
make migration-status    # alembic current
make migration-history   # alembic history

# 雙向健全性測試
make migration-redo      # downgrade base + upgrade head
```

## 設計準則

1. **每個 migration 都要寫 `downgrade()`**
   - CI 會跑 upgrade ↔ downgrade
   - 即使覺得不需要 — 至少加註釋說明為何 no-op

2. **連線帳號**
   - alembic 用 `ta_migration`（CREATEDB + DDL）
   - 業務 code 用 `ta_service_rw`（DML only）
   - Agent 用 `ta_agent_ro`（read-only）

3. **TimescaleDB hypertable / retention policy / view**
   - autogenerate 不認得
   - 一律用 `op.execute("SELECT create_hypertable(...)")` 顯式寫
   - downgrade 用 `op.execute("SELECT remove_retention_policy(...)")` 退回

4. **PG enum vs CHECK constraint**
   - 本專案統一用 CHECK constraint（model 層 `short_enum()` helper）
   - 加新 enum value：直接改 `_*_VALUES` 常數 + 寫新 migration 修 CHECK constraint
   - 不要用 `CREATE TYPE` / `ALTER TYPE`（避免跨 model 衝突）

5. **欄位精度與時區**
   - 金額：`Numeric(20, 6)` 或 `Numeric(24, 2)`；切勿 float
   - 時間：`DateTime(timezone=True)` + `server_default=func.now()`
   - JSON：`postgresql.JSONB`（不退化為 JSON）

## 常見場景

### 加新欄位

```python
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preferred_currency", sa.String(10), nullable=False,
                  server_default="TWD"),
    )

def downgrade() -> None:
    op.drop_column("users", "preferred_currency")
```

### 加 index

```python
def upgrade() -> None:
    op.create_index("ix_users_preferred_currency", "users", ["preferred_currency"])

def downgrade() -> None:
    op.drop_index("ix_users_preferred_currency", table_name="users")
```

### 加 GIN index（pg_trgm 或 JSONB）

```python
def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_news_metadata_title_trgm "
        "ON news_metadata USING gin (title gin_trgm_ops)"
    )

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_news_metadata_title_trgm")
```

### 加 enum value（CHECK constraint 模式）

```python
def upgrade() -> None:
    op.drop_constraint("ck_pending_orders_status", "pending_orders", type_="check")
    op.create_check_constraint(
        "ck_pending_orders_status",
        "pending_orders",
        "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', "
        "'EXECUTED', 'CANCELLED', 'PAUSED')",
    )

def downgrade() -> None:
    op.drop_constraint("ck_pending_orders_status", "pending_orders", type_="check")
    op.create_check_constraint(
        "ck_pending_orders_status",
        "pending_orders",
        "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', "
        "'EXECUTED', 'CANCELLED')",
    )
```

### Hypertable 上加欄位

允許 — 只是不能改 PK 中的 time column。

```python
def upgrade() -> None:
    op.add_column("stock_prices", sa.Column("vwap", sa.Numeric(20, 6)))

def downgrade() -> None:
    op.drop_column("stock_prices", "vwap")
```

## 注意事項

- **不要直接改 baseline migration（0001-0013）**。改了之後 prod 部署不一致。新增 migration 修改即可。
- **不要 `alembic stamp`**（除非你完全理解後果）。
- **每次新 migration 寫完 → 立即 `migration-redo`**，驗證雙向 OK 才 commit。
- **prod 部署前**：staging 跑 `migration-redo` 並做 smoke test。
- **緊急情況下 superuser 可以直接 ALTER**，但要立即補一個 stamp-only migration。

## 連線參數覆寫

CI 或測試環境若不想用 `ta_migration` 帳號，可設環境變數：

```bash
export ALEMBIC_DATABASE_URL="postgresql+asyncpg://test_user:pwd@localhost:5432/test_db"
uv run alembic upgrade head
```

`backend/migrations/env.py` 會優先讀此變數。
