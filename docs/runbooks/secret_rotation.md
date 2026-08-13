# Secret Rotation Runbook（Phase 18）

> 依 PLAN 第 19.4 章「Secret 管理」。所有輪替腳本都在 `scripts/rotate_*.sh`。

---

## 1. JWT `SECRET_KEY`（雙 key，每 6 個月）

### 流程
1. 先備份 `.env`（腳本會自動 `cp .env .env.bak.<ts>`）
2. 跑 rotate：
   ```bash
   ./scripts/rotate_secrets.sh
   ```
   產生新 `SECRET_KEY`、把舊的存進 `SECRET_KEY_PREVIOUS`
3. **重啟** backend + workers：
   ```bash
   make backend-restart
   make workers-restart
   ```
4. 兩個 key 並存 7 天（舊 token 仍可 decode；新 token 用新 key 簽）
5. 7 天後 finalize：
   ```bash
   ./scripts/rotate_secrets.sh --finalize
   ```
   移除 `SECRET_KEY_PREVIOUS`，再重啟一次

### Rollback
```bash
cp .env.bak.<ts> .env
make backend-restart
```

### 注意
- 7 天並存期間若還有客戶端帶舊 access token（15 min TTL），仍能 verify
- Refresh token TTL 7 天 = 並存期 → 全部 client 一定會在這 7 天內換到新 token

---

## 2. DB 帳號密碼（每 6 個月）

### 帳號分離（PLAN 第 12.x）
- `ta_migration`：DDL（migrations）
- `ta_service_rw`：backend / celery RW
- `ta_agent_ro`：agent / read-only 查詢

### 流程
```bash
# 輪 service_rw：
./scripts/rotate_db_passwords.sh ta_service_rw

# 輪 agent_ro：
./scripts/rotate_db_passwords.sh ta_agent_ro
```

腳本動作：
1. 產生新密碼 → `psql ALTER USER ... WITH PASSWORD`
2. 更新 `.env`（`TA_SERVICE_RW_PASSWORD` / `TA_AGENT_RO_PASSWORD`）
3. 提示「請重啟 backend + workers」

### 失敗排查
- 若 `psql ALTER USER` 失敗：通常是 `ta_migration` 沒有 ALTER USER 權限
  → 需要 superuser；改成走 `PGPASSWORD=<super> psql -U postgres`
- 若 backend 重啟後仍連舊密碼：通常是 redis 中 settings cache；`redis-cli flushdb`

### Rollback
```bash
cp .env.bak.<ts> .env
# DB 中的密碼已被 ALTER；需要 superuser 再 ALTER 回舊密碼
psql -U postgres -c "ALTER USER ta_service_rw WITH PASSWORD '<old>'"
```

---

## 3. Fernet `DATA_ENCRYPTION_KEY`（每年）

### 流程
```bash
./scripts/rotate_encryption_key.sh
```

腳本動作：
1. 備份 `.env` → `.env.bak.<ts>`
2. 產生新 Fernet key
3. **用舊 key 解密** `notification_settings.line_token_encrypted` 與 `telegram_bot_token_encrypted`
4. **用新 key 重新加密** → atomic UPDATE 寫回 DB（整批 transaction）
5. 更新 `.env`
6. 提示重啟

### 失敗排查
- 「解密失敗」：通常是 DB 中有用「更舊」的 key 加密的欄位 → 多輪一次
- 「DB connection error」：確認 `.env` 還在原本位置；通常重啟後 settings 重讀

### Rollback
```bash
cp .env.bak.<ts> .env
make backend-restart
# DB 內的欄位已用新 key 加密；若退回舊 key 將解密失敗
# 需要重新跑一次 rotation：./scripts/rotate_encryption_key.sh
```

### 危險警告
**這個 key 同時持有兩種角色**：(a) 加密儲存中的 secret；(b) 解密時的驗證。
若 `.env` 中的 key 與 DB 內儲存的密文加密 key 不一致，所有通知 token 都將失效。

**所以**：
- 一定要先讓腳本「atomic 寫回」成功才能更新 `.env`
- 若途中失敗（DB UPDATE 拋例外）→ `.env` 不會更新；DB 仍是用舊 key 加密 → 不需要 rollback

---

## 4. 外部 API key（人工，每 6 個月）

### Google Gemini
1. 到 https://aistudio.google.com/app/apikey 產生新 key
2. 更新 `.env` 的 `GOOGLE_API_KEY`
3. 重啟 backend
4. 在舊 key 還沒 revoke 前測一次分析 → 看 used_provider 是新 key
5. Revoke 舊 key

### Alpha Vantage / Finnhub / FinMind
同上流程；都是 dashboard → generate new → 改 `.env` → 重啟 → revoke 舊

---

## 5. 全部輪替的時程建議

| 項目 | 頻率 | 緊急輪替（疑似洩漏時） |
| --- | --- | --- |
| `SECRET_KEY` | 6 個月 | 立即 + 強制全 user logout |
| DB passwords | 6 個月 | 立即 + 重啟 backend + workers |
| `DATA_ENCRYPTION_KEY` | 1 年 | 立即 + 重新跑 rotate_encryption_key |
| Google / Alpha Vantage / Finnhub | 6 個月 | 立即（最簡單；只改 .env） |
| LINE / Telegram token | 1 年（自用） | 立即；revoke LINE channel |

---

## 6. 完整輪替演練（test 環境）

1. 建 test 用 user + 設 LINE/Telegram token + 設 quota
2. 跑一次分析 → 確認通知收到
3. 跑全部 3 個 rotation 腳本
4. 重啟服務
5. 再跑一次分析 → 確認：
   - 仍能 login（新 SECRET_KEY 簽 token）
   - LINE 仍收到通知（新 DATA_ENCRYPTION_KEY 仍能解密 token）
6. 7 天後 finalize SECRET_KEY
7. 重啟服務 → 確認仍能 login

**通過驗收後**：在 prod 環境執行同樣流程。
