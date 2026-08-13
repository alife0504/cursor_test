# Phase 04 完成報告 — 完整 DB Schema + Alembic Migration + Hypertable + Trigger

> Phase：v1.0 全部 schema 一次到位（25 業務表 + 6 hypertable + 6 retention policy + 9 trigger + 7 Qdrant collections）
> 起始：2026-05-12
> 完成：2026-05-12
> 對應計劃：PLAN.md 第二十七章 Phase 4（v7.0）
> Git tag：`phase-04-complete`

---

## 1. 做了什麼

### 1.1 Alembic 框架

| 檔案 | 用途 |
|------|------|
| `backend/alembic.ini` | Alembic CLI 設定（ASCII-only 避免 Windows cp950 解碼問題） |
| `backend/migrations/env.py` | async + asyncpg + ta_migration 帳號；支援 `ALEMBIC_DATABASE_URL` 覆寫 |
| `backend/migrations/script.py.mako` | revision template（PEP 8 + `from __future__ import annotations`） |
| `backend/migrations/README` | 用法說明 |

### 1.2 13 個 baseline migrations（按依賴順序）

| 編號 | 主題 | 關鍵點 |
|------|------|--------|
| 0001 | users / user_sessions / password_reset_tokens | onboarding + lockout + UNIQUE LOWER(email) |
| 0002 | stock_list / stock_info | GIN(name gin_trgm_ops) 模糊搜尋 |
| 0003 | stock_prices | hypertable(date, 1mo) + retention 1y |
| 0004 | institutional_trading / margin_trading / monthly_revenue | TW only，複合 PK |
| 0005 | news_metadata / announcements | qdrant_point_id + JSONB extra_meta |
| 0006 | analysis_reports + debate_history | version 樂觀鎖 + debate hypertable(1y) |
| 0007 | pending_orders / portfolio_positions / trade_history | 手動核准下單 + 樂觀鎖 |
| 0008 | user_watchlist | UNIQUE(user_id, symbol, market) |
| 0009 | audit_logs + llm_usage + llm_monthly_quota | 兩個 hypertable + retention 1y |
| 0010 | celery_dead_letters + idempotency_keys | DLQ hypertable + TTL 24h |
| 0011 | notification_log + notification_settings | hypertable(90 days) + Fernet token 欄位 |
| 0012 | trigger：updated_at + audit hash chain | pg_advisory_xact_lock 防 race |
| 0013 | REVOKE UPDATE/DELETE on audit_logs from ta_service_rw | hash chain 雙保險 |

### 1.3 SQLAlchemy ORM models（14 檔）

`backend/app/models/`：
- `base.py` — `DeclarativeBase` + 命名規範 + `short_enum()` helper（native_enum=False）+ TimestampedMixin
- `user.py` / `stock.py` / `price.py` / `tw_specific.py` / `news.py` / `analysis.py` / `order.py`
- `watchlist.py` / `audit.py` / `quota.py` / `dlq.py` / `idempotency.py` / `notification.py`
- `__init__.py` — 集中 export，給 alembic env.py autogenerate 用

### 1.4 Qdrant collections idempotent 初始化

- `backend/app/core/qdrant_init.py` — `COLLECTIONS` 7 個 + `ensure_collections()`
- `backend/app/main.py` lifespan：startup probe 後呼叫 `ensure_collections()`
- 已存在 → skip；不存在 → create；size 不一致 → 警告但繼續

### 1.5 一次性初始化

- `data-pipeline/scripts/init_db.py`：
  - Step 1：subprocess 跑 `alembic upgrade head`
  - Step 2：`ensure_collections()`
  - Step 3：建初始 admin（從 `ADMIN_EMAIL`/`ADMIN_INITIAL_PASSWORD`，`must_change_password=TRUE`）
- 重複跑安全：admin 已存在跳過、collections 已存在跳過、alembic 已 head no-op

### 1.6 backend/app/core/database.py

- 新增 `get_migration_engine()`（pool=2）
- `test_db_connection()` 多列舉表數量，schema 未 migrate 時 log warning

### 1.7 docker/timescaledb/init.sql.template

- 內容不變（extension + 三帳號 + timeout）
- 註釋更新：audit_logs REVOKE 從 P9 改為 P4（已在 migration 0013 做）

### 1.8 Makefile 新 target

```
init-db / migration-up / migration-down / migration-new / migration-status /
migration-history / migration-redo
```

### 1.9 測試（共 27 個新增）

| 檔案 | 數量 | 覆蓋 |
|------|------|------|
| `tests/integration/test_schema.py` | 10 | 表數 / hypertable / retention / trigger / index / 權限 / Qdrant |
| `tests/integration/test_migration_up_down.py` | 3 | upgrade head / downgrade -1 + back / downgrade base + back |
| `tests/unit/test_models.py` | 14 | 型別 / 預設值 / 主鍵 / 唯一鍵 / TTL 計算 |

累積測試：**115 collected，114 passed，1 skipped**（services-down 跳過）。

### 1.10 健康檢查

