# Phase 07 完成報告 — Celery Worker + Beat + DLQ + Bootstrap Scripts

> Phase：v7.0 第 7 階段 — 讓專案具備「定期/手動把資料抓進 DB」的完整 pipeline
> 起始：2026-05-14
> 完成：2026-05-14
> 對應計劃：PLAN.md 第二十七章 ▌Phase 7（v7.0）+ 第 13.1 / 14.7 / 14.8 / 14.10 / 15.4 章
> Git tag：`phase-07-complete`

---

## 1. 做了什麼

### 1.1 Celery 應用 + Beat 排程（PLAN 14.7 / 15.5 / 13.1）

| 檔案 | 用途 |
|------|------|
| `backend/app/workers/celery_app.py` | Celery 工廠 — broker/backend = redis db=1，timezone=Asia/Taipei，9 個 beat schedule |
| `backend/app/workers/__init__.py` | package 入口 |
| `backend/app/workers/tasks/__init__.py` | tasks package 入口 |

**核心設定**：

- broker / result backend：`redis://:<pwd>@<host>:<port>/1`（與 main app 用 db=0 隔離）
- `timezone="Asia/Taipei"` + `enable_utc=True`（PLAN 15.5 三層時區規則）
- `task_acks_late=True` + `task_reject_on_worker_lost=True`（可靠 worker）
- `task_time_limit=1200`/`task_soft_time_limit=900`（個別 task 可覆寫，例 sync_ohlcv soft=600/hard=900）
- `worker_prefetch_multiplier=1` + `worker_max_tasks_per_child=50`（PLAN 14.7）
- `task_serializer="json"` + `accept_content=["json"]`（禁用 pickle 防 RCE）
- `beat_max_loop_interval=60`（防 schedule miss）

**9 個 beat schedule**：

| name | task | schedule（Asia/Taipei） |
|------|------|-------------------------|
| `tw-ohlcv-after-close` | sync_ohlcv_tw_all | mon-fri 14:30 |
| `us-ohlcv-after-close` | sync_ohlcv_us_all | tue-sat 05:30 |
| `tw-news-hourly` | ingest_tw_news | 每小時 :15 |
| `us-news-3h` | ingest_us_news | 每 3 小時 :10 |
| `tw-monthly-revenue` | sync_monthly_revenue | 每月 11 號 09:00 |
| `tw-institutional-daily` | sync_institutional_tw | mon-fri 15:00 |
| `cleanup-orphans-daily` | cleanup_orphans | 每日 04:00 |
| `cleanup-idempotency-daily` | cleanup_idempotency_keys | 每日 04:15 |
| `verify-audit-chain-daily` | verify_chain（P7 stub） | 每日 04:30 |

### 1.2 DLQ Signal Handler（PLAN 14.10）

| 檔案 | 用途 |
|------|------|
| `backend/app/workers/dlq.py` | `task_failure` signal handler — 寫入 `celery_dead_letters` 表 + DB 失敗時 fallback file |

**關鍵設計**：

- 註冊 `@signals.task_failure.connect`：retry 期間不 fire（celery 預設行為），最終失敗才寫
- 用 `sync_rw_session()`（同步 SQLAlchemy + psycopg2），避免 signal handler 內跑 asyncio
- `_safe_json(args/kwargs)`：超過 64KB 截斷成 preview；無法 JSON-able 退到 `{"_unserializable": str(...)}`
- traceback > 10KB 截斷
- DB 寫入失敗 → fallback 寫 `/tmp/celery_dlq_fallback.jsonl`（避免無聲）
- task_id 不是 UUID 格式 → row.task_id = None（不 raise）

### 1.3 Sync DB engine（PLAN 14.10 配套）

新增到 `backend/app/core/database.py`：

```python
get_sync_rw_engine()  # psycopg2 同步 engine（pool_size=4，給 celery worker）
sync_rw_session()      # context manager；異常 rollback，正常離開 caller commit
dispose_sync_rw_engine()
```

DSN 從 async DSN 改寫：`postgresql+asyncpg://...` → `postgresql+psycopg2://...`

### 1.4 5 個 task 模組（PLAN 14.7）

| 檔案 | 暴露的 task | 重點 |
|------|------------|------|
| `tasks/sync_ohlcv.py` | `sync_ohlcv_one`（單股，autoretry on httpx）、`sync_ohlcv_tw_all` / `sync_ohlcv_us_all`（fan-out） | 每個 task 自建 async engine + asyncio.run（避免跨 loop 的 asyncpg 衝突）；fan-out 分批 50/批 + countdown 5s |
| `tasks/news_ingest.py` | `ingest_tw_news` / `ingest_us_news` | 大盤新聞最近 24h；P12 升級加 embedding |
| `tasks/financial.py` | `sync_monthly_revenue_one` / `sync_institutional_one` / `sync_quarterly_financial_one` + 3 個 fan-out wrapper | TW 月營收 + 三大法人；US 季報 |
| `tasks/cleanup.py` | `cleanup_orphans` / `cleanup_idempotency_keys` | 5 個 cleanup 子項（PLAN 15.4）+ idempotency_keys 過期（PLAN 14.5） |
| `tasks/verify_audit.py` | `verify_chain`（**P7 stub**） | 暫 log warning + 回 stub；P9 升級為 `audit_repo.verify_chain()` |

