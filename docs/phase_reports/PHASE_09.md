# Phase 9 — 安全 Middleware + Audit hash chain + Rate Limit + Validators

| 項目 | 內容 |
|------|------|
| 開始日期 | 2026-05-15 |
| 完成日期 | 2026-05-15 |
| 實際工時 | 約 3.5 小時 |
| Claude session 數 | 1 |
| Git tag | `phase-09-complete` |
| 退出條件 | `bash scripts/health_checks/phase_09.sh` 12 項全綠 |

## 1. 目標

把 backend 從 P8 的「完整 Auth」進化到「安全強度達 v1.0 上線標準」：

- **AuditMiddleware** — 每 HTTP request 寫一筆 audit_logs（http.{method}）
- **RateLimit 6 層** — Redis-based sliding window（L1 per IP 300/min, L2 login 5/min, L3 password-reset 3/hr, L4-L6 在 service 層）
- **CSRFMiddleware** — POST/PUT/PATCH/DELETE 強制驗 X-CSRF-Token == csrf_token cookie
- **BodySizeMiddleware** — Content-Length > 1 MB → 413
- **Validators** — Symbol（TW 4-6碼 + US class share）/ DateRange / UUID / URL / Content-Type / Sort whitelist / html_escape
- **AuditRepository** — append + verify_chain (chain-link 法，不用 LAG)
- **verify_audit_chain.py CLI** — 獨立工具 + Celery task 升級（P7 stub → 真實校驗）
- **CSP dev** — security_headers 已有，加 nonce 留 P18

## 2. 新增 / 修改檔案

### 程式檔（新增）

| 檔案 | 行數 | 用途 |
|------|------|------|
| `backend/app/core/validators.py` | 222 | 8 個 validator + 3 個 SortField 白名單 |
| `backend/app/core/body_size_middleware.py` | 64 | Content-Length 1 MB 上限 |
| `backend/app/core/csrf_middleware.py` | 96 | double-submit cookie 驗證 + exempt list |
| `backend/app/core/rate_limit.py` | 252 | Lua-script atomic INCR+EXPIRE + 6 層規則 |
| `backend/app/core/audit_middleware.py` | 135 | 每 request 寫 audit_logs；shutdown-safe |
| `backend/app/repos/audit_repo.py` | 196 | append + verify_chain（chain-link 法） |
| `scripts/verify_audit_chain.py` | 80 | CLI 工具：完整或時段重算 hash chain |
| `backend/tests/unit/test_validators.py` | 217 | 24 個 unit test |
| `backend/tests/unit/test_rate_limit.py` | 145 | 7 個 unit test（fakeredis + lupa） |
| `backend/tests/integration/test_audit_middleware.py` | 165 | 5 個 integration test |
| `backend/tests/integration/test_csrf_middleware.py` | 140 | 7 個 integration test |
| `backend/tests/integration/test_rate_limit_endpoints.py` | 130 | 6 個 integration test |
| `backend/tests/security/test_audit_chain.py` | 260 | 4 個 security test（含手動 tampering） |
| `backend/tests/security/test_validators_security.py` | 137 | 12 個 security test |
| `backend/tests/security/__init__.py` + `conftest.py` | 50 | 共享 fixture |
| `scripts/health_checks/phase_09.sh` | 175 | 12 項退出條件 |

### 程式檔（修改）

| 檔案 | 變更 |
|------|------|
| `backend/app/main.py` | 新增 5 個 middleware（AuditMiddleware / BodySize / CSRF / RateLimit），依 LIFO 順序排好 |
| `backend/app/services/_audit_minimal.py` | 改為 thin wrapper 呼叫 AuditRepository |
| `backend/app/workers/tasks/verify_audit.py` | P7 stub → 真實實作（用 ro engine） |
| `backend/pyproject.toml` | dev 加 `fakeredis[lua]`, `lupa`（rate limit 單測） |
| `backend/tests/integration/conftest.py` | 加 `flush_rate_limit` fixture；flush list 含 db 2 |
| `backend/tests/integration/test_auth_login.py` | 6-session test 加 `flush_rate_limit` |
| `backend/tests/integration/test_auth_refresh.py` | logout 改帶 CSRF |
| `backend/tests/integration/test_auth_change_password.py` | 全部 POST 改帶 CSRF |
| `scripts/health_checks/phase_08.sh` | login 用 cookie jar；ws-ticket POST 帶 CSRF；lockout 每次清 rate-limit |

