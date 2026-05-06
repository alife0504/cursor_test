# 工程規範（Engineering Standards）— TradingAgents-TW v0.3.0

> 對應 PLAN.md 第十七章。本文件由 Phase 1 建立，後續 Phase 視需要修訂。

---

## 1. Logging（structlog + JSON）

### 1.1 規範

- 全 backend 使用 `structlog`，**禁用** `print()` 與 `logging` 直接呼叫
- Production：JSON output；Dev：可選 console
- 每筆 log 必含：`trace_id`、`level`、`logger`、`event`、`timestamp`

### 1.2 敏感欄位遮蔽

下列欄位必須在 log processor 中遮蔽（顯示為 `***`）：

```
password, api_key, token, authorization, line_token, telegram_token,
refresh_token, csrf, cookie, secret_key, data_encryption_key, qdrant_api_key
```

### 1.3 範例

```python
import structlog

logger = structlog.get_logger()

# ✅ 正確
logger.info("user.login", user_id=user.id, ip=ip)
logger.warning("rate_limit.exceeded", endpoint="/api/v1/analysis", user_id=user.id)
logger.error("external_service.failed", source="finmind", err=str(e))

# ❌ 錯誤
print(f"User {user.id} logged in")  # 不允許
logger.info(f"login api_key={api_key}")  # api_key 沒遮蔽
```

---

## 2. Error 階層

```python
class AppError(Exception):
    code: ClassVar[str]              # 例：USER_NOT_FOUND
    message_zh: ClassVar[str]        # 繁中錯誤訊息
    http_status: ClassVar[int] = 500
    def __init__(self, **details):
        self.details = details
```

### 2.1 標準子類

| Class | HTTP | 用途 |
|-------|------|------|
| `ValidationError` | 422 | 輸入驗證失敗 |
| `NotFoundError` | 404 | 資源不存在 |
| `AuthError` | 401 | 認證失敗 |
| `ForbiddenError` | 403 | 權限不足 |
| `ConflictError` | 409 | 衝突（例：訂單已被處理） |
| `RateLimitError` | 429 | 限流 |
| `ExternalServiceError` | 503 | 外部服務失敗 |
| `TooLargeError` | 413 | Payload 過大 |
| `LockedError` | 423 | 帳號鎖定 |
| `QuotaExceededError` | 402 | 配額超限 |
| `IdempotencyConflictError` | 409 | Idempotency-Key 衝突 |

---

## 3. API Envelope 統一格式

### 3.1 成功

```json
{
  "data": { ... },
  "meta": {
    "trace_id": "uuid",
    "version": "v1",
    "timestamp": "2026-05-04T10:00:00Z"
  },
  "pagination": { ... }   // optional
}
```

### 3.2 失敗

```json
{
  "error": {
    "code": "USER_NOT_FOUND",
    "message": "用戶不存在",
    "trace_id": "uuid",
    "details": { ... }
  }
}
```

**重要：** 5xx 錯誤**不洩漏 stack trace** 給 client，只回 `trace_id`，stack 進 log。

---

## 4. 分頁規範（Cursor-based）

```
GET /api/v1/stocks?limit=50&cursor=base64(json_payload)
```

- 預設 `limit=50`，最大 100
- `cursor` 是 base64-encoded JSON（含 last id + 排序欄位的 last value）
- 回應含 `pagination.next_cursor`（無更多資料時為 `null`）

**禁用 offset-based pagination**（深分頁效能差）。

---

## 5. 快取規範（Redis db0）

| 用途 | Key 格式 | TTL | 失效機制 |
|------|---------|-----|---------|
| 個股當日 | `cache:price:{symbol}:{date}` | 收盤後 24h | TTL |
| 個股資訊 | `cache:info:{symbol}` | 7 天 | 排程 DEL |
| 大盤 | `cache:market:overview` | 5 min | TTL |
| Tool 結果 | `cache:tool:{name}:{params_hash}` | 1h | TTL |
| Session | `session:{user_id}` | 7d | logout DEL |
| 自選股 | `cache:watchlist:{user_id}` | 1h | 增刪 DEL |
| 統計 | `cache:stats:{type}:{params}` | 1h | Event-driven DEL |

---

## 6. 測試金字塔

| 層 | 比例 | 工具 | 目標覆蓋率 |
|----|-----|------|-----------|
| Unit | 70% | pytest / vitest | 後端 ≥ 80%、前端 ≥ 60% |
| Integration | 25% | pytest + testcontainers | API + DB 流程 |
| E2E | 5% | Playwright | 關鍵用戶流程 |

### 6.1 標記（pytest markers）

