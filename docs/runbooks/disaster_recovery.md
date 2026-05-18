# 災難復原（DR）SOP

> 對應 PLAN 第 32 章 + Phase 19。
> **RTO = 60 分鐘 / RPO = 24 小時**

## 0. 演練排程

| 情境 | 頻率 | 工具 |
|------|------|------|
| A. DB 損毀 | **每季** | `scripts/dr_drill_a.sh`（自動化） |
| B. Qdrant 損毀 | 半年 | 手動（見下） |
| C. Audit 偵測竄改 | 半年 | 手動 |
| D. 整機損毀 | 半年 | 手動（含新機器架設） |
| E. LLM 持續失敗 | 每季 | 手動（注 .env 切 provider） |
| F. 資料源全失敗 | 半年 | 手動（CB 已自動，演練回復） |

## 1. 情境 A — TimescaleDB 損毀（已腳本化）

```bash
make dr-drill-a
# 或：bash scripts/dr_drill_a.sh
```

腳本流程：

1. `backup.sh` → 取得最新 `full_*.tar.gz.gpg`
2. `docker compose stop backend celery_worker celery_beat`
3. `docker compose stop timescaledb` → `docker volume rm tradingagents_timescaledb_data_prod`
4. `docker compose up -d timescaledb` → 等 healthy（init.sh 跑完）
5. `restore.sh <最新備份>`（含 RESTORE_AUTO_CONFIRM=1）
6. `docker compose up -d backend celery_worker celery_beat`
7. `verify_data.py` + `verify_audit_chain.py`
8. 寫 `docs/dr_drills/scenario_a_YYYYMMDD.md`（含各步驟耗時 + RTO 對比 60 分）

### 預期耗時（依資料量）

| 資料量 | backup | restore | 總 RTO |
|--------|--------|---------|--------|
| < 1 GB | 1 min | 1 min | < 5 min |
| 1-10 GB | 5 min | 5 min | < 20 min |
| 10-50 GB | 15 min | 20 min | < 60 min |

若實測 > 60 min，須調整：
- pg_dump 加 `-j 4`（並行）
- 改用 base backup + WAL replication（v1.1）
- 拆 hypertable chunk（已 retention）

## 2. 情境 B — Qdrant 索引損毀

Qdrant 損毀通常表現為：
- `/collections/{name}` 回 404 但 DB 還有 news/announcement
- search 結果亂跳 / 空回

**還原（兩種選擇）：**

**選項 1：從備份還原（最快）**

```bash
# 1. 停 qdrant
docker compose -f docker-compose.prod.yml stop qdrant

# 2. 清 volume
docker volume rm tradingagents_qdrant_data_prod

# 3. 拉 GPG 解開最新備份的 qdrant tar
gpg --decrypt -o /tmp/full.tar.gz docker/backups/full_<latest>.tar.gz.gpg
tar xzf /tmp/full.tar.gz -C /tmp/
docker run --rm \
  -v tradingagents_qdrant_data_prod:/qdrant \
  -v /tmp:/backup:ro \
  alpine:3.20 \
  tar xzf /backup/qdrant_<TIMESTAMP>.tar.gz -C /qdrant

# 4. 重啟
docker compose -f docker-compose.prod.yml up -d qdrant
```

**選項 2：重新 ingest（fresh 但慢）**

```bash
# 1. 重建空 collections
make init-db  # 會跑 qdrant_init 建 7 個 collection（空）

# 2. 重跑 30 天新聞 ingest
docker compose -f docker-compose.prod.yml exec celery_worker \
  uv run celery -A app.workers.celery_app call \
    backend.app.workers.tasks.news_ingest_tw.news_ingest_tw_backfill --args='[30]'
```

## 3. 情境 C — Audit 偵測竄改

**訊號：** `make slo-report` 顯示 `audit_integrity.passed = false`，且 `broken_count > 0`。

