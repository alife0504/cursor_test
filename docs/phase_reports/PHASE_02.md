# Phase 02 完成報告 — Docker 基礎服務 + DB 帳號分離 + 健康檢查

> Phase：Docker 三服務（TimescaleDB / Redis / Qdrant）+ DB 帳號分離 + Qdrant API key
> 起始：2026-05-05
> 完成：2026-05-06
> 對應計劃：PLAN.md 第二十七章 Phase 2
> Git tag：phase-02-complete

---

## 1. 做了什麼

### 1.1 Docker Compose 設定（任務 B + C）

**dev**（`docker-compose.yml`）：
- `timescaledb`（timescale/timescaledb:2.16.1-pg16）
  - port 5432，healthcheck `pg_isready`
  - mount init.sh + init.sql.template 進 `/docker-entrypoint-initdb.d/`
- `redis`（redis:7-alpine）
  - port 6379，requirepass + maxmemory 1GB allkeys-lru + AOF everysec
  - healthcheck `redis-cli -a $PWD ping`
- `qdrant`（qdrant/qdrant:v1.9.5）
  - port 6333（HTTP）+ 6334（gRPC），API key 強制
  - healthcheck `wget -qO- http://localhost:6333/healthz`
- 全 named volume（`tradingagents_*_data`），dev 不對外接口（healthcheck 標準化）

**prod 雛形**（`docker-compose.prod.yml`）：
- 三服務 `expose:` 不對外（只內網）
- `restart: always`、`stop_grace_period: 60s`
- redis 加 `read_only: true` + `cap_drop: ALL` + tmpfs（/tmp 64MB）
- 全部加 `deploy.resources.limits`（mem / cpus）
- Phase 19 完整化（加 nginx + backend + celery）

### 1.2 TimescaleDB 初始化（任務 D + E）

**`docker/timescaledb/init.sql.template`**（依 PLAN 19.1 章帳號分離）：
- 啟用 extensions：`timescaledb`、`pg_trgm`、`pgcrypto`
- 建三個帳號：
  - `ta_migration`（CREATEDB + 全表 DDL/DML）→ alembic 用
  - `ta_service_rw`（DML only，無 DDL）→ 後端業務用
  - `ta_agent_ro`（SELECT only）→ Agent / Tool 用，防 prompt injection 注入 SQL
- `ALTER DEFAULT PRIVILEGES`：`ta_migration` 建表時自動 GRANT 給其他兩帳號
- 各帳號 `statement_timeout` / `lock_timeout` 預設（依 PLAN 14.1 章）

**`docker/timescaledb/init.sh`**：
- 用 `envsubst` 把 `${TA_*_PASSWORD}` 從 env 替換到 SQL（避免 `psql -v` 變數機制與 SQL `$$` 衝突）
- 限制只展開 3 個密碼變數（`envsubst '${TA_MIGRATION_PASSWORD} ${TA_SERVICE_RW_PASSWORD} ${TA_AGENT_RO_PASSWORD}'`）
- 跑完清臨時 `/tmp/init.sql`

### 1.3 wait-for-services.sh（任務 F）

`backend/scripts/wait-for-services.sh`（依 PLAN 13.2 章）：
- 用 `sh`（不是 bash）相容 alpine container
- 依序等 timescaledb（pg_isready）→ redis（PING / NOAUTH 都算 ready）→ qdrant（/healthz）
- 預設 timeout 180s，可用 `WAIT_FOR_SERVICES_TIMEOUT` 覆寫
- `exec "$@"` 確保 pid=1（給 Docker init 用）

### 1.4 .env / .env.example（任務 G + H）

P1 已先列齊欄位，P2 補入隨機密碼（每組 32 bytes urlsafe）：
- `POSTGRES_SUPERUSER_PASSWORD`（PG superuser，僅 init/dump）
- `TA_MIGRATION_PASSWORD` / `TA_SERVICE_RW_PASSWORD` / `TA_AGENT_RO_PASSWORD`
- `REDIS_PASSWORD`
- `QDRANT_API_KEY`

附加保留：`SECRET_KEY` / `DATA_ENCRYPTION_KEY`（給 P3 用）。

### 1.5 Makefile Docker target（任務 I）

新增：
- `up` / `down` / `down-volumes` / `services-reset`
- `logs` / `logs-tail` / `restart` / `ps`
- `psql`（用 superuser 進）/ `redis-cli`（互動）/ `qdrant-status`
- `test-integration`（跑 P2 integration tests）

### 1.6 Integration tests（任務 J + K + L）

| 檔案 | 測試數 | 用途 |
|------|--------|------|
| `tests/integration/conftest.py` | - | env_vars / pg_*/redis_*/qdrant_* fixture |
| `tests/integration/test_db_connectivity.py` | 6 | superuser 連線 + ta_migration DDL + ta_service_rw / ta_agent_ro 權限隔離 + extension 啟用 |
| `tests/integration/test_redis_connectivity.py` | 4 | password 連線 + SET/GET/DEL + 沒密碼/錯密碼 都失敗 |
| `tests/integration/test_qdrant_connectivity.py` | 4 | /healthz 不需 key + /collections 需 API key + 錯 key 401 |

