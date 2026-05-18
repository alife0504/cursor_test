# Backup / Restore 操作手冊

> 對應 Phase 19。實作於 `scripts/backup.sh` / `restore.sh` / `verify_backup.sh`。

## 0. 概念

| 元件 | 工具 | 格式 |
|------|------|------|
| TimescaleDB | `pg_dump -F custom -Z 9` | `db_TIMESTAMP.dump` |
| Qdrant | `tar czf` on volume | `qdrant_TIMESTAMP.tar.gz` |
| 打包 | `tar czf` | `full_TIMESTAMP.tar.gz` |
| 加密 | `gpg --encrypt --recipient $GPG_RECIPIENT` | `full_TIMESTAMP.tar.gz.gpg` |

預設保留 30 天（`BACKUP_RETENTION_DAYS=30`）。

## 1. 前置（一次性）

### 1.1 產 GPG key pair

如果還沒有：

```bash
gpg --gen-key
# Real name: TradingAgents Backup
# Email: backup@yourdomain.tw
# 設密碼
```

匯出 public key 並貼到所有需要備份的 server：

```bash
gpg --export -a backup@yourdomain.tw > backup_pubkey.asc
```

匯出 private key（**僅 restore 時用**，不要放 prod server）：

```bash
gpg --export-secret-keys -a backup@yourdomain.tw > backup_privkey.asc
# 存到 1Password / 加密隨身碟 / 雲端 KMS
```

### 1.2 在 prod server import public key

```bash
gpg --import backup_pubkey.asc
gpg --list-keys
```

在 `.env.prod` 填：

```
GPG_RECIPIENT=backup@yourdomain.tw
```

## 2. 跑備份

```bash
make backup
# 或 bash scripts/backup.sh
```

過程：
1. 確認 `.env.prod` + `GPG_RECIPIENT` 已 import
2. `docker compose exec timescaledb pg_dump -F custom -Z 9 -d tradingagents_tw` → `/tmp`
3. 對每個 Qdrant collection trigger snapshot
4. `tar czf` Qdrant volume → `/tmp`
5. 打包 + GPG encrypt → `docker/backups/full_TIMESTAMP.tar.gz.gpg`
6. 刪 30 天前的舊備份

成功訊息：

```
✅ Backup complete: docker/backups/full_20260518_020000.tar.gz.gpg
   保留 30 天；目前共 12 個備份
```

## 3. 排程

加 crontab：

```cron
# 每日 02:00
0 2 * * * cd /opt/tradingagents && bash scripts/backup.sh >> docker/backups/backup.log 2>&1
```

## 4. 還原（會清空 DB！）

```bash
make restore FILE=docker/backups/full_20260518_020000.tar.gz.gpg
# 或 bash scripts/restore.sh docker/backups/full_20260518_020000.tar.gz.gpg
```

過程：
1. 互動確認（輸入 `yes`），或 `RESTORE_AUTO_CONFIRM=1` 自動
2. GPG decrypt（需 private key）
3. `tar xzf`
4. `DROP DATABASE tradingagents_tw WITH (FORCE)` → `CREATE DATABASE`
5. `CREATE EXTENSION timescaledb / pgcrypto`
6. `pg_restore --no-owner --no-privileges --if-exists --clean`
7. 停 qdrant → 清 volume → 解壓還原 → 重啟

成功訊息：

```
✅ Restore complete
下一步建議：
  1. uv run python data-pipeline/scripts/verify_data.py
  2. bash scripts/verify_audit_chain.py
  3. 用 admin 登入確認
```

## 5. 驗證備份（不污染 prod）

```bash
make verify-backup FILE=docker/backups/full_20260518_020000.tar.gz.gpg
```

過程：
1. 啟獨立 `docker-compose.test-restore.yml`（timescaledb_test on 5433）
2. GPG decrypt + 解壓
3. 對 `tradingagents_tw_test` DB 跑 `pg_restore`
4. 對隔離 DB 跑 `data-pipeline/scripts/verify_data.py`
5. 自動清除 test DB（`KEEP_TEST_DB=1` 可保留）

每月跑 1 次：

```cron
0 4 1 * * cd /opt/tradingagents && bash scripts/verify_backup.sh "$(ls -t docker/backups/full_*.tar.gz.gpg | head -1)" >> docs/dr_drills/verify.log 2>&1
```

## 6. 把備份送到異地（off-site）

備份在本機毀掉就沒了。建議：

```bash
# 加密後（已加密）再 rsync / aws s3 cp / gsutil cp
rsync -avz docker/backups/full_*.tar.gz.gpg backup-host:/remote/backups/
# 或
aws s3 cp docker/backups/full_$(date +%Y%m%d)*.tar.gz.gpg s3://tradingagents-backups/
```

## 7. 故障排查

### `GPG public key 未 import`

```bash
gpg --import backup_pubkey.asc
gpg --list-keys
# 然後 .env.prod 的 GPG_RECIPIENT 必須對應到 list-keys 的 uid
```

### `docker compose ... timescaledb 未運行`

```bash
make prod-up
sleep 30
make prod-ps   # 確認 healthy
```

### `pg_dump: error: connection failed`

```bash
# 看 timescaledb log
docker compose -f docker-compose.prod.yml logs timescaledb --tail=50
# 通常是 .env.prod 的 POSTGRES_SUPERUSER_PASSWORD 對不上
```

### restore 時 `pg_restore: warning: errors ignored on restore`

通常無傷（owner / privilege 警告）。但若數量太多或含 `relation not found`，請檢查 dump 檔是否完整：

```bash
gpg --decrypt -o /tmp/full.tar.gz docker/backups/full_xxx.tar.gz.gpg
tar tzf /tmp/full.tar.gz   # 應含 db_*.dump + qdrant_*.tar.gz
```

### 備份檔太大

預設 `pg_dump -Z 9`（最大壓縮）。可調：
- chunk retention（timescaledb 自動）
- 砍 `audit_logs` 舊資料（風險：失去歷史審計）
- 改用 `pg_dump --schema=public --exclude-table=audit_logs` 分開備份

### Qdrant volume 名稱對不上

`backup.sh` 預期 volume 名 `tradingagents_qdrant_data_prod`（docker-compose.prod.yml 定義）。
若改過 compose project name，請改 `backup.sh` 的 `QDRANT_VOL` 變數。