```bash
# 1. 立即停 backend（停寫入）
docker compose -f docker-compose.prod.yml stop backend celery_worker

# 2. 立即從可信備份還原 audit_logs
gpg --decrypt -o /tmp/full.tar.gz docker/backups/full_<前一個可信備份>.tar.gz.gpg
tar xzf /tmp/full.tar.gz -C /tmp/

# 只還原 audit_logs（不動其他表）
docker compose -f docker-compose.prod.yml exec -T timescaledb \
  pg_restore -U postgres -d tradingagents_tw \
    -t audit_logs --clean --no-owner \
    < /tmp/db_<TIMESTAMP>.dump

# 3. 重新校驗
docker compose -f docker-compose.prod.yml exec backend \
  uv run python scripts/verify_audit_chain.py

# 4. 調查
#    - 看 broken_ids 對應的 actor_id / action / timestamp
#    - 對應 nginx access log（同 trace_id）
#    - 對應 system log（誰登入過 ta_service_rw 帳號？）

# 5. rotate ta_service_rw 密碼 + SECRET_KEY
bash scripts/rotate_db_passwords.sh
bash scripts/rotate_secrets.sh

# 6. 重啟
docker compose -f docker-compose.prod.yml up -d backend celery_worker
```

## 4. 情境 D — 整機損毀

需要新機器：

```bash
# 1. 新機器：裝 Docker + clone
git clone <repo-url> /opt/tradingagents
cd /opt/tradingagents
git checkout <受損機器的 commit hash>

# 2. 從異地拉回 .env.prod + DATA_ENCRYPTION_KEY + GPG private key
#    （從加密隨身碟 / 雲端 KMS）

# 3. 從異地拉回最近備份檔
scp backup-server:/backups/full_<latest>.tar.gz.gpg docker/backups/

# 4. import GPG private key（才能 decrypt）
gpg --import /tmp/backup_privkey.asc

# 5. 啟 stack（但不要 init-db，因為要 restore）
docker compose -f docker-compose.prod.yml up -d timescaledb redis qdrant
sleep 30

# 6. restore
bash scripts/restore.sh docker/backups/full_<latest>.tar.gz.gpg

# 7. 起其他服務
docker compose -f docker-compose.prod.yml up -d

# 8. 驗證
make verify-data
make slo-report
```

## 5. 情境 E — LLM 持續失敗（fallback chain 都壞）

```bash
# 1. 看 fallback chain log
docker compose -f docker-compose.prod.yml logs backend | grep "llm_chain"

# 2. 若全部 provider 失敗
#    a. 改 .env.prod：把 LLM_DEFAULT_PROVIDER 換到還活著的
#    b. 重啟 backend
docker compose -f docker-compose.prod.yml restart backend

# 3. 若是 API key 過期 / quota 用完
#    換新 key → 重啟

# 4. 通知用戶（前端會自動標 LLM unavailable）
#    pending analyses 自動 retry（celery）
```

## 6. 情境 F — 資料源全失敗

```bash
# 1. CB 已自動 OPEN，前端會標「資料延遲」
# 2. 系統用快取運作（FinMind/yfinance/Alpha 都會 24h cache）
# 3. 等資料源恢復後手動 reset CB
docker compose -f docker-compose.prod.yml exec backend \
  uv run python -c "from app.core.circuit_breaker import get_all_breakers; [b.reset() for b in get_all_breakers().values()]"

# 4. backfill 漏掉的時段
make backfill ARGS="--region TW --symbol 2330 --days 7"
```

## 7. 演練紀錄

每次演練後，務必寫入：

- `docs/dr_drills/scenario_{a,b,...}_YYYYMMDD.md`
- 內容：實際 RTO / 各步驟耗時 / 遇到的問題 / 改善建議

情境 A 的腳本會自動寫；其他情境請手動寫。

## 8. 復原後 checklist

- [ ] 全部 service `make prod-ps` healthy
- [ ] `curl https://<host>/api/v1/health/ready` 200
- [ ] `make verify-data` 通過
- [ ] `make slo-report` 全綠（audit_integrity = true）
- [ ] 用 admin 登入 + 跑一次 2330 分析測試
- [ ] LINE/Telegram 收到「DR 完成」訊息（手動發）
- [ ] 把演練報告 commit 進 git
