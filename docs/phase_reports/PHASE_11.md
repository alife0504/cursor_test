# Phase 11 — 業務 API 第二批（analysis / orders / reports / exports / notifications / admin / ws / metrics）

| 項目 | 內容 |
|------|------|
| 起訖 | 2026-05-15 ~ 2026-05-15 |
| 分支 | `phase/11-api-second-batch` |
| 累積測試 | 518 passed / 2 skipped（P10 的 482 + P11 新增 36） |
| 重要 ADR | ADR-010（Playwright 取代 WeasyPrint）、PLAN 14.5（Idempotency）、PLAN 15.1/15.2（並發核准 + 樂觀鎖）、PLAN 19.1（WS 認證 + IDOR） |

## 一、本 Phase 完成項目

### 1. 業務 API 路由（8 個 router）

| Router | Prefix | 主要 endpoint |
|--------|--------|--------------|
| `analysis_router.py` | `/api/v1/analysis` | POST（需 Idempotency-Key）/ GET 列表 / GET / GET debate / POST cancel / DELETE（admin） |
| `orders_router.py` | `/api/v1/orders` | GET 列表 / GET / POST approve / POST reject |
| `reports_router.py` | `/api/v1/reports` | GET（與 analysis 共表，前端語意 alias） |
| `exports_router.py` | `/api/v1/exports` | GET ?format=pdf\|md\|xlsx |
| `notifications_router.py` | `/api/v1/notifications` | GET/PUT /settings、POST /test、GET /logs |
| `admin_router.py` | `/api/v1/admin` | audit / system/info / system/metrics / pipeline/dlq[/resolve\|/requeue] / users/{id}/sessions[/jti] |
| `ws_router.py` | `/api/v1/ws` | WS `/analysis/{id}` — Subprotocol + 一次性 ticket + IDOR 防護 |
| `metrics_router.py` | `/metrics` | Prometheus exposition format（admin only） |

OpenAPI 共 50 個 path。

### 2. 新增 core / repo / service / schema

- `core/idempotency.py` — Redis db6（24h TTL）+ DB 雙寫；`compute_request_hash`、`IdempotencyService`
- `core/crypto.py` — Fernet 對稱加密（LINE / Telegram token）；用 `settings.DATA_ENCRYPTION_KEY` 派生 key
- `core/metrics.py` — Prometheus counter / histogram / gauge 集中定義
- 4 個新 repo：`analysis_repo`、`order_repo`、`notification_repo`、`admin_repo`
- 5 個新 service：`analysis_service`、`order_service`、`exports_service`、`notification_service`、`admin_service`
- 5 個新 schema：`analysis`、`orders`、`exports`、`notifications`、`admin`

### 3. Dockerfile 升級

- `fonts-noto-cjk` / `fontconfig`（PDF 中文字型）
- `playwright install chromium` 安裝到 `/ms-playwright`（`PLAYWRIGHT_BROWSERS_PATH` env，app user 可讀）
- chromium 在 docker 啟動必須帶 `--no-sandbox`（已寫入 `exports_service`）

### 4. 並發核准設計（PLAN 15.1 + 15.2）

`OrderService.approve()` 流程：

1. `repo.get_for_update()` — `SELECT FOR UPDATE` 鎖該 row
2. 檢查 `status == PENDING` 與 `expected_version`
3. 不符 → `ConflictError("訂單已被其他人處理")`（中文）
4. `mark_status(new_status="APPROVED")` + `version += 1`
5. `add_portfolio_from_order(price=target_price or 1.0)`
6. `audit_repo.append("order.approved", ...)`
7. `session.commit()`

驗證：phase_11.sh 第 10 項並發兩個 approve，DB 只剩 1 筆 APPROVED；測試 `test_orders_concurrent_approve.py` 4 個 case 涵蓋 happy / double-approve / version-mismatch / reject 流程。

### 5. WebSocket 認證 + IDOR 防護（PLAN 19.1）

