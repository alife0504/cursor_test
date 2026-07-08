# Changelog

All notable changes to TradingAgents are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Breaking changes within the 0.x line are called out explicitly.

## [1.1.0] — Unreleased（開發中，2026-07-06，Opus 4.8）— 自動選股預篩選 + 上游 v0.2.5~v0.3.1 對照修補

> 兩件事：① 依使用者需求新增「自動選股預篩選」（在昂貴的多 Agent pipeline 前先用純數據篩股省 LLM）；② 對照上游 TauricResearch/TradingAgents v0.2.5→v0.3.1 的變動，客觀評估後只套用適合本 TW 版的部分。
> 驗證：後端 513 unit 全綠、ruff 乾淨；前端 tsc 0 錯。screening 對真實 dev DB 選股正確（basic/low/mid/high = 6/4/3/2）、批次端點端到端測過（screen_level=high → count=2）。
> 註：本版建立在 v1.0.2 之後一系列尚未提交的工作（Discord 遷移／完整風險架構／per-agent 模型／5 分析師重構）之上。

### Added — 自動選股預篩選（未指定個股時的 fallback）
- 新 [screening_service.py](backend/app/services/screening_service.py)：`ScreeningService.select_symbols(region, level)` — 取近期日均成交額前 N 檔流動性候選池 → 撈近 90 日 K 算價量指標（MA20/60、RSI14、20 日報酬、波動、量比）→ 純函式 `select_candidates()` 依等級加權評分（百分位排名）取前 N（**保證比例**）。門檻/權重全集中檔案頂部常數，方便微調。
- config 加 `SCREEN_BASE_COUNT`(6)／`SCREEN_POOL_SIZE`(60)／`SCREEN_LOOKBACK_DAYS`(90)／`SCREEN_MIN_PRICE`／`SCREEN_MIN_AVG_TURNOVER`（floor 全濾空時自動放寬）。
- `AnalysisCreateRequest` `symbol` 改選填、加 `screen_level`(basic/low/mid/high)＋`market`(TW/US)，model_validator 強制 symbol⊕screen_level 二擇一；回應加 `count/analysis_ids/screened_symbols`。[analysis_router](backend/app/api/v1/analysis_router.py) 分流：有 symbol→單筆；無 symbol→篩選→逐檔建立（美股自動濾掉情緒/籌碼）。
- 前端 [analysis/new/page.tsx](frontend/src/app/(app)/analysis/new/page.tsx) 加「2. 自動選股篩選」步驟卡（新元件 [ScreenLevelChooser.tsx](frontend/src/components/analysis-new/ScreenLevelChooser.tsx)，對齊 AnalystChooser 風格），原步驟順延；未選股也可送出、批次回應跳 /analysis/history；step2 加 TW/US 篩選市場切換；預估卡按檔數估算。

### Security — 批次分析硬上限 + 全棧相依性審計（深度審查）
- **批次分析硬上限（重要）**：自動選股雖可篩出低級約 600 檔，但一次對數百檔各建完整多 Agent 分析會瞬間爆掉 $50 月配額 / 跑數小時。新增 `SCREEN_MAX_ANALYSES`(預設 30) 硬上限——[analysis_router](backend/app/api/v1/analysis_router.py) 只實際建立「篩選排序後前 N 檔」的分析，其餘為候選未分析；回應加 `screened_count`（篩出總數），前端預估卡與 toast 誠實顯示「篩選候選 X 檔 / 實際分析前 N 檔」。
- **相依性審計（pip-audit + npm audit）**：記錄結果、依風險分級（未盲目升級，避免破壞已運行系統）：
  - 前端 **Next.js 14.2.35** 有 6 個 advisory（DoS / cache-poisoning / WS SSRF / CSP-nonce XSS），修補需升到 **Next 16**（大型破壞性遷移）→ 待辦；自用單人 + 認證後風險較低。
  - 後端 pip-audit：`starlette`(多 CVE，FastAPI 綁版)、`langgraph 0.2→1.0`(專案刻意 pin <0.3)、`cryptography 45→46`(超出 range)、`pytest 9`(dev) 皆需大版遷移 → 待辦。`pyjwt` CVE 為 transitive、**認證實際用 python-jose 不受影響**。可安全 in-range 微升者（urllib3/idna/pydantic-settings）風險/效益比低，暫緩。
  - 安全掃描（shell=True/eval/verify=False/弱加密/pickle/yaml.load）：**全 clean**（僅 rate_limit 的 Redis Lua `eval` 為正常用法）。

### Changed — 自動選股 UI/等級重設計（使用者需求）
- **步驟 2 改版**：① 拿掉「篩選市場 TW/US」切換，改成固定的「**基本篩選(必備)**」說明列（基本 floor 永遠先套用、非可選）。② 移除「基本」可選選項（因必備）。③ **步驟 1 選股 ↔ 步驟 2 自動選股「雙向互斥」**：選了等級 → 步驟 1 選股框反灰；選了個股 → 步驟 2 反灰 +「清除選擇」鈕;點已選等級可取消(回未選)。④ 等級改絕對檔數:**低級約 600 / 中級約 300 / 高級約 150 檔**(原 2/3·1/2·1/3 比例制)。
- 後端對應：`screen_level` 僅 `low/mid/high`（移除 basic）;`SCREEN_COUNT_LOW/MID/HIGH`(600/300/150) 取代 `SCREEN_BASE_COUNT`;`SCREEN_POOL_SIZE` 提到 1000;`ScreenLevelChooser`/`StockPicker`(加 disabled) 對應調整。前端加**批次成本警語**(檔數多時成本/時間高、留意月配額)。
- ⚠️ 待辦（真實行情回填後必做）：低級 600 檔＝一次批次建 600 筆完整分析,成本/時間巨大,屆時需加「實際建立筆數上限」或改為「先產清單再逐檔核准」。dev 只有 8 檔股票、天然受限,故目前無立即風險。