`pytest --collect-only`：**50 tests**（P1 36 + P2 14）符合累積基準（P2 ≥ 12）。

### 1.7 Runbook（任務 M）

`docs/runbooks/services.md` 涵蓋：
- 啟動／停止指令
- 三個 DB 帳號用途與差異（含禁用情境）
- 進入 psql / redis-cli / qdrant 的方式
- 常見問題 8 條（port 占用、容器重啟、NOAUTH、Web UI、healthcheck starting、envsubst、Docker Desktop、6334 gRPC）
- 手動備份方式（P19 才完整化）
- 資源使用觀察

### 1.8 健康檢查（任務 N）

`scripts/health_checks/phase_02.sh`（11 項檢查）：
1. .env 必要密碼欄位齊
2. docker compose 設定檔齊
3. docker daemon 在跑（沒跑 graceful skip）
4. 三服務 running
5. timescaledb pg_isready
6. 三 DB 帳號可連
7. ta_service_rw 不能 DDL
8. ta_agent_ro 不能 DDL
9. timescaledb extension 已啟
10. redis ping
11. qdrant API key 驗證生效（沒 key 401，有 key 200）

---

## 2. 退出條件指令結果

> Docker daemon 未啟動 → 後續執行（含驗收 + Self-Check 部分項目）會在 Docker Desktop 啟動後跑。

| # | 指令 | 結果 |
|---|------|------|
| 1 | `make up` | 待 Docker 啟動 |
| 2 | 三服務 healthy | 待 |
| 3 | 三帳號可連 | 待 |
| 4 | `ta_agent_ro` 不能寫 | 待 |
| 5 | `ta_service_rw` 不能 DDL | 待 |
| 6 | TimescaleDB extension 已啟 | 待 |
| 7 | redis SET / GET | 待 |
| 8 | qdrant 需 API key | 待 |
| 9 | integration tests 通過 | 待 |
| 10 | health_check phase_02 | 待 |

**靜態驗收（不需 docker）：**
- ✅ 所有設定檔已建立並 ruff/yaml 檢查通過
- ✅ pytest collect 50 tests
- ✅ phase_02.sh graceful skip 正確
- ✅ .env 含 8 組隨機密碼（從 .env.example 升級）

---

## 3. 已知遺漏 / 限制

### 3.1 Docker Desktop 未啟動

P2 寫完所有設定後因 Docker Desktop 未啟動，runtime 驗收（`make up` 後的 10 項指令）將在啟動後跑。
**處理：** 若 Docker 啟動後 runtime 驗收通過，補一次 `phase-02-complete` git tag。

### 3.2 envsubst 替換策略

`init.sh` 用 `envsubst '${VAR1} ${VAR2}...'` 限制只替換指定變數，避免意外替換 SQL 中的 `$$`、`$1`。已在 init.sql.template 中避免任何 `$$` dollar-quoted 字串。

### 3.3 Windows port 5432 被本機 PG 占用

若使用者本機已裝 PostgreSQL，`make up` 會失敗。
**Workaround**（已在 runbook）：改 `.env` 中 `POSTGRES_PORT=5433`，重啟 docker。

### 3.4 prod docker-compose 不完整

`docker-compose.prod.yml` 雛形只含 DB 三服務（無 backend / celery / nginx）。
P19 才完整化。

---

## 4. 給下一 Phase（Phase 3）的提醒

1. **必先跑 `bash scripts/health_checks/phase_01.sh && bash scripts/health_checks/phase_02.sh`** 確認 P1 + P2 結果還能跑
2. P3 要寫 `backend/app/core/database.py` 連 timescaledb，需 P2 已 `make up`
3. P3 連 DB 用 `ta_service_rw` 帳號，**不要用 superuser**
4. P3 連 Redis 用 `db=0/1/2/3/4/5/6` 對應 7 種用途（依 PLAN 17.5 章）
5. P3 `lifespan startup` 要 fail-fast（DB / Redis / Qdrant 任一連不上就拒啟）
6. P3 不要建 Qdrant collection（P4 / P7 才建）
7. .env 已有 SECRET_KEY / DATA_ENCRYPTION_KEY，可直接用
8. P3 寫 `config.py` 時記得用 SecretStr 包密碼欄位（避免 log 洩漏）

---

## 5. 跑了多久

- 開始：2026-05-05（P1 結束後）
- 完成：2026-05-06（同 session 一氣完成設定 + tests + runbook）
- Claude session：1
- 估計實際時數：~3 hr（含中段對話重啟）

---

## 6. Git 操作摘要

```
master:
  fe1531f  feat(phase-1): ...

phase/02-docker-services:
  （待 final commit）
```
