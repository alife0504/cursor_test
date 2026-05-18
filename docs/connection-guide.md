# TradingAgents-TW 連線指南 — 第一次使用

> v1.0 — 自用 Secure Edition。
> 本文件目標：把一台乾淨機器，從 0 帶到「第一個分析跑出來」。

---

## 0. 確認環境

| 項目 | 最低需求 | 驗證指令 |
|------|---------|---------|
| Docker Desktop | ≥ 4.x，整合 WSL2 / Linux | `docker --version` + `docker compose version` |
| Git | ≥ 2.30 | `git --version` |
| Node.js（僅 dev 模式需要） | 20.x | `node --version` |
| Python（僅 dev 模式需要） | 3.11 + uv | `uv --version` |
| 主機記憶體 | ≥ 16 GB | — |
| 磁碟剩餘 | ≥ 30 GB | — |
| 作業系統 | Windows 10/11、Linux、macOS 12+ | — |

> 純 prod 模式：只需 Docker；不需要 Node / Python 本機環境。

---

## 1. clone 與 env 設定

```bash
# 1. clone（或直接用本機 C:\Projects\TradingAgents）
git clone <repo-url> TradingAgents-TW
cd TradingAgents-TW

# 2. 複製 prod env 範本
cp .env.prod.example .env.prod

# 3. 用文字編輯器填好以下「必須改」的值：
#    POSTGRES_PASSWORD              (DB 密碼，自選強密碼)
#    QDRANT_API_KEY                 (32+ 字隨機，建議 openssl rand -hex 32)
#    REDIS_PASSWORD                 (任意強密碼，可空)
#    SECRET_KEY                     (Flask/FastAPI 簽章用，openssl rand -hex 32)
#    JWT_SECRET_KEY / JWT_SECRET_KEY_NEXT (兩把都填，rotation 用)
#    FERNET_KEY                     (python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
#    ADMIN_EMAIL / ADMIN_INITIAL_PASSWORD  (首次登入後強制改密碼)
#    GOOGLE_API_KEY                 (Gemini Flash 預設 LLM，必填)
#    OPENAI_API_KEY                 (fallback 鏈第 2 順位，可選)
#    ANTHROPIC_API_KEY              (fallback 鏈第 3 順位，可選)
#    FINMIND_TOKEN                  (台股主資料源 token，免費版即可)
#    ALPHA_VANTAGE_API_KEY          (美股備援，每分鐘 5 次免費)
#    LINE_NOTIFY_TOKEN              (可選，要 LINE 通知才填)
#    TELEGRAM_BOT_TOKEN             (可選，要 TG 通知才填)
#    GPG_RECIPIENT                  (備份加密用，gpg --list-keys 取得)
#    BACKUP_DIR                     (主機絕對路徑，建議 D:/ta_backups 或 /backup)
```

詳細欄位用途：`.env.prod.example` 內每行有註解。

---

## 2. 產生 self-signed TLS 憑證

```bash
bash scripts/generate_self_signed_cert.sh
```

- 結果寫到 `docker/nginx/certs/cert.pem` 與 `key.pem`。
- 憑證剩 < 30 天會自動重產。
- 首次 Chrome 訪問 `https://localhost` 會警告 → 「進階」→「仍要前往」即可（自用環境）。

> 真正放網際網路 → 改用 Let's Encrypt + 真實憑證；參考 `docs/runbooks/prod_deployment.md` 第 5 節。

---

## 3. 啟動全部服務

```bash
make prod-up
```

這會啟動 8 個 container：
- `ta-timescaledb` — 資料庫
- `ta-redis` — cache / queue / pubsub / blacklist
- `ta-qdrant` — vector DB（agent memory）
- `ta-backend` — FastAPI + uvicorn workers
- `ta-celery-worker` — Analyst / pipeline 背景任務
- `ta-celery-beat` — 排程器（9 排程：seed_stocks、sync_ohlcv、verify_audit 等）
- `ta-frontend` — Next.js prod build
- `ta-nginx` — HTTPS gateway（唯一對外的 port 443）

確認 healthy（等 30-60 秒）：

```bash
make prod-ps
# 全部 STATUS 應該是 "Up X minutes (healthy)"
```

若某個 service 一直 unhealthy：

```bash
make prod-logs   # 全部 log
docker compose -f docker-compose.prod.yml logs <service-name> --tail=100
```

常見問題見 `docs/runbooks/prod_deployment.md` 第 7 節。

---

## 4. 確認 SLO 跑得起來

```bash
make slo-report
```

第一次跑會：
- 從 audit_logs / analysis_reports / data_sources / nginx access log 計算 5 個 SLI
- 寫到 `docs/slo_reports/YYYY-MM-DD.json`
- 任一 SLO breach → 廣播 `system.alert` 到 Redis pubsub

第一次跑沒資料是正常的，所有 SLI 應為 `null` 或剛剛跑的數字。

---

## 5. 開啟瀏覽器

進 `https://localhost`：

1. 信任 self-signed 憑證（Chrome：進階 → 仍要前往）
2. 看到登入頁面（繁中）

> **不要用 `http://localhost:8000`** — backend port 在 prod compose 設成 `expose` 不對外，只有 nginx 走 443。

---

## 6. 第一次登入

- 帳號：`.env.prod` 中的 `ADMIN_EMAIL`
- 密碼：`.env.prod` 中的 `ADMIN_INITIAL_PASSWORD`

系統會：
1. 強制改密碼（依密碼策略：≥ 12 字、4 類字元、不能跟 email 相關、最近 5 次不能重複）
2. Onboarding：歡迎頁 + 設定一個自選股
3. 跳到 `/dashboard`

---

## 7. 跑第一個分析