### Fixed — 自動選股 relaxed fallback 的 NULL 流動性排序（深度自審發現）
- [screening_service.py](backend/app/services/screening_service.py) `_liquid_shortlist`：floor 把候選池清空後的 relaxed 放寬查詢原本 `ORDER BY avg(turnover) DESC`，但 NULL turnover 在 Postgres DESC 會 NULLS FIRST 排最前 → 反而優先選到零流動性、無法交易的股票。改加 `HAVING avg(turnover) > 0`，放寬價格/門檻但仍要求正成交額。

### Added — LLM 暫時性錯誤退避重試（對齊上游 v0.3.1 `llm_max_retries`）
- [fallback_chain.py](backend/app/llm/fallback_chain.py)：同一 provider 對 429／5xx／timeout 等暫時性錯誤指數退避重試（`is_transient_llm_error` 掃例外鏈比對特徵）。只有 Google 金鑰時 fallback chain 無別家可轉，這層是唯一韌性來源。config 加 `LLM_MAX_RETRIES`(2)／`LLM_RETRY_BASE_DELAY_S`(0.8)。非暫時性錯誤（schema）不重試。

### Fixed — Anthropic provider sampling 參數守衛（配合模型目錄刷新）
- [anthropic_provider.py](backend/app/llm/anthropic_provider.py)：Opus 4.7+／Sonnet 5／Fable 5 移除 sampling 參數，傳 `temperature` 會 400。`generate()` 改為僅在模型接受時才帶 temperature（`_rejects_sampling_params` 前綴判斷）；Haiku 4.5／Sonnet 4.6 照舊。對齊 Anthropic 遷移指南（adaptive thinking only）。

### Added — 模型目錄刷新（對齊上游 v0.3.1 現役 Claude 5 系列）
- 前端 [llm-models.ts](frontend/src/lib/llm-models.ts) 加 Claude Sonnet 5（$3/$15）、Claude Opus 4.8（$5/$25）；後端 anthropic pricing 加 `claude-sonnet-5`、`claude-fable-5`（$10/$50）。皆標「需有效金鑰」（本環境僅 Google key 有效）。

### Reviewed — 上游變動評估後「不適用本版」（客觀結論，未改）
對照上游後判定多數修補因本版架構已避開或處理方式不同而不適用，記錄理由以免日後重工：
- **v0.3.1 #1088 風險/辯論 router crash**：本版兩個 conditional router 各自獨立、path_map 完整涵蓋所有回傳值，結構上不會踩到。
- **v0.3.1 #1116 news prompt/tool 不一致**：本版 news analyst 不走 LLM tool-calling（Python 先抓資料塞 prompt），且 langchain 工具描述已正確標 `symbol`。
- **v0.3.0 look-ahead 安全**：本版無歷史回放模式（永遠跑「當下」），不會抓未來資料；`recursion_limit=50` 已等同 max_recur_limit。
- **v0.2.5 ticker path-traversal**：本版走 DB + validators，無任何以 symbol 組檔案路徑之處。
- **v0.2.5 grounded sentiment**：本版已用「新聞情緒聚合」自行重構（無 PTT/Reddit 爬蟲），方向不同。
- 待辦（真正適用但工程量大，暫緩）：v0.3.0「拒絕過期 OHLCV／標註資料新鮮度」——真實行情回填後再做（見 v1.1 待辦）。

---

## [1.0.2] — 2026-06-03 — 功能接通 + 認證穩定性 + 前端欄位稽核 + 市場數據

> 以 Opus 4.8 視角延續 v1.0.1：聚焦「把宣稱完成但實際失效的功能真正接通」、修補會導致閒置後被強制登出的認證隱憂、全面對齊前端欄位名與後端 schema，並讓大盤指數真正有值。多項修正已於本機接上真實後端（Docker stack）逐頁視覺驗證。
> 驗證：後端新增測試全綠（market router 8 passed 等）；前端 typecheck 0 errors、vitest 209 passed、next build 成功。

### Fixed — 核心功能缺口（v1.0.1 宣稱完成但實際失效）
- **`analyst_outputs` 從未寫入 DB**：分析詳情頁的 AnalystResultCard 永遠 fallback「結構化資料尚未取得」。
  - 新增 [analyst_outputs.py](backend/app/agents/analyst_outputs.py)：把 LangGraph `final_state["analyses"]`（各 analyst 結構化 JSON）轉成前端 `AnalystOutput`（score / signal / key_points / report_md / metrics），含 stub 純文字 fallback。
  - `run_analysis._update_completed` 寫入 `analyst_outputs`，並在 `analyst_types` 為空（auto-select）時用實際跑過的 analyst 回填。
- **大盤指數 KPI 永遠是「—」**：KpiRow 讀 `market.data.index`（物件）但後端只回 `indices`（名稱清單）且無報價。
  - [KpiRow.tsx](frontend/src/components/dashboard/KpiRow.tsx)：後端無報價時改從指數 OHLCV 序列推導 close + 當日漲跌%；無資料時顯示誠實的「指數資料待接入」而非誤導性副標。