```
@pytest.mark.unit          # 預設，無外部依賴
@pytest.mark.integration   # 需 docker compose up
@pytest.mark.security      # 安全 / OWASP 測試
@pytest.mark.network       # 真實打外部 API（CI 預設 skip）
@pytest.mark.expensive     # 真實 LLM 呼叫（會花錢，預設 skip）
```

CI 預設只跑 `unit + integration`；`network` 與 `expensive` 用 `-m network` 顯式啟用。

---

## 7. Migration（DB schema 演進）

### 7.1 工具

- **初始 schema：** Alembic baseline migration（`backend/migrations/versions/0001_*.py` 起）
- **後續演進：** Alembic（hypertable 用 `op.execute()` 包 SQL）
- **連線帳號：** `ta_migration`（CREATEDB 權限）

### 7.2 規範

- 每個 migration **必寫 `downgrade()`**
- CI 跑 `upgrade head` ↔ `downgrade base` 雙向測試
- DDL 前先確認**無進行中的長 transaction**（`pg_stat_activity`）

---

## 8. Code Style

| 語言 | Linter | Formatter | Line length |
|------|--------|-----------|-------------|
| Python | ruff | ruff format | 100 |
| TypeScript | ESLint | Prettier | 100 |
| SQL | sqlfluff | - | - |

### 8.1 Pre-commit hooks（必跑）

- ruff（lint + format）
- prettier（前端，P15 啟用）
- detect-secrets
- trailing-whitespace、end-of-file-fixer
- check-yaml、check-json、check-merge-conflict
- check-added-large-files (max 2MB)
- detect-private-key

---

## 9. Git 工作流程

### 9.1 Branch 命名

| 類型 | 格式 | 範例 |
|------|------|------|
| Phase 開發 | `phase/<NN>-<簡稱>` | `phase/01-migration-and-skeleton` |
| Feature | `feat/<簡稱>` | `feat/watchlist-search` |
| Bugfix | `fix/<簡稱>` | `fix/jwt-rotation-bug` |
| 文件 | `docs/<簡稱>` | `docs/runbook-celery` |
| Hotfix | `hotfix/<簡稱>` | `hotfix/csrf-bypass` |

### 9.2 Commit message 格式

依 Conventional Commits：

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

- **type**：`feat` / `fix` / `chore` / `docs` / `test` / `refactor` / `perf` / `security`
- **scope**：`phase-<NN>` / `auth` / `api` / `frontend` / `db` / 等
- **subject**：祈使句、≤ 72 字

範例：

```
feat(phase-8): 新增 JWT 雙 key rotation 支援
fix(api): 修正並發核准 race condition (SELECT FOR UPDATE)
chore(phase-1): 將原版 v0.2.4 殘留檔遷至 legacy/
```

### 9.3 PR 流程（v1.0 自用）

- **Self-review** 即可（不需第二人審）
- 每個 Phase 結束 merge 到 `main`，並打 git tag `phase-NN-complete`
- **絕不直接在 `main` 上 commit**

---

## 10. Secret 管理

### 10.1 規範

- **永遠不 commit secret**（detect-secrets pre-commit hook 把關）
- Dev 用 `.env`（已 gitignore）
- Prod 用 `.env.prod`（檔案 mode 600，部署機獨立保管）
- DATA_ENCRYPTION_KEY 與 SECRET_KEY **必須分離**（pydantic validator 強制）

### 10.2 旋轉

- JWT key：每 7 天輪替（雙 key 並存過渡期）
- DB 密碼：每 6 個月輪替
- LLM API key：發現洩漏時立即 rotate（自動腳本 P18 提供）

---

## 11. 觀測性（Observability）

### 11.1 三大支柱

| 支柱 | 工具 | 暴露點 |
|------|------|-------|
| Logs | structlog JSON | stdout + log file |
| Metrics | Prometheus format | `/metrics`（admin only） |
| Traces | trace_id（HTTP → Celery → WS） | log 全鏈路 |

### 11.2 trace_id 傳播

- HTTP request 進來 → middleware 生成或從 `X-Request-ID` 取
- Celery task → header 傳遞
- WebSocket event → JSON payload 帶
- 全部 log 自動帶（contextvars）

---

## 12. 跨 Phase 設計原則

依 PLAN.md 第 8.5 章「Phase 設計方法論」：

1. 單 Phase 程式碼 ≤ 1500 行
2. 單 Phase context ≤ 80k token
3. 單 Phase 執行時間 3-5 小時
4. 每 Phase 開頭跑 `bash scripts/health_checks/phase_<NN-1>.sh`
5. 每 Phase 結尾跑 8 項 Self-Check SOP（PLAN.md 第 8.5.4）
6. 每 Phase 產出 `docs/phase_reports/PHASE_NN.md`
7. 每 Phase 完成打 git tag `phase-NN-complete`
