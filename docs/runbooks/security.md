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
