# Phase 8 — 認證系統（JWT/RBAC/CSRF/WS Ticket/密碼重置/Session/Lockout）

| 項目 | 內容 |
|------|------|
| 開始日期 | 2026-05-14 |
| 完成日期 | 2026-05-15 |
| 實際工時 | 約 4.0 小時 |
| Claude session 數 | 1 |
| Git tag | `phase-08-complete` |
| 退出條件 | `bash scripts/health_checks/phase_08.sh` 12 項全綠 |

## 1. 目標

把 backend 從 P7 的「無 Auth」進化到「完整 Auth」狀態，覆蓋：

- bcrypt cost=12 密碼 hash + verify
- JWT HS256 + access (15min) + refresh (7day) + rotation + blacklist + 雙 key rotation
- CSRF (double-submit cookie pattern) 保護 `/auth/refresh`
- 一次性 WS Ticket（Redis db5 / 60s TTL / GETDEL atomic consume）
- 強密碼策略（12+ 字、4 類字元、不可含 email、最近 5 次不重複）
- Lockout（5 fail / 15min）
- Per-user 5 sessions 上限
- RBAC 三角色：ADMIN / ANALYST / VIEWER
- Onboarding next_action（change_password > onboarding > dashboard）
- 完整 audit_logs 寫入（每個 auth event）

## 2. 新增 / 修改檔案

### 程式檔（新增）

| 檔案 | 行數 | 用途 |
|------|------|------|
| `backend/app/core/security.py` | 232 | `hash_password` / `verify_password` / `JWTService` / `TokenBlacklist` / `constant_time_dummy_verify` |
| `backend/app/core/csrf.py` | 33 | `generate_csrf_token` / `verify_csrf_token`（constant-time） |
| `backend/app/core/ws_ticket.py` | 71 | `WSTicketService.issue` / `consume`（GETDEL atomic） |
| `backend/app/core/password_policy.py` | 130 | `validate_password` + `PasswordHistoryService` |
| `backend/app/repos/user_repo.py` | 252 | `UserRepository` / `UserSessionRepository` / `PasswordResetTokenRepository` + 常數 |
| `backend/app/services/auth_service.py` | 415 | `AuthService` 高階整合 |
| `backend/app/services/_audit_minimal.py` | 47 | P8 暫用 audit append（P9 替換為 AuditRepository） |
| `backend/app/api/dependencies.py` | 133 | `get_current_user` / `require_role` / `admin_only` / 服務 factory |
| `backend/app/api/v1/auth_router.py` | 247 | 8 個 endpoints |
| `backend/app/schemas/auth.py` | 142 | Pydantic 請求 / 回應 schemas |
| `backend/migrations/versions/0015_phase8_password_history.py` | 53 | `password_history` 表 |
| `backend/tests/unit/test_password_policy.py` | 169 | 16 tests |
| `backend/tests/unit/test_jwt_service.py` | 168 | 13 tests |
| `backend/tests/unit/test_ws_ticket.py` | 109 | 9 tests |
| `backend/tests/integration/test_auth_login.py` | 256 | 11 tests |
| `backend/tests/integration/test_auth_refresh.py` | 138 | 6 tests |
| `backend/tests/integration/test_auth_password_reset.py` | 153 | 6 tests |
| `backend/tests/integration/test_auth_change_password.py` | 145 | 5 tests |
| `backend/tests/integration/test_rbac.py` | 138 | 8 tests |
| `scripts/health_checks/phase_08.sh` | 165 | 12 項退出條件健康檢查 |

### 程式檔（修改）

| 檔案 | 變更摘要 |
|------|----------|
| `backend/app/models/user.py` | 加 `PasswordHistory` model |
| `backend/app/models/__init__.py` | 匯出 `PasswordHistory` |
| `backend/app/main.py` | lifespan 註冊 `jwt_service` / `ws_ticket_service` / `token_blacklist` 到 `app.state`；`include_router(auth_router)` |
| `backend/pyproject.toml` | dev 加 `fakeredis>=2.26,<3.0` |
| `backend/tests/integration/conftest.py` | 加 `auth_app` / `auth_client` / `db_session_maker` / `make_test_user` fixtures + 同步 redis flush autouse fixture |

### 文件檔

| 檔案 | 用途 |
|------|------|
| `docs/phase_reports/PHASE_08.md` | 本文件 |
| `docs/runbooks/auth.md` | Auth debug runbook |
| `docs/phase_progress.md` | P8 row 更新為 ✅ 完成 |

## 3. 測試統計

| 類型 | 檔案數 | 測試數 |
|------|--------|--------|
| Unit | 3 | 38 |
| Integration | 5 | 36 |
| **小計（P8 新增）** | **8** | **74** |
| 累積（含 P0-P7） | 67+8 = **75** files | 282+74 = **356** items |

ruff check 在 `app/` + `tests/` 全綠。

## 4. 關鍵設計決策

### 4.1 雙 key JWT rotation

`JWTService.__init__` 接 `settings.SECRET_KEY` (current) + `settings.SECRET_KEY_PREVIOUS` (可選)。
- Sign：永遠用 current
- Decode：先試 current；若 `JWTError`（非 expired）→ 試 previous + log warning（可監控 rotation 進度）；若 expired 直接 raise

過渡期典型流程：set previous=舊 + current=新 → 等 7 天（refresh TTL）→ 清掉 previous。

### 4.2 Timing attack 抵抗

`constant_time_dummy_verify()` 在 user 不存在時仍跑一次 bcrypt（用 module-level dummy hash），讓「user 不存在」與「user 存在但密碼錯」耗時相當。