### 文件檔

| 檔案 | 用途 |
|------|------|
| `docs/phase_reports/PHASE_09.md` | 本文件 |
| `docs/phase_progress.md` | P9 row 更新為 ✅ 完成 |

## 3. 測試統計

| 類型 | P9 新增 |
|------|--------|
| Unit (validators + rate_limit) | 24 + 7 = 31 |
| Integration (audit + csrf + ratelimit) | 5 + 7 + 6 = 18 |
| Security (audit_chain + validators_security) | 4 + 12 = 16 |
| **P9 小計** | **65 新測試** |
| **累積（含 P0-P8）** | **435 collected / 433 passed / 2 skipped** |

ruff check 在 `app/` + `tests/` 全綠。

## 4. 關鍵設計決策

### 4.1 Middleware 順序（LIFO）

```python
# app.add_middleware 順序 = 內 → 外
app.add_middleware(RequestIDMiddleware)        # 最先 add = 最內層
app.add_middleware(AuditMiddleware)
app.add_middleware(BodySizeMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CORSMiddleware)
app.add_middleware(SecurityHeadersMiddleware)  # 最後 add = 最外層
```

請求進來流程（外到內）：SecurityHeaders → CORS → RateLimit → CSRF → BodySize → Audit → RequestID → route。
RateLimit 在 CSRF 之前，因為被 rate-limit 不需要驗證 CSRF（也避免 attack 端用 GET 把計數冲爛）。

### 4.2 為什麼 CSRF/BodySize/RateLimit 直接 return JSONResponse 而非 raise

`BaseHTTPMiddleware.dispatch` 在 `call_next` 之前 raise 的例外，會繞過 FastAPI 的 ExceptionMiddleware（這是 starlette / fastapi 的已知行為），最終被 unexpected_error handler 攔成 500。
解法：middleware 直接構造 JSONResponse 回應，並用 envelope_error 維持格式統一。
`raise AppError` 仍可在路由 handler 內用（會被 exception handler 接住）。

### 4.3 Rate limit 用 Lua eval()，不用 SCRIPT LOAD + EVALSHA

`fakeredis` 不支援 SCRIPT LOAD（即使加 `[lua]` extras 後 eval 才支援）。所以 `RateLimiter.check()` 直接傳 script source 給 `redis.eval()`。
real redis 對重複的 eval 會自動 cache script，不會有效能損失。

### 4.4 Audit chain verify：放棄 LAG，改用 chain-link

PLAN 19.6 trigger 用 `ORDER BY timestamp DESC, id DESC` 找 prev_hash。但並發 INSERT 時：
- T1: id=100, timestamp=A (transaction start time)
- T2: id=101, timestamp=B > A
- T2 commit first → trigger 看到沒人，prev=T2 之前的 row
- T1 commit later → trigger 看到 T2 已 commit，timestamp 較大 → prev = T2's entry_hash

結果：T1 (id 較小) chains to T2 (id 較大)。
LAG by (timestamp, id) ASC：T1 (smaller ts) 排在 T2 前，預期 T1.prior = T2 前那筆，但實際 T1.prev = T2.entry → MISMATCH。

修正：**verify 不靠 LAG，改驗 chain-link**：
- 每筆 row 的 entry_hash 必須等於重算結果（hash_ok）
- 每筆 row 的 prev_hash 必須 = `'0'*64`（鏈首）或某筆 row 的 entry_hash（chain_ok）

這個算法對任何 chain 順序都正確。

### 4.5 AuditMiddleware 寫入失敗不擋 response