### Fixed — 認證穩定性（隱憂，會導致被強制登出）
- **Refresh 風暴 → 強制全部登出**：多查詢頁面（如儀表板）在 access token 過期後會同時噴多個 401。原本每個 401 各自呼叫 `/auth/refresh`，但後端 refresh token 是單次輪替，並發 refresh 會被「重用偵測」判為攻擊 → **強制撤銷所有 session**。使用者閒置約 15 分鐘後重整就可能整個被登出。
  - [api.ts](frontend/src/lib/api.ts)：新增共用 in-flight refresh promise（mutex），並發 401 共用同一次 refresh。
  - [AuthBootstrap.tsx](frontend/src/components/common/AuthBootstrap.tsx)：改走同一個共用 `refreshAccessToken()`，與 interceptor 不再互相競態。

### Fixed — 前端欄位對齊後端 schema（全面稽核）
對照 `backend/app/schemas/*.py` 稽核前端，修正多處 typecheck 抓不到的欄位名不一致（前端讀的 key ≠ 後端回傳 → 顯示空 / — / 篩選失效）：
- **MarketOverview**：`index`→`indices`、`advancers/decliners/unchanged` → `advance_count/decline_count/unchanged_count`（市場總覽頁 + 儀表板 MarketIndexMiniChart）
- **NewsItem**：`sentiment_label` → `sentiment`（新聞情緒頁 + SentimentBar）
- **AnnouncementItem**：`type` → `announcement_type`；移除後端不存在的 source 欄
- **ScreenerRow**：`pe` → `pe_ratio`（選股表格 PE 欄）
- **CalendarEvent**：對齊 `event_date/event_type`（供 v1.1；calendar 頁目前仍本地 mock）
- 註：screener filter 的 `PE_min/RSI_min` 大寫是正確的（後端 router 有 alias），未動。

### Added — 大盤指數報價（治本）
- [market_repo.py](backend/app/repos/market_repo.py) `get_index_quotes` + [market_service.py](backend/app/services/market_service.py) `_build_indices`：market overview 的指數 close + 當日漲跌% 改由 stock_prices 動態填入；`DEFAULT_INDICES` symbol 對齊 TAIEX/TPEX。市場總覽指數卡不再「—」（實機驗證 23,680.45 / +1.22%）。
- [IndexCard.tsx](frontend/src/components/market/IndexCard.tsx)：指數值格式化（千分位 + 2 位小數，`23,680.45` 取代 `23680.450000`）。
- [MarketIndexMiniChart.tsx](frontend/src/components/dashboard/MarketIndexMiniChart.tsx)：儀表板大盤趨勢卡同步修正欄位接線 + 空圖提示改 `make seed-index`。
- **漲跌幅雙重 ×100 修正**（seed 真實資料巡覽時抓到）：後端 `change_pct` 已是百分比數字，前端 `MoversTable` 用 `PercentFormat`（會再 ×100）→ 顯示 +253% 應為 +2.54%。改用 `PriceDelta mode="raw"`。`statistics/accuracy`（mock）命中率同類雙重 ×100 一併修正。

### Added — Dev/Demo 工具
- [seed_demo_data.py](data-pipeline/scripts/seed_demo_data.py) + `make seed-demo`：8 檔台股 OHLCV / 三大法人 / 新聞 / 公告 / admin 自選股（source=dev-seed、強制非 prod、uuid5 idempotent），讓市場總覽 / 三大法人 / 儀表板等頁可在「有資料」狀態檢視。
- [seed_index_ohlcv.py](data-pipeline/scripts/seed_index_ohlcv.py) + `make seed-index`：寫入 TAIEX / TPEX 指數 OHLCV（`source=dev-seed`、強制非 prod），讓本機儀表板立即有資料、sparkline 不再空白。正式環境真實大盤回填仍列 v1.1。

### Changed — 登入頁精修
- [(auth)/layout.tsx](frontend/src/app/(auth)/layout.tsx)：左側品牌 hero 改為垂直置中焦點、加入 eyebrow 標籤、放大標題、補足 4 個賣點（含資安賣點呼應 Secure Edition）、賣點改用不同圖示，修正原本「上方大片留白、頭重腳輕」的版面失衡。

### v1.1 待辦（本次審視再確認）
- 大盤 TAIEX / TPEX 真實行情回填（TWSE / TPEX 指數歷史）取代 dev-seed。
- `analyst_outputs` 已可寫入；待真實 LLM 分析跑過後於詳情頁驗證實際呈現。
- 已登入頁面（dashboard / 分析詳情 / 各表格頁）的逐頁視覺精修，待乾淨後端環境完整走訪後進行。

---

## [1.0.1] — 2026-06-02 — UX & Design System Upgrade

> 不破壞 v1.0 範圍下，依 Opus 4.8 全面審視 v1.0、聚焦「日後操作更順手、更專業、更美觀」的改善版本。
> 新增 / 改造的所有測試全綠：**後端 718 passed / 前端 209 unit / typecheck 0 errors / next build 成功**。

### Added — 設計系統 & 共用元件
- **金融感官色彩系統**（[globals.css](frontend/src/app/globals.css) + [tailwind.config.ts](frontend/tailwind.config.ts)）
  - 品牌靛藍（`--primary` 222 47% 22%）取代純黑
  - **台股慣例：紅漲綠跌**（`--bull` / `--bear` / `--flat` / `--signal-*` / `--state-*` token）
  - chart palette 重做（藍/橙/紫/綠/紅，有對比邏輯）
  - `--radius` 加大、Card hover shadow lift、Sidebar 反轉為深色
  - dark mode 完整覆蓋
