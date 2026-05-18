# API Runbook — Cursor Pagination 與 Response Envelope

Phase 10 之後，所有列表類 endpoint 走「**cursor pagination + 統一 envelope**」格式。

## 1. Envelope 結構

成功回應：

```json
{
  "data": [...] | { ... },
  "meta": {
    "trace_id": "9dbfa2e1-92d4-4689-867a-ce102fb1edea",
    "version": "v1",
    "timestamp": "2026-05-15T07:00:00.000000+00:00"
  },
  "pagination": {                // 僅列表類 endpoint 帶
    "next_cursor": "eyJhZnRlcl9zeW1ib2wiOiAiOTAwMDIifQ" | null,
    "limit": 50,
    "has_more": true
  }
}
```

失敗回應：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "繁體中文錯誤訊息",
    "trace_id": "9dbfa2e1-...",
    "details": { "field": "symbol", "value": "BAD" }
  }
}
```

## 2. Cursor Pagination 用法

### Server 端（Phase 10 起所有列表 endpoint）

```bash
# 第一頁
curl -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/api/v1/stocks?market=TW&limit=20'
# → { "data": [...], "pagination": { "next_cursor": "eyJh...", "has_more": true } }

# 接續
curl -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/api/v1/stocks?market=TW&limit=20&cursor=eyJh...'
```

| 參數 | 預設 | 上限 | 行為 |
|------|------|------|------|
| `limit` | 50 | 100 | 超過 100 會自動 clamp 到 100 |
| `cursor` | (無) | 2048 chars | base64(JSON)；無效格式 → 422 |

### 何時 `next_cursor` 為 `null`

- 已到最後一頁（`has_more: false`）
- 結果集為空

### cursor 內容（不保證向後相容）

P10 第一版的 cursor 多半是 `{"after_symbol": "9999"}` 或 `{"after_id": "<uuid>"}`，未來可能改變。**前端絕對不要解析 cursor 字串**，當作 opaque token 帶回即可。

## 3. Decimal 與 datetime 序列化

依 PLAN 第 17.5 章：

- **Decimal** 一律序列化為字串：`"105.500000"`（避免 IEEE 754 精度損失）
- **datetime** 一律 ISO 8601 + UTC：`"2026-04-30T14:30:00+00:00"`

前端應該用 `string` 接 Decimal，運算前用 `BigNumber.js` / `Decimal.js`。

## 4. Phase 10 新增的列表 endpoint 一覽

| Endpoint | RBAC | 排序 | cursor 欄位 |
|----------|------|------|-------------|
| `GET /api/v1/stocks` | 任何登入 | symbol asc | `after_symbol` |
| `GET /api/v1/screener` | 任何登入 | sort whitelist | `after_symbol` |
| `GET /api/v1/users` | admin only | id asc | `after_id` |
| `GET /api/v1/watchlist` | 自己 | sort_order asc | （不分頁，使用者通常 < 100 支） |
| `GET /api/v1/market/movers` | 任何登入 | gainers/losers/volume | （不分頁，固定 top N） |
| `GET /api/v1/market/institutional` | 任何登入 | foreign_net desc | （不分頁，固定 top N） |

## 5. RBAC 規範

依 PLAN 第 19.1 章：

| Role | 可做 |
|------|------|
| ADMIN | 全部 |
| ANALYST | 讀 + 寫 watchlist + 跑 analysis（P11+）|
| VIEWER | 讀 + 寫自己的 watchlist |

`/api/v1/users` 多數 endpoint 是 admin only；`PATCH /api/v1/users/{id}` 允許 self 改個人偏好（但不能改 role / is_active）。

## 6. CSRF

所有 `POST` / `PUT` / `PATCH` / `DELETE` 必須帶 `X-CSRF-Token: <csrf cookie 值>`，否則 403。

例外（豁免，由 `csrf_middleware.CSRF_EXEMPT_PATHS` 維護）：

- `/api/v1/auth/login`
- `/api/v1/auth/password-reset`
- `/api/v1/auth/password-reset/confirm`

## 7. Trace ID

每個 response 一定附 `X-Request-ID` header（從 `RequestIDMiddleware`），對應 `meta.trace_id`。出問題請帶 trace_id 給後端，可在 audit_logs / structlog 中追溯整條鏈。

## 8. 故障排除

| 症狀 | 可能原因 | 修法 |
|------|---------|------|
| `403 FORBIDDEN`（POST/PATCH/DELETE） | 缺 X-CSRF-Token 或 cookie 過期 | 重新 login 拿 csrf cookie |
| `422 cursor 格式錯誤` | 前端拼錯 cursor 或 truncate | 重新從第一頁開始拿 next_cursor |
| `429 RATE_LIMITED` | L1-L3 規則觸發 | 看 Retry-After header；指數 backoff |
| `404 NOT_FOUND` on `/stocks/{symbol}` | symbol 不在 stock_list（seed 未跑） | `make seed-stocks` |