### 4.3 Audit log 寫入策略

P8 用 `app/services/_audit_minimal.py:append_audit()` 直接在 service 層寫 `AuditLog` row。
trigger（baseline 0012）會自動補 `prev_hash` / `entry_hash` hash chain。
**P9 會替換成 `AuditRepository`（含 verify_chain 等）。**

P8 寫入的 events：
- `auth.login` / `auth.login_failed` / `auth.login_locked`
- `auth.logout`
- `auth.refresh`
- `auth.password_changed` / `auth.password_change_failed`
- `auth.password_reset_requested` / `auth.password_reset_confirmed`

### 4.4 5 session 上限的 race condition

`UserSessionRepository.revoke_oldest_if_over_limit` 在 service 層的 `async with session.begin()` 內呼叫，整個流程（建新 session → 撤舊 session）在同一 transaction。
登入並發場景下，最後 commit 的 transaction 看到的 active sessions 是 final state。
極端 race 下可能瞬間超過 5（但收斂為 5）— 接受。

### 4.5 Password history 設計

- 新表 `password_history(id, user_id, password_hash, created_at)`，FK ondelete=CASCADE。
- `is_recent(plain)`：取最近 5 筆 hash，逐筆 bcrypt.checkpw（**順序時間**，但 5 次可接受）。
- `add(hashed)`：每次 change/reset 都把「舊密碼」hash 寫入（service 在 update_password 之前 add）。
- 不存 plaintext，只存 bcrypt hash。

### 4.6 Cookie 與 CSRF

login / refresh 都會種：
- `refresh_token` cookie：httpOnly + SameSite=Lax(dev)/Strict(prod) + path=`/api/v1/auth`
- `csrf_token` cookie：**非 httpOnly**（JS 要能讀來放 `X-CSRF-Token` header）+ SameSite 同上

`/auth/refresh` 強制驗 `X-CSRF-Token` header == cookie；不符 → 403 ForbiddenError。

### 4.7 WS Ticket 一次性

- Redis db5（`RedisDB.WS_TICKET`），key `wst:{ticket}`，TTL 60s。
- `issue`：`setex(key, 60, str(user_id))`。
- `consume`：`getdel(key)` — Redis 6.2+ atomic。退路是 pipeline GET+DEL（非原子但接受）。

### 4.8 lockout 即時鎖定 vs failed_attempts

`failed_attempts` 在每次失敗時 +1；當 +1 後 `>= 5` 立即 `locked_until = now + 15min`。
登入時先檢查 `locked_until > now`：若是 → 直接 raise `LockedError(423)`，不再 verify 密碼（即使密碼是對的也不開）。

## 5. 退出條件 — 12 項全綠

1. uv sync 通過（含 fakeredis 新增）
2. ruff lint 通過（`app/` + `tests/`）
3. backend 啟動 + `/health/live` 200
4. `/openapi.json` 含 `/api/v1/auth/login`
5. admin login 成功並取 access token
6. `/me` 200 + 不含 password_hash 欄位
7. lockout：5 次錯密碼 → 423
8. unlock + WS ticket 發放（並驗 Redis db5 寫入）
9. `audit_logs.action='auth.login'` count > 0
10. 38 unit + 36 integration tests 全綠
11. 累積測試 ≥ 158 → 實際 356
12. `phase_08.sh` 退出碼 0

## 6. 已知 P9 / 之後 phase 要清理的事

- `app/services/_audit_minimal.py` 整合到 P9 `AuditRepository`；trace_id 自動填、hash chain verify 自動跑
- `password_reset_request` 在 dev 直接回 `dev_token`；P18 改寄 email
- TestClient 跨 loop 的解法目前是「每 test 一個小 engine + 同步 redis flush」；P9+ 若改用 httpx.AsyncClient 可整理
- `SECRET_KEY_PREVIOUS` 還沒寫專門 validator（與 SECRET_KEY 同樣需 ≥ 32 bytes）— 可在 P19 補

## 7. Smoke test 路徑（驗收用）

```bash
# 1) login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"ChangeMeOnFirstLogin!1234"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['data']['access_token'])")

# 2) /me
curl -fsS -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me

# 3) /ws-ticket
curl -s -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/ws-ticket

# 4) lockout（5 次錯密碼）
for i in 1 2 3 4 5; do
  curl -s -X POST -H "Content-Type: application/json" \
    -d '{"email":"admin@example.com","password":"WRONG_'$i'!password"}' \
    http://localhost:8000/api/v1/auth/login > /dev/null
done
# 第 6 次應 423
curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"WRONG_X!"}' \
  http://localhost:8000/api/v1/auth/login
# → 423

# 5) docker exec 解鎖
docker compose exec timescaledb psql -h localhost -U postgres tradingagents_tw \
  -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='admin@example.com'"
```

## 8. Phase 完成 self-check

依 PLAN 第 8.5.4 章 8 項 SOP：

- [x] 1. `git status` 乾淨（commit 前 stage 全部）
- [x] 2. `uv run ruff check app/ tests/` 全綠
- [x] 3. `uv run pytest tests/unit tests/integration -q` 通過（74 P8 新測試 + 既有測試）
- [x] 4. `uv run pytest --collect-only -q` 數量符合（≥ 158，實際 356）
- [x] 5. docker compose 全 healthy
- [x] 6. `/health/live` 200
- [x] 7. `bash scripts/health_checks/phase_08.sh` 全綠
- [x] 8. PR / git tag：`phase-08-complete`
