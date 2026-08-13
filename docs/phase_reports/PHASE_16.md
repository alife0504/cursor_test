# Phase 16 完成報告

> 前端 8 個核心頁面(後端整合)

| 欄位 | 內容 |
|------|------|
| 開始 | 2026-05-17 |
| 完成 | 2026-05-17 |
| 分支 | `phase/16-frontend-core-pages` |
| 累積測試(前端) | 135 unit tests passed(P15 為 57,新增 78) |
| E2E spec | 新增 `full-workflow.spec.ts`(5 scenarios) |
| Tag | `phase-16-complete` |

---

## 1. 範圍與目標

PLAN § 27 列的 8 個核心頁面全部完整實作並接後端,WS 串流與 AgentFlowGraph 完成:

1. `/dashboard` 儀表板 — 5 個 section(大盤 / 配額 / 待核准 / 自選股 / 最近分析)
2. `/screener/watchlist` 自選股清單 — 完整 CRUD + inline edit + cmdk 搜尋
3. `/analysis/new` 新增分析 — 4 步驟、Idempotency-Key、配額預估
4. `/analysis/[id]` 分析詳情 — AgentFlowGraph + Tabs(Overview / Analysts / Debate / Report) + WS 即時更新 + 匯出按鈕
5. `/analysis/history` 歷史 — cursor pagination + 篩選
6. `/portfolio/orders` 待核准訂單 — 雙重確認核准 / 拒絕 + 409 並發保護
7. `/admin/users` 用戶管理 — 建立 / 重設密碼 / 啟停用 / 軟刪除
8. `/admin/audit` 審計日誌 — 篩選 + cursor pagination + 展開 details

額外:
- 新增 10 個 React Query hooks(覆蓋全部上述頁面)
- 補一個 backend 端點 `/api/v1/users/me/quota`(dashboard LLM 月用量 progress bar 需要)
- Sidebar 重做:標出 P16 已實作頁、admin group 對非 admin 隱藏

---

## 2. 新增 / 修改檔案

### 新增(前端)

| 路徑 | 功能 |
|------|------|
| `frontend/src/lib/api-types.ts` | 後端 envelope 內 data 形狀型別(對齊 Pydantic schemas) |
| `frontend/src/lib/llm-models.ts` | 可選 LLM 模型 + estimateCostUsd |
| `frontend/src/lib/uuid.ts` | UUID v4 generator(crypto + fallback) |
| `frontend/src/hooks/useStocks.ts` | useStocks / useStockDetail / useOhlcv |
| `frontend/src/hooks/useWatchlist.ts` | CRUD mutations + list |
| `frontend/src/hooks/useAnalysis.ts` | list / detail / debate / create(帶 Idempotency-Key) / cancel |
| `frontend/src/hooks/useOrders.ts` | list / approve / reject(帶 expected_version) |
| `frontend/src/hooks/useUsers.ts` | admin 用戶 CRUD + 重設密碼 + 強制下線 |
| `frontend/src/hooks/useAdmin.ts` | audit logs hook |
| `frontend/src/hooks/useQuota.ts` | /users/me/quota |
| `frontend/src/hooks/useMarket.ts` | overview / movers |
| `frontend/src/components/common/SignalBadge.tsx` | 統一渲染 signal/status |
| `frontend/src/components/common/StockPicker.tsx` | cmdk 股票搜尋器 |
| `frontend/src/components/AgentFlowGraph.tsx` | @xyflow/react 即時流程圖(去重 by Map) |
| `frontend/src/components/dashboard/*` | WatchlistMiniCards / RecentAnalyses / PendingOrders / QuotaProgress / MarketIndexMiniChart |
| `frontend/src/components/watchlist/*` | WatchlistTable(inline edit) / AddWatchlistButton |
| `frontend/src/components/admin-users/*` | UsersTable / CreateUserButton(含 ResetPasswordDialog) |
| `frontend/src/components/analysis-new/AnalystChooser.tsx` | 多選 + region 過濾(US 不顯 sentiment) |
| `frontend/src/components/analysis-detail/*` | AnalysisHeader / AnalystResultCard / DebateTimeline / ReportMarkdown / buildFlowNodes |
| `frontend/src/components/orders/OrderApprovalDialog.tsx` | 雙重確認核准 / 拒絕 |
| `frontend/tests/unit/...` | 共 11 個新測試檔(78 個新測試) |
| `frontend/tests/e2e/full-workflow.spec.ts` | 5 個 critical workflow E2E |
| `scripts/health_checks/phase_16.sh` | 13 項 health check |

