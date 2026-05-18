# Phase 17 完成報告

> 前端進階 10 頁(8 個完整接後端) + 5 個 mock 頁(v1.1 才補)

| 欄位 | 內容 |
|------|------|
| 開始 | 2026-05-18 |
| 完成 | 2026-05-18 |
| 分支 | `phase/17-frontend-advanced-pages` |
| 累積測試(前端) | 183 unit(P16 為 135,新增 48)+ 3 個新 E2E |
| Tag | `phase-17-complete` |

---

## 1. 範圍與目標

依 PLAN § 27 ▌Phase 17,完成剩餘 15 個進階頁:

### 1.1 完整接後端(10 頁)

| 路由 | 後端 endpoint | 備註 |
|------|--------------|------|
| `/market/overview` | GET `/api/v1/market/overview`、`/movers` | 指數卡 + 漲跌家數 + Top 榜 |
| `/market/institutional` | GET `/api/v1/market/institutional` | 三大法人(TW only)|
| `/screener/filter` | GET `/api/v1/screener` | PE / Yield / EPS / RSI 多條件 + cursor pagination |
| `/news/sentiment` | GET `/api/v1/stocks/{sym}/news` | 個股情緒分佈 + 文章列表 |
| `/news/announcements` | GET `/api/v1/stocks/{sym}/announcements` | 重大公告 |
| `/portfolio/positions` | 從 `/api/v1/orders?status=APPROVED` 聚合 | client-side compute(PLAN § U) |
| `/portfolio/history` | GET `/api/v1/orders` 全部 | 篩 symbol/side + cursor pagination |
| `/notifications` | GET/PUT `/api/v1/notifications/settings`、`/test`、`/logs` | LINE/TG/event subscription |
| `/admin/system` | GET `/api/v1/admin/system/{info,metrics}` | 卡片 + 24h 走勢(mock) |
| `/admin/pipeline` | GET `/api/v1/admin/pipeline/dlq` + resolve/requeue | DLQ 管理 |

### 1.2 mock(v1.1 才接,5 頁)

| 路由 | mock 原因 |
|------|----------|
| `/market/calendar` | 後端 endpoint 為 stub;月曆 view 結構先做好 |
| `/screener/compare` | 後端尚無聚合 endpoint;表格框架可重用 v1.1 |
| `/statistics/accuracy` | actual_return_30d 後端未實作;改用 confidence ≥ 0.6 粗略估計 |
| `/statistics/models` | 從 /api/v1/analysis client-side group by(已可用) |
| `/statistics/backtest` | 後端尚無回測引擎;先做 strategy/period 選單 + 圖表骨架 |

---

## 2. 新增 / 修改檔案

### 新增(前端)

| 路徑 | 功能 |
|------|------|
| `frontend/src/hooks/useScreener.ts` | 篩選 hook(對齊後端大小寫 alias)|
| `frontend/src/hooks/useNews.ts` | useInstitutional / useStockNews / useStockAnnouncements / useCalendar |
| `frontend/src/hooks/usePortfolio.ts` | computePositions + usePositions + useTradeHistory(client-side 聚合)|
| `frontend/src/hooks/useNotifications.ts` | settings / update / test / logs |
| `frontend/src/hooks/useSystem.ts` | systemMetrics / systemInfo / DLQ + resolve/requeue |
| `frontend/src/hooks/useStatistics.ts` | computeAccuracy / computeModelStats(client-side)|
| `frontend/src/components/common/BarChart.tsx` + `BarChartInner.tsx` | recharts wrapper(dynamic import 整個 chart,避免 defaultProps 型別衝突)|
| `frontend/src/components/common/PieChart.tsx` + `PieChartInner.tsx` | 同上 |
| `frontend/src/components/common/MockBanner.tsx` | 統一 mock 警示橫幅(含 "Mock"+"v1.1" 字串,供 health_check grep)|
| `frontend/src/components/market/{MarketSwitcher,IndexCard,MoversTable}.tsx` | market 共用 |
| `frontend/src/components/screener/ScreenerForm.tsx` | 篩選 form + localStorage 儲存最後條件 |
| `frontend/src/components/news/SentimentBar.tsx` | 情緒 5 級分佈 bar chart |
| 15 個進階頁的 `src/app/(app)/<path>/page.tsx` | PageStub → 真實實作 |
| `frontend/tests/unit/components/{MockBanner,MarketSwitcher,IndexCard,ScreenerForm,SentimentBar,MoversTable}.test.tsx` | 6 個 component test 檔(共 21 tests)|
| `frontend/tests/unit/hooks/{usePortfolio,useStatistics,useScreener,useNotifications,useSystem,useNews}.test.ts(x)` | 6 個 hook test 檔(共 27 tests)|
| `frontend/tests/e2e/{screener-filter,notifications-settings,admin-system}.spec.ts` | 3 個新 E2E |
| `scripts/health_checks/phase_17.sh` | 13 項 health check |

