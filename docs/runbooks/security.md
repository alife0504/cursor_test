# Runbook：安全 middleware 問題排查

## 1. Rate limit 一直擋（429 連連）

```bash
# 看哪一層擋住
docker compose exec redis redis-cli -n 2 -a $REDIS_PASSWORD KEYS 'rate:*'

# 手動清某層
docker compose exec redis redis-cli -n 2 -a $REDIS_PASSWORD DEL 'rate:login:<ip>'

# 全清（緊急）
docker compose exec redis redis-cli -n 2 -a $REDIS_PASSWORD FLUSHDB
```

調整 limit：改 `app/core/rate_limit.py` 的 `L1_GLOBAL` / `L2_LOGIN` 等常數，**不要在 prod 隨意放寬**。

## 2. CSRF 一直 403

檢查 client 是否：
1. 從 login 回應的 `csrf_token` cookie 取值（非 httpOnly）
2. 在後續 POST/PUT/PATCH/DELETE 帶 `X-CSRF-Token: <csrf_token cookie 值>`
3. 同時把 `csrf_token` cookie 一起送出

豁免路徑：`/api/v1/auth/login`, `/api/v1/auth/password-reset`, `/api/v1/auth/password-reset/confirm`。
若要加入新的豁免（例如 webhook），改 `app/core/csrf_middleware.py` 的 `CSRF_EXEMPT_PATHS`。

## 3. Audit chain 斷裂

```bash
# 跑完整檢查
cd backend && uv run python ../scripts/verify_audit_chain.py

# 只檢查最近 1 小時
cd backend && uv run python ../scripts/verify_audit_chain.py --since 2026-05-15T00:00:00+00:00
```

斷裂可能原因：
- 有人用 superuser 手動 DELETE / UPDATE audit_logs
- TimescaleDB chunk 損壞（極罕見）
- baseline 0012 trigger 在極端並發下未能正確序列化（已知議題；用 chain-link 驗法繞過）

緊急時：
1. 先 `pg_dump audit_logs` 備份
2. 用 verify_chain 找出斷點
3. 評估是否可從備份還原（PG superuser 寫入或重建）

## 4. AuditMiddleware 寫入失敗

middleware 永遠不擋 response，但 audit log 會丟。看 backend log：
```
{"event": "audit.write_failed", "error": "OperationalError", ...}
```

常見原因：
- DB 連線暫時斷
- audit_logs 表權限被改（ta_service_rw 應有 INSERT）

復原：恢復 DB / 權限後自動恢復，不需要手動干預。

## 5. Body size 413 誤判

若合理 request body > 1 MB（例如批次上傳）：
- 短期：調大 `app/core/body_size_middleware.py` 的 `DEFAULT_MAX_BODY_BYTES`
- 長期：對該 endpoint 改 streaming，繞過此 middleware

## 6. CSP 阻擋第三方資源

dev 已開 `'unsafe-inline'` + `'unsafe-eval'`，極少擋到。
prod 將進 nonce-based（P18）；屆時 inline script 需帶 `nonce-{value}` 才能執行。

## 7. SECRET_KEY rotation 後 audit chain

audit chain 不依賴 SECRET_KEY，rotation 不會影響 audit。

## 8. Celery `verify_audit.verify_chain` task log

```
{"task": "app.workers.tasks.verify_audit.verify_chain", "status": "ok"}      # 正常
{"task": "app.workers.tasks.verify_audit.verify_chain", "status": "broken",  # 異常
 "broken_count": 3, "broken_ids": [1234, 1235, 1236]}
```

異常時：
- 立即跑 `verify_audit_chain.py --since <recent>` 確認
- 通知 admin（P18 LINE/Telegram）
- 不要立刻 restart 服務（先保留現場）

---

## 9. Phase 18 — 密碼安全 SOP

> PLAN 第 19.1 章。所有政策已實作於 `app/core/password_policy.py` + `app/models/user.PasswordHistory`。

- **複雜度**：≥ 12 字元 + 4 類字元（大寫 / 小寫 / 數字 / 特殊符號）
- **bcrypt cost = 12**（`app/core/security.hash_password`）
- **密碼歷史**：最近 5 次不可重複（`password_history` 表，change-password / reset-password 時比對）
- **Lockout**：5 次失敗 → 15 分鐘鎖（rate_limit L2 + user.lockout_until）
- **強制改密碼**：
  - 由 admin 建立的初始密碼：`must_change_password=True`，首次登入後強制改
  - **90 天強制週期：v1.0 暫不啟用**（自用單機）
  - v1.1 可開：在 `app/core/password_policy.py` 加 `MAX_AGE_DAYS = 90` 並用 celery beat 每天掃描

---

## 10. Phase 18 — CSP nonce 排錯

dev 模式 CSP 含 `unsafe-eval`（Next.js HMR 需要）。Prod 模式由後端
`SecurityHeadersMiddleware.dispatch` 為每 request 產生 nonce 並寫到
`Content-Security-Policy` header（`script-src 'nonce-<xxx>' 'strict-dynamic'`）。

### 排錯
- **prod 啟用後 inline script 全被擋**：確認前端的 `<Script>` 都帶 `nonce={...}` 且該 nonce 從 SSR 的 request header 讀
- **每次 request CSP nonce 都一樣**：middleware 沒跑（看 main.py middleware 順序）
- **想暫時關掉**：`.env` 設 `CSP_PROD_ENABLED=false`，重啟（**不建議在 prod**）

### 驗證
```bash
# dev：CSP 應該含 unsafe-eval
curl -sI http://localhost:8000/health/live | grep -i content-security-policy

# prod：CSP 應該含 nonce-<value>
APP_ENV=prod CSP_PROD_ENABLED=true curl -sI http://localhost:8000/health/live | grep -i content-security-policy
```

---

## 11. Phase 18 — Notification dispatcher 排錯

通知串接：事件 → `dispatcher.dispatch_*` → notifier.send → log + DLQ。

### 沒收到通知
1. **查 settings**：DB `SELECT * FROM notification_settings WHERE user_id = ?`
   - `line_token_encrypted` / `telegram_bot_token_encrypted` 不為 null
   - `enabled_events` 包含該事件（或為 `null` = 全訂閱）
2. **查 log**：`SELECT * FROM notification_log WHERE user_id = ? ORDER BY sent_at DESC`
   - 有 `status='failed'` → 看 `error_msg`
3. **查 DLQ**：`SELECT * FROM celery_dead_letters WHERE task_name = 'notify' AND resolved = false`
4. **dispatch 沒跑到**：看 backend log 有沒有 `NotificationDispatcher.background.failed`
5. **quiet hours**：`quiet_hours_start` ~ `quiet_hours_end` 內 INFO/WARN 跳過，CRITICAL 仍發

### 手動 dispatch 測試
```python
import asyncio
from app.notifications import NotifyEvent, NotifyLevel, get_dispatcher

dispatcher = get_dispatcher()
results = dispatcher.dispatch_sync(NotifyEvent(
    event_type="test",
    user_id=<your-uuid>,
    title="手動測試",
    body="ad-hoc test",
    level=NotifyLevel.INFO,
))
print(results)
```
