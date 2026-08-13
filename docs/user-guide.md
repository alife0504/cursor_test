# TradingAgents-TW 使用者指南 — 每頁操作 + FAQ

> v1.0 — 18 頁前端 + 完整 FAQ。
> 本文件目標：把整個平台「會操作」的學習曲線降到 1 小時。
> 配套文件：[連線指南](connection-guide.md)（第一次裝機）、[runbooks/](runbooks/)（維運）。

---

## 目錄

- [A. 全域操作](#a-全域操作)
- [B. 各頁面操作說明](#b-各頁面操作說明)
  - [B.1 儀表板 `/dashboard`](#b1-儀表板-dashboard)
  - [B.2 市場頁](#b2-市場頁)
  - [B.3 選股頁](#b3-選股頁)
  - [B.4 AI 分析頁](#b4-ai-分析頁)
  - [B.5 績效統計](#b5-績效統計)
  - [B.6 投資組合](#b6-投資組合)
  - [B.7 資訊頁](#b7-資訊頁)
  - [B.8 通知設定 `/notifications`](#b8-通知設定-notifications)
  - [B.9 管理 `/admin/*`](#b9-管理-admin)
- [C. 常用工作流程](#c-常用工作流程)
- [D. FAQ](#d-faq)

---

## A. 全域操作

### A.1 鍵盤快捷鍵

| 動作 | 快捷鍵 |
|------|-------|
| 全域搜尋（cmdk） | `Ctrl + K` |
| 切換 Sidebar 縮放 | `Ctrl + B` |
| 切換主題（light/dark） | `Ctrl + Shift + L` |
| 登出 | `Ctrl + Shift + Q` |

### A.2 標示說明

- **MockBanner**：頁面上方紅色橫條 → 表示這頁是 mock 資料，v1.1 才會接真實後端
- **MarketBadge**：股票旁的小色塊 → TW（淺綠）、TPEX（綠）、NYSE（藍）、NASDAQ（紫）、AMEX（黃）
- **🔒 admin only**：Sidebar 中只有 admin 看得到，普通用戶不會顯示

### A.3 資料新鮮度

每頁右上角有「最後更新」時間戳：
- 綠：< 1 小時前
- 黃：1-6 小時前
- 紅：> 6 小時前（可能資料源熔斷，去 `/admin/system` 查）

### A.4 錯誤處理

- 出現「載入失敗」→ 看右下 toast 詳細訊息
- 連續 3 次 API 失敗 → 自動跳登入頁（access token 過期）
- 出現 `409 Conflict` → 多人操作衝突（你重新拉資料、再做一次）

---

## B. 各頁面操作說明

### B.1 儀表板 `/dashboard`

**功能**：登入後第一個看到的「總覽」頁。

5 個 section（從上到下）：
1. **歡迎 + 系統健康**：上次登入、系統狀態（live/degraded）
2. **大盤指數 4 卡**：TWSE、TPEX、Nasdaq、S&P 500
3. **自選股 Top 5**：點任一張卡跳到 `/screener/watchlist`
4. **最近分析 Top 5**：點 row 跳到 `/analysis/[id]`
5. **待核准訂單**：警告數字；點跳 `/portfolio/orders`
6. **LLM 月用量進度條**：超過 80% 顯示橘色警告

**常用動作**：
- 看大盤 → 點任一指數卡跳到 `/market/overview`
- 看分析報告 → 直接點 row

### B.2 市場頁

#### B.2.1 `/market/overview`

**功能**：跨市場大盤、漲跌、成交量。

- 頂部 4 大指數 + 簡單 sparkline
- Movers Top 10：漲跌幅、成交量 3 個排行
- 切換 TW / US 用右上的 MarketSwitcher

#### B.2.2 `/market/institutional`（台股 only）

**功能**：三大法人（外資、投信、自營商）買賣超。

- 表格：每日買賣超 + 累計 5/20 日
- 篩選：日期區間、最小金額

#### B.2.3 `/market/calendar`（v1.0 mock）

**Mock 頁面**：v1.0 沒有真實財報日曆資料源；v1.1 會接 MOPS 公告 + SEC 4-K。
頁面有紅色 MockBanner 提示。

### B.3 選股頁

#### B.3.1 `/screener/watchlist`

**功能**：自選股清單（CRUD）。

**操作**：
- **加入**：右上「+ 新增自選股」→ cmdk 搜尋（輸入 2330 或「台積電」）→ 確認
- **編輯 note**：點 note 欄位直接 inline 編輯（Enter 儲存、Esc 取消）
- **排序**：拖曳 row 改 `sort_order`（會即時 PATCH 到後端）
- **刪除**：右側垃圾桶 → ConfirmDialog 確認

#### B.3.2 `/screener/filter`

**功能**：選股篩選器（5 維）。

維度：
- PE（本益比）：0-50
- Yield（殖利率）：≥ %
- EPS：≥
- RSI：< 30 / > 70 等
- 市值：億元

**操作**：
- 拉條 / 輸入區間
- 「儲存條件」→ 寫到 localStorage，下次自動載入
- 結果以 DataTable 呈現，可點 row 直接「新增分析」

#### B.3.3 `/screener/compare`（v1.0 mock）

**Mock 頁面**：多股比較雷達圖、財報橫向比較。v1.1 才接後端。

### B.4 AI 分析頁

#### B.4.1 `/analysis/new`

**功能**：建立一個新的 AI 分析任務。

4 個 Step：
1. **Step 1 — 選股票**：cmdk 搜尋 / 從自選股清單選
2. **Step 2 — 選 Analyst**：4 個 TW（market / fundamental / news / sentiment）或 3 個 US（無 sentiment）
3. **Step 3 — 選 LLM**：
   - `Gemini Flash`（預設，最便宜）— $0.075/1M input, $0.30/1M output
   - `GPT-4o-mini`（fallback 第 2）— $0.15/1M, $0.60/1M
   - `Claude Haiku 3.5`（fallback 第 3）— $0.80/1M, $4.00/1M
4. **Step 4 — 辯論輪數**：1 / 2 / 3（越多越貴）

**確認頁顯示**：
- 預估費用（USD）
- 預估時間（分鐘）
- 本月已用配額（必須 < monthly_llm_budget_usd）

**提交**：
- 帶 `Idempotency-Key`（前端產 UUID v4，避免重複建立）
- 跳到 `/analysis/[id]`
- 後端建 row + 推 Celery task

#### B.4.2 `/analysis/[id]`

**功能**：分析進度 + 結果。

**進度狀態**：
- 上方 **AgentFlowGraph**（@xyflow）：節點依序變綠
- 走 WS（subprotocol + ticket）即時串流，看到每個 analyst 完成的時刻
- 進度條右側有「終止」按鈕（admin 才有，會把 status 設成 cancelled）

**完成後 Tabs**：
1. **Overview**：signal.action / confidence / target_price / 風險評級
2. **Analysts**：每個 analyst 的結論（市場、基本、新聞、籌碼）
3. **Debate**：Bull vs Bear 完整辯論（多輪）+ Manager 綜合
4. **Report**：完整 Markdown 報告

**匯出**（右上「⋮」選單）：
- PDF（含中文，Playwright + chromium 渲染）
- Markdown（純文字）
- Excel/XLSX（表格 + 圖）

#### B.4.3 `/analysis/history`

**功能**：所有分析的歷史列表。

- Cursor pagination（每頁 20 筆）
- 篩選：股票、市場、status、日期區間
- 點 row 跳到 `/analysis/[id]`

### B.5 績效統計

#### B.5.1 `/statistics/accuracy`

**功能**：分析準確率（用 `confidence` 粗估，v1.1 才有真實回測）。

#### B.5.2 `/statistics/models`

**功能**：各 LLM 模型表現比較（client-side group by）。

#### B.5.3 `/statistics/backtest`（v1.0 mock）

**Mock 頁面**：mock equity curve。v1.1 接真實後端回測引擎。

### B.6 投資組合

#### B.6.1 `/portfolio/positions`

**功能**：模擬持倉（從 `APPROVED` orders 聚合，client-side 計算）。

- 股票 × 累積數量 × 加權平均成本 × 目前市價 × 浮動損益

#### B.6.2 `/portfolio/orders`（重要！）

**功能**：核准 / 拒絕 AI 建議的訂單。

**雙重確認流程**（依 ADR-007，防 AI 誤判直接下單）：
1. AI 完成分析 → 自動建 `PendingOrder`（status=pending）
2. 你登入這頁看
3. 點「核准」按鈕 → **ConfirmDialog** 顯示完整明細（股票、買賣、數量、預估金額）
4. 再次點「確認核准」→ status=approved + 寫 audit
5. （v1.0 不直連券商，須自己去券商手動下單）
6. 後續自己更新 `executed_at` + `actual_price`

**核准 vs 拒絕**：
- 核准：寫 audit、推通知（如訂閱）、計入持倉
- 拒絕：寫 audit + reason、不計入持倉

**409 race 保護**：兩個瀏覽器同時點 → 後到的看到 `409 Conflict`（依 `version` 欄位 SELECT FOR UPDATE）。

#### B.6.3 `/portfolio/history`

**功能**：所有 orders 的歷史（含已拒絕、已執行）。

### B.7 資訊頁

#### B.7.1 `/news/sentiment`

**功能**：個股新聞情緒。

- 5 級分佈（強烈負面 / 負面 / 中立 / 正面 / 強烈正面）
- 標題列表 + 連結

#### B.7.2 `/news/announcements`

**功能**：MOPS（台股）/ SEC EDGAR（美股）公告。

### B.8 通知設定 `/notifications`

**功能**：設定 LINE / Telegram + 訂閱事件。

**設定**：
1. 「LINE Notify token」：到 https://notify-bot.line.me 申請
2. 「Telegram chat_id」：找 @userinfobot 取得
3. 按「測試發送」→ 手機應收到 `「測試訊息」`

**訂閱事件**：
- 分析完成（`analysis.completed`）
- 訂單核准/拒絕（`order.approved` / `order.rejected`）
- LLM 配額 80%（`llm.quota.warning`）
- LLM 配額 100%（`llm.quota.exhausted`）
- 資料源熔斷（`data_source.cb_open`）
- 備份失敗（`backup.failed`）
- 系統警告（`system.alert`）

**通知 log**：頁尾 cursor pagination 顯示最近發送紀錄（已發、失敗）。

### B.9 管理 `/admin/*`

> Sidebar 的「⚙️ 管理」section 只有 `role=admin` 才看得到。

#### B.9.1 `/admin/users`

**功能**：用戶管理。

操作：
- 建立用戶（email、initial password）
- 重設密碼（會清掉 lockout、強制下次登入改密碼）
- 啟用 / 停用
- 軟刪除（`deleted_at` 設值；資料保留 90 天後 hard delete）
- 改 `monthly_llm_budget_usd`（解 LLM 配額用盡）

#### B.9.2 `/admin/audit`

**功能**：審計日誌（不可竄改 hash chain）。

- Cursor pagination（每頁 50 筆）
- 篩選：actor、event_type、日期區間、target_type
- 點 row 展開看 `details` JSONB
- 每日 02:00 排程 `verify_audit_chain` task 校驗 hash 鏈完整性

#### B.9.3 `/admin/system`

**功能**：系統監控（v1.0 部分為 24h mock，真實 metrics 來自 Prometheus，v2.0 完整化）。

- API request rate / 延遲
- DB connection pool
- Redis memory
- Celery 佇列深度
- 磁碟使用率
- LLM 月成本

#### B.9.4 `/admin/pipeline`

**功能**：Celery DLQ 管理。

- 列 DLQ 中的失敗 task
- 點「resolve」標為已解決（不重跑）
- 點「requeue」重推回原 queue（ConfirmDialog 顯示原始 traceback）

---

## C. 常用工作流程

### C.1 「我想分析 2330 並決定買賣」

1. `/analysis/new` → 選 2330 → 4 個 analyst → Gemini Flash → debate=1 → 提交
2. 等 ~2 分鐘看完整報告
3. 訊號 BUY → 系統自動建 PendingOrder
4. 進 `/portfolio/orders` → 核准 → 寫 audit + 推通知
5. 自己去券商實際下單（v1.0 不直連）

### C.2 「我想找今天該關注的股票」

1. `/dashboard` 看「自選股 Top 5」+「最近分析」
2. `/market/overview` 看 Movers Top 10
3. `/screener/filter` 用條件找：PE < 20、Yield > 3%、RSI < 30
4. 對結果 row 直接點「新增分析」

### C.3 「我要看上個月的分析準確率」

1. `/statistics/accuracy` 看整體
2. `/statistics/models` 看哪個模型最準
3. （v1.1 才會有真實回測 `/statistics/backtest`）

### C.4 「DB 還原（災難復原）」

詳見 `docs/runbooks/disaster_recovery.md`。

簡版：
```bash
make restore FILE=backups/ta_backup_YYYYMMDD.tar.gz.gpg
```

---

## D. FAQ

### Q1：為何要手動核准訂單？AI 不能直接下單嗎？

依 ADR-007，AI 投資建議可能誤判（特別是黑天鵝事件），自動執行有財務風險。v1.0 強制手動核准；v2.0 才開放真實券商 API（仍需手動核准每筆）。

### Q2：為何 calendar / compare / backtest 頁是 Mock？

這三個頁面需要可靠資料源 / 真實計算引擎：
- calendar：完整 MOPS + SEC 公告解析 + 法說會時程
- compare：多股財報橫向 SQL
- backtest：真實事件回放引擎

v1.0 聚焦核心分析流程，這三個延到 v1.1。

### Q3：我的密碼忘了怎麼辦？

- 你是 admin：用 admin 帳號登入 → `/admin/users` → 對該用戶按「重設密碼」
- 你是 admin 也忘記：直接改 DB
  ```bash
  docker exec ta-timescaledb psql -U postgres tradingagents -c \
    "UPDATE users SET password_hash = crypt('NewPassword123!', gen_salt('bf', 12)), must_change_password = true WHERE email='admin@example.com';"
  ```

### Q4：系統很慢怎麼辦？

1. `/admin/system` 找瓶頸（DB CPU? Celery 飽和? Redis memory?）
2. `make prod-logs` 看 backend / celery 是否頻繁出錯
3. 重啟：`make prod-restart`
4. 詳細排查：`docs/runbooks/services.md`

### Q5：如何升級到 v1.1？

v1.1 release 後（預計 1-2 個月）：

```bash
git fetch --tags
git checkout v1.1.0
make prod-down
make migration-up      # 跑新的 alembic migration
make prod-up
```

每個 release 會附 `docs/UPGRADE_v1.0_to_v1.1.md`。

### Q6：分析卡 `running` 超過 30 分鐘？

1. 看 Celery worker log
   ```bash
   docker compose -f docker-compose.prod.yml logs celery_worker --tail=200
   ```
2. 確認 LLM API key 有額度
3. `cleanup_orphans` task 會每 30 分鐘把超過 10 分鐘的 running 設成 `failed`（已排程）
4. 詳見 `docs/runbooks/agents.md` 第 6 節

### Q7：LLM 月配額用盡？

1. 進 `/admin/users` → 找用戶 → 改 `monthly_llm_budget_usd`
2. 或直接 SQL：
   ```bash
   docker exec ta-timescaledb psql -U postgres tradingagents -c \
     "UPDATE users SET monthly_llm_budget_usd = 50 WHERE email = '...';"
   ```
3. 配額在每月 1 號 00:00 自動歸零（依 `usage_month_start` 欄位）

### Q8：資料源（FinMind / yfinance）熔斷怎麼辦？

- 系統會自動 fallback 到備用資料源（依 `docs/runbooks/data_sources.md` 的對照表）
- 連 fallback 也失敗 → 廣播 `data_source.cb_open` 通知
- 重置 CB：等 60 秒（half-open）→ 一次成功就 CLOSED
- 強制重置：`docker exec ta-redis redis-cli DEL "cb:finmind:*"`

### Q9：我要新增一個 Analyst（v1.0 已凍結 interface）

依 PHASE_13 結尾「P14 介面已凍結（FinalSignal schema + Analyst protocol 不會中途改）」，v1.0 不再加 Analyst。

v1.1 才加。流程：
1. 建一個 `app/agents/analysts/<name>.py` 繼承 `BaseAnalyst`
2. 寫 prompt template `app/agents/prompts/<name>_tw.md` / `_us.md`
3. 在 `app/agents/plugins/registry.py` 註冊（含 `supported_regions`）
4. `build_graph` 會自動納入

### Q10：怎麼啟用 `FEATURE_*` flag？

v1.0 所有 feature flag 預設關閉，啟用方式（系統內部開發者用）：

```bash
FEATURE_KAIROS=1 bun run dev
```

或在 `.env.prod` 寫：
```
FEATURE_KAIROS=1
FEATURE_PROACTIVE=1
```

詳見 [CLAUDE.md Feature Flag 章節](../CLAUDE.md)。

### Q11：每天備份有自動嗎？

**沒有**。backup.sh 不會自己跑；你要把它排入 cron / Task Scheduler。詳見 `docs/connection-guide.md` 第 9 節。

### Q12：怎麼匯出我的分析報告到 Obsidian？

v1.0 沒有自動匯出（v1.1 計畫）。手動流程：
1. 在 `/analysis/[id]` 右上「⋮」→ 匯出 Markdown
2. 把 .md 檔移到 `obsidian_vault/reports/YYYY-MM-DD/`
3. Obsidian 自動偵測新檔
4. 詳見 `docs/runbooks/obsidian_setup.md`

### Q13：v1.0 不支援多用戶嗎？

v1.0 是「自用單機」設計：
- 認證、RBAC、audit 都已實作 → 可有多個用戶
- 但**不支援多組織**（沒有 `organization_id` 欄位、沒有跨組織隔離）
- 也**沒有設計給數十人併發使用**（單機 ~ 1000 WS 連線上限）

v2.0 才會做完整多組織 + K8s 部署。

### Q14：怎麼看實際的 LLM 用量 / 成本？

```bash
docker exec ta-timescaledb psql -U postgres tradingagents -c \
  "SELECT provider, COUNT(*) AS calls, SUM(cost_usd) AS total_usd
   FROM llm_usage
   WHERE created_at >= date_trunc('month', now())
   GROUP BY provider ORDER BY total_usd DESC;"
```

### Q15：為何 PDF 匯出含中文需要等 5 秒？

PDF 用 Playwright + chromium（Dockerfile 已預裝 fonts-noto-cjk）渲染。首次匯出會 cold start ~ 3-5 秒；後續 ~ 2 秒。

詳見 [docs/runbooks/exports.md](runbooks/exports.md)。

### 還有問題？

- 操作問題：本文件 + 連線指南
- 維運問題：[docs/runbooks/](runbooks/)
- 設計問題：[PLAN.md](../PLAN.md)
- 安全問題：[SECURITY.md](../SECURITY.md)
- 還是不會 → 看 [docs/phase_reports/](phase_reports/) 對應 Phase 的「已知限制」段

歡迎使用 TradingAgents-TW v1.0。
