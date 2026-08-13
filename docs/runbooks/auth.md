# Runbook：Auth 問題排查

當 onboarding / 登入 / refresh 出問題時，照此順序檢查。

## 0. 快速健康檢查

```bash
bash scripts/health_checks/phase_08.sh
```

通過 = backend 認證鏈完整正常；任一項 fail 跳到對應章節。

## 1. 「login 一直 401」

**症狀**：admin 帳號用對的密碼還是 401。

**檢查順序**：
1. 帳號是否被鎖：
   ```bash
   docker compose exec timescaledb psql -h localhost -U postgres tradingagents_tw \
     -c "SELECT email, failed_attempts, locked_until FROM users WHERE email='admin@example.com'"
   ```
   `locked_until` 不為 NULL 且 > 現在時間 → 鎖中。
2. 解鎖：
   ```bash
   docker compose exec timescaledb psql -h localhost -U postgres tradingagents_tw \
     -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='admin@example.com'"
   ```
3. 密碼是否正確（admin 初始密碼在 `.env` 的 `ADMIN_INITIAL_PASSWORD`）。
4. 看 audit 紀錄為什麼 fail：
   ```sql
   SELECT action, details, ip, timestamp
   FROM audit_logs
   WHERE actor_id IS NULL AND action LIKE 'auth.%'
   ORDER BY timestamp DESC LIMIT 20;
   ```

## 2. 「access token 一拿就 401」

**症狀**：login 拿到 token，丟 Authorization header 卻 401。

**檢查**：
1. token 是否 expired（access TTL 15 分鐘）：
   ```bash
   python -c "
   from jose import jwt
   import sys
   payload = jwt.get_unverified_claims(sys.argv[1])
   print(payload)
   " "$TOKEN"
   ```
   看 `exp` 是不是已過。
2. token 的 `jti` 是否在 blacklist：
   ```bash
   docker compose exec redis redis-cli -n 3 -a $REDIS_PASSWORD GET "bl:jti:$JTI"
   ```
   有值 → 在 blacklist。
3. backend 啟動時 `SECRET_KEY` 換過 → 用舊 key 簽的 token 失效（除非 `SECRET_KEY_PREVIOUS` 還留著）。

## 3. 「refresh 一直 403 / CSRF token 驗證失敗」

**症狀**：refresh 給 X-CSRF-Token 但仍 403。

**檢查**：
1. cookie 與 header 是否相符：在瀏覽器 dev tool 看 `csrf_token` cookie 值，比對 request header `X-CSRF-Token`。
2. 跨 port 開發（前端 :3000 → 後端 :8000）：dev 用 SameSite=Lax；prod 用 Strict。
3. CORS 是否擋掉了 cookie：`CORS_ORIGINS` 含前端網址 + `allow_credentials=True`（main.py 已預設）。

## 4. 「WS 連不上 / ticket 失效」

**症狀**：前端拿到 ticket 後 WS handshake 失敗。

**檢查**：
1. ticket 是否還在 Redis db5：
   ```bash
   docker compose exec redis redis-cli -n 5 -a $REDIS_PASSWORD GET "wst:$TICKET"
   ```
   無值 = 已被 consume 或 TTL 過（60 秒）。
2. subprotocol 是否傳對：
   ```js
   new WebSocket(url, ["tradingagents.v1", `ticket.${ticket}`])
   ```
   必須兩個值，第一個是 protocol 名，第二個是 `ticket.` 前綴 + ticket 值。

## 5. 「改密碼一直被拒（最近 5 次重複）」

```sql
SELECT count(*), max(created_at)
FROM password_history
WHERE user_id = (SELECT id FROM users WHERE email='admin@example.com');
```

清掉某個 user 的歷史（dev 環境 only）：
```sql
DELETE FROM password_history WHERE user_id = ...;
```

## 6. 「session 數一直破 5」

```sql
SELECT count(*) FILTER (WHERE revoked=false AND expires_at > NOW()) AS active,
       count(*) AS total
FROM user_sessions WHERE user_id = '<user-id>';
```

active 應該 ≤ 5。若 > 5：
- 確認 `auth_service.login` 有跑 `revoke_oldest_if_over_limit`。
- 強制清：`UPDATE user_sessions SET revoked=true WHERE user_id=...`。

## 7. 「audit_logs 寫不進去 / hash chain verify 失敗」

**症狀**：login 成功但 `SELECT count(*) FROM audit_logs WHERE action='auth.login'` 為 0。

**檢查**：
1. ta_service_rw 是否仍有 INSERT 權限（baseline 0013 只 REVOKE UPDATE/DELETE/TRUNCATE）：
   ```sql
   SELECT has_table_privilege('ta_service_rw', 'audit_logs', 'INSERT'); -- 應 true
   ```
2. trigger 是否存在：
   ```sql
   SELECT tgname FROM pg_trigger WHERE tgrelid = 'audit_logs'::regclass;
   ```
3. 看 backend log 有沒有 ROLLBACK 訊息。

## 8. JWT key rotation 流程（半年一次）

1. 產新 key：`python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(48)).decode())"`
2. 改 `.env`：
   ```
   SECRET_KEY=<新 key>
   SECRET_KEY_PREVIOUS=<舊 key>
   ```
3. 重啟 backend。
4. 等 7 天（refresh TTL）— 期間所有舊 token 可正常 decode（用 previous key），新 token 用 current 簽。
5. 7 天後改 `.env`：
   ```
   SECRET_KEY=<新 key>
   SECRET_KEY_PREVIOUS=
   ```
6. 再重啟 backend。

## 9. 緊急把所有 session 砍光（incident response）

```sql
-- 撤銷所有 refresh session
UPDATE user_sessions SET revoked=true, revoked_at=NOW() WHERE revoked=false;
```

```bash
# 全部 jti 加入 blacklist（保險）
docker compose exec redis redis-cli -n 3 -a $REDIS_PASSWORD FLUSHDB
```

之後所有 user 都得重新 login。