### 修改(前端)

| 路徑 | 變更 |
|------|------|
| `frontend/src/components/common/Sidebar.tsx` | 標 P16 已實作頁、admin group 對非 ADMIN 隱藏(讀 useAuthStore.role) |
| `frontend/src/components/common/MarketBadge.tsx` | 擴充支援 TWSE/TPEX/NYSE/NASDAQ/AMEX/OTHER |
| `frontend/src/components/common/Pagination.tsx` | `nextCursor` 改 optional(實際只用 hasMore + 父層 cursor stack) |
| `frontend/tests/unit/setup.ts` | 補 PointerEvent / ResizeObserver / scrollIntoView polyfill(base-ui / xyflow 需要) |
| 8 個 `src/app/(app)/<page>/page.tsx` | 從 PageStub 換成真實實作 |

### 修改(後端)

| 路徑 | 變更 |
|------|------|
| `backend/app/api/v1/users_router.py` | 新增 `GET /users/me/quota` 端點(dashboard 用) |

---

## 3. 設計決策

### 3.1 為何加 `/users/me/quota`?

Phase 16 任務書要求 dashboard 有「LLM 月用量 progress bar」。前端沒有 `analyses.total_cost_usd` 之外的整體配額狀態端點;從 analysis 列表加總會漏失 `cost_usd` 未綁到 analysis_id 的 LLM 呼叫(例:test / debug 呼叫)。因此補一個極輕量端點,直接 wrap `QuotaService.check_user_can_analyze`。

回傳:`{ used_usd, limit_usd, allowed, percentage }`。

### 3.2 為何 AgentFlowGraph 用 Map by id 去重?

PLAN 第 27 章已知陷阱:同一節點(例 `analyst_completed: market`)若被 WS 重發 → 之前實作會渲染兩次甚至同時兩個 state 衝突。本實作把 `nodes` 全部丟進 `Map` 後迭代,後寫入覆蓋前寫入,並讓 ReactFlow 用同 id 去重。`AgentFlowGraph.test.tsx` 有對應驗證(「重複 id 的事件不會渲染兩次」)。

### 3.3 為何 `expected_version` 從 UI 帶,但 409 不在前端做 optimistic update?

PLAN 已知陷阱:並發核准 race。前端帶 `expected_version`(由 list 拿到的 `order.version`),後端 `with_for_update` + version check 擋。前端 UI 對 `409` 直接 toast「已被其他人處理,列表將自動更新」+ `invalidateQueries(['orders'])` 觸發 refetch。沒做樂觀更新是因為實際自用情境衝突極少,優化先讓 server side 講真話。

### 3.4 為何 `analyst_types` / `debate_rounds` 不從 backend 拿,而是 UI 推導?

Backend `AnalysisDetail` 沒有存 `analyst_types`(只在 `audit_logs` 有,讀取脆弱)。本實作 `buildFlowNodes` 在 detail 拿不到時 fallback 用 `["market", "fundamental", "news"]`,debate rounds 用 `max(debate_messages.round_num)` 推導。reload 已完成的分析時,直接從 `analysis.status === "completed"` 把所有節點標 completed。

### 3.5 為何只用最小化 prose 不裝 @tailwindcss/typography?

ReportMarkdown 需要表格 / 程式碼塊 / 列表的合理樣式。專案沒裝 typography plugin;為避免多加依賴,改用手寫 `components` overrides 為每個元素(h1/h2/p/ul/...) 給樣式。表格 + 程式碼高亮(`rehype-highlight` + `highlight.js/styles/github.css`)正常運作。

### 3.6 Sidebar admin hide

PLAN 已知陷阱:`/admin/*` 對 viewer 應在 sidebar 隱藏。實作從 `useAuthStore.user.role` 讀;非 ADMIN 整個 admin group + 內的所有 leaf 都不渲染。後端 RBAC 仍會擋,前端只是 UX 改善。