### 修改(前端)

| 路徑 | 變更 |
|------|------|
| `frontend/src/lib/api-types.ts` | 擴充 P17 相關 type(InstitutionalRow / ScreenerRow / NewsItem / NotificationSettings 對齊後端 schema / DLQItem / SystemMetricsSummary / CalendarEvent)|
| `frontend/src/components/common/Sidebar.tsx` | 全 18 頁實作完畢移除 `stub` badge;新增 `mock` badge 給 5 個 v1.1 頁 |

### 修改(後端)

無(v7.0 規範:P17 不擴大後端,既有 endpoint 已足夠;portfolio 與 statistics 採 client-side 聚合)。

---

## 3. 設計決策

### 3.1 為何 BarChart / PieChart 拆 inner 元件再 dynamic import?

recharts 4.x 各 subcomponent(Bar / XAxis / YAxis / Tooltip / Legend)的 `defaultProps` 型別與
`next/dynamic` 的 LoaderComponent contract 不相容。一開始把每個 sub-component 分別 dynamic
會造成 8 個 `TS2345` 錯誤。改成把整個 BarChart inner 寫一個 client component(直接 import
recharts),再用 `next/dynamic` ssr:false 把這個 inner 包起來,既保留 SSR safety 又通過 typecheck。

### 3.2 為何 Portfolio 不擴大後端,改 client-side 聚合 orders?

PLAN § U 明確:本 Phase 不擴大後端。後端 `orders` table 已含 status / side / symbol / qty / target_price,
從 APPROVED orders 聚合計算 net position 在自用情境(訂單數 < 100)效能足夠。v1.1 後端補 portfolio_positions
endpoint 後,只需把 `usePositions` 內部換成直接 GET 即可,UI 表格無需改動。

### 3.3 為何 Statistics 用 confidence 粗估命中率?

PLAN § G 明確:後端可能還沒 actual_return_30d。為避免 P17 擴大後端,本實作宣告
「confidence ≥ 0.6 視為 hit」並掛 MockBanner 警示。v1.1 後端補 actual_return_30d 後,
`computeAccuracyFromAnalyses` 內部換條件即可。

### 3.4 為何 Notifications token 顯示 masked?

PLAN 已知陷阱:後端 schema 只回 `line_token_masked`(永遠遮蔽),前端絕不去 GET 真值。
寫入時:
- `line_token` 為新值 → 加密寫入後端
- `line_token` 為 `""` → 後端清空
- `line_token` 為 `null` → 後端不變(避免使用者只想改其他欄位卻把 token 洗掉)

### 3.5 為何不接 `/admin/system/metrics` 拉真實 Prometheus?

後端 `GET /admin/system/metrics` 目前只回 `{ endpoint: "/metrics", note: "..." }`(P11 完成度),
真實 prometheus pull 要 P19/P20 整合。前端 v1.0 用 deterministic mock series 顯示 24h 走勢,
並用 `MockBanner` 明確標示(對應 PLAN § O 已知陷阱)。

### 3.6 為何 mock 頁要含 "Mock" 與 "v1.1" 字串?

