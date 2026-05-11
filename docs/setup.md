# 開發環境設定（Setup Guide）

> 對應 PLAN.md 第 P0-P1 章節。本文件由 Phase 1 建立，後續 Phase 會補充。

---

## 0. 前置條件

請先完成 PLAN.md **Phase 0** 的 Pre-flight Checklist：

- ✅ Docker Desktop ≥ 4.x（dev 至少 8GB RAM）
- ✅ Python 3.11（透過 `uv python install 3.11`）
- ✅ Node.js ≥ 18（推薦 20 LTS）
- ✅ Git ≥ 2.30
- ✅ 磁碟 ≥ 50 GB free
- ✅ Git tag `pre-tw-edition-backup` 已建立
- ✅ `.env` 至少含 `GOOGLE_API_KEY=...`
- ✅ `docs/phase_progress.md` 與 `scripts/health_checks/` 已建

### Shell 環境（Windows 用戶必讀）

**Phase 0** 用 PowerShell 即可（`Test-NetConnection`、`Get-PSDrive` 等）。

**Phase 1 起所有 Bash 指令**請在以下任一環境執行：

1. **Git Bash**（推薦，最簡單）：Git for Windows 內建
2. **WSL2**（推薦長期開發）：`wsl --install`
3. ❌ **PowerShell** 不能跑 `${VAR}`、`$(uuidgen)`、`grep`、`awk`、`jq`、heredoc

---

## 1. Phase 1：原版遷移 + 新骨架（已完成）

```bash
# 切分支
git checkout -b phase/01-migration-and-skeleton

# 安裝 backend 依賴
cd backend
uv sync
uv run pre-commit install
cd ..

# 驗證
bash scripts/health_checks/phase_01.sh
```

退出條件：
- 所有 12 個驗收指令 exit code 0
- `bash scripts/health_checks/phase_01.sh` 通過
- 5+ 個 unit test 已 collect

---

## 2. Phase 2：Docker 基礎服務（✅ 完成）

```bash
make up               # 啟動 timescaledb / redis / qdrant
make down             # 停止
make logs             # 看 log
make ps               # 看狀態
make psql             # 進 psql（superuser）
make redis-cli        # 進 redis-cli（互動）
make qdrant-status    # Qdrant 健康檢查
```

driver 用三個 DB 帳號（從 .env 取對應密碼）：
- `ta_migration`：alembic 用
- `ta_service_rw`：後端業務用（DML only）
- `ta_agent_ro`：Agent 用（read only）

---

## 3. Phase 3：後端工程基礎（✅ 完成）

```bash
# 本機跑 backend（dev mode，reload）
make backend-dev

# 開另一終端
curl http://localhost:8000/health/live    # 200 + envelope
curl http://localhost:8000/health/ready   # 三服務 OK → 200
curl http://localhost:8000/health/seeded  # 暫回 false（P7 後 true）
open http://localhost:8000/docs           # Swagger UI

# 容器化跑（背景）
make backend-image    # build image
docker compose up -d backend
make backend-logs     # 跟 log
make backend-shell    # 進容器 shell
```

**Phase 3 core 模組（後續 Phase 共用）：**
- `app/core/config.py`：settings 單例（pydantic v2）
- `app/core/logging_config.py`：`from app.core.logging_config import get_logger`
- `app/core/database.py`：`get_rw_session() / get_ro_session()` (FastAPI Depends)
- `app/core/redis_client.py`：`get_redis(RedisDB.CACHE)` 等 7 個 db
- `app/core/qdrant_client.py`：`get_qdrant_client()`
- `app/core/errors.py`：`raise NotFoundError(message_zh="...")` 等
- `app/core/response_envelope.py`：`envelope_success(data, trace_id=...)`

---

## 4. Phase 4：DB Schema + Alembic（TBD）

```bash
make init-db          # alembic upgrade head + Qdrant collections + 第一個 admin
make migration-up
make migration-down
```

---

## 5. Phase 7：資料種子（TBD）

```bash
make seed-stocks      # 抓 1500+ 股票清單
make seed-admin       # 建 admin user
make backfill ARGS="--region TW --symbol 2330 --years 1"
make verify-data
```

---

## 6. Phase 15：前端啟動（TBD）

```bash
make frontend-dev     # Next.js dev mode
# 開瀏覽器：http://localhost:3000
```

---

## 7. 第一次完整 dev 環境啟動（P15 後）

```bash
# Terminal 1：DB 三服務
make up

# Terminal 2：backend
make backend-dev

# Terminal 3：frontend
make frontend-dev

# Terminal 4：celery worker（P7 後）
make up-workers

# 開瀏覽器
open http://localhost:3000
```

---

## 8. 常見問題

依 PLAN.md 第二十八章「Phase 失敗回復程序」+ 各 Phase「已知陷阱」處理。

進階：見 `docs/runbooks/` 目錄。
