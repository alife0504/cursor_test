# Frontend Pages Map(v1.0)

> 對應 PLAN § 21 18 頁完整地圖。每頁列出資料來源、相關 hooks、v1.1 待補項目。

## 完整接後端(13 頁)

| 路由 | 主要 hooks | 後端 endpoint | 備註 |
|------|----------|---------------|------|
| `/dashboard` | useMarketOverview / useMyQuota / useOrders / useWatchlist / useAnalysisList | 5 個合計 | P16 完成 |
| `/market/overview` | useMarketOverview / useMarketMovers | `/market/overview`、`/market/movers` | TW/US 切換 |
| `/market/institutional` | useInstitutional | `/market/institutional` | TW only |
| `/screener/watchlist` | useWatchlist | `/watchlist/*` | P16 完成 |
| `/screener/filter` | useScreener | `/screener` | 條件存 localStorage |
| `/analysis/new` | useCreateAnalysis | `/analysis` | P16,Idempotency-Key |
| `/analysis/[id]` | useAnalysisDetail / useAnalysisDebate / useAnalysisWS | `/analysis/{id}`、`/analysis/{id}/debate`、WS | P16 |
| `/analysis/history` | useAnalysisList | `/analysis` | P16 |
| `/portfolio/orders` | useOrders / useApproveOrder / useRejectOrder | `/orders/*` | P16 |
| `/portfolio/positions` | usePositions(內部用 useOrders APPROVED) | `/orders?status=APPROVED` | client-side 聚合 |
| `/portfolio/history` | useTradeHistory(內部用 useOrders) | `/orders` | client-side 篩選 |
| `/news/sentiment` | useStockNews | `/stocks/{sym}/news` | 個股 view |
| `/news/announcements` | useStockAnnouncements | `/stocks/{sym}/announcements` | 個股 view |
| `/notifications` | useNotificationSettings / useUpdateNotificationSettings / useSendTestNotification / useNotificationLogs | `/notifications/*` | LINE/TG/Email |
| `/admin/users` | useUsers | `/users/*`(admin) | P16 |
| `/admin/audit` | useAuditLogs | `/admin/audit` | P16 |
| `/admin/system` | useSystemInfo / useSystemMetrics | `/admin/system/{info,metrics}` | 24h 走勢用 mock |
| `/admin/pipeline` | useDLQ / useResolveDLQ / useRequeueDLQ | `/admin/pipeline/dlq*` | 手動 trigger v1.1 |

## Mock(v1.1 才接真實,5 頁)

| 路由 | 為何 mock | v1.1 接什麼 |
|------|----------|-------------|
| `/market/calendar` | 後端 endpoint 為 stub | 接 GET `/market/calendar` 真實事件 |
| `/screener/compare` | 後端無聚合 endpoint | 加 GET `/screener/compare?symbols=...` |
| `/statistics/accuracy` | actual_return_30d 後端未實作 | 把 confidence 條件換成真實命中 |
| `/statistics/models` | 已 client-side 聚合(算可用) | 後端可補 admin endpoint 加速 |
| `/statistics/backtest` | 後端無回測引擎 | 加 BacktestService + endpoint |

## 替換 mock → 真實的步驟

每頁的 mock 替換指引集中在自身的 `MockBanner trackingRef` 屬性。共通流程:

1. **加 type** 到 `src/lib/api-types.ts`(對齊後端 Pydantic schema)
2. **加 hook** 到 `src/hooks/`(沿用既有 axios + envelope pattern)
3. **替換 inline mock data 為 hook 呼叫**;`<MockBanner />` 一併移除
4. **Sidebar:**`mock: true` 移除即可

---

## 圖表元件

| 元件 | 對應檔案 | 用途 | 注意 |
|------|---------|------|------|
| `<ChartContainer />` | `common/ChartContainer.tsx` | 固定高度容器(避免 recharts 0px 問題)| P15 已就緒 |
| `<BarChart />` | `common/BarChart.tsx` + `BarChartInner.tsx` | bar chart wrapper | 整個 inner dynamic import 避型別衝突 |
| `<PieChart />` | `common/PieChart.tsx` + `PieChartInner.tsx` | pie chart wrapper | 同上 |
| `<MarketIndexMiniChart />` | `dashboard/MarketIndexMiniChart.tsx` | dashboard 大盤 mini chart | 用 lightweight-charts |

---

## 已知 UX 細節

- **Mock badge**:Sidebar 對 mock 頁顯示黃色 `mock` badge,游標 hover 顯示「v1.1 將完整實作」。
- **跨市場切換閃爍**:`<MarketSwitcher />` 用 `useTransition` 包裹 setState,符合 PLAN § B 已知陷阱。
- **大表格效能**:目前 18 頁無使用 react-window 虛擬化(自選股 + screener 自用情境 < 100 筆)。
- **dark theme 對比**:BarChart / PieChart 用 hard-coded HEX 而非 CSS var(自訂 theme color),確保 dark mode 下對比足夠。