1. **左側 Sidebar** → 「自選股清單」(`/screener/watchlist`)
2. 加 `2330`（台積電）—輸入「2330」或「台積電」會自動找到
3. **左側 Sidebar** → 「新增分析」(`/analysis/new`)
4. Step 1：選 `2330`
5. Step 2：勾選 4 個 Analyst（market / fundamental / news / sentiment）
6. Step 3：LLM 選 `Gemini Flash`（最便宜）
7. Step 4：辯論輪數選 `1`（最快，~2 分鐘）
8. 確認預估費用（~ $0.05 USD）+ 預估時間（~ 2 分鐘）
9. 「提交」→ 跳到 `/analysis/[id]`
10. 看 **AgentFlowGraph** 動畫進度（節點依序變綠）
11. 1-3 分鐘後完成 → 看 Tabs（Overview / Analysts / Debate / Report）
12. 看 `signal.action`（BUY / HOLD / SELL）和 `signal.confidence`

完成後，系統會自動建一張 `PendingOrder`（如果 signal != HOLD）。
你需要去 `/portfolio/orders` 手動「核准」才會視為成交（系統不直連券商）。

---

## 8. 設定 LINE / Telegram 通知（可選）

1. 進 `/notifications`
2. 填 LINE Notify token 或 Telegram chat_id
3. 按「測試發送」→ 手機應收到 `「測試訊息」`
4. 訂閱事件：勾選「分析完成」、「訂單核准」、「資料源熔斷」等

詳細：見「使用者指南」`docs/user-guide.md` 通知頁章節。

---

## 9. 設定每日備份

backup.sh 不會自己跑；你需要把它排入 cron / Task Scheduler。

### Linux / macOS（cron）

```bash
crontab -e
# 加入：每天 02:00 跑備份
0 2 * * * cd /path/to/TradingAgents && make backup >> /var/log/ta-backup.log 2>&1
```

### Windows Task Scheduler

1. 開「工作排程器」
2. 建立基本工作：每天 02:00
3. 動作：執行程式
4. 程式：`C:\Program Files\Git\bin\bash.exe`
5. 引數：`-c "cd /c/Projects/TradingAgents && make backup"`

每月手動跑一次還原驗證（10-15 分鐘）：

```bash
make verify-backup FILE=backups/ta_backup_YYYYMMDD.tar.gz.gpg
```

詳細：`docs/runbooks/backup_restore.md`。

---

## 10. 常用維運指令

| 動作 | 指令 |
|------|------|
| 看全部 service | `make prod-ps` |
| 看某個 service log | `docker compose -f docker-compose.prod.yml logs <name> -f` |
| 重啟所有 service | `make prod-restart` |
| 手動跑 SLO 報表 | `make slo-report` |
| 手動跑備份 | `make backup` |
| DR 演練（情境 A） | `make dr-drill-a` |
| 進 DB psql | `docker exec -it ta-timescaledb psql -U postgres tradingagents` |
| 進 Redis cli | `docker exec -it ta-redis redis-cli` |
| 停掉全部 | `make prod-down` |

---

## 11. 常見問題（FAQ 精選）

### Q1：服務一直 unhealthy？
看具體 log：
```bash
docker compose -f docker-compose.prod.yml logs <service-name> --tail=200
```
最常見：
- TimescaleDB 第一次啟動慢（等 60 秒）
- Backend 等 DB 還沒準備好（`wait-for-it.sh` 已處理，重啟一次）
- nginx cert 路徑錯（`bash scripts/generate_self_signed_cert.sh`）

### Q2：登入失敗 `401`？
- 密碼錯：先用 `ADMIN_INITIAL_PASSWORD` 而非已改過的
- Lockout：連續 5 次錯誤密碼會鎖 15 分鐘，去 DB 改 `users.locked_until = NULL` 解鎖
- Cookie：清掉瀏覽器 cookies 重試

### Q3：分析卡在 `running` 30 分鐘？
- 看 Celery worker log：`docker compose -f docker-compose.prod.yml logs celery_worker --tail=200`
- 確認 GOOGLE_API_KEY 還有額度（Gemini Flash 免費版每分鐘 60 次）
- 看 `analysis_reports` 表的 `error_msg`：`docker exec ta-timescaledb psql -U postgres tradingagents -c "SELECT id, status, error_msg FROM analysis_reports WHERE status='running';"`
- 啟動 `cleanup_orphans` task 兜底（已排在 beat 30 分鐘跑一次）

### Q4：LLM 月配額用盡？
- 進 `/admin/users` → 找用戶 → 改 `monthly_llm_budget_usd`
- 或直接 SQL：`UPDATE users SET monthly_llm_budget_usd = 50 WHERE email = '...';`
- 配額計算詳見 `docs/runbooks/llm_providers.md`

### Q5：DB 損壞，要還原？
1. 找到最近的備份：`ls -lt backups/ | head -5`
2. 跑：`make restore FILE=backups/ta_backup_YYYYMMDD.tar.gz.gpg`
3. 詳見 `docs/runbooks/disaster_recovery.md` 情境 A

更多 FAQ 見 `docs/user-guide.md` 與 `docs/runbooks/`。

---

## 12. 下一步

- 第一個分析跑通 → 看 [使用者指南 `docs/user-guide.md`](user-guide.md) 學 18 頁怎麼用
- 想懂底層 → 看 [PLAN.md](../PLAN.md) 第 2-10 章
- 想自己加 Analyst → 看 [docs/runbooks/agents.md](runbooks/agents.md)
- 想串新資料源 → 看 [docs/runbooks/data_sources.md](runbooks/data_sources.md)
- v1.1 起想擴充 → 看 [PLAN.md 第 33 章後續延展路線圖](../PLAN.md)

歡迎使用 TradingAgents-TW v1.0。