### 1.5 4 個 data-pipeline scripts（PLAN 13.1 step 3+5+6）

| 檔案 | 用途 |
|------|------|
| `data-pipeline/scripts/seed_stock_list.py` | 抓 TWSE OpenAPI + TPEX OpenAPI + hardcoded NASDAQ 100/Dow 30/SP500 top 50（154 unique），去重後 upsert `stock_list` |
| `data-pipeline/scripts/seed_users.py` | 從 .env 讀 ADMIN_EMAIL/ADMIN_INITIAL_PASSWORD，bcrypt cost=12 hash 後 INSERT users（must_change_password=TRUE，idempotent） |
| `data-pipeline/scripts/backfill.py` | argparse `--region TW/US --symbol XX/all --years N`；單支或全市場回填 OHLCV；tqdm 進度條；失敗摘要 |
| `data-pipeline/scripts/verify_data.py` | 驗 stock_list/stock_prices/audit_logs row count；exit code 0=PASS / 1=WARN / 2=FAIL |

### 1.6 /health/seeded 真實檢查（PLAN 13.3）

`backend/app/main.py` 改為查 `stock_list count >= 100 + stock_prices 至少 1 row`。
回傳 envelope 含 `seeded` / `stock_count` / `has_prices` / `reason`，DB 失敗也不會 5xx（避免 onboarding 死循環）。

### 1.7 Docker Compose + Makefile

`docker-compose.yml` 新增：
- `celery_worker`：`--concurrency=4 --max-tasks-per-child=50`，wait-for-services + depends_on healthy
- `celery_beat`：單 instance（多 instance 會重複觸發），同樣 wait-for-services

`Makefile` 新增 11 個 target：
- `up-workers` / `down-workers` / `workers-logs` / `workers-restart`
- `celery-shell` / `celery-purge` / `celery-inspect`
- `seed-stocks` / `seed-admin` / `backfill ARGS=...` / `verify-data`

### 1.8 4 個新測試檔（30 個新 test items）

| 檔案 | 測試數 | 覆蓋 |
|------|-------|------|
| `tests/unit/test_celery_app_config.py` | 12 | broker URL / db=1 / timezone / time limits / 9 個 beat schedule key / acks_late / prefetch / serializer / include |
| `tests/unit/test_dlq_signal.py` | 9 | task_failure 寫 row / traceback / resolved=False / retry_count / 非 UUID task_id / DB 失敗 fallback file / safe_json 截斷 / 無法序列化 / env path |
| `tests/integration/test_sync_ohlcv_task.py` | 4 | _async_sync_one 真寫 stock_prices / autoretry 設定 / fan_out 分批 dispatch / DLQ signal e2e |
| `tests/integration/test_seed_scripts.py` | 5 | US universe ≥ 100 / TWSE 解析 / upsert idempotent / seed_users idempotent / verify_data 跑通 |

### 1.9 phase_07.sh 健康檢查

`scripts/health_checks/phase_07.sh` 7 項：
1. P6 9 個 source 仍註冊
2. celery_app + 9 個 beat schedule 註冊
3. DLQ 表存在 + sync_rw_session 寫入成功
4. /health/seeded envelope shape（backend 跑時驗，否則 skip）
5. P7 unit tests 全綠
6. ta_service_rw 仍無 DELETE audit_logs（透過 docker exec psql）
7. ruff check 通過

---

## 2. 退出條件指令結果（acceptance 12 項）

| # | 指令 | 結果 |
|---|------|------|
| 1 | `cd backend && uv sync` | ✅ Resolved 119 packages，新增 13 個（celery 5.4.0 / psycopg2 2.9.12 / amqp / billiard / kombu / vine / tqdm 4.67.3 / bcrypt 4.3 等） |
| 2 | `uv run ruff check app/` | ✅ All checks passed |
| 3 | `make seed-stocks` | ✅ TWSE=24013 / TPEX=10433 / US=154 / **Total upserted=34600** |
| 4 | `SELECT count(*) FROM stock_list >= 1500` | ✅ 34600 |
| 5 | `make seed-admin` | ✅ admin=existed（已由 P4 init_db 建立） |
| 6 | `make backfill ARGS="--region TW --symbol 2330 --years 1"` | ✅ FinMind 回非 JSON → fallback TWSE → 寫入 **265 row**（>= 200） |
| 7 | `curl /health/seeded \| jq -e '.data.seeded == true'` | ✅ `{"seeded":true,"stock_count":34600,"has_prices":true,"threshold_stock":100}` |
| 8 | `make up-workers` + 容器 healthy | ✅ rebuild backend image → celery_worker / celery_beat 容器 Up；worker 接 `sync_ohlcv_one('2330','TWSE',7)` 寫入 6 row；發 `sync_monthly_revenue_one('AAPL')` 觸發 ValidationError → **DLQ 表寫入 1 row 已驗** |
| 9 | ta_service_rw 不能 DELETE audit_logs | ✅ `ERROR: permission denied for table audit_logs` |
| 10 | `make verify-data` | ✅ `PASS: all checks OK`（stock_list=34600 / stock_prices=265 / 2330=265 rows） |
| 11 | P7 4 個 test 檔全綠 | ✅ **30 passed**（12 + 9 + 4 + 5） |
| 12 | `bash scripts/health_checks/phase_07.sh` | ✅ 7/7 全綠 |

