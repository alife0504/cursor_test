# TradingAgents-TW Secure Edition — 完整實施計劃 v6.0

> 工作目錄：`C:\Projects\TradingAgents`（直接改造現有專案）
> 日期：2026-05-02 | 上一版：v5.0 | 規劃模型：Claude Opus 4.7
> 主場：台股；輔助：美股
> **本版核心：收斂決策、解決原版衝突、補強可執行性**

---

## 文件目錄

### Part A — 執行前必讀（讀一次就好）
1. [變更摘要 v5 → v6](#一變更摘要-v5--v6)
2. [TL;DR 30 秒理解](#二tldr30-秒理解)
3. [Pre-flight Checklist](#三pre-flight-checklist執行-p1-前必跑)
4. [原版專案遷移指南](#四原版專案遷移指南)
5. [架構決策記錄（ADR）](#五架構決策記錄adr)
6. [版本相容性矩陣](#六版本相容性矩陣)
7. [接受的限制](#七接受的限制honest-tradeoffs)
8. [反模式清單](#八反模式清單禁止做的事)

### Part B — 設計參考（按需查閱）
9. [願景與 SLO](#九願景與-slo)
10. [跨市場架構](#十跨市場架構)
11. [風險評估矩陣](#十一風險評估矩陣)
12. [技術架構](#十二技術架構)
13. [系統 Bootstrap 流程](#十三系統-bootstrap-流程)
14. [穩定性工程](#十四穩定性工程)
15. [資料一致性與並發](#十五資料一致性與並發)
16. [可觀測性與 SLO 監控](#十六可觀測性與-slo-監控)
17. [跨 Phase 工程規範](#十七跨-phase-工程規範)
18. [程式碼分層架構](#十八程式碼分層架構)
19. [安全架構](#十九安全架構)
20. [資料模型與來源](#二十資料模型與來源)
21. [完整頁面地圖](#二十一完整頁面地圖)
22. [目錄結構](#二十二目錄結構)
23. [CI/CD](#二十三cicd)

### Part C — 執行
24. [Phase 總覽 + 時程預估](#二十四phase-總覽--時程預估)
25. [Phase 0：Pre-flight 環境驗證](#二十五phase-0pre-flight-環境驗證)
26. [Phase 1-9 Prompts](#二十六phase-1-9-prompts)
27. [Phase 失敗回復程序](#二十七phase-失敗回復程序)

### Part D — 運維
28. [容量規劃](#二十八容量規劃)
29. [資源、預算與成本](#二十九資源預算與成本)
30. [部署架構](#三十部署架構)
31. [災難復原 SOP](#三十一災難復原-sop)
32. [後續延展路線圖](#三十二後續延展路線圖)

---

# Part A — 執行前必讀

---

## 一、變更摘要 v5 → v6

| 維度 | v5 | v6 強化 |
|------|----|---------|
| **原版衝突** | 「保留作參考」（語焉不詳） | **完整遷移指南**：`git mv tradingagents/ legacy/` + 處理根目錄 pyproject.toml |
| **架構決策** | 散落 | **ADR 章節**：每個關鍵選擇的「為什麼」 |
| **執行前準備** | 隱含 | **Phase 0 + Pre-flight Checklist** |
| **版本相容** | pin 版本但未說明組合 | **版本相容性矩陣** |
| **限制誠實度** | 只寫「不做」 | **接受的限制**：寫清楚什麼會壞但接受 |
| **反模式** | 散落「已知陷阱」 | **集中反模式清單** |
| **時程估計** | 只有 token 估算 | **calendar days 預估** |
| **Phase 退出條件** | 抽象（「測試全綠」） | **具體指令**（5 個 exit code 0 的 cmd） |
| **容量規劃** | 缺 | **容量章節**：用戶數、QPS、儲存增長 |
| **TL;DR** | 缺 | **30 秒理解**頁 |
| **章節組織** | 32 章平鋪 | **A/B/C/D 四部分**：Decisions / Reference / Execution / Ops |

---

## 二、TL;DR（30 秒理解）

**做什麼？** 把現有 `C:\Projects\TradingAgents`（原版 v0.2.4）改造成台股主、美股輔的多 Agent AI 投資分析平台 v1.0。

**為什麼不開新專案？** 用戶要求；保留 git history；原版 agent prompt 經驗有參考價值。

**架構：**
- 前端：Next.js 14.2（18 頁繁中 UI）
- 後端：FastAPI + LangGraph（4 種 Analyst 跨市場辯論）
- 儲存：TimescaleDB（行情/審計）+ Qdrant（新聞 RAG）+ Redis（快取/隊列）
- LLM：Gemini 2.0 Flash 預設，自動 fallback OpenAI/Anthropic

**安全：** DB 帳號分離、手動核准下單、Audit hash chain、JWT + CSRF + WS Ticket。

**執行方式：** 9 個 Phase 依序，每個 Phase 開新 Claude 對話貼對應 Prompt。

**預期投入：** ~2 週 calendar time（每天 4-6 小時）+ ~$154/月運行成本。

**第一步：** 跑 Phase 0 Pre-flight 驗證環境，再跑 Phase 1。

---

## 三、Pre-flight Checklist（執行 P1 前必跑）

### 3.1 環境驗證

```powershell
# 在 C:\Projects\TradingAgents 執行：

# 1. Docker（需 ≥ 4.x，dev 配 8GB+ memory）
docker --version
docker info | Select-String "Total Memory"

# 2. uv（Python 套件管理）
uv --version
uv python install 3.11           # 確保 3.11 可用（即使本機是 3.14）

# 3. Node.js（需 ≥ 18，推薦 20）
node --version
npm --version

# 4. Git（>= 2.30）
git --version

# 5. 磁碟空間（至少 50 GB free）
Get-PSDrive C | Format-Table Used,Free

# 6. Port 占用檢查（需空：3000, 5432, 6333, 6334, 6379, 8000, 80, 443）
Test-NetConnection -ComputerName localhost -Port 5432
Test-NetConnection -ComputerName localhost -Port 6379
# ... 其他 port
```

**結果預期：** Docker ≥ 4.x，uv 可用，Node ≥ 18，磁碟 ≥ 50GB，所有 port 都未占用（連線失敗）。

### 3.2 帳號與 API Key 準備

執行 P1 前先**取得這些 key**（先註冊好，避免 P2 時卡住）：

| 服務 | 用途 | 必需性 | 註冊網址 |
|------|------|--------|---------|
| Google AI Studio | Gemini API key | ✅ 必需 | https://aistudio.google.com/apikey |
| FinMind | 台股資料 token | 🟡 強烈建議 | https://finmindtrade.com |
| Alpha Vantage | 美股資料 key | 🟡 強烈建議 | https://www.alphavantage.co/support/#api-key |
| LINE Notify | 通知 token | 🟢 可選 | https://notify-bot.line.me |
| Telegram Bot | 通知 | 🟢 可選 | @BotFather |
| OpenAI / Anthropic | LLM Fallback | 🟢 可選 | platform.openai.com / console.anthropic.com |

### 3.3 原版專案備份

**強制要求**（v6 新增）：

```bash
cd C:\Projects\TradingAgents
git status                         # 確認 working tree 乾淨
git tag pre-tw-edition-backup      # 打標籤標記改造前狀態
git push origin pre-tw-edition-backup  # 如果有 remote
```

如此確保任何時候可以 `git checkout pre-tw-edition-backup` 回到改造前狀態。

### 3.4 完成標準

- [ ] 上述環境驗證 6 項全綠
- [ ] 至少取得 `GOOGLE_API_KEY`（Gemini）
- [ ] git tag `pre-tw-edition-backup` 已建立
- [ ] 確認 `C:\Projects\TradingAgents\PLAN.md` 是 v6.0
- [ ] 已讀完 Part A 全部章節

✅ 全部勾完 → 進 Phase 1

---

## 四、原版專案遷移指南

> v6 全新章節。**這是 v1-v5 都沒明確處理的關鍵衝突。**

### 4.1 現況

`C:\Projects\TradingAgents` 已是完整 Python 套件（v0.2.4）：

```
C:\Projects\TradingAgents\
├── tradingagents/          ← Python 套件（agents/, graph/, llm_clients/, dataflows/）
├── cli/                    ← 原版 CLI 入口
├── tests/                  ← 原版測試
├── scripts/                ← 原版工具腳本
├── main.py                 ← 原版範例入口
├── pyproject.toml          ← 套件定義（會與新 backend/pyproject.toml 衝突）
├── requirements.txt, requirements.lock
├── docker-compose.yml      ← 會與新版衝突
├── Dockerfile              ← 會與新版衝突
├── setup.bat, setup.ps1, start.bat, start.ps1, add_to_path.bat
├── README.md, CHANGELOG.md, LICENSE, SECURITY.md, SECURITY_FIXES.md
└── assets/, build/
```

### 4.2 衝突項目

| 衝突 | v5 處理 | v6 解法 |
|------|---------|---------|
| 根目錄 `pyproject.toml` | 沒提 | **移到 `legacy/pyproject.toml`** |
| `tradingagents/` 套件 | 「保留」 | **移到 `legacy/tradingagents/`** |
| 根目錄 `docker-compose.yml` | 隱含覆蓋 | **覆寫**（git 會保留 history） |
| 根目錄 `Dockerfile` | 沒提 | **覆寫**（移到 backend/Dockerfile） |
| 根目錄 `main.py` | 沒提 | **移到 `legacy/main.py`** |
| `cli/` | 沒提 | **移到 `legacy/cli/`** |
| `tests/` | 沒提 | **移到 `legacy/tests/`** |
| `scripts/` | 撞名 | **移到 `legacy/scripts/`**，新建空 `scripts/` |
| `requirements*.txt` | 沒提 | **移到 `legacy/`** |
| `setup.bat / start.bat / add_to_path.bat` | 沒提 | **移到 `legacy/`** |
| `assets/, build/` | 沒提 | **移到 `legacy/`**（build/ 可選擇刪除） |
| `README.md` | 沒提 | **改寫成新版 README**，原版備份到 `legacy/README.md` |
| `LICENSE / SECURITY.md / CHANGELOG.md` | 沒提 | **保留根目錄**（與新版相容） |

### 4.3 遷移指令（在 Phase 1 開頭執行）

```bash
cd C:\Projects\TradingAgents

# 1. 確認 Phase 0 已 tag
git tag --list | grep pre-tw-edition-backup || echo "❌ 請先跑 Phase 0"

# 2. 建 legacy 目錄並搬遷
mkdir legacy
git mv tradingagents legacy/
git mv cli legacy/
git mv tests legacy/
git mv scripts legacy/
git mv main.py legacy/
git mv pyproject.toml legacy/
git mv requirements.txt legacy/
git mv requirements.lock legacy/
git mv setup.bat legacy/
git mv setup.ps1 legacy/
git mv start.bat legacy/
git mv start.ps1 legacy/
git mv add_to_path.bat legacy/
git mv assets legacy/
git mv main.py legacy/ 2>/dev/null || true
git mv test.py legacy/ 2>/dev/null || true
git mv Dockerfile legacy/
git mv docker-compose.yml legacy/

# 3. 可選：刪除 build/（之前 setuptools 產物）
rm -rf build/  # 不用 git rm，因為應該本來就在 .gitignore

# 4. 寫 legacy/README.md 備註
cat > legacy/README.md << 'EOF'
# Legacy: 原版 TradingAgents (v0.2.4)

此目錄保留改造前的原版套件作為參考。
- 原版的 Agent prompts 與 LangGraph 邏輯可在 Phase 5 參考
- 不要直接 import 此處的程式碼到新後端
- 完整原版回到方式：`git checkout pre-tw-edition-backup`
EOF

# 5. commit
git add -A
git commit -m "chore: 將原版 v0.2.4 遷至 legacy/ 為 TW Edition 改造做準備"
```

### 4.4 從原版可以「複製參考」的內容

Phase 5 LangGraph Agent 系統時，建議**閱讀**（不是 import）以下原版檔案：

| 原版檔案 | 用途 |
|---------|------|
| `legacy/tradingagents/agents/analysts/*.py` | Analyst prompt 範例（我們改繁中 + 台股脈絡） |
| `legacy/tradingagents/agents/researchers/*.py` | Bull/Bear 辯論結構 |
| `legacy/tradingagents/agents/managers/research_manager.py` | 結構化輸出模式 |
| `legacy/tradingagents/graph/setup.py` | LangGraph StateGraph 構造 |
| `legacy/tradingagents/agents/utils/agent_states.py` | TypedDict 狀態設計 |

**注意：**
- Prompt 必須改繁中
- LLM client 全部改用我們的 `app/llm/__init__.py`（不用原版 `llm_clients/`）
- Tool 全部用新版（DB 來源不同）
- 結構化輸出 schema 可參考但要對齊新版 Pydantic v2

### 4.5 IDE 設定避免噪音

`.vscode/settings.json`（v6 建議）：

```json
{
  "python.analysis.exclude": ["legacy/**"],
  "python.testing.pytestArgs": ["backend/tests"],
  "files.watcherExclude": {
    "**/legacy/**": true,
    "**/.next/**": true,
    "**/node_modules/**": true
  },
  "search.exclude": {
    "legacy/**": true
  }
}
```

確保新開發時 IDE 不會搜到 legacy 內容、減少混淆。

---

## 五、架構決策記錄（ADR）

> v6 全新章節。記錄關鍵架構選擇的「為什麼」，避免未來反覆爭論。

### ADR-001：時序資料庫選 TimescaleDB（不選 InfluxDB / MongoDB）

**決定：** TimescaleDB（PostgreSQL extension）
**原因：**
- 同時需要時序（行情）+ 關聯式（用戶/訂單/審計），單一 PostgreSQL 處理避免兩套 DB
- TimescaleDB 的 hypertable 自動分片，10 年股價資料效能優於原生 PG
- 完整 SQL 與 PG 生態（Alembic、SQLAlchemy 都支援）
- InfluxDB Flux 語言學習成本高
- MongoDB 對交易類審計、ACID 要求弱

**取捨：**
- ✅ 一個 DB 處理所有結構化資料
- ✅ 標準 SQL，工程師熟悉
- ❌ Alembic 對 hypertable migration 支援不完整 → 用 raw SQL 補

### ADR-002：向量資料庫選 Qdrant（不選 pgvector / Pinecone / Weaviate）

**決定：** Qdrant（Docker 自架）
**原因：**
- Self-hosted 免費（vs Pinecone $70+/月）
- gRPC API 比 pgvector 快（百萬級向量時差距明顯）
- pgvector 雖然免裝新服務，但與行情資料混在一個 PG 會競爭資源
- Weaviate 太重（內建很多功能，但我們只要向量搜尋）
- Qdrant 的 hybrid search（dense + sparse）對 RAG 品質有幫助

**取捨：**
- ✅ 與 PG 隔離，互不干擾
- ✅ 免費 + 效能好
- ❌ 多一個服務要維運

### ADR-003：前端選 Next.js 14（不選 Vue / SvelteKit）

**決定：** Next.js 14.2 App Router
**原因：**
- React 生態最大（shadcn/ui, recharts, @xyflow/react 等首選）
- App Router 的 RSC 對 SEO 友善（雖然目前內部用，但保留未來擴展）
- TypeScript 支援最完整
- Vue 3 + Element Plus（CN 版選擇）社群比 React 小
- SvelteKit 漂亮但生態小

**取捨：**
- ✅ 元件生態最豐富
- ✅ 招人好招（如未來擴展團隊）
- ❌ App Router 學習曲線較陡

### ADR-004：後端 Web 選 FastAPI（不選 Django / Flask）

**決定：** FastAPI
**原因：**
- async/await 原生支援，與 LangGraph、httpx、SQLAlchemy 2.0 async 完美相容
- Pydantic v2 整合，型別安全
- OpenAPI 自動產生，前端 codegen 友善
- Django 同步為主（Django 5 雖然 async 但生態未跟上）
- Flask 太裸，需要自己組裝太多

**取捨：**
- ✅ async 原生
- ✅ 自動 OpenAPI
- ❌ Admin 需自建（Django 內建免費）

### ADR-005：LLM 預設選 Gemini 2.0 Flash（不選 OpenAI / Claude）

**決定：** 預設 `gemini-2.0-flash`，提供 fallback chain
**原因：**
- 成本：~$0.012/分析（OpenAI 4o-mini ~$0.018，Claude Haiku ~$0.10）
- 品質：對中文（台股新聞、財報）理解優秀
- 速度：1-3 分鐘完成完整分析
- 配額：免費版相對寬鬆

**取捨：**
- ✅ 中文最強（重要！台股新聞）
- ✅ 成本最低
- ❌ Tool calling 偶爾不穩 → 用 fallback chain

### ADR-006：認證選 JWT 自管（不選 Auth0 / Keycloak / Clerk）

**決定：** 自管 JWT + Refresh Token rotation
**原因：**
- 單機自用，不需要多 IdP / SSO
- Auth0 / Clerk 月費（最低 ~$25）對個人用戶不划算
- Keycloak 太重（要跑另一個 service）
- 自管在後端是 ~300 行程式碼，可控

**取捨：**
- ✅ 無外部依賴
- ✅ 完全控制
- ❌ 自己要管 token rotation、blacklist、CSRF

### ADR-007：手動核准下單（不做自動執行）

**決定：** AI 建議 → `pending_orders` → 人工核准
**原因：**
- AI 投資建議可能誤判，自動執行有財務風險
- 法規與責任歸屬考量（台灣金管會）
- 養成使用者「審視 AI 輸出」的習慣

**取捨：**
- ✅ 安全
- ✅ 符合 v1.0「不直連券商」原則
- ❌ 無法 fully automated

### ADR-008：時區策略：UTC 儲存 + Asia/Taipei 排程 + 用戶時區顯示

**決定：** 三層時區規則
**原因：** 標準做法，避免閏年/夏令時間問題

### ADR-009：金額用 Decimal + 字串 JSON 序列化

**決定：** 後端 Python `Decimal` + DB `NUMERIC` + JSON 序列化為**字串**
**原因：**
- JS Number 是 IEEE 754 double，不能精確表示 0.1 + 0.2
- 股價 12.34 經 JSON serialize 為 number 後，前端可能變 12.339999...
- 字串序列化 + 前端 BigNumber.js 完全保留精度

### ADR-010：使用 Playwright 替代 WeasyPrint 產 PDF

**決定：** PDF 用 Playwright headless Chrome 渲染 HTML
**原因：**
- WeasyPrint Windows 安裝 GTK 痛苦
- Playwright 中文支援完美（注入 Noto Sans TC CSS）
- HTML 模板用 Jinja2，所見即所得
- Docker image 加上 fonts-noto-cjk + chromium 即可

**取捨：**
- ✅ 跨平台
- ✅ 中文 OK
- ❌ Image 體積大（多 ~300MB）

---

## 六、版本相容性矩陣

> v6 全新章節。明確哪些版本組合是「已驗證可用」。

### 6.1 後端核心

| 組件 | 版本 | 為何選 | 升級風險 |
|------|------|--------|---------|
| Python | 3.11.x | 穩定 + langgraph 支援 + uv 預設好 | 3.12 部分 lib 還沒適配 |
| PostgreSQL | 16.x | TimescaleDB 2.x 主推版本 | 17.x TimescaleDB 兼容測試中 |
| TimescaleDB | 2.16+ | hypertable + retention policy 穩定 | - |
| Redis | 7.x alpine | AOF 穩定、maxmemory policies 完整 | - |
| Qdrant | 1.9+ | gRPC 穩定 + hybrid search | 2.x 大改 API |
| FastAPI | 0.115.x | startup/shutdown lifespan 穩定 | - |
| SQLAlchemy | 2.0.x | async session 穩定 | 2.1 待觀察 |
| asyncpg | 0.29+ | PG 16 完整支援 | - |
| LangGraph | **0.2.50+, <0.3** | 生產實測穩定 | **0.3 大改 API（注意！）** |
| LangChain Core | 0.3.x | 與 langgraph 配 | 4.x 大改 |
| Pydantic | 2.7+ | strict mode 穩定 | - |
| Celery | 5.4.x | Redis broker 穩定 | - |

### 6.2 前端核心

| 組件 | 版本 | 為何選 |
|------|------|--------|
| Node | 20.x LTS | 穩定 + 工具鏈完整 |
| Next.js | **14.2.x** | App Router 穩定 + RSC 成熟 |
| React | 18.3.x | Next 14.2 配 |
| TypeScript | 5.4+ | strict 模式好用 |
| Tailwind CSS | 3.4.x | shadcn 配 |
| shadcn/ui | latest | unstyled 元件 + 可客製 |
| @tanstack/react-query | 5.x | server state 標準 |
| zustand | 4.x | 輕量狀態 |
| @xyflow/react | 12.x | Agent flow 圖標準 |
| lightweight-charts | 4.x | TradingView 出品，K 線最佳 |
| recharts | 2.x | 統計圖表 |

### 6.3 不相容組合（明令禁止）

- ❌ Python 3.10：langgraph 部分功能 broken
- ❌ Python 3.13/3.14：太多 lib 還沒支援（用戶本機是 3.14，但 uv 會抓 3.11 給專案用）
- ❌ Next.js 15：App Router caching 行為大改
- ❌ LangGraph 0.3.x：API 大幅變動
- ❌ Pydantic 1.x：完全不相容
- ❌ Node 22：部分套件還沒適配
- ❌ PostgreSQL 17 + TimescaleDB：兼容測試中
- ❌ asyncpg 0.28 ↓：PG 16 SCRAM-SHA-256 認證問題

### 6.4 lock file 策略

- 後端：`backend/uv.lock`（commit 進 git）
- 前端：`frontend/package-lock.json`（commit 進 git）
- 不要用 `^` / `~` 範圍，pin 到 minor version

---

## 七、接受的限制（Honest Tradeoffs）

> v6 全新章節。誠實列出 v1.0 已知會有問題、但我們選擇接受的事。

| 限制 | 為何接受 | 預期影響 | 補救措施 |
|------|---------|---------|---------|
| yfinance 偶爾失敗（Yahoo 改 API） | 免費、其他來源也不完美 | 美股資料偶爾延遲 1-2 天 | Alpha Vantage fallback + 24h 快取 |
| FinMind 免費版配額 600/day | 付費 $99 不是每人都願意 | 大量 backfill 要分多天 | 主用 TWSE/TPEX OpenAPI（無限制）+ FinMind 補強 |
| LangGraph state 累積會慢 | 多輪辯論本來就會累 | 5+ 輪辯論可能超過 prompt 限制 | trim + summary，硬上限 6 輪 |
| 單機 WebSocket 約 1000 連線上限 | uvicorn 單 process 限制 | 自用足夠，多用戶會撞 | v2.0 才考慮多 worker + Redis pub/sub broadcaster |
| PDF 匯出耗時 ~5 秒 | Playwright 啟動成本 | 用戶體驗略慢 | 顯示進度條，未來預啟動 chromium pool |
| 前端 Bundle ~1.5 MB（gzip 後 ~500 KB） | Next.js + 圖表 lib | 首次載入慢 | App Router 自動 code splitting + dynamic import |
| Docker 啟動 ~30 秒（健康檢查含等待） | 多服務依賴 | 開發體驗略慢 | wait-for-services.sh 已最佳化 |
| TimescaleDB 不能在 hypertable 改主鍵 | 設計限制 | 一旦定義不能改 | schema 定義謹慎 + 加 version column 樂觀鎖 |
| 第一次跑 backfill 約 30 分鐘 | API 配額 + 串行處理 | 安裝後不能立刻分析 | Phase 9 onboarding 引導用戶等待 |
| 中文 PDF 偶爾排版略醜 | weasyprint 替代品 Playwright 不是專業排版 | 美觀略差於 Word | 模板優化 + 用戶可改 export 為 Markdown |
| Audit log 1 年後刪除 | 儲存成本 | 一年前的審計不可查 | 異地歸檔（壓縮 + 加密） |
| 每月 LLM 成本可能波動 ±50% | 用戶使用頻率變動 | 預算無法精確 | 月度 dashboard + 80% 警告 |
| Yahoo Finance 對台股部分代號支援不全 | 非官方 | 美股輔助、台股以 FinMind 為主 | 不依賴 yfinance 抓台股 |
| Celery beat 在容器重啟時可能 miss 一次 schedule | 設計使然 | 一次資料延遲 | beat_max_loop_interval 設小 + 開機 catch-up task |

---

## 八、反模式清單（禁止做的事）

> v6 全新章節。**這些事不要做，做了系統會壞。**

### 8.1 程式碼層

| ❌ 不要 | ✅ 要 |
|--------|-------|
| 在 Agent tool 中用 `ta_service_rw` 連 DB | 只用 `ta_agent_ro`（read-only） |
| `from tradingagents.xxx import ...`（從 legacy） | 自己重新實作 in `backend/app/` |
| 用 float 算金額 | 用 `Decimal` |
| API 回傳 datetime 物件直接 JSON | ISO 8601 字串（UTC） |
| `print()` 除錯 | `structlog.get_logger().info(...)` |
| 同步 `requests.get()` 在 async function | `httpx.AsyncClient` |
| `time.sleep()` in async | `asyncio.sleep()` |
| 直接 `session.execute(text("DELETE FROM users WHERE id=" + str(id)))` | SQLAlchemy ORM 或參數化 |
| Catch all `except Exception: pass` | 具體例外 + 至少 log |
| 在 prompt 中放 API key | 永遠不傳 secret 給 LLM |
| LLM 輸出直接當 SQL 執行 | Pydantic 嚴格驗證後再用 |

### 8.2 資料庫層

| ❌ 不要 | ✅ 要 |
|--------|-------|
| 在 hypertable 改主鍵 | 設計階段定好，不改 |
| `DELETE FROM stock_prices WHERE ...` 大量刪除 | 用 retention policy 自動 drop chunks |
| 大量 INSERT 不開 transaction | `executemany` 或 COPY |
| 在 audit_logs 用 `service_rw` UPDATE | audit_logs 只能 INSERT（已 REVOKE） |
| 跨 hypertable 大 JOIN（沒 time filter） | 一定要有 time range |
| 沒 index 的欄位排序 | 加 index 或限制排序欄位白名單 |
| 在 production DB 跑 `EXPLAIN ANALYZE` 大查詢 | 用 read replica 或 staging |
| 直接修改 `stock_list`（人工） | 透過 `seed_stock_list.py` |

### 8.3 安全層

| ❌ 不要 | ✅ 要 |
|--------|-------|
| API key 進 git（即使是 test key） | 用 `.env` + `detect-secrets` |
| JWT in URL query | Authorization header 或 cookie |
| WS 認證用 query token（會記入 nginx log） | Subprotocol + Ticket（v6 規範） |
| 密碼明文比對 | bcrypt + verify |
| 5xx 錯誤直接吐 stack trace 給前端 | trace_id 給前端，stack 進 log |
| CORS `allow_origins=["*"]` + `allow_credentials=True` | 列舉具體 origin |
| `eval()` / `exec()` 處理用戶輸入 | 永遠不要 |
| 用 LLM 輸出構造 shell command | 永遠不要 |

### 8.4 部署層

| ❌ 不要 | ✅ 要 |
|--------|-------|
| Container 跑 root | uid 1000 非 root |
| 把 `.env` 打進 image | mount as volume / docker secrets |
| Backend port 對外（prod） | 只 nginx 對外 |
| `docker compose up` 不加 `-d` 在 prod | 加 `-d` 背景執行 |
| 改 prod 設定不留 backup | 改前 backup script |
| Migration 直接在 prod 跑沒 dry-run | staging 演練 |
| TLS 用自簽憑證（prod） | Let's Encrypt |

### 8.5 流程層

| ❌ 不要 | ✅ 要 |
|--------|-------|
| Phase 沒驗收完直接進下一 Phase | 走完 Phase 退出條件 |
| 在 main 直接 commit | 切 feat/ 分支 + PR |
| 跳過 pre-commit hook | 修好再 commit |
| 跳 Phase（先做 P5 再回頭做 P3） | 嚴格依序 |
| 把 Phase Prompt 全部一次貼進一個對話 | 開新對話貼一個 Phase |

---

# Part B — 設計參考

---

## 九、願景與 SLO

### 9.1 願景

打造**正式產品等級**、**台股主、美股輔**的多 Agent AI 投資分析平台。

**v1.0 範圍：**
- 台股完整資料管線、4 種 Analyst（含籌碼面）
- 美股輔助：OHLCV/財報/新聞、3 種 Analyst（無籌碼面）
- 18 頁繁中前端、手動核准、不可竄改審計、LINE/Telegram 通知、PDF/MD/XLSX

**v1.0 不做：** 真實券商 API、即時分鐘 K、法說會錄音、多用戶多組織、行動 App、雲端 IaC、英文 UI、港股/A 股、Prometheus/Grafana。

### 9.2 SLO

| 指標 | 目標 | 量測 |
|------|------|------|
| API 可用性 | 99% | /health/ready |
| API P95 延遲（除分析） | < 500ms | nginx access log |
| 分析完成率 | > 95% | analysis_reports.status |
| 分析延遲 P95 | < 5 分鐘 | execution_time_seconds |
| 資料新鮮度 | 收盤後 1 小時內入庫 | last_update vs market_close |
| Audit 完整性 | 100% | 每日 verify_audit_chain |

---

## 十、跨市場架構

### 10.1 市場識別

```python
class Market(str, Enum):
    TWSE = "TWSE"; TPEX = "TPEX"
    NASDAQ = "NASDAQ"; NYSE = "NYSE"; AMEX = "AMEX"

class MarketRegion(str, Enum):
    TW = "TW"; US = "US"
```

### 10.2 Symbol 驗證

涵蓋所有台股實際樣態：

```python
TW_SYMBOL_PATTERN = re.compile(r'^[0-9]{4}[A-Z0-9]?$|^[0-9]{6}[A-Z]?$')
US_SYMBOL_PATTERN = re.compile(r'^[A-Z]{1,5}(\.[A-Z])?$')
```

涵蓋：一般股 `2330`、ETF `0050/006208/00878`、特別股 `2884A`、權證 `030001/043333P`、美股 `AAPL/BRK.B`。

`validate_symbol_exists()` 驗證 stock_list 中存在（防亂打字）。

### 10.3 統一資料表

跨市場表加 `market` 欄位；台股獨有表（institutional_trading、margin_trading、monthly_revenue）保持 TW only。

### 10.4 資料來源對照

| 資料 | 台股主 | 台股備 | 美股主 | 美股備 |
|------|-------|-------|-------|-------|
| OHLCV | FinMind | TWSE/TPEX | yfinance | Alpha Vantage |
| 財報 | FinMind | MOPS | yfinance | Finnhub |
| 新聞 | cnyes RSS | money.udn | yfinance | NewsAPI |
| 公告 | MOPS | - | SEC EDGAR | - |
| 籌碼 | FinMind/TWSE | - | N/A | - |

### 10.5 Analyst × 市場

| Analyst | TW | US |
|---------|----|----|
| Market | ✅ | ✅ |
| Fundamental | ✅ | ✅ |
| News | ✅ | ✅ |
| Sentiment（籌碼） | ✅ | ❌ v1.1 |

`build_graph(symbol, market)` 自動依 region 過濾可用 analysts。

---

## 十一、風險評估矩陣

| 風險 | 機率 | 影響 | 緩解 |
|------|------|------|------|
| FinMind 配額不足 | 高 | 高 | 主用 TWSE/TPEX + 強制 Redis 快取 |
| WeasyPrint Windows 困難 | 高 | 中 | **改用 Playwright（ADR-010）** |
| yfinance 不穩 | 中 | 中 | Alpha Vantage 備援 + 24h 快取 |
| LangGraph 0.3 大改 | 中 | 高 | pin `>=0.2.50,<0.3` |
| Backend 啟動 DB 未 ready | 高 | 高 | wait-for-services.sh + healthy depends_on |
| 訂單並發核准 | 低 | 高 | SELECT FOR UPDATE + version column |
| WS JWT 寫入 nginx log | 高 | 中 | Subprotocol + Ticket |
| Celery 任務超 retries 失蹤 | 中 | 中 | DLQ table + admin 告警 |
| 時區誤判 | 中 | 高 | 3 層時區規則 + 測試覆蓋 |
| JS 浮點誤差 | 中 | 中 | Decimal + 字串序列化 + BigNumber.js |
| 大量股票表格前端崩 | 中 | 中 | react-window 虛擬化 |
| LLM 全失敗 | 低 | 高 | Provider chain + LINE 通知 |

---

## 十二、技術架構

### 12.1 邏輯架構

```
Browser (Chrome ≥120)
    │ HTTPS:443 (prod) / HTTP:3000 (dev)
Nginx 1.27 (prod only)
    │
    ├─ /         → Next.js 14.2 (3000)
    └─ /api/*    → FastAPI 0.115 (8000)
       /ws/*       └─ Middleware: TrustedHost → SecHeaders → CORS
                              → CSRF → RequestID → Audit → RateLimit
                       └─ API: 15 routers, 4 layers
                       └─ Celery 5.4 (worker + beat + DLQ)
                       └─ LangGraph 0.2.50+

Storage:
  TimescaleDB (pg16+ts2): pool rw=20, ro=30, statement_timeout=30s
  Qdrant 1.9 (gRPC:6334, API key)
  Redis 7 alpine (7 db: cache/celery/ratelimit/jwt/pubsub/wsticket/idem)
```

### 12.2 服務通訊

| 來源 → 目標 | 協定 | 認證 | TLS |
|-------------|------|------|-----|
| Browser → Nginx | HTTPS | - | ✅ |
| Browser → Backend (WS) | wss + subprotocol | **WS Ticket** | ✅ |
| Backend → DB | TCP/asyncpg | 帳密 | 內網 |
| Backend → Redis | TCP/hiredis | requirepass | 內網 |
| Backend → Qdrant | gRPC:6334 | API key | 內網 |
| Backend → External | HTTPS | API key | ✅ |

---

## 十三、系統 Bootstrap 流程

### 13.1 啟動依賴順序

```
1. Docker → timescaledb / qdrant / redis（並行 + healthcheck）
2. init_db.py → schema + Qdrant collections + 第一個 admin
3. seed_stock_list.py → stock_list 至少 1500 筆（必跑！否則前端搜尋空）
4. backend → wait-for-services.sh 確認後啟動
5. celery_worker + celery_beat → 排程開始
6. backfill.py → 至少 1 支股票（如 2330）有 1 年資料
7. frontend → 啟動
8. admin 登入 → onboarding（強制改密碼 + 引導）→ 第一個分析
```

### 13.2 wait-for-services.sh

```bash
#!/bin/sh
until pg_isready -h timescaledb -U postgres; do sleep 2; done
until redis-cli -h redis ping | grep PONG; do sleep 2; done
until curl -sf http://qdrant:6333/healthz > /dev/null; do sleep 2; done
exec "$@"
```

`docker-compose.yml` backend service：
```yaml
depends_on:
  timescaledb: { condition: service_healthy }
  redis:       { condition: service_healthy }
  qdrant:      { condition: service_healthy }
```

### 13.3 健康檢查三層

| 層 | 條件 |
|----|------|
| /health/live | 程式還活著 |
| /health/ready | 上述 + 依賴可連 + DB pool 至少 1 idle |
| /health/seeded | 上述 + stock_list ≥ 100 + 至少 1 支有 OHLCV |

### 13.4 Onboarding

新增欄位：
```sql
ALTER TABLE users
  ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE,
  ADD COLUMN must_change_password BOOLEAN DEFAULT TRUE;
```

`POST /auth/login` 回應加 `next_action`：`change_password` | `onboarding` | `dashboard`。

---

## 十四、穩定性工程

### 14.1 連線池

| 連線 | 最小 | 最大 | Idle TO |
|------|-----|-----|---------|
| asyncpg rw | 5 | 20 | 300s |
| asyncpg ro | 5 | 30 | 300s |
| Redis | 5 | 50 | 60s |
| httpx FinMind | - | 10 | 60s |
| httpx Yahoo | - | 5 | 60s |
| httpx Gemini | - | 10 | 120s |

PG session：`SET statement_timeout='30s', lock_timeout='10s', idle_in_transaction_session_timeout='60s'`

### 14.2 重試（tenacity）

```python
RETRY_CONFIG = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=30) + wait_random(0, 2),  # jitter
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
)
```

LLM **不重試**（內建 retry，重試成本高）→ 改 fallback chain。

### 14.3 Circuit Breaker

連續 5 次失敗 → OPEN 10 分鐘 → HALF_OPEN 試 1 次 → 成功 CLOSED / 失敗繼續 OPEN。
觸發 OPEN 立即發 LINE + audit (CRITICAL)。

### 14.4 LLM Fallback Chain

```python
LLM_FALLBACK_CHAIN = {
    "google":    ["openai", "anthropic"],
    "openai":    ["google", "anthropic"],
    "anthropic": ["google", "openai"],
}
```

### 14.5 Idempotency

POST 建立類接受 `Idempotency-Key` header（Redis db6, TTL 24h）。

### 14.6 Graceful Shutdown

`stop_grace_period: 60s`，FastAPI lifespan close → 等 in-flight → 關 pool。

### 14.7 Worker

`celery_worker --concurrency=4 --max-tasks-per-child=50 --prefetch-multiplier=1`

### 14.8 任務超時

| 任務 | soft | hard | mem |
|------|------|------|-----|
| sync_ohlcv | 600s | 900s | 512MB |
| news_ingest | 300s | 600s | 256MB |
| run_analysis | 900s | 1200s | 1GB |

### 14.9 LangGraph State 控制

```python
MAX_STATE_SIZE_BYTES = 500_000

def trim_state_messages(state):
    if len(state["debate_history"]) > 6:
        old, recent = state["debate_history"][:-6], state["debate_history"][-6:]
        state["debate_history"] = [{"role": "summary", "content": summarize(old)}] + recent
```

### 14.10 Dead Letter Queue

```sql
CREATE TABLE celery_dead_letters (
  id BIGSERIAL PRIMARY KEY,
  task_name TEXT, task_id UUID, args JSONB, kwargs JSONB,
  exception TEXT, traceback TEXT,
  failed_at TIMESTAMPTZ DEFAULT NOW(),
  retry_count INT, resolved BOOLEAN DEFAULT FALSE,
  resolved_at TIMESTAMPTZ, resolved_by UUID
);
```

`task_failure` signal 寫入 + 通知 admin。Admin `/admin/pipeline` 頁手動 resolve / re-queue。

---

## 十五、資料一致性與並發

### 15.1 Transaction 原則

「跨多表的業務動作必須在同一 transaction 內，失敗整體 rollback。」

關鍵：訂單核准

```python
async def approve_order(order_id, admin_id, idempotency_key):
    async with rw_session.begin():
        order = await session.execute(
            select(PendingOrder).where(PendingOrder.id == order_id).with_for_update()
        )
        if order.status != "PENDING":
            raise ConflictError("ORDER_ALREADY_PROCESSED")
        order.status = "APPROVED"
        order.reviewed_by = admin_id
        session.add(PortfolioPosition(...))
        await audit_repo.append(action="order.approved", ...)
```

### 15.2 樂觀鎖（version column）

```sql
ALTER TABLE analysis_reports ADD COLUMN version INT DEFAULT 1;
```

讀多寫少場景用 version 比對 + RETURNING。

### 15.3 N+1 防護

統計頁面：明確用 `join + group_by`，Repository 提供 `with_usage()` 等聚合方法。

### 15.4 Orphan Cleanup

每日 04:00：
- analysis_reports `running` 超過 30 分 → `failed`
- pending_orders `PENDING` 超過 7 天 → `EXPIRED`
- password_reset_tokens 過期 → 刪除
- user_sessions 過期 → 刪除
- notification_log 超過 90 天 → 歸檔

### 15.5 時區三層規則

1. **儲存層：** DB TIMESTAMPTZ 全 UTC
2. **排程層：** Celery beat `timezone="Asia/Taipei"`，內部轉 UTC
3. **顯示層：** 前端依 `users.preferred_timezone`（預設 Asia/Taipei）

### 15.6 小數精度

| 層 | 處理 |
|----|------|
| DB | NUMERIC(precision, scale) |
| Python | `Decimal`（禁用 float 算錢） |
| API JSON | 序列化為**字串** |
| 前端 | BigNumber.js 或 Intl.NumberFormat |

---

## 十六、可觀測性與 SLO 監控

### 16.1 三大支柱

**Logs：** structlog JSON，遮蔽敏感欄位
**Metrics：** `/metrics` Prometheus format（admin only）
**Traces：** trace_id 全鏈路（HTTP → Celery headers → WS event）

### 16.2 Metrics 範例

```
analysis_total{status="completed"} 142
analysis_duration_seconds{quantile="0.95"} 187
llm_cost_usd_today 0.42
http_request_duration_seconds_bucket{path="/api/v1/stocks", le="0.1"} 234
db_connections_used{pool="rw"} 8
celery_queue_length 0
data_pipeline_last_success_seconds_ago{worker="ohlcv_tw"} 3621
```

前端 `/admin/system` 直接拉解析（v1.0），v2.0 接 Prometheus。

### 16.3 關鍵告警

| 告警 | 觸發 | 通知 |
|------|------|------|
| Audit chain 斷裂 | verify 失敗 | LINE CRITICAL |
| Circuit Breaker OPEN | 任何 source/LLM | LINE WARN |
| LLM 月成本 80% | 預算 80% | LINE WARN |
| LLM 月成本 100% | 達標 | 拒絕新分析 + CRITICAL |
| 磁碟 > 80% | 每小時 | LINE WARN |
| 磁碟 > 95% | 每小時 | CRITICAL + 暫停寫入 |
| Celery DLQ 新任務 | 即時 | LINE WARN |
| /health/ready 連 5 次 503 | 監控 | CRITICAL |
| 資料管線 24h 未更新 | 每小時 | LINE WARN |

### 16.4 SLO 報表

`scripts/slo_report.py` 每天 06:00：計算 24h SLI、對比 SLO、算「錯誤預算消耗率」，超過 1.0 → LINE 警告。

---

## 十七、跨 Phase 工程規範

### 17.1 Logging
structlog + JSON + 遮蔽（password, api_key, token, authorization, line_token, telegram_token, refresh_token, csrf, cookie）。

### 17.2 Error 階層

```python
class AppError(Exception):
    code: str; message_zh: str; http_status: int = 500; details: dict = {}

ValidationError(422), NotFoundError(404), AuthError(401),
ForbiddenError(403), ConflictError(409), RateLimitError(429),
ExternalServiceError(503), TooLargeError(413), LockedError(423),
QuotaExceededError(402), IdempotencyConflictError(409)
```

### 17.3 API Envelope

成功：`{"data": ..., "meta": {trace_id, version, timestamp}, "pagination": {...}}`
失敗：`{"error": {code, message, trace_id, details}}`

### 17.4 分頁

統一 cursor-based：`?limit=50&cursor=base64(json)`，max limit=100。

### 17.5 快取

| 用途 | Key | TTL | Invalidation |
|------|-----|-----|--------------|
| 個股當日 | `cache:price:{symbol}:{date}` | 收盤後 24h | TTL |
| 個股資訊 | `cache:info:{symbol}` | 7 天 | 排程更新後 DEL |
| 大盤 | `cache:market:overview` | 5 min | TTL |
| Tool 結果 | `cache:tool:{name}:{params_hash}` | 1h | TTL |
| Session | `session:{user_id}` | 7d | logout/改密碼 DEL |
| 自選股 | `cache:watchlist:{user_id}` | 1h | 增刪 DEL |
| 統計聚合 | `cache:stats:{type}:{params}` | 1h | Event-driven DEL |

### 17.6 測試金字塔

| 層 | 比例 | 工具 | 目標 |
|----|------|------|------|
| Unit | 70% | pytest / vitest | 後端 80%、前端 60% |
| Integration | 25% | pytest + testcontainers | API + DB |
| E2E | 5% | Playwright | 關鍵流程 |

### 17.7 Migration

初始 schema：raw SQL（init.sql）
後續：Alembic（hypertable 用 `op.execute()`，連線用 `ta_migration` 帳號）
每個 migration 必寫 `downgrade()`，CI 跑 upgrade↔downgrade 測試。

### 17.8 Code Style

| 語言 | Linter | Formatter |
|------|--------|-----------|
| Python | ruff | ruff format（line=100） |
| TS | ESLint + security | Prettier |
| SQL | sqlfluff | - |

Pre-commit：ruff、prettier、detect-secrets、trailing-whitespace。

### 17.9 跨 Phase 依賴矩陣

| 元件 | 建立 Phase | 後續使用 |
|------|-----------|---------|
| 工程規範 | P1 | 全部 |
| Docker + wait-for-it | P1 | 全部 |
| Settings | P1 | 全部 |
| structlog | P1 | 全部 |
| AppError | P1 | 全部 |
| API Envelope | P1 | P3+ |
| TimescaleDB schema | P2 | P3+ |
| stock_list seed | P2 | **前端搜尋必需** |
| Qdrant collections | P2 | P5、P7 |
| BaseDataSource | P2 | P5 |
| Repository 基類 | P2 | P3+ |
| Celery + DLQ | P2 | P5 |
| Auth + Middleware | P3 | P4+ |
| Audit hash chain | P3 | 全部 |
| WS Ticket | P3 | P4、P5、P6 |
| BaseAnalyst Plugin | P5 | 未來 |
| BaseLLMProvider | P5 | 未來 |
| Frontend 共用元件 | P6 | P7 |
| EventBus 訂閱者 | P8 | 跨 Phase |

---

## 十八、程式碼分層架構

### 18.1 後端分層

```
API → Service → Domain → Repository → Infrastructure
```

| 層 | 職責 |
|----|------|
| API | HTTP、Pydantic、權限 |
| Service | 業務、事件發布 |
| Domain | 純規則（signal, risk, scoring） |
| Repository | DB / Redis / Qdrant 抽象 |
| Infrastructure | core/, data_sources/, llm/, notifications/ |

### 18.2 Plugin Pattern

```python
class BaseAnalyst(ABC):
    name: str; display_name_zh: str
    supported_regions: list[MarketRegion]
    @abstractmethod
    async def analyze(self, state) -> str: ...

ANALYST_REGISTRY = {"market": MarketAnalyst, ...}
```

Data Source / LLM Provider / Notifier 同樣模式。

### 18.3 Event-Driven

`AnalysisCompletedEvent`、`OrderPendingEvent`、`CircuitBreakerOpenEvent`、`LLMQuotaExceededEvent`、`AuditChainBrokenEvent`

Redis pubsub（跨 process）+ in-process EventEmitter（同 process）。

---

## 十九、安全架構

### 19.1 認證授權

| 項 | 規範 |
|----|------|
| 密碼 | 12 字元 + 4 類字元、bcrypt cost=12、不可同最近 5 次 |
| Lockout | 5 次失敗 → 15 分鐘鎖 |
| JWT | HS256 (key 32 bytes) + access 15 min + refresh 7 天 + rotation + blacklist |
| CSRF | refresh path X-CSRF-Token + SameSite=Strict |
| WS 認證 | **Subprotocol + Ticket**（一次性 60s） |
| Session | per user 5 個上限 |
| 角色 | ADMIN / ANALYST / VIEWER |
| 密碼重置 | 限速 3/hr/IP + 一次性 token + 撤銷舊 sessions |
| 註冊 | v1.0 不開放（admin 建用戶） |

### 19.2 輸入驗證

Pydantic strict + Symbol Dispatcher + Symbol 存在性 + 日期範圍 + Body size 1MB + URL 2048 + UUID + HTTP method 嚴格 + 排序白名單 + Content-Type 強制 application/json。

### 19.3 Rate Limit（多層）

| 層 | 範圍 | 限制 |
|----|------|------|
| L1 | per IP | 300/min（Nginx） |
| L2 | /auth/login | 5/min/IP |
| L3 | /auth/password-reset | 3/hr/IP |
| L4 | per user | 60/min |
| L5 | /analysis/start | 10/hr/user |
| L6 | LLM 月成本 | $50/user |

### 19.4 Secret 管理

- Dev `.env`、Prod Docker secrets
- JWT 雙 key 7 天並存 rotation
- DB 半年輪換
- LINE/Telegram token 用 Fernet 加密（DATA_ENCRYPTION_KEY 與 SECRET_KEY 分離）
- log 自動遮蔽

### 19.5 容器安全

| 項 | Prod |
|----|------|
| 非 root | uid 1000 |
| Read-only fs | 是（除必要 volumes） |
| Capabilities | drop ALL（nginx 加 NET_BIND_SERVICE） |
| Image 掃描 | Trivy（CI） |

### 19.6 Audit 不可竄改

hash chain（prev_hash, entry_hash）+ 撤銷 UPDATE/DELETE 權限 + 每日校驗。

### 19.7 CSP

```
default-src 'self';
script-src 'self' 'unsafe-inline' 'unsafe-eval';   # dev
style-src 'self' 'unsafe-inline';
img-src 'self' data: https:;
font-src 'self' data:;
connect-src 'self' wss: https:;
frame-ancestors 'none';
```

prod：移除 `unsafe-eval`，改 nonce-based。

---

## 二十、資料模型與來源

### 20.1 資料來源（依官方為準）

| 來源 | 區域 | 配額 | 月費 |
|------|------|------|------|
| FinMind 免費 | TW | 依官方 | 0 |
| FinMind 付費 | TW | 較高 | ~$99 |
| TWSE/TPEX OpenAPI | TW | 1 req/sec 建議 | 0 |
| MOPS | TW | 1 req/sec | 0 |
| cnyes RSS | TW | 公開 | 0 |
| yfinance | US | 非官方不穩 | 0 |
| Alpha Vantage | US | 25/day 免費 / 付費 | 0 / $50 |
| Finnhub | US | 60/min 免費 | 0 |
| SEC EDGAR | US | 10/sec | 0 |
| Gemini 2.0 Flash | - | pay-as-go | ~$5（5 次/天） |
| Gemini Embedding | - | < 1500/min 免費 | 0 |

**自用建議：** FinMind 付費 + Alpha Vantage 付費 + Gemini Flash ≈ **$154/月**

### 20.2 完整資料表

依先前章節 + v6 補（含 onboarding、user_watchlist、analysis_reports.version、celery_dead_letters）。

### 20.3 Qdrant Collections

```python
COLLECTIONS = [
    {"name": "tw_news_v1", "size": 768, "distance": "Cosine"},
    {"name": "tw_announcements_v1", "size": 768},
    {"name": "tw_earnings_calls_v1", "size": 768},
    {"name": "tw_macro_news_v1", "size": 768},
    {"name": "tw_industry_reports_v1", "size": 768},
    {"name": "us_news_v1", "size": 768},
    {"name": "us_filings_v1", "size": 768},
]
```

### 20.4 Embedding Model

主：Gemini `text-embedding-004`（768 維，免費 < 1500/min）
備：本地 `BAAI/bge-m3`（多語、768 維、sentence-transformers）

**警告：** 同 collection 不可混用！v1.0 預設 Gemini。

---

## 二十一、完整頁面地圖

```
側邊欄
├── 🏠 儀表板                      [P6 完整]
├── 📊 市場
│   ├── 市場總覽                   [P7 完整]
│   ├── 三大法人                   [P7 完整]（台股 only）
│   └── 財報日曆                   [P7 mock → v1.1]
├── 🔍 選股
│   ├── 自選股清單                 [P6 完整]
│   ├── 選股篩選器                 [P7 完整]
│   └── 多股比較                   [P7 mock → v1.1]
├── 🤖 AI 分析
│   ├── 新增分析                   [P6 完整]
│   ├── 分析進度                   [P6 完整]
│   ├── 分析歷史                   [P6 完整]
│   └── 辯論詳情                   [P6 完整]
├── 📈 績效統計
│   ├── 準確率分析                 [P7 完整]
│   ├── 模型比較                   [P7 完整]
│   └── 回測結果                   [P7 mock → v1.1]
├── 💼 投資組合
│   ├── 模擬持倉                   [P7 完整]
│   ├── 待核准訂單                 [P6 完整]
│   └── 交易記錄                   [P7 完整]
├── 📰 資訊
│   ├── 新聞情緒                   [P7 完整]
│   └── 重大公告                   [P7 完整]
├── 🔔 通知設定                    [P7 + P8]
└── ⚙️ 管理
    ├── 用戶管理                   [P6 完整]
    ├── 審計日誌                   [P6 完整]
    ├── 系統監控                   [P7 完整]
    └── 資料管線                   [P7 完整]
```

---

## 二十二、目錄結構

```
C:\Projects\TradingAgents\
├── legacy/                      ← 原版 v0.2.4（v6 強制搬遷）
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/              ← 15 routers + ws.py + metrics.py
│   │   ├── core/                ← config, database, redis, qdrant, security,
│   │   │                          security_headers, audit, rate_limit, csrf,
│   │   │                          validators, crypto, logging_config,
│   │   │                          error_handlers, event_bus, http_client,
│   │   │                          circuit_breaker, market_dispatcher,
│   │   │                          request_id, ws_ticket, response_envelope,
│   │   │                          pagination
│   │   ├── repos/
│   │   ├── services/
│   │   ├── domain/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── agents/
│   │   ├── data_sources/{base, fallback, tw/, us/}
│   │   ├── llm/
│   │   ├── workers/
│   │   ├── notifications/
│   │   └── exports/
│   ├── migrations/
│   ├── tests/{unit, integration, security}
│   ├── scripts/wait-for-services.sh
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── Dockerfile
│
├── data-pipeline/
│   ├── schemas/{timescaledb.sql, qdrant_init.py}
│   └── scripts/{init_db, seed_stock_list, seed_users, backfill,
│                 verify_data, verify_security}.py
│
├── frontend/
│   ├── src/{app, components, lib, store, hooks, i18n}
│   ├── tests/{unit, e2e}
│   ├── Dockerfile
│   └── package.json
│
├── docker/
│   ├── timescaledb/init.sql
│   ├── nginx/{nginx.conf, certs/}
│   ├── backups/
│   └── playwright/
│
├── scripts/
│   ├── backup.sh, restore.sh
│   ├── verify_backup.sh
│   ├── rotate_secrets.sh
│   ├── verify_audit_chain.py
│   ├── slo_report.py
│   └── healthcheck.sh
│
├── .github/workflows/{ci.yml, security.yml, release.yml}
│
├── docs/
│   ├── README.md, setup.md, connection-guide.md, user-guide.md,
│   ├── api.md, security.md, engineering-standards.md,
│   ├── deployment.md, runbook.md, disaster-recovery.md, obsidian-setup.md
│
├── .vscode/settings.json        ← v6 新（IDE 排除 legacy）
├── docker-compose.yml, docker-compose.prod.yml
├── .env.example, .env.prod.example
├── Makefile
├── PLAN.md                      ← 本文件
├── README.md                    ← 改寫成新版（原版備份在 legacy/）
├── LICENSE                      ← 保留根目錄
├── SECURITY.md                  ← 保留根目錄
└── CHANGELOG.md                 ← 保留並繼續更新
```

---

## 二十三、CI/CD

### 23.1 GitHub Actions

`.github/workflows/ci.yml`（PR 與 push）：
- backend：ruff、pytest unit + integration（testcontainers）、Alembic up/down 測試
- frontend：lint、test、build

`.github/workflows/security.yml`（每週 + PR）：
- bandit、detect-secrets baseline、Trivy image scan、npm audit

`.github/workflows/release.yml`（tag）：
- build images → push ghcr.io

### 23.2 Pre-commit
ruff、prettier、detect-secrets、trailing-whitespace。

---

# Part C — 執行

---

## 二十四、Phase 總覽 + 時程預估

| # | 主題 | 行數 | Token | Calendar Time | 風險 |
|---|------|------|-------|--------------|------|
| **P0** | Pre-flight 環境驗證（手動） | - | - | 30 分鐘 | 低 |
| **P1** | 基礎設施 + 規範 + Migration | ~600 | ~60k | **1-2 天** | 低 |
| **P2** | 資料管線 + Bootstrap scripts | ~1200 | ~95k | **2-3 天** | 中 |
| **P3** | 後端基礎（auth/middleware） | ~1400 | ~115k | **2-3 天** | 中 |
| **P4** | 業務 API（15 routers） | ~2000 | ~155k | **3-4 天** | 高 |
| **P5** | LangGraph Agent | ~2000 | ~155k | **3-4 天** | 高 |
| **P6** | 前端 + 8 核心頁 | ~2400 | ~160k | **3-4 天** | 高 |
| **P7** | 前端 10 進階頁 | ~2100 | ~145k | **2-3 天** | 高 |
| **P8** | 安全 + 通知 + 測試 | ~1000 | ~85k | **2-3 天** | 中 |
| **P9** | 部署 + DR + Obsidian | ~700 | ~65k | **1-2 天** | 中 |

**合計：** ~19-28 天 calendar time（每天 4-6 小時）≈ **3-5 週完成 v1.0**

**Token 合計：** ~1.03M（每 Phase 都在 200k context window 內）

**P4-P7 注意：** 開新乾淨 Claude 對話，只貼該 Phase Prompt；遇到 context 接近上限 → 分段 Apply。

---

## 二十五、Phase 0：Pre-flight 環境驗證

> v6 全新。**P1 之前必跑**。手動執行（約 30 分鐘）。

### 25.1 環境驗證指令

依第三章 3.1 執行所有指令並確認結果。

### 25.2 取得 API Keys

依第三章 3.2 取得至少 `GOOGLE_API_KEY`。

### 25.3 git 備份

```bash
cd C:\Projects\TradingAgents
git status                                    # 確認 clean
git tag pre-tw-edition-backup
git log --oneline -5                          # 記下原版最後 commit
```

### 25.4 P0 退出條件（具體可執行）

跑以下 5 個指令全部回傳 success：

```bash
# 1. Docker 可用
docker info > $null; echo $?       # 應為 True

# 2. uv + Python 3.11 可用
uv python list | Select-String "3.11"

# 3. Node ≥ 18
node --version | %{ if ([version]($_ -replace 'v','') -ge [version]'18.0.0') { 'OK' } else { 'FAIL' } }

# 4. Magnetic 50 GB+ 空間
$free = (Get-PSDrive C).Free / 1GB
if ($free -gt 50) { 'OK' } else { 'FAIL' }

# 5. Git 備份 tag 存在
git tag --list | Select-String "pre-tw-edition-backup"
```

✅ 5 個都 OK → 進 P1
❌ 任一失敗 → 修正後重跑

---

## 二十六、Phase 1-9 Prompts

每個 Prompt 自包含。**fresh Claude 收到 Prompt 後，可主動讀取 `C:\Projects\TradingAgents\PLAN.md` 對應章節獲取完整細節。**

---

### ▌Phase 1 — 基礎設施 + 原版遷移 + 工程規範

```
=== TradingAgents-TW Phase 1（v6.0） ===
工作目錄：C:\Projects\TradingAgents
計劃文件：C:\Projects\TradingAgents\PLAN.md（必讀第 4, 13, 14, 17, 22 章）

【目標】
1. 把原版 v0.2.4 整體遷至 legacy/（必做，依第四章）
2. 建立新後端骨架 + Docker 基礎 + 工程規範文件 + CI/CD 雛形

【任務】

A. 原版遷移（依第四章 4.3 指令）：
   - 確認 git tag pre-tw-edition-backup 存在
   - mkdir legacy + git mv 所有原版檔案
   - 寫 legacy/README.md
   - commit "chore: 遷至 legacy/"
   - 建 .vscode/settings.json 排除 legacy/

B. 新目錄骨架（依第二十二章）：
   backend/app/{api/v1, core, repos, services, domain, models, schemas,
                agents/{analysts,researchers,managers,risk_mgmt,trader,tools/{tw,us}},
                data_sources/{tw,us}, llm, workers, notifications, exports}/
   data-pipeline/{schemas, scripts}/
   docker/{timescaledb, nginx/certs, backups, playwright}/
   scripts/, docs/, .github/workflows/, frontend/（空）

C. docker-compose.yml（dev）：
   依第十二章 + 第十三章 13.2：
   - timescaledb / qdrant / redis 全 healthcheck
   - backend 用 wait-for-services.sh
   - depends_on condition: service_healthy
   - stop_grace_period: 60s

D. docker/timescaledb/init.sql：建 3 個 user（依第十九章）

E. backend/scripts/wait-for-services.sh（依 13.2）

F. .env.example（完整含註解，依先前 v5 + 加 ALPHA_VANTAGE_API_KEY、FINNHUB_API_KEY）：
   SECRET_KEY 範例值用 base64 32 bytes，附產生指令：
   `python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`

G. backend/pyproject.toml（uv，pin 版本依第六章 6.1）：
   依賴清單依先前版本 + 加 alembic-utils、bigt（如有需要）

H. backend/app/core/config.py：依先前版本

I. backend/app/core/logging_config.py：structlog + JSON + 遮蔽

J. backend/app/core/error_handlers.py + response_envelope.py：依第十七章 17.2-17.3

K. backend/app/core/request_id.py：trace_id middleware

L. backend/app/core/http_client.py + circuit_breaker.py：依第十四章

M. backend/app/main.py（最小版）：FastAPI + lifespan + /health/live + /health/ready + /health/seeded（暫回 false）

N. Makefile：依先前版本

O. .github/workflows/ci.yml + security.yml：依第二十三章

P. .pre-commit-config.yaml

Q. docs/engineering-standards.md：完整輸出第十七章
   docs/setup.md：前置 + 一鍵啟動 + 連線資訊

R. README.md：寫新版總覽（原版的已備份在 legacy/）

S. LICENSE：原版已有 Apache 2.0，保留

【完成驗收（具體指令）】

完成 Phase 1 = 以下 8 個指令全部 exit code 0：

```bash
# 1. legacy 遷移完成
test -d legacy/tradingagents && echo OK
test ! -e tradingagents && echo OK    # 根目錄不該有

# 2. Docker 啟動
make up
docker compose ps | grep -c "healthy" | grep -E "^3$"   # 應 3 個 healthy

# 3. backend uv sync 成功
cd backend && uv sync && cd ..

# 4. backend 啟動成功
cd backend && uv run uvicorn app.main:app --port 8000 &
sleep 3
curl -f http://localhost:8000/health/live
curl -f http://localhost:8000/health/ready

# 5. 結構化 log + trace_id
curl -i http://localhost:8000/health/live | grep -i "X-Trace-Id"

# 6. detect-secrets 通過
make secrets-scan

# 7. pre-commit 通過
pre-commit run --all-files

# 8. CI 綠燈（push 後檢查）
git push && sleep 30 && gh run list --limit 1 | grep -i "completed.*success"
```

【Smoke Test】
✓ docker logs 看到 structured JSON
✓ 故意拋錯（curl /nonexistent）→ envelope 格式 + trace_id

【已知陷阱】
✗ git mv 時若有未 commit 變更 → 先 commit 或 stash
✗ Windows Docker volume 權限 → 用 named volume
✗ wait-for-it.sh 在 alpine 用 sh（非 bash）
✗ SECRET_KEY 32 字元 ≠ 32 bytes → 必用 base64 44 字元
✗ pre-commit 自動修檔 → git add 後再 commit
✗ uv 找不到 Python 3.11 → uv python install 3.11
✗ 根目錄遺漏的 main.py、test.py → ls 確認後 git mv
```

---

### ▌Phase 2 — 台股 + 美股資料管線 + Bootstrap

```
=== TradingAgents-TW Phase 2（v6.0） ===
工作目錄：C:\Projects\TradingAgents
前置：Phase 1 完成
計劃文件：必讀第 13, 14, 15, 20 章

【目標】完整 schema、TW/US 資料源 Adapter（含 Plugin + Fallback + Circuit Breaker）、
Celery + DLQ + Beat、Qdrant 7 collections、Bootstrap scripts。

【任務】依先前 v5 第十八章 Phase 2 任務 + 補：
- 加 user_watchlist 表（依第二十章）
- analysis_reports 加 version 欄位
- celery_dead_letters 表（依第十四章 14.10）
- users 加 onboarding 欄位（依第十三章 13.4）
- index 補強（依第二十章 20.2）

【完成驗收（具體指令）】

```bash
# 1. schema 建立
make init-db
docker compose exec timescaledb psql -U postgres tradingagents_tw -c "\dt" | wc -l   # 至少 15 個表

# 2. Qdrant collections
curl -s http://localhost:6333/collections | jq -r '.result.collections | length'    # 應 7

# 3. stock_list seed
make seed-stocks
docker compose exec timescaledb psql -U ta_agent_ro tradingagents_tw -c "SELECT COUNT(*) FROM stock_list"   # ≥ 1500

# 4. 至少 1 支股票有資料
make backfill -- --region TW --symbol 2330 --years 1
docker compose exec timescaledb psql -U ta_agent_ro tradingagents_tw -c "SELECT COUNT(*) FROM stock_prices WHERE symbol='2330'"   # ≥ 200（一年交易日）

# 5. /health/seeded 為 true
curl -s http://localhost:8000/health/seeded | jq '.seeded'   # true

# 6. ta_service_rw 不能改 audit_logs
docker compose exec timescaledb psql -U ta_service_rw tradingagents_tw -c "INSERT INTO audit_logs (event) VALUES ('test')"   # 應失敗

# 7. unit tests 綠
cd backend && uv run pytest tests/unit/test_data_sources.py -v   # 全綠

# 8. Celery worker 啟動
make up-workers
docker compose ps celery_worker | grep -i "running"
```

【Smoke Test】
✓ qdrant dashboard 看 7 collections
✓ 用 ta_agent_ro 查 stock_prices 有資料

【已知陷阱】
✗ TimescaleDB extension 未啟 → init.sql 有 CREATE EXTENSION
✗ FinMind 免費 quota 跑 backfill 會爆 → 用 TWSE/TPEX
✗ yfinance 大寫敏感
✗ alembic + hypertable → op.execute()
✗ embedding 維度錯誤 → collection 重建
✗ 漏建 user_watchlist → 前端 P6 自選股會炸
```

---

### ▌Phase 3 — 後端基礎（auth、middleware、core）

```
=== TradingAgents-TW Phase 3（v6.0） ===
工作目錄：C:\Projects\TradingAgents\backend
前置：Phase 1, 2 完成
計劃文件：必讀第 14, 16, 17, 19 章

【目標】FastAPI 完整框架：所有 middleware、認證授權（含 CSRF、WS Ticket、密碼重置）、
audit hash chain、Liveness/Readiness/Seeded、僅 auth router 完整。

【任務】依 v5 第十八章 Phase 3 + 加：
- 連線池參數依第十四章 14.1（pool_size, statement_timeout, lock_timeout）
- WS Ticket 依第十九章 19.1（subprotocol + 一次性 60s）
- DLQ middleware（連 Phase 2 的 dlq table）

【完成驗收（具體指令）】

```bash
# 1. 啟動成功
make backend-dev
sleep 3
curl -f http://localhost:8000/docs

# 2. Auth integration tests 全綠
cd backend && uv run pytest tests/integration/test_auth.py -v

# 3. 登入成功
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"YourAdminPass!"}' \
  | jq -r '.data.access_token')
test -n "$TOKEN" && echo OK

# 4. /me 可呼叫
curl -f -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me

# 5. lockout 測試（連 6 次錯密碼第 6 次 423）
for i in 1 2 3 4 5; do
  curl -s -X POST http://localhost:8000/api/v1/auth/login \
    -d '{"email":"admin@example.com","password":"wrong"}'
done
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/login \
  -d '{"email":"admin@example.com","password":"wrong"}'   # 應為 423

# 6. WS Ticket 一次性
TICKET=$(curl -s -X POST http://localhost:8000/api/v1/auth/ws-ticket -H "Authorization: Bearer $TOKEN" | jq -r '.data.ticket')
# 第一次用應該成功，第二次 401（在 P4 WS endpoint 測）

# 7. Audit chain 完整
python scripts/verify_audit_chain.py   # 應通過

# 8. ta_service_rw 不能改 audit_logs
docker compose exec timescaledb psql -U ta_service_rw tradingagents_tw -c "UPDATE audit_logs SET event='hack' WHERE id=1"   # 失敗
```

【Smoke Test】
✓ 完整流程：登入 → 取 me → 登出 → 過期 token 重試 → refresh 換新 access

【已知陷阱】
✗ middleware 順序錯誤
✗ RequestID 必在 Audit 前
✗ SECRET_KEY < 32 bytes
✗ CORS allow_credentials=true 才能傳 cookie
✗ SameSite=Strict 在 dev 跨 port 擋（用 Lax for dev）
✗ testcontainers 啟不起 → Docker daemon + port 不衝突
```

---

### ▌Phase 4 — 業務 API（15 routers）

```
=== TradingAgents-TW Phase 4（v6.0） ===
工作目錄：C:\Projects\TradingAgents\backend
前置：Phase 1-3 完成
計劃文件：必讀第 15, 17, 18 章

【目標】完整業務 API。LangGraph 整合留 P5（分析 endpoint stub）。
跨市場 + Transaction + Idempotency + Cursor Pagination。

【任務】依 v5 第十八章 Phase 4 + 加：
- 訂單核准 SELECT FOR UPDATE 並發測試（依第十五章 15.1）
- Cursor pagination 統一規範（依第十七章 17.4）
- WS Ticket 整合（依第十九章 19.1.5）
- Decimal JSON 字串序列化（依第十五章 15.6）
- /metrics endpoint（依第十六章 16.2）
- DLQ 管理 API（GET/POST 對 celery_dead_letters）

【完成驗收（具體指令）】

```bash
# 1. /docs 顯示所有 routers
curl -s http://localhost:8000/openapi.json | jq -r '.paths | keys | length'   # 至少 50 個 endpoints

# 2. POST /analysis 接受 TW 與 US
TOKEN=...
curl -s -X POST http://localhost:8000/api/v1/analysis -H "Authorization: Bearer $TOKEN" \
  -d '{"symbol":"2330","analyst_types":["market"],"llm_model":"gemini-2.0-flash"}' | jq '.data.status'   # "queued"
curl -s -X POST http://localhost:8000/api/v1/analysis -H "Authorization: Bearer $TOKEN" \
  -d '{"symbol":"AAPL","analyst_types":["market"],"llm_model":"gemini-2.0-flash"}' | jq '.data.status'   # "queued"

# 3. Idempotency
KEY=$(uuidgen)
curl -s -X POST http://localhost:8000/api/v1/analysis -H "Idempotency-Key: $KEY" -d ...
curl -s -X POST http://localhost:8000/api/v1/analysis -H "Idempotency-Key: $KEY" -d ...
# 第二次應回相同 analysis_id

# 4. PDF 匯出（中文）
curl -s -o /tmp/report.pdf "http://localhost:8000/api/v1/reports/$REPORT_ID/export?format=pdf"
file /tmp/report.pdf | grep "PDF document"

# 5. 並發核准測試
ORDER_ID=...
curl -X POST .../orders/$ORDER_ID/approve &
curl -X POST .../orders/$ORDER_ID/approve &
wait
# 一個 200，一個 409 ConflictError

# 6. WS 連線（用 ticket）
TICKET=$(curl -s -X POST .../auth/ws-ticket | jq -r .data.ticket)
wscat -c "ws://localhost:8000/api/v1/ws/analysis/$ANALYSIS_ID" -s "tradingagents.v1,ticket.$TICKET"   # 應連通

# 7. Pagination cursor 正確
curl -s ".../api/v1/analysis?limit=2" | jq '.pagination.next_cursor'   # 非 null

# 8. Integration tests 全綠
cd backend && uv run pytest tests/integration/ -v
```

【Smoke Test】
✓ Swagger 試打每個 endpoint
✓ 故意送錯 symbol → 422 中文 message + trace_id
✓ /metrics 回 Prometheus format

【已知陷阱】
✗ PDF 中文亂碼 → Dockerfile 加 fonts-noto-cjk + Playwright chromium
✗ Symbol regex 漏 ETF → 用第十章 10.2
✗ WS subprotocol 寫法（client array 第 2 個值）
✗ Cursor encode 含 UUID → str(uuid)
✗ NUMERIC json 序列化 → Decimal 加 json_encoders
✗ N+1 統計查詢 → join + group by
```

---

### ▌Phase 5 — LangGraph Agent 系統（跨市場）

```
=== TradingAgents-TW Phase 5（v6.0） ===
工作目錄：C:\Projects\TradingAgents\backend
原版參考：C:\Projects\TradingAgents\legacy\tradingagents\
前置：Phase 1-4 完成
計劃文件：必讀第 14.9, 18.2, 20.4 章

【目標】完整 LangGraph + 4 種 Analyst（Plugin）+ TW/US Tools +
Provider Fallback Chain + WebSocket 串流 + 手動核准 + 跨市場。

【任務】依 v5 第十八章 Phase 5 + 加：
- Analyst Plugin 含 supported_regions（依第十八章 18.2）
- LLM 啟動 readiness check（每 provider 試 ping）
- 從 legacy/tradingagents/agents/ **參考**（不 import）原版 prompt 結構
- State trim（依第十四章 14.9）
- LLM monthly_quota 整合（拒絕新分析）

【完成驗收（具體指令）】

```bash
# 1. workers 啟動
make up-workers
docker compose ps | grep celery | grep -i running

# 2. 真實分析 2330
TOKEN=...
ANALYSIS_ID=$(curl -s -X POST .../analysis -H "Authorization: Bearer $TOKEN" \
  -d '{"symbol":"2330","analyst_types":["market","fundamental","news","sentiment"],"llm_model":"gemini-2.0-flash","debate_rounds":1}' | jq -r '.data.analysis_id')

# 等 1-3 分鐘
sleep 180
curl -s ".../analysis/$ANALYSIS_ID" | jq '.data.status'   # "completed"

# 3. WS 收到事件流
TICKET=$(curl -s -X POST .../auth/ws-ticket | jq -r .data.ticket)
wscat -c "ws://.../ws/analysis/$ANALYSIS_ID" -s "tradingagents.v1,ticket.$TICKET" -x 30   # 至少 5 個 events

# 4. 美股 AAPL（無 sentiment）
curl -s -X POST .../analysis -d '{"symbol":"AAPL","analyst_types":["market","fundamental","news"]}'
# 等待後檢查 debate_history 不含 sentiment_analyst

# 5. token cost < $0.05
psql ... -c "SELECT cost_usd FROM llm_usage WHERE analysis_id='$ANALYSIS_ID'"   # < 0.05

# 6. monthly_quota 累計
psql ... -c "SELECT cost_usd FROM llm_monthly_quota WHERE user_id='$USER_ID'"

# 7. pending_orders 視 signal 建立
psql ... -c "SELECT * FROM pending_orders WHERE analysis_id='$ANALYSIS_ID'"

# 8. Integration tests
cd backend && uv run pytest tests/integration/test_analysis_pipeline.py -v
```

【Smoke Test】
✓ Celery worker log 含 trace_id 串接
✓ Mock LLM 故意拋 OPEN circuit → 切到 fallback provider

【已知陷阱】
✗ LangGraph 卡住 → 檢查 state 大小、recursion_limit
✗ Tools permission denied → Agent engine 必用 ro 帳號
✗ WS 收不到事件 → channel name 一致 (analysis:{id})
✗ State 過大 → 啟用 trim_state_messages
✗ LLM token 超限 → 縮短 prompt + 降 max_output_tokens
✗ Embedding model 切換 → 同 collection 不可混用
```

---

### ▌Phase 6 — 前端基礎 + 8 核心頁

```
=== TradingAgents-TW Phase 6（v6.0） ===
工作目錄：C:\Projects\TradingAgents\frontend
後端：http://localhost:8000/api/v1
前置：Phase 1-5 完成
計劃文件：必讀第 21 章

【目標】Next.js 14.2 基礎 + 8 核心頁完整後端整合 + Onboarding 流程。

【技術棧】
Next.js 14.2 / TS / shadcn/ui / Tailwind / lightweight-charts /
@xyflow/react / recharts / Zustand / @tanstack/react-query /
next-themes / react-markdown + rehype-highlight + remark-gfm /
date-fns / cmdk / axios / react-window / bignumber.js / dayjs+timezone

【任務】依 v5 第十八章 Phase 6（含 Onboarding 流程）

【完成驗收（具體指令）】

```bash
# 1. 啟動成功
cd frontend && npm run dev &
sleep 5
curl -f http://localhost:3000

# 2. 登入頁可訪問
curl -f http://localhost:3000/login

# 3. 18 頁路由都有
for path in dashboard screener/watchlist analysis/new analysis/history portfolio/orders admin/users admin/audit; do
  curl -s -o /dev/null -w "%{http_code} $path\n" http://localhost:3000/$path
done   # 全部 200 或 307（未登入 redirect）

# 4. WebSocket 連線
# 手動：在瀏覽器 DevTools 看 wss 連線用 subprotocol，無 token in URL

# 5. 完整 E2E 流程（手動）：
#    - admin 登入 → onboarding → 改密碼
#    - 加 2330 自選股
#    - 新增 2330 分析 → AgentFlowGraph 動態 → 完成
#    - 核准訂單（二次確認）
#    - viewer 登入 → 看不到 admin 頁

# 6. 響應式
# 1280 / 1024 / 768 都不破版（手動）

# 7. 無 console error
# DevTools console 0 errors

# 8. lighthouse score
npx lighthouse http://localhost:3000/dashboard --only-categories=performance --quiet | grep "performance"   # > 70
```

【Smoke Test】
✓ 跨市場：加 2330 + AAPL 都能搜尋（旗幟正確）
✓ 數字千分位、百分比、貨幣、日期格式正確

【已知陷阱】
✗ WS 連線立即斷 → ticket 在 subprotocol 第 2 個值
✗ CORS 錯誤 → 後端 CORS_ORIGINS 加 http://localhost:3000
✗ Hydration 警告 → date 用 useEffect 初始化
✗ shadcn 樣式錯亂 → tailwind config content paths
✗ K 線高度 0 → 父容器明確高度
✗ JS 精度 → BigNumber.js
✗ 時區 → dayjs UTC ISO 接，轉用戶時區
```

---

### ▌Phase 7 — 前端 10 進階頁

```
=== TradingAgents-TW Phase 7（v6.0） ===
工作目錄：C:\Projects\TradingAgents\frontend
前置：Phase 6 完成

【目標】完成 10 進階頁（依第二十一章標註）。

【任務】依 v5 第十八章 Phase 7

【完成驗收（具體指令）】

```bash
# 1. 18 頁全部能開
for path in dashboard market/overview market/institutional market/calendar \
            screener/watchlist screener/filter screener/compare \
            analysis/new analysis/history \
            statistics/accuracy statistics/models statistics/backtest \
            portfolio/positions portfolio/orders portfolio/history \
            news/sentiment news/announcements notifications \
            admin/users admin/audit admin/system admin/pipeline; do
  status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/$path)
  echo "$status $path"
done   # 全部 200 / 307

# 2. /admin/system 顯示 metrics
# 手動：頁面顯示分析次數、token cost、queue length 等圖表

# 3. /admin/pipeline DLQ 列表
# 手動：能看到 DLQ 列表（即使空）

# 4. 跨市場切換無誤
# 手動：選股篩選器切 TW/US 都能用

# 5. 響應式 1280 / 1024 / 768 不破版

# 6. Console 無 error

# 7. Bundle size 合理
cd frontend && npm run build && du -sh .next/static/   # 合理範圍

# 8. lighthouse
npx lighthouse http://localhost:3000/market/overview --only-categories=performance --quiet
```

【已知陷阱】
✗ recharts SSR → dynamic import + ssr: false
✗ lightweight-charts 高度 0 → 父容器固定
✗ 跨市場切換閃爍 → useTransition
✗ 大表格效能 → react-window
✗ 通知設定密碼欄位顯示明文 → 後端僅回 isSet
```

---

### ▌Phase 8 — 安全強化 + 通知整合 + 整合測試

```
=== TradingAgents-TW Phase 8（v6.0） ===
工作目錄：C:\Projects\TradingAgents
前置：Phase 1-7 完成

【目標】OWASP 全面稽核、E2E 測試、LINE/Telegram 通知整合、
SLO 監控、備份/還原驗證、最後把關。

【任務】依 v5 第十八章 Phase 8

【完成驗收（具體指令）】

```bash
# 1. bandit 高風險 0
cd backend && uv run bandit -r app/ -ll | grep "Severity: High" | wc -l   # = 0

# 2. detect-secrets 無新發現
cd .. && detect-secrets scan --baseline .secrets.baseline

# 3. Trivy HIGH+CRITICAL 0
trivy image tradingagents-backend:latest --severity HIGH,CRITICAL --exit-code 1

# 4. OWASP tests
cd backend && uv run pytest tests/security/ -v

# 5. E2E 全綠
cd frontend && npx playwright test

# 6. 通知測試（已設 LINE token）
curl -X POST .../notifications/test -H "Authorization: Bearer $TOKEN"
# 手機收到中文 + emoji 測試訊息

# 7. Audit chain 校驗
python scripts/verify_audit_chain.py   # 應通過

# 8. 備份還原驗證
bash scripts/backup.sh
bash scripts/verify_backup.sh   # 還原到隔離 DB → verify_data 通過
```

【已知陷阱】
✗ LINE Notify 401 → token 過期
✗ Trivy 高風險 → 升級基底 image
✗ E2E flaky → 加 waitFor + data-testid
✗ 備份還原 hypertable 報錯 → 還原順序（extension 先建）
```

---

### ▌Phase 9 — 部署 + 災難復原 + Obsidian

```
=== TradingAgents-TW Phase 9（v6.0） ===
工作目錄：C:\Projects\TradingAgents
前置：Phase 1-8 完成

【目標】生產部署、災難復原 SOP、Obsidian 第二大腦。

【任務】依 v5 第十八章 Phase 9

【完成驗收（具體指令）】

```bash
# 1. prod 模擬啟動
docker compose -f docker-compose.prod.yml up -d
sleep 30
docker compose -f docker-compose.prod.yml ps | grep -c "healthy"   # 全 healthy

# 2. nginx 對外
curl -kf https://localhost/health/live   # 200

# 3. backend 不對外（從 host 不能直連）
curl --connect-timeout 2 http://localhost:8000/health/live   # 失敗（被防火牆/網路隔離）

# 4. PDF 匯出（中文）
curl -k -H "Authorization: Bearer $TOKEN" -o /tmp/r.pdf https://localhost/api/v1/reports/$ID/export?format=pdf
file /tmp/r.pdf | grep "PDF document"
pdftotext /tmp/r.pdf - | head | grep -P "[一-鿿]"   # 含中文

# 5. 災難演練（情境 A：DB 損毀）
make down
docker volume rm tradingagents_timescaledb_data
make up
make init-db
bash scripts/restore.sh /docker/backups/latest.tar.gz.enc
python data-pipeline/scripts/verify_data.py   # 通過

# 6. Obsidian 安裝
where obsidian || powershell -Command "Test-Path '$env:LOCALAPPDATA\Obsidian\Obsidian.exe'"   # 應存在

# 7. 完整端到端
# 手動：admin 登入 → 跑 2330 分析 → LINE 通知 → 核准訂單 → 匯出 PDF

# 8. SLO 報表正常
python scripts/slo_report.py | grep "API availability"
```

【完成輸出】
docs/connection-guide.md 連線資訊報告（標準模板）

【已知陷阱】
✗ Let's Encrypt 本地用 → self-signed 替代
✗ Playwright 缺 deps → 完整裝 chromium-deps
✗ Nginx SSE buffering 沒關 → /stream 卡住
✗ WS proxy timeout 太短 → 設 86400s
✗ Volume 權限 → named volume + uid 1000
```

---

## 二十七、Phase 失敗回復程序

### 27.1 通用流程

1. **診斷：** 看 Phase Prompt【已知陷阱】
2. **隔離：** 保留 log
3. **回退：** `git checkout <commit>` / `alembic downgrade -1` / `make down && make up`
4. **修正：** 乾淨環境重跑該 Phase Prompt
5. **驗收：** 跑【完成驗收】具體指令

### 27.2 各 Phase 特殊狀況

依 v5 + 補：
- P1 失敗：`git mv` 漏檔 → `ls` 確認 → 補 `git mv` → commit
- P3 失敗：CSP 太嚴 → 從 dev 寬鬆 → 逐步加緊
- P4 失敗：建議分批（先 a-h router，再 i-o）
- P5 失敗：State 過大 → 啟用 trim
- P6 失敗：分批（先共用元件，再頁面）
- P7 失敗：5 + 5 分批

### 27.3 緊急回到原版

如果整個改造嚴重失敗，要回到原版：

```bash
git stash                                  # 暫存當前未 commit 變更
git checkout pre-tw-edition-backup        # 回到 P0 的 tag
# 或新建分支保留改造嘗試
git checkout -b failed-tw-edition-attempt
git checkout pre-tw-edition-backup
```

---

# Part D — 運維

---

## 二十八、容量規劃

> v6 全新章節。

### 28.1 預期負載（v1.0 自用）

| 維度 | 目標 |
|------|------|
| 同時在線用戶 | 1-5 |
| 每天分析次數 | 5-20 |
| 每天 API 請求數 | < 10,000 |
| 同時 WebSocket 連線 | < 10 |
| 每月儲存增長（行情） | ~500 MB |
| 每月儲存增長（Qdrant） | ~200 MB |
| 每月儲存增長（audit log） | ~100 MB |

### 28.2 瓶頸與處理

| 瓶頸 | 觸發點 | 處理 |
|------|-------|------|
| LLM API 配額 | 50 次分析/天 | 增加月預算 / 切換 provider |
| FinMind 配額 | backfill 大量股票 | 升級付費 / 減少 backfill 範圍 |
| TimescaleDB 磁碟 | > 80% | 加大 retention（v1.0 1 年）/ 加磁碟 |
| Qdrant 記憶體 | 向量 > 100 萬 | 加機器 RAM / 啟用 quantization |
| Celery worker 飽和 | concurrent > 4 | 加 worker count |
| Nginx 連線 | 同時 > 1000 | 升級到多 worker |

### 28.3 擴容路線

| 階段 | 配置 | 月費 |
|------|------|------|
| 現在 v1.0 自用 | 單機 16GB | ~$154 |
| 增長 1（5+ 用戶） | 加 RAM 至 32GB | ~$200 |
| 增長 2（多用戶） | 拆 DB + Backend | v2.0 重新規劃 |
| 增長 3（公開服務） | K8s + 多 region | v3.0 |

---

## 二十九、資源、預算與成本

### 29.1 硬體（單機）

| 配置 | 最低 | 推薦 |
|------|-----|------|
| CPU | 4 cores | 8 cores |
| RAM | 16 GB | 32 GB |
| 磁碟 | 100 GB SSD | 500 GB SSD |
| 網路 | 100 Mbps | 1 Gbps |

### 29.2 月費

| 項目 | 月費 |
|------|------|
| FinMind 付費 | ~$99 |
| Alpha Vantage 付費 | ~$50 |
| Gemini Flash | ~$5 |
| **小計** | **~$154/月** |

### 29.3 LLM 單次成本

| 模型 | 成本 |
|------|------|
| Gemini 2.0 Flash | ~$0.012 |
| Gemini 2.5 Pro | ~$0.15 |
| GPT-4o-mini | ~$0.018 |
| Claude Haiku 3.5 | ~$0.10 |

### 29.4 開發 Token 預算

| Phase | Token | Phase | Token |
|-------|-------|-------|-------|
| P0 | 0（手動） | P5 | ~155k |
| P1 | ~60k | P6 | ~160k |
| P2 | ~95k | P7 | ~145k |
| P3 | ~115k | P8 | ~85k |
| P4 | ~155k | P9 | ~65k |
| | | **合計** | **~1.04M** |

---

## 三十、部署架構

### 30.1 開發

```bash
make up               # DB 三服務
make init-db          # schema + admin（一次性）
make seed-stocks      # 股票清單（一次性）
make backend-dev
make frontend-dev
make up-workers
```

### 30.2 自用伺服器

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml --profile worker up -d
```

### 30.3 備份

| 資料 | 頻率 | 保留 |
|------|------|------|
| TimescaleDB | 每日 02:00 | 30 天 |
| Qdrant | 每日 02:30 | 30 天 |
| .env / DATA_ENCRYPTION_KEY | 變動時手動 | 永久（加密隨身碟） |
| 備份還原驗證 | 每月 | - |

### 30.4 監控（v1.0）

- /metrics endpoint
- 前端 /admin/system
- 每日 verify_data + verify_audit + slo_report
- 異常 → LINE
- v2.0 接 Prometheus + Grafana

---

## 三十一、災難復原 SOP

### 31.1 目標
RTO 1 小時 / RPO 24 小時

### 31.2 情境

| 情境 | 步驟 |
|------|------|
| **A. TimescaleDB 損毀** | make down → 移除 volume → make up → init-db → restore.sh → verify_data |
| **B. Qdrant 索引損毀** | recreate collections → restore snapshot 或重跑 news_ingest（過去 30 天） |
| **C. Audit 偵測竄改** | 立即停服 → 從可信備份還原 audit_logs → 重新校驗 → 調查原因 |
| **D. 整機損毀** | 新機 Docker → clone repo 同 commit → 還原 .env + DATA_ENCRYPTION_KEY → backups → make up + restore |
| **E. LLM 持續失敗** | 檢查 fallback chain log → 改 .env 預設 provider → 重啟 |
| **F. 資料源全失敗** | Circuit breaker 已通知 → 用快取運作（前端標延遲）→ 恢復後 backfill |

### 31.3 演練

每季演練情境 A，記錄實際 RTO 調整 SOP。

---

## 三十二、後續延展路線圖

### v1.1（1-2 個月）
- 法說會錄音轉文字（Whisper）
- 美股 13F、insider trading
- 回測引擎真實後端
- 多股比較後端
- 財報日曆完整資料源
- Email 通知（含 password reset）
- 移動裝置響應式
- AI 對話介面（chat with reports）
- 自動匯出報告到 Obsidian

### v1.2（3-6 個月）
- 英文介面（i18n 完整）
- 2FA TOTP
- IP 白名單
- 自定義警報
- LINE Bot 雙向
- 港股加入

### v2.0（6-12 個月）
- 多用戶多組織
- 即時盤中分鐘 K
- Prometheus + Grafana + OpenTelemetry
- Kubernetes 部署
- 真實券商 API（仍手動核准）
- 行動 App
- A 股、日股
- AI Trading Bot 自動策略

---

## 結語：v6.0 的設計目標達成

v6.0 是**收斂版本**。經過 6 個版本疊代，本版焦點不在新增功能，而在：
- ✅ **解決 v1-v5 都漏的原版衝突**（第四章遷移指南）
- ✅ **記錄關鍵架構決策的 WHY**（第五章 ADR）
- ✅ **誠實列出限制**（第七章 Honest Tradeoffs）
- ✅ **集中反模式**（第八章 Anti-patterns）
- ✅ **具體 Phase 退出條件**（每個 Phase 的具體指令）
- ✅ **時程預估**（calendar days）
- ✅ **容量規劃**（第二十八章）
- ✅ **Phase 0 Pre-flight**（手動環境驗證）

**繼續迭代的邊際效益已遞減。建議：跑 Phase 0 → Phase 1 開始實作。**

實際執行中發現問題 → 在 docs/runbook.md 累積，作為 v6.1 修訂依據。

*計劃文件 v6.0 完成。*
*下一步：跑 Phase 0 環境驗證 → 開新對話貼 Phase 1 Prompt 開始執行。*
*嚴格依序 P1 → P9，每 Phase 通過具體驗收指令才進下一個。*
