# Prod 部署 SOP

> 對應 PLAN 第 31 章「部署架構」+ Phase 19。
> 用於自用伺服器（單機 Docker），非雲端 IaC。

## 0. 前置條件

- Linux / Windows + Docker Engine 27+（含 Compose v2）
- Disk ≥ 50 GB 可用空間（DB + Qdrant + backup）
- RAM ≥ 16 GB 建議
- 對外開放 port 80 + 443（防火牆設定好）
- 一組 GPG public key（用於 backup 加密）

## 1. 首次部署

### 1.1 拉 code + 環境

```bash
git clone <repo-url> /opt/tradingagents
cd /opt/tradingagents
git checkout main  # 或對應 release tag
```

### 1.2 填 `.env.prod`

```bash
cp .env.prod.example .env.prod
chmod 600 .env.prod

# 產隨機密碼（重複 8 次填到對應欄位）
python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

# 必填：
#   SECRET_KEY / DATA_ENCRYPTION_KEY（隨機 32 bytes base64）
#   POSTGRES_SUPERUSER_PASSWORD / TA_MIGRATION_PASSWORD / TA_SERVICE_RW_PASSWORD / TA_AGENT_RO_PASSWORD
#   REDIS_PASSWORD / QDRANT_API_KEY
#   ADMIN_EMAIL / ADMIN_INITIAL_PASSWORD
#   GOOGLE_API_KEY（必需，否則 LangGraph 不能跑）
#   PUBLIC_HOST（你的 domain）
#   CORS_ORIGINS（["https://你的-domain"]）
#   GPG_RECIPIENT（GPG public key user-id）
```

### 1.3 import GPG public key（給 backup 用）

```bash
gpg --import path/to/backup_pubkey.asc
# 確認：
gpg --list-keys
```

### 1.4 SSL 憑證

**Self-signed（dev/staging）**：

```bash
bash scripts/generate_self_signed_cert.sh tradingagents.local
# 或 make generate-cert
```

**Let's Encrypt（真實 prod，需有 public domain）**：

```bash
# 先 stop nginx 釋出 80
docker compose -f docker-compose.prod.yml stop nginx 2>/dev/null

docker run --rm -it \
  -v $(pwd)/docker/nginx/certs:/etc/letsencrypt \
  -p 80:80 \
  certbot/certbot:latest certonly --standalone \
    -d your-domain.tw -m admin@your-domain.tw --agree-tos --non-interactive

# 把產生的 fullchain.pem / privkey.pem 複製到 docker/nginx/certs/
cp docker/nginx/certs/live/your-domain.tw/fullchain.pem docker/nginx/certs/
cp docker/nginx/certs/live/your-domain.tw/privkey.pem docker/nginx/certs/

# 之後每 90 天 renewal
# crontab：0 3 1 * * docker run ... certbot renew
```

### 1.5 啟動 stack

```bash
make prod-up
# 或 docker compose -f docker-compose.prod.yml up -d

# 等 healthcheck（約 60s）
sleep 60
make prod-ps    # 應看到 8 個 service 都 healthy
```

### 1.6 初始化 DB + seed

```bash
# init schema + admin
make init-db
# seed stock list（約 5 分鐘抓 ~1500 筆台股 + 美股）
make seed-stocks
# 首次 backfill 一支股票（例如 2330）測試
make backfill ARGS="--region TW --symbol 2330 --years 1"
make verify-data
```

### 1.7 第一次登入

開 `https://<PUBLIC_HOST>`：
1. 信任 self-signed cert（chrome 進階 → 繼續前往）
2. admin email + ADMIN_INITIAL_PASSWORD 登入
3. 強制改密碼
4. 完成 onboarding wizard
5. 確認 LINE/Telegram 通知測試發送

## 2. 例行操作

```bash
# 看狀態
make prod-ps
make prod-logs            # tail 全部
docker compose -f docker-compose.prod.yml logs backend --tail=100

# 重啟單一服務
docker compose -f docker-compose.prod.yml restart backend

# 升級 image（依 BUILD_VERSION）
BUILD_VERSION=1.0.1 docker compose -f docker-compose.prod.yml up -d --no-deps backend frontend

# 停整個 stack（保留 volume）
make prod-down

# 完全清掉（會丟資料！）
docker compose -f docker-compose.prod.yml down -v
```

## 3. 排程任務（crontab）

```cron
# 每日 02:00 備份
0 2 * * * cd /opt/tradingagents && bash scripts/backup.sh >> docker/backups/backup.log 2>&1

# 每日 06:00 SLO 報表
0 6 * * * cd /opt/tradingagents && uv --project backend run python scripts/slo_report.py >> docs/slo_reports/slo.log 2>&1

# 每月 1 日 04:00 驗證備份
0 4 1 * * cd /opt/tradingagents && bash scripts/verify_backup.sh "$(ls -t docker/backups/full_*.tar.gz.gpg | head -1)" >> docs/dr_drills/verify.log 2>&1
```

## 4. 監控指標（v1.0：手動 + LINE）

| 指標 | 看哪 | 異常時 |
|------|------|--------|
| API 健康 | `curl -kfsS https://<host>/api/v1/health/ready` | 503 → 看 backend log |
| LLM 月成本 | 前端 `/admin/system` 或 `/api/v1/users/me/quota` | ≥ 80% 會收 LINE WARN |
| Disk usage | `df -h /var/lib/docker/volumes` | > 80% 砍舊 backup / chunk retention |
| DLQ | 前端 `/admin/pipeline` | 任何 row 都要 resolve |
| Audit chain | `make slo-report` → `slo_reports/*.json` | broken → 立即停服 + restore from backup |
| docker stats | `docker stats --no-stream` | mem/cpu > 80% 持續 → 加 resource limit |

## 5. 故障排查

### 5.1 backend 起不來

```bash
docker compose -f docker-compose.prod.yml logs backend
```

常見：
- `Settings missing required field` → `.env.prod` 漏填
- `connection refused timescaledb:5432` → wait-for-services.sh 還在等；30s 後仍未起，看 timescaledb log
- `/tmp permission denied` → 確認 `tmpfs: [/tmp:size=128M]` 在 compose

### 5.2 nginx 502

```bash
docker compose -f docker-compose.prod.yml logs nginx
```

通常是 backend 或 frontend 沒 healthy；先 `make prod-ps`。

### 5.3 cert 過期

```bash
openssl x509 -in docker/nginx/certs/fullchain.pem -noout -enddate
# 若快過期，重新跑：
make generate-cert   # self-signed
# 或 certbot renew
docker compose -f docker-compose.prod.yml restart nginx
```

## 6. 安全 checklist

- [ ] `.env.prod` 權限 600，git 不追蹤
- [ ] `docker/nginx/certs/privkey.pem` 權限 600
- [ ] GPG private key 不在 server（restore 時臨時 import）
- [ ] backup 加密後再傳到 off-site（雲端 / 異地）
- [ ] firewall 只開 80/443（DB / Redis / Qdrant 全內網）
- [ ] backend 用 read_only + cap_drop + user 1000（compose 已設）
- [ ] CSP_PROD_ENABLED=true（必開）
- [ ] HSTS 確認 cert 永久部署後再打開（nginx.conf 取消註解）
- [ ] LINE/Telegram token 加密寫 DB（dispatcher 自動處理）
- [ ] 每月 1 日 verify_backup 通過
- [ ] 每季演練 DR 情境 A 一次