- **新共用元件**（`frontend/src/components/common/`）
  - `PageHeader.tsx` — 統一所有頁面的 `<h1>` + `<p>` + actions slot
  - `Breadcrumbs.tsx` — 從 `usePathname()` 自動產生繁中麵包屑（含 UUID → 「詳情」）
  - `KpiCard.tsx` — 統一 KPI 卡（標題 + 大數值 + PriceDelta + sparkline + footer + 可點擊）
  - `Sparkline.tsx` + `SparklineInner.tsx` — recharts Area 包裝、自動 tone
  - `PriceDelta.tsx` — 統一漲跌幅顯示（紅漲綠跌 + 圖示 + sign + `data-tone` attribute）
  - `StatusStepper.tsx` — 5 階段分析進度（queue → analysts → debate → manager → done），running 階段 pulse-glow
  - `ErrorState.tsx` — 取代到處 `<p className="text-destructive">無法載入...</p>`，含 inline / card variant + 重試 CTA
  - `CommandPalette.tsx` — 全域 ⌘K（cmdk）：股票搜尋 + 18 頁跳轉 + 最近分析
  - `NotificationBell.tsx` — Topbar 通知 bell（30 秒輪詢，近 1h 有事件顯示紅點）
  - 重做 `EmptyState.tsx` / `LoadingSkeleton.tsx`（補 `CardSkeleton` / `KpiSkeleton` / `ChartSkeleton`）

### Added — Mobile 響應式
- `Sidebar.tsx` 拆出 `<NavList>`、桌機保留 `aside`、Mobile 用 `<Sheet>` drawer
- `Topbar.tsx` 加漢堡 trigger、Mobile 品牌標、⌘K hint button
- `useUiStore` 管理 mobile nav / command palette 開關
- 各頁 grid breakpoints 整理（sm / lg / xl 完善）

### Added — Dashboard 重做
- **`KpiRow.tsx`** — 頂部 4 KPI 牆（加權 / 櫃買 / LLM 配額 / 待核訂單，含 sparkline 與 delta）
- **`QuickActions.tsx`** — 4 顆主要功能快捷
- **`TodayAlerts.tsx`** — 「今日重點」事件 widget（近 24h 通知）
- **`MarketIndexMiniChart.tsx`** 重做 — 真正 7/30/90D sparkline（fallback 提示）
- 整版佈局：KPI 牆 + 快速行動 + 大盤趨勢 + 今日重點 + 最近分析 + 待核准訂單 + 自選股

### Added — 分析詳情頁升級
- **StatusStepper** 進度視覺化
- **`SignalOverview.tsx`** — 信心圓環（SVG arc）+ Risk/Reward 數線（target / stop / take）
- `AgentFlowGraph.tsx` 視覺升級：高度 360 → 420-480px、加 group icon、edge animate when source running、MiniMap
- `AnalystResultCard.tsx` 真正接 `analysis.analyst_outputs[type]`，展示 score / key_points / report_md
- `DebateTimeline.tsx` 改用 `ReportMarkdown` 渲染（取代 `<pre>`）+ 左側時間軸
- `AnalysisHeader.tsx` 匯出按鈕加 loading state + 分享連結 copy

### Added — 後端缺口修補
- **Migration 0017** — `analysis_reports` 加 4 個 nullable 欄位（`analyst_outputs JSONB` / `analyst_types TEXT[]` / `debate_rounds INTEGER` / `risk_tolerance VARCHAR(20)`）
- `AnalysisDetail` schema 顯露上述新欄位 → 前端 AnalystResultCard / AgentFlowGraph 可還原
- `AnalysisRepository.create` 寫入新參數
- `AnalysisService.create_analysis` 接 `risk_tolerance` 並傳遞
- **`AnalysisService._infer_market` 改為 async + 查 stock_list** — 解原本「OTC 上櫃股票被誤標 TWSE / AMEX 被誤標 NASDAQ」的 bug
- `backend/scripts/dev_cleanup_audit_artefacts.py` — dev/test only，清 audit_logs 測試殘留，恢復 `audit_integrity` SLO = 100%
- Makefile 新增 `dev-cleanup-audit` target
- 2 個新 integration test：`test_analysis_create_persists_metadata_and_detail_exposes_it` / `test_infer_market_uses_stock_list_for_tpex_symbol`

### Added — Auth Layout 品牌化
- `(auth)/layout.tsx` 左右兩欄（lg+）：左品牌 hero（漸層 mesh + 4 個賣點）/ 右登入卡
- 加 ThemeToggle（登入前可切深淺）

### Added — 前端測試
- 6 個新 unit test：`PriceDelta`、`PageHeader`、`ErrorState`、`KpiCard`、`StatusStepper`、`Breadcrumbs`
- 既有測試適配新色彩 token（`SignalBadge` / `IndexCard` / `PercentFormat` 改用 `data-tone` attribute）
- 前端 **183 → 209** unit tests / typecheck 0 errors / next build 成功

### Added — i18n 補完
- zh-TW 字典擴充：dashboard / analysis / portfolio / status / signal / market / common.error / common.empty 等 key
- en dict 仍 fallback 到 zh-TW（v1.2 才補完整翻譯）

### Changed
- 全部 18 頁 `<h1>` + `<p>` 改用 `<PageHeader>` 統一
- 全部 `text-emerald-*` / `text-rose-*` 漲跌語意改 `text-bull` / `text-bear`（紅漲綠跌）
- 漲跌語意之外的 emerald/rose 改 `text-success` / `text-destructive` 語意 token（admin users / pipeline / notifications）
- 沿用既有的 ErrorBoundary / RBAC / Audit / Idempotency — 不動內部架構