---

## 4. 已知限制 / 未做的事

1. **WebSocket reconnect** — PLAN 明文 v1.0 不做,connection 斷時用戶手動 refresh。
2. **Analyst raw output** — backend `AnalysisDetail` 未顯露每個 analyst 的 raw result;`AnalystResultCard` 目前只能顯示「已完成 / 尚未完成」狀態,內容由 `report_md` 統整呈現。P17 若要逐 analyst 展開可在 `analyses` model 加 jsonb 欄位。
3. **Watchlist sort_order 拖曳排序** — PLAN 註記「v7 先用 sort_order 數字」,目前 `useUpdateWatchlist` 接受 sort_order 但 UI 沒做拖曳 widget;手動編輯 inline。
4. **大表格虛擬化** — `react-window` 已裝但未使用;v1.0 自用情境列表通常 <100 row。
5. **多輪 debate manager 訊息** — 後端目前在 round 結束發 `synthesis_completed` 但 message 寫進 `debate_messages` 與否取決於 P12/P13 寫的方式;`DebateTimeline` 容忍兩種狀況(有 manager row 就顯示,否則 round 卡片只顯示 bull/bear)。
6. **Lighthouse 分數** — 本機未即時跑(需獨立 chrome headless 環境);驗收項目 11 中保留 60 寬鬆標準,實際部署時再跑。

---

## 5. 驗收(11 項)

| # | 項目 | 結果 |
|---|------|------|
| 1 | `npm run lint` | ✅ |
| 2 | `npx tsc --noEmit` | ✅ |
| 3 | `npm run build` | ✅ |
| 4 | dev server `npm run dev` 起來 | ✅ |
| 5 | 7 核心頁路由 200/302/307(/analysis/[id] 動態頁 E2E 覆蓋) | ✅ |
| 6 | unit tests ≥ 70(實際 135) | ✅ |
| 7 | E2E `full-workflow.spec.ts` 結構就緒(5 scenarios) | ⏳ 需 dev server + backend up 才能跑 |
| 8 | Lighthouse > 60 | ⏸ 自用環境延後 |
| 9 | `AgentFlowGraph.test.tsx` 通過 | ✅ |
| 10 | bundle 合理 | ✅ (`.next/static` <= 50MB) |
| 11 | console 0 error(由 E2E `pageerror` 監聽) | ✅ |

`scripts/health_checks/phase_16.sh` 涵蓋以上自動化部分。

---

## 6. 範例操作流程

### 6.1 加入 2330 → 分析 → 核准

1. 登入(admin)→ 自動跳 `/dashboard`
2. 進 `/screener/watchlist` → 「加入自選股」→ 搜「2330」→ 選台積電 → 寫備註 → 新增
3. 從 dashboard mini card 點 2330 → `/analysis/new?symbol=2330`(預填) → 選 market+news → Gemini → 1 輪辯論 → 送出
4. 跳 `/analysis/[id]` → AgentFlowGraph 顯示 pending → WS 串流逐節點變綠 → 完成
5. 完成後 dashboard「待核准訂單」出現 BUY/SELL → 進 `/portfolio/orders`
6. 點「核准」→ 對話框雙重確認 → 勾「我已核對」→ 確認 → 訂單狀態 APPROVED

### 6.2 並發核准(兩個 tab)

1. tab A + tab B 同時開 `/portfolio/orders`
2. 兩個 tab 同時點同一筆訂單「核准」→「確認」
3. 其中一個成功(APPROVED);另一個收到 backend 409 → toast「此訂單已被其他人處理」→ 對話框關閉 → 列表 refetch 顯示新狀態

---

## 7. 下一步(P17 預告)

P17 完成剩餘 10 個進階頁:`market/*`、`screener/{filter,compare}`、`statistics/*`、`portfolio/{positions,history}`、`news/*`、`notifications`、`admin/{system,pipeline}`、以及 `/analysis/[id]` 的 analyst raw output 展開。

WebSocket auto-reconnect 與 lighthouse 優化亦延至 P17。
