# Runbook: Docker 基礎服務

> Phase 2 建立。對應 timescaledb / redis / qdrant 三服務維運。

---

## 1. 啟動 / 停止

```bash
# 啟動三服務（背景）
make up

# 看狀態
make ps

# 看 log
make logs           # follow
make logs-tail      # 最近 100 行

# 停止（保留資料）
make down

# 重啟
make restart
```

---

## 2. 進入服務 console

### 2.1 PostgreSQL（superuser）

```bash
make psql
# 等同：docker compose exec timescaledb psql -U postgres -d tradingagents_tw
```

### 2.2 PostgreSQL（特定帳號）

```bash
# 用 ta_service_rw（DML only）
PGPASSWORD=$(grep ^TA_SERVICE_RW_PASSWORD= .env | cut -d= -f2) \
  psql -h localhost -U ta_service_rw -d tradingagents_tw

# 用 ta_agent_ro（read-only）
PGPASSWORD=$(grep ^TA_AGENT_RO_PASSWORD= .env | cut -d= -f2) \
  psql -h localhost -U ta_agent_ro -d tradingagents_tw
```

### 2.3 Redis

```bash
make redis-cli
# 互動模式（已自動帶 -a $REDIS_PASSWORD）
```

### 2.4 Qdrant

```bash
# Health check（不需 API key）
curl http://localhost:6333/healthz

# 列 collections（需 API key）
make qdrant-status

# 或手動：
curl -H "api-key: $(grep ^QDRANT_API_KEY= .env | cut -d= -f2)" \
  http://localhost:6333/collections
```

---

## 3. 三個 DB 帳號用途與差異（依 PLAN 第 19.1 章）

| 帳號 | 權限 | 用於 | 後續 Phase |
|------|------|------|-----------|
| `ta_migration` | CREATEDB + 全表 DDL/DML | Alembic schema migration | P4 alembic |
| `ta_service_rw` | DML only（SELECT/INSERT/UPDATE/DELETE） | 後端業務（CRUD） | P3+ FastAPI |
| `ta_agent_ro` | SELECT only | LangGraph Agent / Tool（防 prompt injection 注入 SQL） | P12+ Agent |
| `postgres` (superuser) | 全部 | 維運：dump、init、cluster 操作 | 維運手動 |

**安全規則：**
- 後端 service 不得使用 `postgres` 或 `ta_migration` 連線（除 alembic 跑時）
- Agent / Tool **必須**使用 `ta_agent_ro`
- audit_logs 在 P9 會 REVOKE UPDATE/DELETE from `ta_service_rw`（hash chain 不可竄改）

---

## 4. 資料持久化

```
named volumes（git 不追蹤）:
  - tradingagents_timescaledb_data
  - tradingagents_redis_data
  - tradingagents_qdrant_data
```

```bash
# 看 volume
docker volume ls | grep tradingagents

# 砍 volume（會清資料！）
make down-volumes
# 等同：docker compose down -v

# 完全重設（停 + 砍 volume + 重啟）
make services-reset
```

---

## 5. 常見問題排查

### 5.1 Port 5432 已被本機 PostgreSQL 占用

**症狀：** `make up` 報 `bind: address already in use`

**處理：**
```bash
# 1. 改 .env 裡的 POSTGRES_PORT 為 5433
sed -i 's/^POSTGRES_PORT=5432$/POSTGRES_PORT=5433/' .env

# 2. 重啟
make down && make up
```

### 5.2 timescaledb 容器反覆重啟

**症狀：** `make ps` 看到 timescaledb 狀態 `Restarting`

**處理：**
```bash
# 1. 看 log
docker compose logs timescaledb | tail -30

# 2. 常見原因：init.sql.template 語法錯（envsubst 後 SQL 不合法）
# 直接看跑出來的 init.sql：
docker compose exec timescaledb cat /tmp/init.sql 2>/dev/null

# 3. 改完 init.sql.template 後，必須砍 volume 重跑（init script 只在 volume 第一次建立時跑）
make down-volumes && make up
```

### 5.3 Redis NOAUTH error

**症狀：** integration test 報 `NOAUTH Authentication required`

**處理：**
```bash
# 確認 .env 中 REDIS_PASSWORD 不為空
grep "^REDIS_PASSWORD=" .env | wc -c   # 應 > 30

# 確認 docker compose 有把 REDIS_PASSWORD 帶入
docker compose exec redis env | grep REDIS_PASSWORD

# 重啟（dot-env 改了要 docker compose down/up）
make down && make up
```

### 5.4 Qdrant Web UI 打不開

**症狀：** 瀏覽器開 http://localhost:6333/dashboard 顯示 `Unauthorized`

**這是預期行為**（v0.3.0 安全設計：dashboard 需 API key）。

**Workaround：**
- 用 `make qdrant-status` 看 collections
- 或用 Qdrant CLI / Python SDK（帶 API key）

### 5.5 healthcheck 一直 `starting`

**處理：** 等 30-60 秒。timescaledb 第一次跑 init.sh 較慢。

```bash
# 看每個 healthcheck 詳細狀態
docker inspect ta-timescaledb --format='{{json .State.Health}}' | python -m json.tool
docker inspect ta-redis --format='{{json .State.Health}}' | python -m json.tool
docker inspect ta-qdrant --format='{{json .State.Health}}' | python -m json.tool
```

### 5.6 envsubst 在 alpine container 沒裝

**症狀：** init.sh 跑 `envsubst: command not found`

**處理：** TimescaleDB image 是基於 debian-slim，預設有 envsubst。若改用 alpine 變體，需在 init.sh 加 `apk add gettext`。本專案用 `timescale/timescaledb:2.16.1-pg16`（debian-based），不會有此問題。

### 5.7 Windows Docker Desktop 啟動慢 / 卡住

```bash
# 重啟 Docker Desktop
powershell -Command "Stop-Process -Name 'Docker Desktop' -Force"
powershell -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'"
# 等 60 秒後試 docker info
```

### 5.8 port 6334（Qdrant gRPC）連不上

**症狀：** P12+ LangGraph 或 SDK 用 gRPC 連 Qdrant 失敗

**處理：**
```bash
# 確認 6334 已 expose
docker compose ps qdrant
# PORTS 欄應有 0.0.0.0:6334->6334/tcp
```

---

## 6. 備份（P19 才完整實作）

P2 階段沒有 backup script。以下是手動方式：

```bash
# PG dump
docker compose exec timescaledb pg_dump -U postgres -F custom \
  tradingagents_tw > /tmp/db_$(date +%Y%m%d).dump

# Redis save
docker compose exec redis redis-cli -a "$(grep ^REDIS_PASSWORD= .env | cut -d= -f2)" \
  SAVE
docker cp ta-redis:/data/dump.rdb /tmp/redis_$(date +%Y%m%d).rdb

# Qdrant snapshot
curl -X POST -H "api-key: $(grep ^QDRANT_API_KEY= .env | cut -d= -f2)" \
  http://localhost:6333/collections/<collection>/snapshots
```

P19 會提供 `make backup` / `make restore` / `make verify-backup`。

---

## 7. 觀察資源使用

```bash
# 即時 CPU / RAM / network
docker stats ta-timescaledb ta-redis ta-qdrant

# 預期（dev 模式）：
# - timescaledb: ~150-300 MB RAM
# - redis: ~30-100 MB RAM
# - qdrant: ~80-200 MB RAM
# - 三服務合計 < 1 GB
```