### Fixed
- `_infer_market` 不再 hardcode TWSE/NASDAQ；TPEX/AMEX 股票市場標籤正確
- AnalystResultCard 不再是「已完成 → 點箭頭展開但沒內容」的 stub
- dev DB 殘留 tampering audit row（v1.0 結案報告中 broken_id=535, 559）有了清理腳本

### Migration
從 v1.0.0 升級：
```bash
cd backend && uv run alembic upgrade head  # 套用 0017 migration（nullable，向後相容）
cd frontend && npm install && npm run build  # 重建（依賴沒變）
# 若 dev DB 有 audit tampering 殘留：
make dev-cleanup-audit ARGS="--yes"
```

### v1.1 待辦（仍依 PLAN 第 33 章 + 本次改善留下）
- 大盤 OHLCV symbol（TAIEX / TPEX）真實 backfill，讓 dashboard sparkline 有資料
- analyst_outputs 由 LangGraph workflow 寫入（目前只有 schema 顯露，實際還沒寫）
- `data_freshness_minutes` / `audit_integrity` SLO 在 prod 跑 30 天回填基準
- v1.1 真實後端化 calendar / compare / backtest（5 個 mock 頁）

---

## [1.0.0] — 2026-05-18 — TradingAgents-TW Release

> **Release Ready** — 21 個 Phase（P0-P20）全部完成；716 後端 tests + 183 前端 unit + 57 E2E 全綠。
>
> 詳細：[docs/PROJECT_FINAL_REPORT.md](docs/PROJECT_FINAL_REPORT.md)

### Added (Phase 20)

- **scripts/health_checks/all.sh** — 一鍵跑 19 phase health checks + backend pytest + frontend test + bandit + detect-secrets
- **scripts/health_checks/phase_20.sh** — Phase 20 自家 14 項健康檢查
- **scripts/check_obsidian_installed.sh** — 跨平台檢查 Obsidian 安裝（Windows / Linux / macOS）
- **backend/tests/integration/test_final_smoke.py** — 5 個 v1.0 最終 smoke test（login / dashboard / analysis / audit chain / slo report）
- **docs/PROJECT_FINAL_REPORT.md** — v1.0 結案報告（最重要交付物）
- **docs/connection-guide.md** — 第一次裝機完整 10 步驟指南
- **docs/user-guide.md** — 18 頁前端操作 + 15 條 FAQ
- **docs/runbooks/obsidian_setup.md** — Obsidian 個人筆記整合手冊（v1.0 手動 / v1.1 自動）
- **docs/phase_reports/PHASE_20.md** — Phase 20 完成報告

### Changed (Phase 20)

- **README.md** — 全面升級為 v1.0 完整版（v0.3.0 → v1.0）
- **docs/phase_progress.md** — P20 ✅ 標記，21 個 Phase 全部完成
- **backend/tests/integration/conftest.py** — 加 `_reset_redis_pools_per_test` autouse fixture，修正用 `asyncio.run()` 跑 LangGraph 的測試把 redis pool 綁到臨時 loop，導致下個 test ERROR/FAIL 的跨 event-loop 污染
- **backend/tests/security/conftest.py** — 補齊 `login_helper / flush_rate_limit / seed_*` 等 fixture import，修正 OWASP / secret handling tests 的 "fixture not found" ERROR

### Fixed (Phase 20)

- backend full pytest 從 `1 failed, 715 passed, 10 errors` → **`716 passed, 3 skipped, 0 fail, 0 error`**（修正以上 conftest 兩個 bug）
- ruff check 在 `app/ tests/` 全綠（移除 unused noqa / unused import）

### Security

- 已沿用 Phase 18 的 OWASP / bandit HIGH=0 / detect-secrets baseline / Trivy 規則
- v1.0 接受的風險清單見 [SECURITY.md](SECURITY.md)

### Release artifacts

- Git tag: `v1.0.0`
- 累積測試：**716 後端 + 183 前端 unit + 57 E2E**（遠超 P20 基準 545+）
- 累積 Phase tag：`phase-00-complete` ~ `phase-20-complete` + `v1.0.0`
- 21 個 Phase 報告：`docs/phase_reports/PHASE_00.md` ~ `PHASE_20.md`
- 19 個 health check + `all.sh` + `phase_20.sh`：`scripts/health_checks/`

---

## [Unreleased] — TradingAgents-TW v1.0 development（已併入 [1.0.0]，保留歷史紀錄）

### Added (Phase 17)

- **前端進階 10 頁(接後端):**
  - `/market/overview`、`/market/institutional`(TW 三大法人)
  - `/screener/filter`(PE / Yield / EPS / RSI / 市值多條件 + localStorage 儲存)
  - `/news/sentiment`(個股 5 級情緒分佈)、`/news/announcements`
  - `/portfolio/positions`(從 APPROVED orders 聚合,client-side)、`/portfolio/history`
  - `/notifications`(LINE Notify token / Telegram chat_id / 事件訂閱 / 測試發送 / 通知 log)
  - `/admin/system`(API/延遲/磁碟/佇列卡片 + 24h mock 走勢)
  - `/admin/pipeline`(Celery DLQ 列表 + resolve/requeue 含 ConfirmDialog 顯示原始 traceback)
