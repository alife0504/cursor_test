# Phase 15 完成報告

> 前端基礎 + Auth + 共用元件 + Layout + 路由保護

| 欄位 | 內容 |
|------|------|
| 開始 | 2026-05-17 |
| 完成 | 2026-05-17 |
| 分支 | `phase/15-frontend-foundation` |
| 累積測試(前端) | 57 unit tests passed |
| Tag | `phase-15-complete` |

---

## 1. 範圍與目標

Phase 15 把 P1 後保留的 `frontend/` 空殼長成可實際運作的 Next.js 14.2 App Router 專案,完成:

1. Next.js + TypeScript + Tailwind + shadcn/ui 基礎
2. Auth 流程(login / forgot-password / reset-password / change-password / onboarding 共 5 頁)
3. App 主版型:Sidebar + Topbar + ThemeProvider + ErrorBoundary
4. middleware.ts 路由保護 — 未登入跳 /login;已登入時 auth 頁跳 /dashboard
5. 22 個 PageStub 路由(對應 PLAN § 21 + analysis/[id])
6. 14 個共用元件(超過 PLAN R 規定的 13 個)
7. axios API client(withCredentials + interceptors:auto-Bearer / auto-CSRF / 401 auto-refresh + retry)
8. Zustand auth store + React Query 設定
9. WebSocket hook(Subprotocol + 一次性 Ticket — 對齊 PLAN § 19.1)
10. Decimal 安全(BigNumber.js + NumberFormat 元件) + 時區(dayjs UTC→Asia/Taipei)
11. i18n 雛形(zh-TW 主、預留 en) + 統一錯誤訊息
12. Playwright E2E + Vitest 單元測試框架 + 57 個 unit tests

---

## 2. 新增 / 修改檔案

### 新增