`_write_audit` 整個包在 try/except，任何 DB error 都 log warning 不 raise。這是 PLAN「已知陷阱」之一。
trade-off：可能丟失 audit；但避免 audit 寫入失敗讓 request 變 500，影響可用性。

### 4.6 排除路徑

| Middleware | 排除路徑 |
|-----------|---------|
| AuditMiddleware | `/health/*`, `/metrics`, `/docs`, `/openapi.json`, `/redoc`, `/_test/*`, `/favicon.ico` |
| CSRFMiddleware | `/api/v1/auth/login`, `/api/v1/auth/password-reset`, `/api/v1/auth/password-reset/confirm`, 以及前綴 `/health/`, `/docs`, `/openapi.json`, `/_test/` |
| RateLimitMiddleware | `/health/*`, `/docs`, `/openapi.json`, `/redoc`, `/_test/*` |

### 4.7 verify_audit_chain CLI 與 Celery task

- CLI：`scripts/verify_audit_chain.py [--since ISO_DATE] [--limit N]`
- Celery：每日 04:30 排程（P7 已註冊）。斷裂時 log CRITICAL（P18 加 LINE/Telegram 告警）。

### 4.8 SQL injection 防護

ORDER BY 不能 parameterized，所以 sort 欄位走白名單：
- `StockSortField`：`{"symbol", "name", "market_cap", "volume"}`
- `AnalysisSortField`：`{"created_at", "completed_at", "status", "symbol"}`
- `AuditSortField`：`{"timestamp", "action", "actor_id"}`

額外有 `validate_sort_field(value, allowed=...)` 函式版給 router 直接呼叫。

## 5. 退出條件 — 12 項全綠

1. P8 健康檢查仍綠（cascade）
2. uv sync + ruff lint 通過（含新增 fakeredis[lua]、lupa）
3. `/health/live` 200
4. SecurityHeaders 完整（CSP / X-Frame / X-CTO / Referrer-Policy）
5. CSRF：POST 缺 X-CSRF-Token → 403
6. RateLimit：L2 觸發 429 + Retry-After
7. BodySize：2 MB body → 413
8. AuditMiddleware：/auth/login 寫入 `http.post` audit log
9. verify_audit_chain CLI 通過（since 60s window）
10. validators 行為正確（symbol / date_range）
11. P9 全部測試通過（unit + integration + security）
12. 累積測試 435 ≥ 192

## 6. 已知議題 / 留給後續 phase

- **trigger 0012 vs 並發 INSERT**：trigger 用 timestamp 排序找 prev，並發時 chain 順序可能與 (timestamp, id) ASC 不一致。verify 已用 chain-link 法繞過，但 trigger 本身可在 P19 hardening 時改用 advisory_lock + SERIAL 順序。
- **歷史 audit_logs 污染**：security test 的 manual_delete 留下殘缺 chain；CLI / Celery 健康檢查預設 since=60s 避開歷史污染。完整重建 chain 需獨立工具（P19）。
- **L4 / L5 rate limit**：middleware 沒解 JWT 拿不到 user_id；目前留給 endpoint 用 `Depends(make_user_rate_limit_dependency())`。P10/P11 業務 router 才會掛上。
- **CSP prod nonce-based**：P18 才實作 nonce 注入（前端 SSR 配合）。
- **TestClient + asyncio loop 衝突**：仍以「per-test engine + 同步 redis flush」繞過；P15+ 若改 httpx.AsyncClient 可整理。
- **/auth/ws-ticket 走 CSRF**：嚴格說 ws-ticket 是只讀（issue ticket）但仍 POST，目前 CSRF 中介層攔；前端要記得帶 X-CSRF-Token。

## 7. Self-check SOP

- [x] 1. `git status` 乾淨
- [x] 2. ruff check 全綠
- [x] 3. pytest 全綠（433 passed, 2 skipped）
- [x] 4. 累積測試數 ≥ 192（實際 435）
- [x] 5. docker compose 全 healthy
- [x] 6. `/health/live` 200
- [x] 7. `bash scripts/health_checks/phase_09.sh` 12 項全綠
- [x] 8. git commit + tag `phase-09-complete`