- **前端進階 5 頁(Mock,v1.1 完整實作):**
  - `/market/calendar`(月曆 view + 12 mock events / 月)
  - `/screener/compare`(最多 5 支並排比較,內建 mock 字典)
  - `/statistics/accuracy`(confidence ≥ 0.6 粗估命中率;v1.1 等後端 actual_return_30d)
  - `/statistics/models`(LLM 模型用量 group by;client-side 從 /analysis 聚合)
  - `/statistics/backtest`(策略/期間 + deterministic mock equity curve & drawdown)
- **6 個 React Query hooks**:useScreener / useNews(三大法人+stock news+stock announcements+calendar)/ usePortfolio(computePositions + useTradeHistory)/ useNotifications / useSystem(metrics+info+DLQ)/ useStatistics
- **共用元件**:`<BarChart />`、`<PieChart />`(內含 inner client component + ssr:false dynamic 包裝,避開 recharts 4.x defaultProps 與 Next.js dynamic LoaderComponent 型別衝突);`<MockBanner />`(含必含 "Mock"+"v1.1" 字串,供 health_check grep)
- **Sidebar 升級**:全 18 頁實作完畢,移除 `stub` badge;5 個 mock 頁加 `mock` badge(hover 提示 v1.1 將完整實作)
- **48 個新 unit test**(累積 135 → 183);3 個新 E2E spec(screener-filter / notifications-settings / admin-system)
- **`scripts/health_checks/phase_17.sh`** 13 項自動化檢查
- **docs/phase_reports/PHASE_17.md** + **docs/runbooks/frontend_pages.md**(每頁資料來源 + mock 替換指引)

### v1.1 Todo(由 P17 留下)

- 後端 `actual_return_30d` endpoint → 真實準確率取代 confidence 粗估
- 後端 `portfolio_positions` 直接 endpoint → 取代 client-side 聚合(訂單量大時)
- 後端 BacktestService → 取代 `/statistics/backtest` 的 mock
- `/market/calendar`、`/screener/compare`、`/news/{sentiment,announcements}` 全市場聚合 endpoint
- `/admin/pipeline` 手動觸發 task button → 後端 admin-only POST endpoint

### Added (v0.3.0 - Phase 1 完成)

- **v7.0 完整實施計劃**：`PLAN.md` 重構為 21 個 Phase（P0-P20）詳細 prompt
- **Phase 1：原版遷移 + 新骨架 + 工程規範**
  - 原版 v0.2.4 套件碼遷移至 `legacy/`，確保新版完全隔離
  - 新後端骨架：`backend/app/{api,core,repos,services,domain,models,schemas,agents,data_sources,llm,workers,notifications,exports}/`
  - 前端骨架：`frontend/src/{app,components,lib,store,hooks,i18n}/`
  - 資料管線骨架：`data-pipeline/{schemas,scripts}/`
  - Docker 骨架：`docker/{timescaledb,nginx/certs,backups,playwright}/`
- **工程規範文件**：`docs/engineering-standards.md`、`docs/setup.md`、`docs/contributing.md`
- **CI/CD 雛形**：`.github/workflows/ci.yml`（lint + secret scan + pre-commit）+ `security.yml`（bandit + gitleaks + CodeQL）
- **Pre-commit hooks**：ruff、detect-secrets、trailing-whitespace、check-yaml/json/toml
- **`.env.example`**：列齊 v1.0 所有欄位（依 Phase 補值時程標註）
- **`backend/pyproject.toml` + `uv.lock`**：FastAPI / Pydantic v2 / SQLAlchemy 2.0 async / structlog 等依賴
- **5 個 unit test 雛形**：`test_skeleton.py` 等（驗證骨架 + 模組可 import）
- **Phase 健康檢查腳本**：`scripts/health_checks/phase_01.sh`
- **Phase 進度追蹤**：`docs/phase_progress.md` + `docs/phase_reports/PHASE_01.md`

### Changed

- **`README.md`** 改寫為新版（原版備份至 `legacy/README_original.md`）
- **`.gitignore`** 升級（涵蓋 .venv / node_modules / .env / docker/backups / IDE 等）
- **`.vscode/settings.json`** 排除 `legacy/` 等目錄避免搜尋雜訊

### Migration Notes

- `git checkout pre-tw-edition-backup` 可回到改造前狀態
- 原版套件碼在 `legacy/`，**不可直接 import**（架構已大改）
- Phase 13 LangGraph Agent 系統時可參考 `legacy/tradingagents/agents/` 的結構

---

## [0.2.4] — 2026-04-25

### Added