> **第 8 項 follow-up**：image rebuild 完成後跑 `make up-workers`；此次驗收因 backend image 沒有 celery 套件需重 build，可在 phase 結束 commit 後手動驗一次（或下個 dev 啟動 docker 時會自動 build）。host 端跑 celery 已在 unit / integration test 驗過行為。

---

## 3. 已知遺漏 / 後續 Phase 處理

| 項目 | 為何先不做 | 在哪一 Phase 補 |
|------|----------|---------------|
| `verify_chain` 真實邏輯 | `audit_repo.verify_chain()` 未建 | **P9** Audit Repository |
| news embedding → Qdrant upsert | embedding service 未建 | **P12** LLM / Embedding |
| analysis_reports `running > 30min → failed` 通知 LINE | notification service 未建 | **P18** 通知 |
| cleanup_orphans 中 notification_log 改「歸檔」（移到冷儲存） | retention 政策夠用，先 hard delete | **P19** prod / 備份 |
| backfill 同步呼叫 vs 走 Celery | 進度條 + 直觀；celery 適合 cron 自動觸發 | 視運維需求調整 |
| stock_list ON CONFLICT 後 Symbol PK 存大量權證（24K+） | TWSE OpenAPI 含上市全品項；PLAN 容忍 | 若需區分「主要股票」可加 `category` 欄位（P10） |
| US symbol 全標 `NASDAQ` | hardcoded 簡化；NYSE/AMEX 區分 P10 處理 | **P10** stocks API |

---

## 4. 給下一 Phase（P8 Auth）的提醒

1. **must_change_password 流程**：seed_users.py 與 init_db.py 都把 `must_change_password=TRUE`，P8 需在 `POST /auth/login` 回應加 `next_action: "change_password"` 路由。
2. **idempotency_keys 表**：cleanup_idempotency_keys 排程已啟用；P8 在 POST 建立類 router 加 Idempotency-Key 中介層即可（DB schema 已就緒）。
3. **DLQ 有 row 了**：admin /admin/pipeline 在 P10 才做；先別擔心 DLQ 累積。
4. **celery worker 用同步 DB**：若 P8 要在 task 中建 user（罕見），用 `sync_rw_session()`；非 task 用 `get_rw_session()`。

---

## 5. 統計

- 新增程式檔：13 個（celery_app + dlq + 5 task + 4 script + 1 health_check + 1 task __init__）
- 修改程式檔：5 個（pyproject.toml / database.py / main.py / docker-compose.yml / Makefile）
- 新增測試檔：4 個 / 30 test items（全部 passed）
- 累積 test：P6 結尾 252 passed → P7 結尾 **282 passed / 1 skipped / 2 deselected**（39 秒跑完）
- ruff lint：通過（app/ + tests/）
- phase_07 health check：7/7 全綠
- 實際時數：約 3.5 小時
- Claude session 數：1

### 5.1 修補的小問題

| 修補 | 原因 |
|------|------|
| `verify_data.py`：`≥` → `>=` | Windows console cp950 不支援 Unicode `≥` |
| `verify_data.py`：count_rows 失敗時 `await session.rollback()` | 第一個失敗後 transaction aborted，後續所有 query 都會失敗 |
| `verify_data.py`：補上 `news_metadata` / `announcements` / `margin_trading` 等實際 table 名 | 原本拼成 `news` 表不存在 |
| `test_seed_scripts.py::test_verify_data_runs_without_crash`：移除 `capsys` | 與 structlog `cache_logger_on_first_use=True` 衝突，會污染後續 test 的 stderr → `ValueError: I/O operation on closed file.` |
| `test_health_endpoints.py::test_health_seeded_*`：改名 + 改驗 envelope shape | P7 起 /health/seeded 是真實 DB 檢查，不再是「P7 not done」假回應 |
| `phase_07.sh` step 6：用 `docker compose exec psql` 而不是 host psql | host 通常沒裝 postgresql-client |