`ws_router.ws_analysis` 流程：

1. 從 subprotocol 取 `ticket.<XXX>` → `WSTicketService.consume()`（一次性 GETDEL）
2. 解碼 user_id（UUID），驗 active + non-deleted
3. **IDOR 檢查**：admin 可看所有；其他 role 只能看 `analysis.user_id == user.id`
4. `websocket.accept(subprotocol="tradingagents.v1")`
5. 訂閱 Redis db4 channel `analysis:{id}`，把 `pubsub.listen()` 訊息轉發給 client
6. `WebSocketDisconnect` 時 unsubscribe + close pubsub

OWASP IDOR 測試（`test_ws_analysis.py`）：
- userA 開的 analysis，userB 拿其 id 嘗試 ws 訂閱 → close code 1008
- 同 ticket 用兩次：第二次必失敗（一次性）

## 二、Self-Check SOP（8 項）

| 項 | 結果 |
|----|------|
| 1. `git status` 無遺失追蹤 | ✅ |
| 2. detect-secrets baseline | ✅（無新 secret） |
| 3. 無 print() 殘留 | ✅ |
| 4. ruff check | ✅ 通過 |
| 5. tsc / type check | N/A（無 TS 變更） |
| 6. pytest | ✅ 518 passed / 2 skipped |
| 7. docker compose ps healthy | ✅ |
| 8. /health/live 200 | ✅ |

## 三、累積測試覆蓋

| 模組 | 數量 |
|------|------|
| P11 unit (test_metrics) | 3 |
| P11 integration (analysis) | 6 |
| P11 integration (orders) | 4 |
| P11 integration (exports) | 5（含 1 個 skip-if-no-chromium） |
| P11 integration (notifications) | 6 |
| P11 integration (admin) | 6 |
| P11 integration (ws) | 4 |
| P11 integration (idempotency) | 4 |
| **P11 小計** | **38** |

P10 + P11 累積：**518 passed / 2 skipped**

## 四、ADR / 設計筆記

### ADR-010 落實：Playwright 取代 WeasyPrint

- 原因：WeasyPrint 在 Windows / Alpine 環境字型 / library 安裝麻煩；Playwright 走完整 chromium → 渲染品質一致
- 成本：image 多 ~250MB（chromium binary），啟動慢 ~3s（第一次）
- 預備：runbook 在 `docs/runbooks/exports.md`

### Idempotency-Key per-user namespace

- Redis key: `idem:{user_id|anon}:{key}`
- 不同 user 用同 key 不會撞
- 同 user 同 key 不同 body → `IdempotencyConflictError`（中文）
- DB 持久備份（`idempotency_keys` 表，TTL 24h）：Redis 重啟時可重建快取

### `/metrics` 不寫 audit

`AuditMiddleware.AUDIT_EXCLUDED_PATH_PREFIXES` 已含 `/metrics`，避免 Prometheus 抓取造成 audit log 爆量 / 遞迴。

### 並發核准 transaction 模型

由於 FastAPI `get_rw_session` dependency 已透過 autobegin 開了 transaction，service 內**不再呼叫** `session.begin()`（會撞 `InvalidRequestError: A transaction is already begun`）。

正確 pattern：
```python
try:
    order = await repo.get_for_update(order_id)  # 觸發 autobegin
    ...
    await session.commit()
except Exception:
    await session.rollback()
    raise
```

## 五、後續 Phase 待辦

- P12+：實際接 LangGraph workflow（`run_analysis` celery task）
- P12+：notification_service 真正接 LINE Notify / Telegram bot
- P12+：DLQ requeue 真正重新 enqueue celery task（目前只標記 resolved）
- P14+：訂單成交價接 price service（目前用 target_price 或 1.0）
- P18+：把 OWASP IDOR / WS 認證測試擴大到所有 WS endpoint

## 六、Git tag

```
git tag phase-11-complete
```