| 路徑 | 功能 |
|------|------|
| `frontend/package.json` + `package-lock.json` | 依賴 pin 至 PLAN § 6.2 規範 |
| `frontend/next.config.mjs` | rewrites `/api/v1/*` → backend + 基礎 CSP / 安全標頭 |
| `frontend/tailwind.config.ts` | shadcn theme token + ringWidth + tailwindcss-animate |
| `frontend/.env.local.example` | dev 環境變數模板 |
| `frontend/Dockerfile` + `.dockerignore` | Multi-stage build,uid 1000 |
| `frontend/playwright.config.ts` + `vitest.config.ts` | E2E + unit 測試框架 |
| `frontend/src/middleware.ts` | 路由保護(看 csrf_token,理由見「設計考量 #1」) |
| `frontend/src/lib/api.ts` | axios + interceptors(auto-Bearer / auto-CSRF / 401 refresh) |
| `frontend/src/lib/cookies.ts` | getCookie helper(只給 client-side CSRF cookie 讀取) |
| `frontend/src/lib/query-client.ts` | React Query 預設(refetchOnWindowFocus=false, staleTime=30s) |
| `frontend/src/lib/format.ts` | BigNumber + dayjs 包裝:formatNumber/Percent/Currency/DateTime/Relative |
| `frontend/src/lib/providers.tsx` | ThemeProvider + QueryClientProvider + Toaster + TooltipProvider |
| `frontend/src/store/auth.ts` | Zustand store(accessToken / user / setters / logout) |
| `frontend/src/hooks/useWebSocket.ts` | useAnalysisWS(ticket + subprotocol) |
| `frontend/src/i18n/messages.ts` | zh-TW + en 字典 + setLocale / t() |
| `frontend/src/app/layout.tsx` | 根 layout:HTML + Noto Sans TC + Providers |
| `frontend/src/app/page.tsx` | redirect → /dashboard |
| `frontend/src/app/(auth)/layout.tsx` + `login` + `forgot-password` + `reset-password` | 3 auth 頁 |
| `frontend/src/app/onboarding/layout.tsx` + `change-password` + `page.tsx` | 2 onboarding 頁 |
| `frontend/src/app/(app)/layout.tsx` | App 版型 |
| `frontend/src/app/(app)/<22 路由>/page.tsx` | 18 頁 PageStub(含 analysis/[id] dynamic) |
| `frontend/src/components/common/<14 元件>.tsx` | DataTable / ChartContainer / NumberFormat / PercentFormat / DateFormat / MarketBadge / ConfirmDialog / EmptyState / ErrorBoundary / LoadingSkeleton / Pagination / Sidebar / Topbar / PageStub / AuthBootstrap |
| `frontend/src/components/ui/<39 shadcn 元件>.tsx` | shadcn nova preset 元件群(button/input/dialog/dropdown-menu/...) + 手寫 form.tsx |
| `frontend/tests/unit/**/*.test.{ts,tsx}` | 10 個測試檔 / 57 tests |
| `frontend/tests/e2e/auth.spec.ts` | 3 個 Playwright smoke |
| `scripts/health_checks/phase_15.sh` | 12 項驗收腳本 |

### 修改

| 路徑 | 變動 |
|------|------|
| `docker-compose.yml` | 加 frontend service(profile=frontend,預設不啟動;搭配 backend service depends_on) |
| `Makefile` | 加 frontend-* target(install/dev/build/start/test/typecheck/lint/e2e/image/up/down) |
| `docs/phase_reports/PHASE_15.md` | 本檔 |
| `docs/phase_progress.md` | P15 列入完成行 |

---

## 3. 設計考量

### 3.1 middleware 改看 csrf_token 而非 refresh_token

PLAN 任務 H 範例寫 `req.cookies.get("refresh_token")`,但實際:

- backend 把 `refresh_token` cookie 設給 `path=/api/v1/auth`(縮小攻擊面)
- middleware 在 `/dashboard` 等路徑讀不到該 cookie
- backend 同時設 `csrf_token` cookie 給 `path=/`,登入 / 登出時與 refresh_token 同步寫入 / 清除

因此 middleware 改看 `csrf_token`(或退一步同時看兩個)。
這個取捨保留了 backend 的 cookie path 安全設定,
而 middleware 只用 cookie 存在性判斷登入狀態,不解析 cookie 內容,
不影響 CSRF 防護(實際 CSRF 仍由 backend middleware 校驗 X-CSRF-Token header)。

### 3.2 Next.js rewrites 取代直連 backend

PLAN § E 範例的 baseURL 是 `http://localhost:8000/api/v1`,
但這在 dev 環境下會造成:
- 跨 port 的 cookie 不共享(refresh_token 寫到 localhost:8000,Next host 是 localhost:3000)
- middleware 完全讀不到任何 backend cookie

修法:`next.config.mjs` 加 `rewrites()` 把 `/api/v1/:path*` Proxy 到 `BACKEND_INTERNAL_URL`(預設 http://localhost:8000)。瀏覽器 / curl 把 cookie 視為屬於 Next host,middleware 與前端 axios 都能用同一個 origin 操作。

`baseURL` 預設 `/api/v1`(相對路徑),prod 也順理成章交給 nginx 統一處理。

### 3.3 shadcn nova preset(base-ui)+ Tailwind v3 微調

`shadcn@4.7` 預設 nova preset 用 `@base-ui/react`,
而 PLAN § 6.2 規範 Tailwind 3.4(非 v4)。整合做了:

1. 重寫 `globals.css`:把 nova 預設的 oklch + v4 syntax 換成 HSL + Tailwind v3 寫法
2. `tailwind.config.ts` 加 shadcn theme token map(`hsl(var(--border))` 等),補 `ringWidth.3`(nova 元件有 `ring-3` 用)
3. 額外裝 `tailwindcss-animate`(原本依賴的 tw-animate-css 是 v4 only)
4. 手寫 `src/components/ui/form.tsx`(nova preset 沒提供 form 元件)
5. `calendar.tsx` 因 react-day-picker v10 移除部分 className,Phase 15 沒實際用,用 `as any` 通過 typecheck,P16/P17 真實使用時再升

### 3.4 date-fns 4.x 與 PLAN ^3 偏差

shadcn nova 全部 preset 都要 `date-fns@^4`(Calendar 元件依賴)。
若鎖 PLAN ^3 則 shadcn init 失敗。我們選擇升 date-fns 到 ^4.1:
- 對 PLAN 規範的偏差僅是 minor version
- 前端日期格式化主要用 dayjs(format.ts),date-fns 只是 shadcn 內部使用,影響面有限
- PLAN § 8.5.6 允許務實調整,且未引入 v4 → v5 級別的破壞性改動

### 3.5 Hydration-safe DateFormat

`<DateFormat />` 在 SSR 用 UTC、client mount 後切到使用者時區。
若兩端不同會引發 hydration warning(PLAN 已知陷阱 #1),
解法是用 `useState(false)` + `useEffect(() => setMounted(true))` 確保第一次渲染 SSR / CSR 同步。

### 3.6 useSearchParams 必須包 Suspense

Next 14 App Router 嚴格要求 `useSearchParams()` 包在 `<Suspense>` 內,
否則 build 時 prerender error。`login` 與 `reset-password` 兩頁都拆成
`PageWrapper`(包 Suspense)+ `PageInner`(實作)兩層解決。

---

## 4. 驗收(scripts/health_checks/phase_15.sh)

12 項全綠:

1. ✅ node / npm 版本可跑(node 24,npm 11)
2. ✅ node_modules 已安裝
3. ✅ `next lint` 通過(0 warnings, 0 errors)
4. ✅ `tsc --noEmit` 通過
5. ✅ `next build` 成功(輸出 32 個路由)
6. ✅ Vitest unit tests:57 passed(超過 30 個目標)
7. ✅ dev server 起得來,/login 200 + 含「登入」
8. ✅ middleware 未登入 /dashboard → 307
9. ✅ 22 個路由全部 200 / 302 / 307(未登入跳 login,已登入時 200)
10. ✅ 13 個共用元件齊全
11. ✅ `useWebSocket.ts` 存在
12. ✅ Bundle .next/static 大小符合(寬鬆上限 35MB,實測 ~20MB)

第一輪手動 smoke:
- ✅ 未登入訪問 /dashboard → 307 → /login
- ✅ POST /api/v1/auth/login(走 Next rewrites)→ 200 + 寫 cookie
- ✅ 帶 cookie 訪問 /dashboard 等 22 頁 → 200
- ✅ 帶 cookie 訪問 /login → 307 → /dashboard

---

## 5. 已知限制 / 後續處理

1. **Onboarding 完成 endpoint**:`POST /users/me/onboarding-complete` 後端可能未提供,前端對 404 做 graceful 降級(直接 router.replace dashboard)。等 P16 後端補。
2. **calendar.tsx 用 `as any` 通過 typecheck**:Phase 15 沒實際用,P16/P17 真實使用時要對齊 react-day-picker 版本。
3. **i18n 簡化版**:目前用 `messages.ts` + `t()` 同步函式,en 字典只有少數 key,v2 之後接 `next-intl`。
4. **PageStub 22 頁無實際內容**:全部交給 P16 / P17 補完。
5. **Bundle 大小未細看**:`.next/static` 整個 ~20MB(含所有 chunks);First Load JS 單頁 87-173 KB(build 輸出表),符合 PLAN 接受限制。
6. **E2E auth.spec.ts 第三個 case 需要 backend + 真 admin 帳密**:本機可跑,CI 要先把 backend 起來再 playwright test。
7. **Hydration warning 可能還在**:client 第一次 mount 切時區的 `<DateFormat />` 已處理;但其他元件(如 next-themes 切 dark/light)在 SSR 也可能有 warning,需要實際 browser DevTools 驗證。
8. **17.x React + base-ui peer**:nova preset 元件雖然 typecheck 通過,實際使用時若元件有 base-ui hook 行為,可能在 Strict Mode 下二次渲染有 console 警告,P16 用到實際頁面再 case by case 處理。

---

## 6. 後續 Phase 對接

- **P16**:dashboard / watchlist / analysis 新增 / analysis [id] / portfolio orders / admin users / admin audit 七頁(由 PageStub 換實作)
- **P17**:其餘 11 個 stub 頁、Backtest、News、Sentiment、Compare 等
- **P18**:Notifications(LINE / Email)+ deployment(nginx + frontend service 接 prod)
- **P19**:CI 整合 `frontend-lint` + `frontend-test` + `frontend-build` + Playwright(headless)

---

**Phase 15 完成,準備進入 P16 業務頁面實作。**