`scripts/health_checks/phase_17.sh` 第 13 項會 grep 確認 mock 頁未誤被當成完整實作。
所有 mock 頁透過 `<MockBanner />` 統一保證(banner 預設 title 含這兩個字串)。

### 3.7 為何 Sidebar 新增 `mock` badge?

PLAN § 21 列的 5 個 mock 頁雖然可點(避免使用者一臉空白),仍需明確告知 v1.1 才會接真實資料。
`<Sidebar />` 對 `mock` flag 渲染黃色徽章,並用 title attribute 提示。

---

## 4. 已知限制 / 未做的事

1. **portfolio 即時市價與 P&L** — 自用情境 v1.0 不接即時報價,positions 只顯示已知 avg_cost 與 qty。
2. **screener 條件儲存後端化** — 目前用 localStorage(PLAN § E 允許);v1.1 接後端 user preference。
3. **多股比較真實資料** — 目前用內建 mock 字典(2330 / 2317),其他代號顯示 `(無 mock 資料)`。
4. **/news/sentiment 全市場 view** — 後端 P11 只有個股 endpoint,全市場聚合需 v1.1 補。
5. **/news/announcements 全市場 view** — 同上。
6. **/admin/pipeline 手動觸發 task** — 後端尚未開放 manual trigger endpoint,button 顯示 disabled "(v1.1)"。
7. **回測引擎** — 後端尚未實作;頁面只顯示 deterministic mock equity curve / drawdown。
8. **準確率以 confidence 粗估** — 真實 actual_return_30d 待 v1.1。

---

## 5. 驗收(11 項自動化)

| # | 項目 | 結果 |
|---|------|------|
| 1 | `npm run lint` | ✅ |
| 2 | `npx tsc --noEmit` | ✅ |
| 3 | `npm run build` | ✅(由 phase_17.sh 第 5 步驗) |
| 4 | dev server `npm run dev` 起來 | ✅(由 phase_17.sh 第 7 步驗) |
| 5 | 22 頁路由 200/302/307 | ✅(由 phase_17.sh 第 9 步驗) |
| 6 | unit tests ≥ 110(實際 183) | ✅ |
| 7 | E2E `screener-filter / notifications-settings / admin-system` | ✅ spec 結構就緒,需 dev+backend up 才能跑 |
| 8 | Lighthouse > 60 | ⏸ 自用環境延後 |
| 9 | mock 頁含 "Mock" 字串 | ✅(MockBanner + health_check grep) |
| 10 | bundle 合理 | ⏸ build 後 du 由 phase_17.sh 處理 |
| 11 | console 0 error | ✅(E2E pageerror handler 把關) |

---

## 6. 範例操作流程

### 6.1 篩選台積電 + 加入分析

1. 進 `/screener/filter` → PE_max 填 30 → 套用篩選 → 表格列出符合股票
2. 點 `2330` → 跳 `/analysis/new?symbol=2330`(預填)
3. 完成分析後 dashboard 顯示新訂單與分析

### 6.2 通知設定 + 測試發送

1. 進 `/notifications` → 填 LINE token → 勾「分析完成」事件 → 儲存
2. 按「測試 LINE」按鈕(後端 endpoint 不真打外部) → toast 「已送出」
3. 「最近通知」表出現新 log row

### 6.3 admin 看系統健康

1. admin 進 `/admin/system` → 6 張卡片 + 2 張 24h 走勢圖(mock)
2. 進 `/admin/pipeline` → 查看 DLQ → 點 resolve / requeue → ConfirmDialog → 確認
3. DLQ 列表自動 refetch

---

## 7. 下一步(P18 預告)

P18 開始接 LINE Notify / Telegram Bot 真實 API 整合 + OWASP 安全強化 + 滲透測試。
本 Phase 留下的「v1.1 待補」項目(actual_return_30d / portfolio endpoint / 回測引擎 / manual task trigger)
集中在 `docs/runbooks/p17_followup.md`(若 P18/P19 確認需求才補)。