`scripts/health_checks/phase_04.sh` — 13 個檢查項目，全 pass：
1. 表數 ≥ 24
2. hypertable ≥ 6
3. retention policy ≥ 6
4. audit hash chain trigger 存在
5. updated_at trigger ≥ 8
6. audit_logs INSERT 回 64 字 hex entry_hash
7-8. ta_service_rw 不可 UPDATE/DELETE audit_logs
9-10. ta_agent_ro 可 SELECT / 不可 INSERT
11. alembic 雙向 OK
12. Qdrant 7 collections
13. P4 測試全綠

---

## 2. 設計決策（與 PLAN 對齊）

### 2.1 Alembic async（不用 sync）

- 重用既有 asyncpg + SQLAlchemy 2.0 async（不引入 psycopg2）
- env.py 中以 `async_engine_from_config` + `run_sync(do_run_migrations)` 包裝
- 對 hypertable 用 `op.execute("SELECT create_hypertable(...)")`，不依賴 autogenerate

### 2.2 PG-native ENUM → CHECK constraint

- 多 model 用同名 ENUM（如 `market_enum` 在 6 個 model 出現）
- PG-native ENUM 跨表 CREATE TYPE 容易衝突，且加 enum value 需 `ALTER TYPE`（prod 高風險）
- 改用 `short_enum()` helper（`native_enum=False`），背後為 VARCHAR + CHECK constraint
- 失去微小 IO 效能，換來 multi-table reuse 安全 + alter 容易 + sqlite 測試相容

### 2.3 hypertable 複合 PK

- TimescaleDB 要求 time column 在 PK；BIGSERIAL append-only 表改為 `(id, time)` 複合 PK：
  - `audit_logs(id, timestamp)`
  - `llm_usage(id, created_at)`
  - `notification_log(id, sent_at)`
  - `debate_history(id, created_at)`
  - `celery_dead_letters(id, failed_at)`
- `stock_prices(symbol, date)` 自然主鍵符合要求

### 2.4 audit hash chain 公式

```
sha256(prev_hash || '|' || id || '|' || actor_id || '|' || action || '|' ||
       entity_type || '|' || entity_id || '|' || details::text || '|' || timestamp)
```

- BEFORE INSERT trigger
- 用 `pg_advisory_xact_lock(hashtext('audit_logs_hash_chain'))` 序列化並發 INSERT
- 第一筆 prev_hash = 64 個 `0`
- entry_hash 64 字 hex（sha256）

### 2.5 retention policy

| 表 | 期間 |
|----|------|
| stock_prices | 1 年 |
| audit_logs | 1 年 |
| llm_usage | 1 年 |
| debate_history | 1 年 |
| celery_dead_letters | 1 年（應用層 cleanup 才看 resolved=true） |
| notification_log | 90 天 |

---

## 3. 跑出來的數字

- **表**：25（24 業務 + 1 alembic_version）
- **hypertable**：6
- **retention policy**：6
- **trigger**：9（8 updated_at + 1 hash chain）+ TimescaleDB 內建 `ts_insert_blocker`
- **Qdrant collections**：7
- **新增測試**：27（unit 14 + integration 13）
- **累積測試**：115（P1 21 + P2 14 + P3 53 + P4 27）— 數字含 collect 期跳過/skipped

---

## 4. Smoke test 通過

✓ DBeaver / pgAdmin 連 ta_agent_ro 可看到所有表結構
✓ Qdrant dashboard（用 API key）看到 7 個 collections
✓ INSERT 一筆 audit_logs，entry_hash = 64 字 hex
✓ INSERT 第二筆 audit_logs，prev_hash = 第一筆的 entry_hash

---

## 5. 跨 Phase 影響

| 元件 | P5+ 使用方式 |
|------|--------------|
| ORM models | repos/ 直接 import；schemas/ 寫 Pydantic v2 對應 |
| AnalysisReport.version | repos 寫 update 時帶 `WHERE version=?` + `RETURNING version` |
| audit_logs trigger | service layer 寫 `INSERT INTO audit_logs ...`，無需手算 hash |
| Qdrant ensure_collections | startup 自動跑，P5 ingest 直接 upsert points |

---

## 6. 已知 / 接受的妥協

1. **alembic.ini 全英文註釋** — Windows cp950 console 讀不了 UTF-8，標題目錄保留 ASCII
2. **migration 顯示文字亂碼** — alembic console 用 cp950 印 docstring，不影響執行
3. **bcrypt 4.x + passlib 衝突** — init_db.py 直接用 bcrypt 套件，繞過 passlib wrap-bug 偵測
4. **debate_history.analysis_id 未設 FK** — hypertable 對 FK 有限制，靠 index 維持查詢性能

---

## 7. 文件與工具

- `docs/runbooks/migrations.md` — 如何新增 migration
- `docs/setup.md` — 加「初始化 DB」章節
- `Makefile` — 6 個 P4 新 target
- `scripts/health_checks/phase_04.sh` — 接續 P3 的健康檢查

---

## 8. 下個 Phase 的入口

P5（資料管線）會用到本 phase 的：
- 所有 ORM models
- `ta_service_rw` 帳號（DML）做 ingest
- DLQ schema（任務失敗寫入）
- Qdrant collections（news / announcements 寫入）

P5 起 schema 演進**必走 Alembic**（除緊急熱修，否則禁止直接 ALTER）。