- **Structured-output decision agents.** Research Manager, Trader, and Portfolio
  Manager now use `llm.with_structured_output(Schema)` on their primary call
  and return typed Pydantic instances. Each provider's native structured-output
  mode is used (`json_schema` for OpenAI / xAI, `response_schema` for Gemini,
  tool-use for Anthropic, function-calling for OpenAI-compatible providers).
  Render helpers preserve the existing markdown shape so memory log, CLI
  display, and saved reports keep working unchanged. (#434)
- **LangGraph checkpoint resume** — opt-in via `--checkpoint`. State is saved
  after each node so crashed or interrupted runs resume from the last
  successful step. Per-ticker SQLite databases under
  `~/.tradingagents/cache/checkpoints/`. `--clear-checkpoints` resets them. (#594)
- **Persistent decision log** replacing the per-agent BM25 memory. Decisions
  are stored automatically at the end of `propagate()`; the next same-ticker
  run resolves prior pending entries with realised return, alpha vs SPY, and
  a one-paragraph reflection. Override path with `TRADINGAGENTS_MEMORY_LOG_PATH`.
  Optional `memory_log_max_entries` config caps resolved entries; pending
  entries are never pruned. (#578, #563, #564, #579)
- **DeepSeek, Qwen (Alibaba DashScope), GLM (Zhipu), and Azure OpenAI**
  providers, plus dynamic OpenRouter model selection.
- **Docker support** — multi-stage build with separate dev and runtime images.
- **`scripts/smoke_structured_output.py`** — diagnostic that exercises the
  three structured-output agents against any provider so contributors can
  verify their setup with one command.
- **5-tier rating scale** (Buy / Overweight / Hold / Underweight / Sell) used
  consistently by Research Manager, Portfolio Manager, signal processor, and
  the memory log; Trader keeps 3-tier (Buy / Hold / Sell) since transaction
  direction is naturally ternary.
- **Pytest fixtures** — lazy LLM client imports plus placeholder API keys so
  the test suite runs cleanly without credentials. (#588)

### Changed

- **`backend_url` default is now `None`** rather than the OpenAI URL. Each
  provider client falls back to its native default. The previous default
  leaked the OpenAI URL into non-OpenAI clients (e.g. Gemini), producing
  malformed request URLs for Python users who switched providers without
  overriding `backend_url`. The CLI flow is unaffected.
- All file I/O passes explicit `encoding="utf-8"` so Windows users no longer
  hit `UnicodeEncodeError` with the cp1252 default. (#543, #550, #576)
- Cache and log directories moved to `~/.tradingagents/` to resolve Docker
  permission issues. (#519)
- `SignalProcessor` reads the rating from the Portfolio Manager's rendered
  markdown via a deterministic heuristic — no extra LLM call.
- OpenAI structured-output calls default to `method="function_calling"` to
  avoid noisy `PydanticSerializationUnexpectedValue` warnings emitted by
  langchain-openai's Responses-API parse path. Same typed result, no warnings.

### Fixed

- Empty memory no longer triggers fabricated past-lessons in agent prompts;
  the memory-log redesign makes this structurally impossible since only the
  Portfolio Manager consults memory and only when entries exist. (#572)
- Tool-call logging processes every chunk message, not just the last one, and
  memory score normalization handles empty score arrays. (#534, #531)

### Removed

- `FinancialSituationMemory` (the per-agent BM25 system) and the dead
  `reflect_and_remember()` plumbing; subsumed by the persistent decision log.
- Hardcoded Google endpoint that caused 404 when `langchain-google-genai`
  changed its API path. (#493, #496)

### Contributors

Thanks to everyone who shaped this release through code, design, and reports:

- [@claytonbrown](https://github.com/claytonbrown) — checkpoint resume (#594), test fixtures (#588), design feedback on cost tracking (#582) and structured validation (#583)
- [@Bcardo](https://github.com/Bcardo) — memory-log redesign (#579), empty-memory hallucination report (#572), encoding fix proposal (#570)
- [@voidborne-d](https://github.com/voidborne-d) — memory persistence design (#564), portfolio manager state fix (#503)
- [@mannubaveja007](https://github.com/mannubaveja007) — structured-output feature request (#434)
- [@kelder66](https://github.com/kelder66) — RAM-only memory issue (#563)
- [@Gujiassh](https://github.com/Gujiassh) — tool-call logging fix (#534), test stub PR (#533)
- [@iuyup](https://github.com/iuyup) — memory score normalization fix (#531)
- [@kaihg](https://github.com/kaihg) — Google base_url fix (#496)
- [@32ryh98yfe](https://github.com/32ryh98yfe) — Gemini 404 report (#493)
- [@uppb](https://github.com/uppb) — OpenRouter dynamic model selection (#482)
- [@guoz14](https://github.com/guoz14) — OpenRouter limited-model report (#337)
- [@samchenku](https://github.com/samchenku) — indicator name normalization (#490)
- [@JasonOA888](https://github.com/JasonOA888) — y_finance pandas import fix (#488)
- [@tiffanychum](https://github.com/tiffanychum) — stale import cleanup (#499)
- [@zaizou](https://github.com/zaizou) — Docker permission issue (#519)
- [@Stosman123](https://github.com/Stosman123), [@mauropuga](https://github.com/mauropuga), [@hotwind2015](https://github.com/hotwind2015) — Windows encoding bug reports (#543, #550, #576)
- [@nnishad](https://github.com/nnishad), [@atharvajoshi01](https://github.com/atharvajoshi01) — encoding fix proposals (#568, #549)

## [0.2.3] — 2026-03-29

### Added

- **Multi-language output** for analyst reports and final decisions, with a
  CLI selector. Internal agent debate stays in English for reasoning quality. (#472)
- **GPT-5.4 family models** in the default catalog, with deep/quick model split.
- **Unified model catalog** as a single source of truth for CLI options and
  provider validation.

### Changed

- `base_url` is forwarded to Google and Anthropic clients so corporate proxies
  work consistently across providers. (#427)
- Standardised the Google `api_key` parameter to the unified `api_key` form.

### Fixed

- Backtesting fetchers no longer leak look-ahead data when `curr_date` is in
  the middle of a fetched window. (#475)
- Invalid indicator names from the LLM are caught at the tool boundary instead
  of crashing the run. (#429)
- yfinance news fetchers respect the same exponential-backoff retry as price
  fetchers. (#445)

### Contributors

- [@ahmedk20](https://github.com/ahmedk20) — multi-language output (#472)
- [@CadeYu](https://github.com/CadeYu) — model catalog typing (#464)
- [@javierdejesusda](https://github.com/javierdejesusda) — unified Google API key parameter (#453)
- [@voidborne-d](https://github.com/voidborne-d) — yfinance news retry (#445)
- [@kostakost2](https://github.com/kostakost2) — look-ahead bias report (#475)
- [@lu-zhengda](https://github.com/lu-zhengda) — proxy/base_url support request (#427)
- [@VamsiKrishna2021](https://github.com/VamsiKrishna2021) — invalid indicator crash report (#429)

## [0.2.2] — 2026-03-22

### Added

- **Five-tier rating scale** (Buy / Overweight / Hold / Underweight / Sell)
  introduced for the Portfolio Manager.
- **Anthropic effort level** support for Claude models.
- **OpenAI Responses API** path for native OpenAI models.

### Changed

- `risk_manager` renamed to `portfolio_manager` to match the role description
  shown in the CLI display.
- Exchange-qualified tickers (e.g. `7203.T`, `BRK.B`) preserved across all
  agent prompts and tool calls.
- Process-level UTF-8 default attempted for cross-platform consistency
  (note: this approach did not actually take effect; replaced in v0.2.4 with
  explicit per-call `encoding="utf-8"` arguments).

### Fixed

- yfinance rate-limit errors are retried with exponential backoff. (#426)
- HTTP client SSL customisation is supported for environments that need
  custom certificate bundles. (#379)
- Report-section writes handle list-of-string content gracefully.

### Contributors

- [@CadeYu](https://github.com/CadeYu) — exchange-qualified ticker preservation (#413)
- [@yang1002378395-cmyk](https://github.com/yang1002378395-cmyk) — HTTP client SSL customisation (#379)

## [0.2.1] — 2026-03-15

### Security

- Patched `langchain-core` vulnerability (LangGrinch). (#335)
- Removed `chainlit` dependency affected by CVE-2026-22218.

### Added

- `pyproject.toml` build-system configuration; the project now installs via
  modern packaging tooling.

### Removed

- `setup.py` — dependencies consolidated to `pyproject.toml`.

### Fixed

- Risk manager reads the correct fundamental report source. (#341)
- All `open()` calls receive an explicit UTF-8 encoding (initial pass).
- `get_indicators` tool handles comma-separated indicator names from the LLM. (#368)
- `Propagation` initialises every debate-state field so risk debaters never
  see missing keys.
- Stock data parsing tolerates malformed CSVs and NaN values.
- Conditional debate logic respects the configured round count. (#361)

### Contributors

- [@RinZ27](https://github.com/RinZ27) — `langchain-core` security patch (#335)
- [@Ljx-007](https://github.com/Ljx-007) — risk manager fundamental-report fix (#341)
- [@makk9](https://github.com/makk9) — debate-rounds config issue (#361)

## [0.2.0] — 2026-02-04

This is the largest release since the initial public version. The framework
moved from single-provider to a multi-provider architecture and grew several
production-ready surfaces.

### Added

- **Multi-provider LLM support** (OpenAI, Google, Anthropic, xAI, OpenRouter,
  Ollama) via a factory pattern, with provider-specific thinking configurations.
- **Alpha Vantage** integration as a configurable primary data provider, with
  yfinance as a community-stability fallback.
- **Footer statistics** in the CLI: real-time tracking of LLM calls, tool
  calls, and token usage via LangChain callbacks.
- **Post-analysis report saving** — the framework writes per-section markdown
  files (analyst reports, debate transcripts, final decision) when a run
  completes.
- **Announcements panel** — fetches updates from `api.tauric.ai/v1/announcements`
  for the CLI welcome screen.
- **Tool fallbacks** so a single vendor outage does not stop the pipeline.

### Changed

- Risky / Safe risk debaters renamed to **Aggressive / Conservative** for
  consistency with the displayed agent labels.
- Default data vendor switched to balance reliability and quota across
  community deployments.
- Ollama and OpenRouter model lists updated; default endpoints clarified.

### Fixed

- Analyst status tracking and message deduplication in the live display.
- Infinite-loop guard in the agent loop; reflection and logging hardened.
- Various data-vendor implementation bugs and tool-signature mismatches.

### Contributors

This release is the first with substantial outside contributions; many community
PRs from late 2025 also landed here.

- [@luohy15](https://github.com/luohy15) — Alpha Vantage data-vendor integration (#235)
- [@EdwardoSunny](https://github.com/EdwardoSunny) — yfinance fetching optimisations (#245)
- [@Mirza-Samad-Ahmed-Baig](https://github.com/Mirza-Samad-Ahmed-Baig) — infinite-loop guard, reflection, and logging fixes (#89)
- [@ZeroAct](https://github.com/ZeroAct) — saved results path support (#29)
- [@Zhongyi-Lu](https://github.com/Zhongyi-Lu) — `.env` gitignore (#49)
- [@csoboy](https://github.com/csoboy) — local Ollama setup (#53)
- [@chauhang](https://github.com/chauhang) — initial Docker support attempt (#47, later reverted; the merged Docker support shipped in v0.2.4)

## [0.1.1] — 2025-06-07

### Removed

- Static site assets that had been bundled with v0.1.0; the public site now
  lives separately.

## [0.1.0] — 2025-06-05

### Added

- **Initial public release** of the TradingAgents multi-agent trading
  framework: market / sentiment / news / fundamentals analysts; bull and bear
  researchers; trader; aggressive, conservative, and neutral risk debaters;
  portfolio manager. LangGraph orchestration, yfinance data, per-agent
  BM25 memory, single-provider OpenAI integration, interactive CLI.

[0.2.4]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/TauricResearch/TradingAgents/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/TauricResearch/TradingAgents/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/TauricResearch/TradingAgents/releases/tag/v0.1.0
