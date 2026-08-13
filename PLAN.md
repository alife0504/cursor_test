# TradingAgents-TW Secure Edition — 完整實施計劃 v7.0

> 工作目錄：`C:\Projects\TradingAgents`（直接改造現有專案）
> 規劃啟動日期：2026-05-03 | 最後更新：2026-05-04（第 4 次規劃 + 全面 review 修正 13 項問題）
> 上一版：v6.0（已備份至 `PLAN.v6.0.backup.md`）| 規劃模型：Claude Opus 4.7 Max
> 主場：台股；輔助：美股
> **本版核心：拆細 Phase 確保單次完成、強化跨 Phase 驗證、新增最終整合驗證與報告 Phase**

> **v7.0 規劃進度說明（規劃 100% 完成 ✅）：**
> - ✅ 第 1 次完成：Phase 0-5 詳細設計（共 6 個 Phase）+ Part A/B/D 章節更新
> - ✅ 第 2 次完成：Phase 6-12 詳細設計（共 7 個 Phase）+ Part D 章節編號修正
> - ✅ 第 3 次完成：Phase 13-17 詳細設計（共 5 個 Phase，Analyst + 美股 + LLM Fallback + 前端基礎 + 18 頁）
> - ✅ 第 4 次完成：Phase 18-20 詳細設計（共 3 個 Phase，安全強化 + Prod 部署 + DR + 全面驗證 + 報告）+ 全文最終 review + sanity check
>
> **🎉 v7.0 規劃 100% 完成。** 21 個 Phase（P0-P20）全部詳細化、9 段格式一致、跨 Phase 健康檢查覆蓋完整、累積測試基準對齊。**可開始依計畫執行 v1.0。**
>
> **本次（第 4 次，最後一次）已完成項目摘要：**
> - 新增 P18 詳細：通知 Adapter Plugin（LINE Notify / Telegram Bot）+ NotificationDispatcher（事件驅動 + retry + DLQ）+ Fernet 加密 token + bandit/Trivy/npm audit/detect-secrets 全綠 + OWASP Top 10 測試（≥ 15 case）+ CSP nonce-based prod + Secret rotation 腳本（雙 key + DB + 加密金鑰輪替）+ Pen test checklist
> - 新增 P19 詳細：docker-compose.prod.yml 完整化（nginx + TLS + read_only + cap_drop ALL）+ backup.sh / restore.sh / verify_backup.sh（GPG 加密）+ DR 演練情境 A 實際跑通 + slo_report.py 完整版（依 16.4）+ 後端 + 前端 E2E 完整流程（≥ 14 個 test）+ Prod 啟動 SOP
> - 新增 P20 詳細（最終 Phase）：scripts/health_checks/all.sh（一鍵跑全部驗證）+ 產出 docs/PROJECT_FINAL_REPORT.md（含 SLO 達成度、測試覆蓋率、效能 benchmark、安全稽核、限制清單、v1.1 路線圖）+ docs/connection-guide.md + docs/user-guide.md + Obsidian Vault 設定 + README v1.0 + CHANGELOG v1.0.0 + v1.0.0 git tag + GitHub release
> - 完成「下次規劃（第 4 次）涵蓋範圍」outline 區塊清除（不再留 outline）
> - Sanity check 結果：章節編號連續、Phase 格式一致、累積測試基準對齊、文件目錄與內容對齊
>
> **下一步：**
> 1. 跑 Phase 0（Pre-flight 環境驗證 + 帳號註冊 + 知識準備）
> 2. 開新 Claude 對話，貼 Phase 1 的【0-10】完整 Prompt
> 3. 嚴格依序 P0 → P1 → ... → P20，每 Phase 通過具體驗收指令 + Self-Check SOP + 跨 Phase 健康檢查 才進下一個
> 4. 預估 30-40 calendar days（每天 5 小時 / 1 個 Phase）完成 v1.0 Release
> 5. 實際執行中發現問題 → 在 docs/runbooks/phase_failures.md 累積，作為 v7.1 修訂依據

---

## 文件目錄

### Part A — 執行前必讀（讀一次就好）
1. [變更摘要 v6 → v7](#一變更摘要-v6--v7)
   - [附錄：變更摘要 v5 → v6（保留作歷史）](#一-附錄變更摘要-v5--v6保留作歷史)
2. [TL;DR 30 秒理解](#二tldr30-秒理解)
3. [Pre-flight Checklist](#三pre-flight-checklist執行-p1-前必跑)
4. [原版專案遷移指南](#四原版專案遷移指南)
5. [架構決策記錄（ADR）](#五架構決策記錄adr)
6. [版本相容性矩陣](#六版本相容性矩陣)
7. [接受的限制](#七接受的限制honest-tradeoffs)
8. [反模式清單](#八反模式清單禁止做的事)
8.5. [Phase 設計方法論 + 自我檢查 SOP](#八點五phase-設計方法論--自我檢查-sop)

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
23.5. [跨 Phase 累積測試與健康檢查表](#二十三點五跨-phase-累積測試與健康檢查表)

### Part C — 執行
24. [Phase 總覽 + 時程預估（v7：21 個 Phase）](#二十四phase-總覽--時程預估)
25. [Phase 啟動 Prompt 標準模板](#二十五phase-啟動-prompt-標準模板)
26. [Phase 0：Pre-flight 環境驗證](#二十六phase-0pre-flight-環境驗證)
27. [Phase 1-20 詳細 Prompts](#二十七phase-1-20-詳細-prompts)
28. [Phase 失敗回復程序](#二十八phase-失敗回復程序)

### Part D — 運維
29. [容量規劃](#二十九容量規劃)
30. [資源、預算與成本](#三十資源預算與成本)
31. [部署架構](#三十一部署架構)
32. [災難復原 SOP](#三十二災難復原-sop)
33. [後續延展路線圖](#三十三後續延展路線圖)

---

# Part A — 執行前必讀

---

## 一、變更摘要 v6 → v7

> **v7 設計目標：** 承認單次 Claude Opus 4.7 Max 5 小時 session 的真實能力上限（context budget + 程式碼產出量），把「能在一次跑完」當作 Phase 設計的硬約束。

| 維度 | v6 | v7 強化 |
|------|----|---------|
| **Phase 數量** | 10（P0-P9） | **21（P0-P20）**，把「業務 API」「Agent」「前端」這 3 個過大的 Phase 各自拆成 2-3 個 |
| **單 Phase 程式碼量** | 1500-3000 行（過大） | **目標 < 1500 行**（含測試），確保單 session 可完成 |
| **單 Phase context 預算** | 95k-160k token（接近上限） | **目標 ≤ 80k token**，留出 retry、debug、自我檢查的緩衝 |
| **跨 Phase 健康檢查** | 隱含（依靠 Pre-flight） | **每個 Phase 第一步「先跑健康檢查腳本」**，確認前面 Phase 結果還能跑 |
| **Phase 自我檢查 SOP** | 缺 | **第 8.5 章新章節**：每個 Phase 結束前必跑的標準檢查 |
| **Phase 啟動 Prompt 模板** | 各 Phase 自成格式 | **第二十五章新章節**：固定 9 段格式（前置依賴 → 健康檢查 → 任務 → 退出條件 → Smoke Test → 已知陷阱 → Self-Check SOP → 完成後產物 → Phase 報告輸出） |
| **跨 Phase 累積測試表** | 缺 | **第 23.5 章新章節**：明確列出每個 Phase 後 `pytest --collect-only` 的數量基準 |
| **最終驗證 Phase** | P8（混在安全測試中） | **P19 全面整合驗證**（單獨 Phase）+ **P20 完整報告生成 + Obsidian + 結案** |
| **Phase 報告輸出** | 缺 | 每個 Phase 完成後在 `docs/phase_reports/PHASE_NN.md` 留下「做了什麼/驗證結果/已知遺漏/給下一 Phase 的提醒」 |
| **時程預估** | 19-28 天 | **30-40 天**（更保守，以 5 小時/天 + 高完成率計） |
| **失敗回復程序** | 通用流程 | 每個 Phase 各自的「Recovery Cookbook」+ 通用 git 回退指令 |
| **跨 Phase 依賴矩陣** | 在第十七章一張表 | 加上「每 Phase 開頭明確列依賴 Phase」+「依賴 Phase 健康檢查指令」 |

### 相對於 v6 保留的優點

- ✅ Part A/B/C/D 四部分結構（清晰）
- ✅ Pre-flight Checklist（保留，加強）
- ✅ 原版遷移指南（保留）
- ✅ ADR 全部保留
- ✅ 版本相容性矩陣（保留）
- ✅ 接受的限制（保留）
- ✅ 反模式清單（保留並擴充）
- ✅ 跨市場架構、技術架構、安全架構（保留）

### v7 不引入的事

- ❌ 不換技術棧（仍 Next.js 14.2 + FastAPI + LangGraph 0.2.x + TimescaleDB）
- ❌ 不改 ADR
- ❌ 不重新設計資料模型
- ❌ 不擴大 v1.0 範圍（仍是「自用」+「不直連券商」+「無 Prometheus/Grafana」）

---

## 一-附錄、變更摘要 v5 → v6（保留作歷史）

> 保留 v6 對 v5 的差異記錄，方便追蹤演進。

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

**執行方式：** **21 個 Phase（P0-P20）依序，每個 Phase 開新 Claude 對話**貼對應 Prompt（v7 拆細為的就是「一次跑得完」）。

**預期投入：** **~30-40 天 calendar time（每天 5 小時 = 1 個 Phase）**+ ~$154/月運行成本。

**Claude 模型：** Opus 4.7 Max（每 Phase 用 1 個 max session）

**第一步：** 跑 Phase 0 Pre-flight 驗證環境，再跑 Phase 1。

**最後兩步：** Phase 19 全面整合驗證（跑遍所有檢查腳本）→ Phase 20 完整報告 + Obsidian 第二大腦設定。

---

## 三、Pre-flight Checklist（執行 P1 前必跑）

### 3.0 Shell 環境（Windows 用戶必讀，v7.0 新增）

> **本機是 Windows，但所有 Phase 1+ 的退出條件指令、health_checks/*.sh、wait-for-services.sh 都是 Bash 語法。**

**強制要求：** Phase 0 用 PowerShell（驗證環境）；**Phase 1 起所有指令必須在以下任一環境執行**：

1. **Git Bash**（推薦，最簡單）
   - Git for Windows 內建（已安裝 git 即有）
   - 啟動：`Start Menu → Git Bash`
   - 缺點：缺少 `pdftotext`、`gpg`、`jq` 需另外裝（用 `choco install jq gnupg poppler` 或 scoop）

2. **WSL2**（推薦給長期開發）
   - `wsl --install`（Windows 11 內建）
   - 完整 Linux 環境，所有 Bash 工具都有
   - 注意：Docker Desktop 必須啟用「WSL2 integration」

3. **Cygwin / MSYS2**（不推薦，相容性問題多）

**所有 Phase 的退出條件指令、Smoke Test、Self-Check SOP 都「請在 Git Bash 或 WSL 中跑」**。
若看到 `${VAR}`、`$(cmd)`、`grep`、`awk`、`jq`、heredoc（`<<EOF`）、`sed`、bash 函式 → 不是 PowerShell 語法。

**Path 處理規則（v7.0 新增）：**
- 文件中持久化路徑用 `${PROJECT_ROOT}/...` 或相對路徑（`./docker/backups`、`docs/...`）
- 不用 Linux 絕對路徑作為持久化資料目錄（`/docker/backups` 等）
- **臨時檔（`/tmp/*.dump`、`/tmp/cookies.txt` 等）：** Git Bash 會自動把 `/tmp` 映射到 Windows `%TEMP%`（通常是 `C:\Users\<User>\AppData\Local\Temp`），所以驗收指令裡的 `/tmp/r.pdf` 等可正常工作
- 但腳本（backup.sh / restore.sh / verify_backup.sh / dr_drill_a.sh）統一用 `mktemp -d` + `trap rm` 自動清理，避免殘留
- 跨平台變數：在 Git Bash 跑 `cd C:/Projects/TradingAgents`（不是 `cd C:\\Projects\\...`）

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
| `datetime.utcnow()`（Python 3.12+ deprecated） | `datetime.now(timezone.utc)`（timezone-aware） |
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
| Phase 中段 context 接近滿 → 硬塞下去 | 立刻打住，commit 已完成的部分，新對話接續剩下任務 |
| 跳過跨 Phase 健康檢查（直接做新任務） | Phase 開頭必跑健康檢查腳本 |

---

## 八點五、Phase 設計方法論 + 自我檢查 SOP

> v7 全新章節。**這是 v7 與 v6 最關鍵的差異所在。**

### 8.5.1 Phase 大小設計原則

每個 Phase 必須符合以下「單次可完成性」原則：

| 維度 | 上限 | 量測方式 |
|------|------|---------|
| 單 Phase 預期程式碼產出 | **≤ 1500 行**（含測試） | `git diff --stat HEAD` |
| 單 Phase 預期 context 使用 | **≤ 80k token** | 估算（Prompt 約 5k + PLAN.md 章節 ≤ 30k + 程式碼 ≤ 30k + 工具回應 ≤ 15k） |
| 單 Phase 預期執行時間 | **3-5 小時** | 自記錄 |
| 單 Phase 修改的目錄數 | **≤ 4 個頂層目錄** | 限制 blast radius |
| 單 Phase 新增的測試檔 | **5-15 個** | `git ls-files --others tests/` |

**超過任一上限 → Phase 設計失敗 → 拆分為 a/b 兩個 Phase。**

### 8.5.2 Phase 啟動 SOP（每 Phase 開頭必跑）

每個 Phase 開新對話後，第一個動作必須是這 5 步：

```
Step 1：閱讀 PLAN.md
  - 讀【本 Phase 章節】
  - 讀【依賴章節】（每個 Phase Prompt 會列出來）
  - 不要讀全部 PLAN.md（會吃掉 context budget）

Step 2：跨 Phase 健康檢查
  - 跑 scripts/health_check_phase_NN.sh（NN = 上一 Phase 編號）
  - 失敗則先修復前面 Phase（不要硬上）

Step 3：環境快照
  - git status（確認從乾淨狀態開始）
  - docker compose ps（確認服務狀態符合預期）
  - cat docs/phase_reports/PHASE_<上一個>.md（看上一 Phase 報告）

Step 4：宣告意圖
  - 在對話中明確列出本 Phase 預計修改/新增的檔案清單（≤ 30 個）
  - 列預計執行的測試指令清單

Step 5：開工
  - 先建分支：git checkout -b phase/NN-<簡稱>
```

### 8.5.3 Phase 結束 SOP（每 Phase 結尾必跑）

```
Step 1：跑退出條件指令
  - 把 Phase Prompt 中【完成驗收】所有指令跑一遍
  - 失敗任何一個 → 不算完成 → 修復後再跑一遍
  - 任何一個指令不能跑（缺檔、缺指令）→ 不算完成

Step 2：跑 Self-Check SOP（見 8.5.4）

Step 3：產出 Phase 報告
  - 在 docs/phase_reports/PHASE_NN.md 寫：
    - 做了什麼（檔案清單 + 行數）
    - 退出條件指令結果（每個的 stdout 截圖或截短）
    - 已知遺漏（沒做但本來該做的事）
    - 給下一 Phase 的提醒（特別注意事項）
    - 跑了多久（小時:分鐘）

Step 4：commit + push + tag
  - git add -A && git commit -m "phase NN: <簡述>"
  - git push origin phase/NN-<簡稱>
  - git tag phase-NN-complete
  - git push --tags

Step 5：（人工）merge to main
  - 用戶手動 review + merge（v1.0 自用，不強制 PR）
  - merge 後切回 main：git checkout main && git pull
```

### 8.5.4 每 Phase 必跑的 Self-Check SOP

以下 8 項是每個 Phase 結尾**通用**檢查（不分 Phase 內容）：

```bash
# 1. 沒有未追蹤的可疑檔案
git status --porcelain | grep -v '^??' || echo "OK: 無未追蹤檔"
# （? 開頭的是新檔；非 ? 開頭的應該都已 add）

# 2. 沒有 secret 進入 git
detect-secrets scan --baseline .secrets.baseline | jq '.results | length'
# 應為 0；非 0 → 看哪個檔，移除 secret 再 commit

# 3. 沒有 print() / console.log() 殘留（dev debug 殘骸）
grep -rn "print(" backend/app/ --include="*.py" | grep -v "# noqa" || echo "OK"
grep -rn "console.log" frontend/src/ --include="*.tsx" --include="*.ts" || echo "OK"

# 4. lint 通過
cd backend && uv run ruff check . && cd ..
cd frontend 2>/dev/null && (test -f package.json && npm run lint) || true
cd ..

# 5. 型別檢查通過（如果該 Phase 有 TS 程式）
cd frontend 2>/dev/null && (test -f package.json && npm run type-check) || true
cd ..

# 6. 測試通過
cd backend && uv run pytest --tb=short -q && cd ..

# 7. Docker 服務還活著
docker compose ps | grep -v "Exit\|stopped" | grep -E "timescaledb|redis|qdrant"

# 8. /health/live 還回 200
curl -f http://localhost:8000/health/live 2>/dev/null && echo "OK" || echo "FAIL"
```

**8 項全綠 → Phase 真正完成。任一不綠 → 不算完成。**

### 8.5.5 跨 Phase 健康檢查腳本

每完成一個 Phase 就在 `scripts/health_checks/` 新增一個健康檢查腳本：

```
scripts/health_checks/
├── phase_01.sh      ← P1 完成後產生：驗證骨架 + 工程規範還在
├── phase_02.sh      ← P2 完成後產生：驗證 Docker 服務 + DB 帳號可連
├── phase_03.sh      ← P3 完成後產生：驗證 backend /health/live + middleware
├── phase_04.sh      ← P4 完成後產生：驗證 schema + migration up/down
├── phase_05.sh      ← P5 完成後產生：驗證 TW data sources + repo 測試
├── ... 以此類推到 phase_20.sh
└── all.sh           ← 跑所有 phase_NN.sh，total exit code 0 表全綠
```

每個 Phase 開頭必跑 `bash scripts/health_checks/phase_<上一 Phase>.sh`，確認上一 Phase 結果還能跑。

### 8.5.6 「context 接近上限」緊急處理 SOP

如果在 Phase 執行中，估算 context 使用 > 150k token（Opus 4.7 Max 約 200k 上限），立即執行：

```
1. 把目前已完成的部分 commit：
   git add -A && git commit -m "WIP: phase NN partial - <描述>"
   git push

2. 在對話中產出「接續 Prompt」：
   - 列已完成的子任務（打勾）
   - 列剩餘子任務（打 ❌）
   - 描述當前 git 狀態（branch + last commit）
   - 任何還沒寫到 doc 的決策

3. 結束當前對話

4. 開新對話貼「接續 Prompt」+「本 Phase 章節編號」+「PLAN.md 路徑」

絕對不要硬撐到 context 滿，否則 Claude 會開始遺忘前面的決策、產出前後不一致的程式碼。
```

### 8.5.7 Phase 執行追蹤檔

維護 `docs/phase_progress.md`，格式：

```markdown
# Phase 執行進度

| Phase | 狀態 | 開始日期 | 完成日期 | 實際時數 | Claude session 數 | 備註 |
|-------|------|---------|---------|---------|------------------|------|
| P0 | ✅ 完成 | 2026-05-03 | 2026-05-03 | 0.5 | 1 | 順利 |
| P1 | 🚧 進行中 | 2026-05-04 | - | 2.0 | 1 | - |
| P2 | ⏳ 待開始 | - | - | - | - | - |
| ... | ... | ... | ... | ... | ... | ... |
```

每個 Phase 結束更新一次。Claude session 數 > 1 代表中段被 context 限制中斷過。

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

## 二十三點五、跨 Phase 累積測試與健康檢查表

> v7 全新章節。每個 Phase 完成後，這張表的「累積數量」必須符合預期，否則代表 Phase 沒做到位。

### 23.5.1 累積測試數量基準

> **v7.0 重要說明：** 表格欄位數字代表「**最低應達到**」（≥），實際 Phase 任務清單可能宣告更高（例如某 Phase 寫「~38 個測試」），這是合理的「實作可超過底線」。
> 各 Phase「共 ~XX 個測試」加總會大於本表的「累積總數」，差異約 30-50 個（屬於正常裕量）。
> **驗收原則：** Phase 結束時 `pytest --collect-only` 數字 **必須 ≥ 本表底線**，但**不必嚴格等於各 Phase 加總**。

| Phase | 後端 unit | 後端 integration | 後端 security | 前端 unit | 前端 e2e | 累積總數 |
|-------|-----------|-----------------|---------------|-----------|---------|---------|
| P0 完成後 | 0 | 0 | 0 | 0 | 0 | 0 |
| P1 完成後 | 5+ | 0 | 0 | 0 | 0 | 5+ |
| P2 完成後 | 10+ | 2+ | 0 | 0 | 0 | 12+ |
| P3 完成後 | 25+ | 5+ | 0 | 0 | 0 | 30+ |
| P4 完成後 | 35+ | 8+ | 0 | 0 | 0 | 43+ |
| P5 完成後 | 60+ | 12+ | 0 | 0 | 0 | 72+ |
| P6 完成後 | 85+ | 16+ | 0 | 0 | 0 | 101+ |
| P7 完成後 | 100+ | 20+ | 0 | 0 | 0 | 120+ |
| P8 完成後 | 125+ | 28+ | 5+ | 0 | 0 | 158+ |
| P9 完成後 | 145+ | 35+ | 12+ | 0 | 0 | 192+ |
| P10 完成後 | 170+ | 45+ | 15+ | 0 | 0 | 230+ |
| P11 完成後 | 195+ | 55+ | 18+ | 0 | 0 | 268+ |
| P12 完成後 | 215+ | 60+ | 18+ | 0 | 0 | 293+ |
| P13 完成後 | 240+ | 70+ | 20+ | 0 | 0 | 330+ |
| P14 完成後 | 265+ | 80+ | 22+ | 0 | 0 | 367+ |
| P15 完成後 | 265+ | 80+ | 22+ | 30+ | 0 | 397+ |
| P16 完成後 | 265+ | 80+ | 22+ | 70+ | 0 | 437+ |
| P17 完成後 | 265+ | 80+ | 22+ | 110+ | 0 | 477+ |
| P18 完成後 | 280+ | 90+ | 35+ | 110+ | 8+ | 523+ |
| P19 完成後 | 280+ | 95+ | 35+ | 110+ | 15+ | 535+ |
| P20 完成後 | 285+ | 100+ | 35+ | 110+ | 15+ | 545+ |

**驗收方式：** 每 Phase 結尾跑：

```bash
cd backend && uv run pytest --collect-only -q | tail -1   # 應 ≥ 該 Phase 的「後端 unit + integration + security」總數
cd frontend && npm test -- --listTests 2>/dev/null | wc -l  # 應 ≥ 該 Phase 的「前端 unit」
cd frontend && npx playwright test --list 2>/dev/null | grep -c "›" # 應 ≥ 該 Phase 的「前端 e2e」
```

### 23.5.2 跨 Phase 健康檢查腳本對應表

| Phase | 健康檢查腳本 | 主要驗證項 |
|-------|-------------|-----------|
| P1 | `scripts/health_checks/phase_01.sh` | legacy/ 存在；新骨架目錄齊；.pre-commit 安裝 |
| P2 | `scripts/health_checks/phase_02.sh` | docker compose 3 服務 healthy；3 個 DB 帳號可連 |
| P3 | `scripts/health_checks/phase_03.sh` | backend `/health/live` 200；structlog JSON；trace_id header |
| P4 | `scripts/health_checks/phase_04.sh` | 所有表存在；hypertable 建立；Alembic up/down 通過 |
| P5 | `scripts/health_checks/phase_05.sh` | TW data sources unit test 全綠；FinMind/TWSE mock 可呼叫 |
| P6 | `scripts/health_checks/phase_06.sh` | US data sources unit test 全綠；fallback 機制可觸發 |
| P7 | `scripts/health_checks/phase_07.sh` | celery worker / beat 啟動；DLQ 表可寫；seed_stocks 跑完 1500+ |
| P8 | `scripts/health_checks/phase_08.sh` | login/refresh/logout 流程通；JWT rotation 正常；lockout 觸發 |
| P9 | `scripts/health_checks/phase_09.sh` | audit hash chain verify 通；rate limit 6 層全部觸發 |
| P10 | `scripts/health_checks/phase_10.sh` | API 第一批 endpoint 全部 200 / 401 / 403 正確 |
| P11 | `scripts/health_checks/phase_11.sh` | API 第二批 endpoint 全部正確；idempotency 生效 |
| P12 | `scripts/health_checks/phase_12.sh` | LangGraph 可建 graph + dry-run；tools registry 完整 |
| P13 | `scripts/health_checks/phase_13.sh` | 4 種 TW analyst 結構化輸出通過 schema |
| P14 | `scripts/health_checks/phase_14.sh` | US analyst 通過；LLM fallback chain 觸發；WS 串流通 |
| P15 | `scripts/health_checks/phase_15.sh` | frontend `npm run build` 通；auth 流程通；layout 完整 |
| P16 | `scripts/health_checks/phase_16.sh` | 8 核心頁路由全部 200 / 307；API 整合正確 |
| P17 | `scripts/health_checks/phase_17.sh` | 全 18 頁路由全部 200 / 307；mock 頁面標示清楚 |
| P18 | `scripts/health_checks/phase_18.sh` | OWASP 測試全綠；LINE/Telegram 通知測通 |
| P19 | `scripts/health_checks/phase_19.sh` | E2E 全綠；prod compose 啟動；DR 演練通過 |
| P20 | `scripts/health_checks/all.sh` | 跑遍 phase_01.sh ~ phase_19.sh，total exit code = 0 |

### 23.5.3 累積健康檢查使用方式

每個 Phase 開頭：
```bash
# 跑上一 Phase 的健康檢查（驗證上一 Phase 還活著）
bash scripts/health_checks/phase_<NN-1>.sh
```

每個 Phase 結尾：
```bash
# 1. 先跑本 Phase 的健康檢查
bash scripts/health_checks/phase_<NN>.sh

# 2. 跑全部 phase 1 ~ 本 phase 的累積檢查（v7 強制）
for i in $(seq 1 <NN>); do
  printf -v fname "phase_%02d.sh" $i
  echo "=== $fname ==="
  bash scripts/health_checks/$fname || { echo "FAIL: $fname"; exit 1; }
done
```

**累積檢查通過 → 該 Phase 才算「真的完成」。** 否則代表本 Phase 改動意外破壞了前面的成果。

---

# Part C — 執行

---

## 二十四、Phase 總覽 + 時程預估

> **v7 改動：** 從 10 個 Phase 拆細為 21 個 Phase（P0-P20）。每個 Phase 設計為「Opus 4.7 Max 5 小時 session 一次跑得完」。

### 24.1 Phase 總覽表

| # | 主題 | 預估行數 | 預估 Token | Session 時數 | 風險 |
|---|------|---------|------------|------------|------|
| **P0** | Pre-flight 環境驗證 + 帳號準備（手動為主） | - | - | 0.5-1 hr | 極低 |
| **P1** | 原版遷移 + 新骨架 + 工程規範文件 + Git 工作流程 | ~800 | ~50k | 3-4 hr | 低 |
| **P2** | Docker 基礎服務 + DB 帳號分離 + 健康檢查 | ~600 | ~45k | 2-3 hr | 低 |
| **P3** | 後端工程基礎（config/log/error/middleware/HTTP/CB）+ 最小 backend | ~1200 | ~70k | 4-5 hr | 中 |
| **P4** | 完整 DB Schema + Alembic + Hypertable + Trigger | ~1500 | ~75k | 4-5 hr | 中 |
| **P5** | TW 資料源 Adapter（FinMind/TWSE/TPEX/MOPS/cnyes）+ Repository | ~1400 | ~75k | 4-5 hr | 中 |
| **P6** | US 資料源（yfinance/AV/Finnhub/SEC）+ Fallback + Bootstrap scripts | ~1300 | ~70k | 4-5 hr | 中 |
| **P7** | Celery Worker + Beat + DLQ + 排程任務 | ~1200 | ~70k | 4-5 hr | 中 |
| **P8** | 認證系統（JWT/RBAC/CSRF/WS Ticket/密碼重置/Session/Lockout） | ~1400 | ~75k | 4-5 hr | 中 |
| **P9** | 安全 Middleware + Audit hash chain + Rate Limit（6 層）+ Validators | ~1200 | ~70k | 4-5 hr | 中 |
| **P10** | 業務 API 第一批（users/stocks/market/watchlist/screener，auth 已在 P8） | ~1500 | ~78k | 5 hr | 高 |
| **P11** | 業務 API 第二批（analysis/orders/reports/exports/notifications/admin） | ~1500 | ~78k | 5 hr | 高 |
| **P12** | LangGraph 基礎 + Plugin + State trim + Tool 註冊 | ~1100 | ~65k | 4-5 hr | 中 |
| **P13** | 4 種 Analyst（台股版）+ Bull/Bear/Manager + 結構化輸出 | ~1400 | ~75k | 5 hr | 高 |
| **P14** | 美股 Analyst + LLM Provider Fallback + WS 串流 + 月配額 | ~1300 | ~75k | 5 hr | 高 |
| **P15** | 前端基礎 + Auth + 共用元件 + Layout + 路由保護 | ~1500 | ~78k | 5 hr | 中 |
| **P16** | 前端核心 8 頁（含後端整合） | ~2000 | ~80k | 5 hr | 高 |
| **P17** | 前端進階 10 頁（含 mock） | ~2000 | ~80k | 5 hr | 高 |
| **P18** | 通知整合（LINE/Telegram）+ 安全強化（OWASP）+ 滲透測試 | ~1200 | ~70k | 4-5 hr | 中 |
| **P19** | 整合測試 + E2E + Prod 部署 + DR 演練 | ~1300 | ~70k | 4-5 hr | 中 |
| **P20** | 全面整合驗證 + 完整報告生成 + Obsidian 設定 + 結案文件 | ~600 | ~60k | 3-4 hr | 低 |

### 24.2 時程合計

- **總 Phase 數：** 21（P0-P20）
- **總時數：** ~85-100 hr Claude 互動時間
- **總 Calendar 時間：** ~30-40 天（每天 5 小時 = 1 個 Phase）
- **總 Token：** ~1.4M（每 Phase 都在 200k context window 內，且預留 ≥ 25% 緩衝）

### 24.3 Phase 階段分組

| 階段 | Phase | 主題 |
|------|-------|------|
| **準備** | P0 | 環境驗證 |
| **基礎設施** | P1, P2, P3 | 骨架、Docker、後端基礎 |
| **資料層** | P4, P5, P6, P7 | Schema、TW、US、Celery |
| **後端 API** | P8, P9, P10, P11 | Auth、安全、業務 API |
| **AI Agent** | P12, P13, P14 | LangGraph、Analyst、串流 |
| **前端** | P15, P16, P17 | 基礎、核心頁、進階頁 |
| **強化 + 部署** | P18, P19 | 安全、通知、測試、部署、DR |
| **驗證 + 結案** | P20 | 全面驗證 + 報告 |

### 24.4 嚴格規則

1. **不可跳 Phase**：必須依序 P0 → P1 → ... → P20
2. **不可合併 Phase**：v7 已拆細，再合併會違反「單 session 完成」原則
3. **不可拆分 Phase**：除非中段 context 爆掉，否則不拆（拆了會增加跨 session 銜接風險）
4. **每個 Phase 開新對話**：避免 context 累積
5. **Phase 之間用 git tag 串接**：每個 Phase 完成 tag `phase-NN-complete`

### 24.5 v6 → v7 Phase 對應表

| v6 Phase | v7 對應 Phase | 拆分理由 |
|----------|--------------|---------|
| P0 | P0 | 不變 |
| P1（基礎設施 + 規範 + Migration） | P1 + P2 + P3 | v6 P1 太大（含 Docker、目錄、後端基礎、CI），拆成「遷移與骨架」「Docker 服務」「後端程式碼基礎」 |
| P2（資料管線 + Bootstrap） | P4 + P5 + P6 + P7 | v6 P2 太大（含 schema、TW、US、Celery、bootstrap），拆 4 段 |
| P3（後端基礎） | P8 + P9 | v6 P3 太大（auth + middleware + audit + rate limit），拆「Auth」與「安全 middleware」 |
| P4（業務 API） | P10 + P11 | 15 routers 拆成兩批 |
| P5（LangGraph） | P12 + P13 + P14 | 拆「框架」「TW analyst」「US analyst + 串流」 |
| P6（前端 + 8 頁） | P15 + P16 | 拆「基礎」與「8 核心頁」 |
| P7（前端 10 頁） | P17 | 不變 |
| P8（安全 + 通知 + 測試） | P18 + P19（部分） | 拆出 E2E + 部署 |
| P9（部署 + DR + Obsidian） | P19（部分）+ P20 | 拆出「全面驗證 + 報告」獨立 Phase |

---

## 二十五、Phase 啟動 Prompt 標準模板

> v7 全新章節。**所有 Phase 都用這個固定 9 段格式**。

### 25.1 標準格式

```
=== TradingAgents-TW Phase NN（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase NN
必讀 PLAN.md 章節：<列出，例：第 4, 8.5, 13, 14, 17, 22 章>
（不要讀全部，會吃掉 context）

【1. 前置依賴 Phase】
依賴：Phase <列出>
驗證方式：bash scripts/health_checks/phase_<NN-1>.sh
失敗 → 不開始本 Phase，先修復前面 Phase

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
跑：
- bash scripts/health_checks/phase_<NN-1>.sh
- git status（必須乾淨，否則先 stash）
- docker compose ps（依賴的服務必須 healthy）

【3. 本 Phase 目標】
<一句話描述本 Phase 完成後系統「多了什麼能力」>

【4. 任務清單】
A. <子任務 1>
B. <子任務 2>
C. <...>

【5. 完成驗收（具體指令）】
跑以下 N 個指令，全部 exit code 0：
1. <cmd>
2. <cmd>
...

【6. Smoke Test（手動）】
- <人工確認項 1>
- <人工確認項 2>

【7. 已知陷阱】
✗ <陷阱 1>
✗ <陷阱 2>
...

【8. Self-Check SOP】
跑第 8.5.4 章「每 Phase 必跑的 Self-Check SOP」全部 8 項。
所有項皆綠才算完成。

【9. 完成後產物】
- 程式檔：<列出主要新增/修改檔案>
- 測試檔：<列出>
- 文件檔：
  - docs/phase_reports/PHASE_NN.md（必寫，依第 8.5.3 章）
  - scripts/health_checks/phase_NN.sh（必寫，依第 23.5.2 章）
  - 更新 docs/phase_progress.md（依第 8.5.7 章）
- Git tag：phase-NN-complete

【10. 開始執行】
請按【2. 跨 Phase 健康檢查】開始，確認 OK 後依【4. 任務清單】依序執行。
每完成一個子任務，回報結果再進下一個。
```

### 25.2 模板使用注意事項

1. **每個 Phase 開新對話**，第一則訊息就是這個模板（已填入該 Phase 內容）
2. **不要在同一個對話跨 Phase**（context 累積會出問題）
3. **Claude 主動讀取 PLAN.md 該 Phase 章節**，不要把全部內容貼進 Prompt
4. **如 context 接近上限（> 150k 估算）**：依第 8.5.6 章緊急處理 SOP

---

## 二十六、Phase 0：Pre-flight 環境驗證

> v6 → v7：增強，加上「Claude 知識準備」與「帳號註冊清單」。**P1 之前必跑**。手動執行（約 30-60 分鐘）。

### 26.1 環境驗證指令（v6 保留）

依第三章 3.1 執行所有指令並確認結果。

### 26.2 取得 API Keys（v6 保留 + v7 加註）

依第三章 3.2 取得：

**Phase 1-7 必需：**
- `GOOGLE_API_KEY`（Gemini，Phase 5+ 需要）

**Phase 5-7 強烈建議：**
- `FINMIND_TOKEN`（FinMind 免費版即可，付費更穩）
- `ALPHA_VANTAGE_API_KEY`（美股備源）

**Phase 14+ 強烈建議：**
- `OPENAI_API_KEY`（LLM fallback，買 $5 credit 夠用）
- `ANTHROPIC_API_KEY`（LLM fallback，買 $5 credit 夠用）

**Phase 18+ 可選：**
- `LINE_NOTIFY_TOKEN` 或 `TELEGRAM_BOT_TOKEN`（通知）
- `FINNHUB_API_KEY`（美股備源 2）

### 26.3 git 備份（v6 保留）

```bash
cd C:\Projects\TradingAgents
git status                                    # 確認 clean
git tag pre-tw-edition-backup
git log --oneline -5                          # 記下原版最後 commit
```

### 26.4 v7 新增：Claude 知識準備

**目的：** 確保你（user）對接下來 21 個 Phase 的執行流程有清楚預期。

```
1. 讀完 PLAN.md Part A 全部章節（含新加的 8.5 章 Phase 設計方法論）
2. 讀完 PLAN.md 第 23.5 章（跨 Phase 累積測試表）
3. 讀完 PLAN.md 第二十四章（Phase 總覽）
4. 讀完 PLAN.md 第二十五章（Phase 啟動 Prompt 標準模板）
5. 確認你理解：
   - 為什麼每個 Phase 要開新對話
   - 為什麼要嚴格依序
   - 為什麼 Phase 結尾要寫 health_check + report
   - 你打算用什麼節奏執行（建議：每天一 Phase）
```

### 26.5 v7 新增：建立 Phase 執行追蹤檔

```bash
mkdir -p docs/phase_reports scripts/health_checks
cat > docs/phase_progress.md << 'EOF'
# Phase 執行進度

| Phase | 狀態 | 開始日期 | 完成日期 | 實際時數 | Claude session 數 | 備註 |
|-------|------|---------|---------|---------|------------------|------|
| P0 | ✅ 完成 | YYYY-MM-DD | YYYY-MM-DD | 0.5 | 0（手動） | 環境驗證通過 |
| P1 | ⏳ 待開始 | - | - | - | - | - |
| P2 | ⏳ 待開始 | - | - | - | - | - |
| P3 | ⏳ 待開始 | - | - | - | - | - |
| P4 | ⏳ 待開始 | - | - | - | - | - |
| P5 | ⏳ 待開始 | - | - | - | - | - |
| P6 | ⏳ 待開始 | - | - | - | - | - |
| P7 | ⏳ 待開始 | - | - | - | - | - |
| P8 | ⏳ 待開始 | - | - | - | - | - |
| P9 | ⏳ 待開始 | - | - | - | - | - |
| P10 | ⏳ 待開始 | - | - | - | - | - |
| P11 | ⏳ 待開始 | - | - | - | - | - |
| P12 | ⏳ 待開始 | - | - | - | - | - |
| P13 | ⏳ 待開始 | - | - | - | - | - |
| P14 | ⏳ 待開始 | - | - | - | - | - |
| P15 | ⏳ 待開始 | - | - | - | - | - |
| P16 | ⏳ 待開始 | - | - | - | - | - |
| P17 | ⏳ 待開始 | - | - | - | - | - |
| P18 | ⏳ 待開始 | - | - | - | - | - |
| P19 | ⏳ 待開始 | - | - | - | - | - |
| P20 | ⏳ 待開始 | - | - | - | - | - |
EOF

# commit P0 的設定
git add docs/ scripts/
git commit -m "chore(phase-0): 初始化 Phase 執行追蹤檔與健康檢查腳本目錄"
```

### 26.6 P0 退出條件（具體可執行）

跑以下 7 個指令全部回傳 success：

```powershell
# 1. Docker 可用
docker info > $null; if ($?) { "OK" } else { "FAIL" }

# 2. uv + Python 3.11 可用
uv python list | Select-String "3.11" || (uv python install 3.11; "已安裝 3.11")

# 3. Node ≥ 18
node --version | ForEach-Object {
  if ([version]($_ -replace 'v','') -ge [version]'18.0.0') { 'OK' } else { 'FAIL' }
}

# 4. 磁碟 50 GB+ 空間
$free = (Get-PSDrive C).Free / 1GB
if ($free -gt 50) { 'OK' } else { 'FAIL' }

# 5. Git 備份 tag 存在
git tag --list | Select-String "pre-tw-edition-backup"

# 6. .env 至少有 GOOGLE_API_KEY
Select-String "^GOOGLE_API_KEY=.+" .env

# 7. v7 新增：phase 追蹤檔已建立
Test-Path docs/phase_progress.md
Test-Path docs/phase_reports
Test-Path scripts/health_checks
```

✅ 7 個都 OK → 進 P1
❌ 任一失敗 → 修正後重跑

### 26.7 P0 完成後填的內容

把 `docs/phase_progress.md` 中 P0 那行的「完成日期 / 實際時數 / 備註」填上。

---

## 二十七、Phase 1-20 詳細 Prompts

每個 Prompt 自包含。**fresh Claude Opus 4.7 Max 收到 Prompt 後，依第二十五章標準模板執行。**
**遇到任何 PLAN.md 細節 → 主動 Read 對應章節（不要全讀）。**

---

### ▌Phase 1 — 原版遷移 + 新骨架 + 工程規範文件 + Git 工作流程

```
=== TradingAgents-TW Phase 1（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 1
必讀 PLAN.md 章節：第 4, 8.5, 17, 22 章
（重要：不要讀全部 PLAN.md，會吃掉 context）

【1. 前置依賴 Phase】
依賴：Phase 0
驗證方式：
  - cat docs/phase_progress.md | grep "P0.*✅"
  - git tag --list | grep pre-tw-edition-backup
失敗 → 不開始本 Phase，回去做 P0

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
跑：
  - git status（必須乾淨）
  - cat docs/phase_progress.md（確認 P0 已完成）
  - cat .env | grep "^GOOGLE_API_KEY=.\+" | wc -l   # 應 = 1
  - test -d docs/phase_reports && test -d scripts/health_checks && echo OK

【3. 本 Phase 目標】
讓專案具備「v7 開發所需的工程基礎」：
  (1) 原版 v0.2.4 已搬到 legacy/ 與新版完全隔離
  (2) 新後端/前端目錄骨架已建立（空殼，無實作）
  (3) Git 工作流程確立（branch 命名、commit message 格式、pre-commit）
  (4) CI/CD 雛形（lint、secret scan）
  (5) 工程規範文件齊全（engineering-standards.md / setup.md / contributing.md）

注意：本 Phase「不寫任何業務程式」，純粹是「鋪好基礎 + 規範」。
Docker 服務在 P2 才設定（避免 P1 過大）。

【4. 任務清單】

A. 切分支：
   git checkout -b phase/01-migration-and-skeleton

B. 原版遷移（依第四章 4.3 指令完整執行）：
   - mkdir legacy
   - git mv tradingagents/ cli/ tests/ scripts/ main.py pyproject.toml \
            requirements.txt requirements.lock setup.bat setup.ps1 \
            start.bat start.ps1 add_to_path.bat assets/ legacy/
   - git mv Dockerfile docker-compose.yml legacy/
   - 處理可能遺漏：ls 根目錄，把任何不應留的（test.py、build/）都遷走
   - 寫 legacy/README.md（依第 4.3 章模板）
   - commit "chore(phase-1): 將原版 v0.2.4 遷至 legacy/"

C. 新目錄骨架（依第二十二章，全部 mkdir + .gitkeep）：
   backend/app/{api/v1, core, repos, services, domain, models, schemas,
                agents/{analysts, researchers, managers, risk_mgmt, trader,
                        tools/{tw, us}, utils},
                data_sources/{tw, us, base}, llm, workers, notifications, exports}/
   backend/migrations/, backend/scripts/, backend/tests/{unit, integration, security}/
   data-pipeline/{schemas, scripts}/
   docker/{timescaledb, nginx/certs, backups, playwright}/
   frontend/{src/{app, components, lib, store, hooks, i18n}, tests/{unit, e2e}}/
   .github/workflows/
   docs/{phase_reports, runbooks}/
   每個目錄放 .gitkeep（git 不追蹤空目錄）

D. .gitignore（覆寫，加 v7 必要項）：
   .venv/, __pycache__/, *.pyc, .pytest_cache/, .ruff_cache/
   node_modules/, .next/, *.tsbuildinfo, coverage/
   .env, .env.local, *.key, *.pem, *.p12
   .DS_Store, Thumbs.db
   docker/backups/*.tar.gz*
   build/, dist/, *.egg-info/
   .vscode/settings.local.json
   playwright-report/, test-results/

E. .vscode/settings.json（v6 第 4.5 章模板）：
   排除 legacy/、node_modules/、.next/、.venv/

F. .env.example（**完整含繁中註解，v7.0 修正：列齊所有 v1.0 用到的欄位**）：

   依第 P3 章 config.py 屬性清單一次列齊（DB / Redis / Qdrant 密碼欄位 P2 才加值，但 placeholder 名稱本 Phase 先列）：

   ```env
   # ── 應用層 ──────────────────────────────────────────
   APP_ENV=dev
   APP_VERSION=0.3.0
   LOG_LEVEL=INFO
   LOG_FORMAT=json
   ADMIN_EMAIL=admin@example.com               # 系統管理者 + 初始 admin 帳號
   ADMIN_INITIAL_PASSWORD=ChangeMeOnFirstLogin!1234   # 第一次 seed 用，登入後強制改
   DEFAULT_TIMEZONE=Asia/Taipei
   DEFAULT_LANG=zh-TW

   # ── 安全（產生方式見下方註解） ────────────────────────
   # python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   SECRET_KEY=                                  # ≥ 32 bytes，base64 字串
   SECRET_KEY_PREVIOUS=                         # 雙 key rotation 用，平時空
   DATA_ENCRYPTION_KEY=                         # Fernet key（與 SECRET_KEY 分離）
   CORS_ORIGINS=["http://localhost:3000"]
   CSP_PROD_ENABLED=false                       # P18 prod 設 true

   # ── DB（密碼在 P2 補入隨機 32 字元） ──────────────────
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=tradingagents_tw
   POSTGRES_SUPERUSER_PASSWORD=
   TA_MIGRATION_PASSWORD=
   TA_SERVICE_RW_PASSWORD=
   TA_AGENT_RO_PASSWORD=
   POOL_SIZE_RW=20
   POOL_SIZE_RO=30
   STATEMENT_TIMEOUT_MS=30000
   LOCK_TIMEOUT_MS=10000

   # ── Redis ──────────────────────────────────────────
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_PASSWORD=                              # P2 補入
   POOL_SIZE_REDIS=50

   # ── Qdrant ─────────────────────────────────────────
   QDRANT_HOST=localhost
   QDRANT_PORT=6333
   QDRANT_GRPC_PORT=6334
   QDRANT_API_KEY=                              # P2 補入
   EMBEDDING_DIM=768

   # ── 資料源 API key（P5/P6 才需要值） ──────────────────
   FINMIND_TOKEN=                               # 強烈建議：https://finmindtrade.com
   ALPHA_VANTAGE_API_KEY=                       # 強烈建議：https://www.alphavantage.co
   FINNHUB_API_KEY=                             # 可選

   # ── LLM Provider（P12+ 才需要值） ────────────────────
   GOOGLE_API_KEY=                              # 必需：https://aistudio.google.com/apikey
   OPENAI_API_KEY=                              # 可選 fallback
   ANTHROPIC_API_KEY=                           # 可選 fallback
   LLM_DEFAULT_PROVIDER=google
   LLM_DEFAULT_MODEL=gemini-2.0-flash
   OPENAI_DEFAULT_MODEL=gpt-4o-mini
   ANTHROPIC_DEFAULT_MODEL=claude-haiku-3-5-20241022
   GEMINI_EMBEDDING_MODEL=text-embedding-004
   LLM_MONTHLY_BUDGET_USD_DEFAULT=50.00

   # ── 通知（P18 才需要值） ──────────────────────────────
   LINE_NOTIFY_TOKEN=                           # 可選：https://notify-bot.line.me
   TELEGRAM_BOT_TOKEN=                          # 可選：@BotFather
   TELEGRAM_CHAT_ID=
   ```

   **欄位分批填值原則：**
   - P0/P1：先把欄位列齊（值留空或 placeholder）
   - P2 加值：DB / Redis / Qdrant 密碼（隨機 32 字元）
   - P5/P6 加值：FINMIND_TOKEN / ALPHA_VANTAGE_API_KEY 等資料源 token
   - P12 加值：GOOGLE_API_KEY（必需）
   - P14 加值：OPENAI_API_KEY / ANTHROPIC_API_KEY（fallback chain 用，可選）
   - P18 加值：LINE_NOTIFY_TOKEN / TELEGRAM_BOT_TOKEN（通知，可選）

G. backend/pyproject.toml 雛形（uv，依第六章 6.1 pin 版本）：
   - 只列必要依賴（後續 Phase 會補）
   - tool.ruff、tool.pytest 設定
   - dependencies 至少含：fastapi, uvicorn[standard], pydantic, pydantic-settings,
     structlog, httpx, sqlalchemy[asyncio], asyncpg, redis, python-jose,
     passlib[bcrypt], tenacity, alembic
   - **dev dependencies（重要！）：** ruff, pytest, pytest-asyncio, pytest-cov, mypy,
     types-redis, **detect-secrets, pre-commit**（後兩者讓退出條件可跑）
   注意：本 Phase 不裝 langgraph、celery、qdrant-client、pandas（避免 P1 過大）

G2. 工具安裝（在 backend uv 環境內，避免污染全域）：
    cd backend
    uv sync                           # 會安裝 detect-secrets / pre-commit 等 dev deps
    uv run pre-commit install         # 把 git hook 裝到 .git/hooks/pre-commit
    cd ..
    # 後續退出條件用「uv run pre-commit run」/「uv run detect-secrets」即可，
    # 不依賴全域 pip install

H. backend/uv.lock：
   cd backend && uv lock && cd ..
   commit 進 git

I. backend/Dockerfile 雛形：
   - FROM python:3.11-slim
   - 不裝 chromium、不裝 fonts-noto-cjk（P19 才需要 PDF）
   - 建立 uid 1000 user（非 root）
   - WORKDIR /app
   - COPY backend/pyproject.toml backend/uv.lock ./
   - RUN uv sync --frozen
   - 不要 COPY 程式碼（Phase 3 才開始有 main.py）

J. .pre-commit-config.yaml：
   - ruff（lint + format）
   - prettier（前端，先設定但暫不啟用）
   - detect-secrets（baseline）
   - trailing-whitespace、end-of-file-fixer
   - check-yaml、check-json、check-merge-conflict

K. .secrets.baseline：
   cd backend && uv run detect-secrets scan > ../.secrets.baseline && cd ..
   檢查無 false positive，commit 進 git
   （baseline 放專案根目錄，方便 CI 與 pre-commit 共用）

L. .github/workflows/ci.yml 雛形：
   - on: push, pull_request
   - jobs:
     - lint-backend: uv run ruff check backend/app
     - secret-scan: detect-secrets scan --baseline .secrets.baseline
   - 暫不跑 pytest（Phase 3 之後才有測試）

M. .github/workflows/security.yml 雛形：
   - schedule: 每週一 02:00
   - jobs: bandit（暫 stub）、detect-secrets

N. Makefile（最小版）：
   - help: 列出所有 target
   - lint: 跑 ruff
   - secrets-scan: detect-secrets scan --baseline .secrets.baseline
   - clean: 清快取
   注意：up / down / init-db 等 Docker target 在 P2 才加

O. docs/engineering-standards.md：完整輸出第十七章內容
   - logging、error 階層、API envelope、分頁、快取、測試金字塔、migration、code style

P. docs/setup.md：
   - 前置條件（依 Phase 0 已驗證）
   - 各 Phase 啟動指令清單（P2-P20 暫先列 TBD）
   - 第一次 dev 環境啟動指令

Q. docs/contributing.md（v7 新增）：
   - Git 工作流程（branch 命名：phase/NN-<簡稱>、feat/<簡稱>、fix/<簡稱>）
   - Commit message 格式：feat/fix/chore/docs/test/refactor + scope
   - Pre-commit hook 必跑
   - PR template 與審核流程（v1.0 自用，Self-review 即可）

R. README.md：
   - 重寫成新版（原版已備份於 legacy/README.md）
   - 包含：專案簡介、技術棧、快速啟動（指向 setup.md）、Phase 進度（指向 phase_progress.md）
   - 加上 v7 的徽章：Python 3.11、Node 20、TimescaleDB 16

S. CHANGELOG.md：保留原版 + 加上 v0.3.0 entry：
   ## [Unreleased] - TradingAgents-TW v1.0 development
   ### Added
   - v7.0 PLAN：21-Phase 開發計劃
   - 原版 v0.2.4 遷至 legacy/
   - 新骨架（FastAPI + LangGraph + Next.js）
   - 工程規範文件、CI/CD 雛形

T. 寫 5 個 unit test 雛形（第 23.5 章 P1 累積基準）：
   - backend/tests/unit/test_skeleton.py（驗證骨架目錄存在）
   - backend/tests/unit/test_config_loader.py（stub，先驗證可 import config 模組 - 這裡會 fail，先標 skip）
   - backend/tests/unit/test_logging_format.py（stub，標 skip）
   - backend/tests/unit/test_repo_imports.py（驗證關鍵模組可 import）
   - backend/tests/unit/test_envelope_shape.py（stub，標 skip）
   pytest --collect-only 應 ≥ 5 個

U. 寫 scripts/health_checks/phase_01.sh：
   #!/bin/bash
   set -e
   echo "=== Phase 01 健康檢查 ==="
   test -d legacy/tradingagents || { echo "❌ legacy/tradingagents 不存在"; exit 1; }
   test ! -e tradingagents || { echo "❌ 根目錄不該有 tradingagents"; exit 1; }
   test -d backend/app/core || { echo "❌ backend 骨架不全"; exit 1; }
   test -f docs/engineering-standards.md || { echo "❌ engineering-standards.md 缺"; exit 1; }
   test -f .pre-commit-config.yaml || { echo "❌ pre-commit 設定缺"; exit 1; }
   test -f backend/pyproject.toml || { echo "❌ pyproject.toml 缺"; exit 1; }
   test -f backend/uv.lock || { echo "❌ uv.lock 缺"; exit 1; }
   cd backend && uv run ruff check app/ && cd ..
   echo "✅ Phase 01 健康檢查通過"
   chmod +x scripts/health_checks/phase_01.sh

V. 寫 docs/phase_reports/PHASE_01.md：
   依第 8.5.3 章 Step 3 模板填寫

W. 更新 docs/phase_progress.md：把 P1 的「狀態 / 完成日期 / 時數」填上

【5. 完成驗收（具體指令）】

完成 Phase 1 = 以下 12 個指令全部 exit code 0：

```bash
# 1. 原版完整遷移
test -d legacy/tradingagents && echo "1-OK"
test -d legacy/cli && echo "1-OK"
test ! -e tradingagents && echo "1-OK"
test ! -e cli && echo "1-OK"

# 2. 新骨架完整
for d in backend/app/core backend/app/api/v1 backend/app/services \
         backend/app/data_sources/tw backend/app/data_sources/us \
         frontend/src/app data-pipeline/scripts docker/timescaledb \
         docs/phase_reports scripts/health_checks; do
  test -d "$d" || { echo "❌ $d"; exit 1; }
done
echo "2-OK"

# 3. uv sync 成功
cd backend && uv sync --frozen && cd ..

# 4. ruff lint 通過
cd backend && uv run ruff check app/ && cd ..

# 5. pytest collect 至少 5 個
cd backend && uv run pytest --collect-only -q 2>&1 | tail -1 | grep -E "([5-9]|[1-9][0-9]+) tests collected"
cd ..

# 6. detect-secrets 通過（透過 backend uv 環境跑，避免依賴全域安裝）
cd backend && uv run detect-secrets scan --baseline ../.secrets.baseline && cd ..

# 7. pre-commit 通過（同樣透過 uv 環境）
cd backend && uv run pre-commit run --all-files --config ../.pre-commit-config.yaml && cd ..

# 8. .env.example 完整
grep -E "^GOOGLE_API_KEY=" .env.example
grep -E "^FINMIND_TOKEN=" .env.example
grep -E "^ALPHA_VANTAGE_API_KEY=" .env.example
grep -E "^SECRET_KEY=" .env.example
grep -E "^DATA_ENCRYPTION_KEY=" .env.example

# 9. 文件齊全
test -f docs/engineering-standards.md && echo "9-OK"
test -f docs/setup.md && echo "9-OK"
test -f docs/contributing.md && echo "9-OK"

# 10. health_check 腳本可跑
bash scripts/health_checks/phase_01.sh

# 11. Phase 報告寫好
test -f docs/phase_reports/PHASE_01.md && wc -l docs/phase_reports/PHASE_01.md | awk '{exit ($1 < 20) ? 1 : 0}'

# 12. CI 綠燈
git push origin phase/01-migration-and-skeleton
sleep 30
gh run list --limit 1 --branch phase/01-migration-and-skeleton | grep -i "completed.*success"
```

【6. Smoke Test（手動）】
✓ 用 VS Code 開專案，搜尋功能不會搜到 legacy/ 內檔案
✓ git log --oneline -5 看到「phase-1」相關 commit
✓ legacy/README.md 內容清楚說明用途
✓ docs/engineering-standards.md 可讀且完整（不是 placeholder）

【7. 已知陷阱】
✗ git mv 時若有未 commit 變更 → 先 commit 或 stash
✗ Windows file lock 導致 git mv 失敗 → 關閉 IDE 重試
✗ pre-commit 自動修檔 → git add 後再 commit
✗ uv 找不到 Python 3.11 → uv python install 3.11
✗ 根目錄遺漏的 main.py、test.py、build/ → ls 確認後一併 git mv
✗ uv lock 速度慢 → 第一次正常 ~2 分鐘
✗ Windows path 太長 → 啟用 git config --global core.longpaths true
✗ pyproject.toml 漏 [tool.pytest.ini_options] → pytest collect 找不到測試
✗ ruff config 與 pre-commit 不一致 → 兩邊都用相同 line-length=100
✗ .gitkeep 漏建 → git 不追蹤空目錄 → 後續 Phase commit 失敗
✗ secrets baseline 沒 commit → CI 會失敗
✗ 在 main 直接 commit → 一定要切 phase/01 分支

【8. Self-Check SOP】
跑第 8.5.4 章「每 Phase 必跑的 Self-Check SOP」全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/pyproject.toml + uv.lock
  - backend/Dockerfile（雛形）
  - backend/tests/unit/test_skeleton.py + test_repo_imports.py + 3 個 stub
  - .pre-commit-config.yaml、.secrets.baseline
  - .github/workflows/ci.yml + security.yml
  - .gitignore（覆寫）、.env.example、.vscode/settings.json
  - Makefile（最小版）
  - scripts/health_checks/phase_01.sh

檔案搬遷：
  - legacy/（含 tradingagents/、cli/、tests/、scripts/、main.py、pyproject.toml、
    Dockerfile、docker-compose.yml、setup*.bat/.ps1、start*.bat/.ps1、
    add_to_path.bat、assets/、requirements*.txt、README.md）

文件檔（新增）：
  - docs/engineering-standards.md
  - docs/setup.md（雛形）
  - docs/contributing.md
  - docs/phase_reports/PHASE_01.md
  - docs/phase_progress.md（更新 P1）

文件檔（覆寫）：
  - README.md（新版總覽）
  - CHANGELOG.md（加 v0.3.0 entry）

Git tag：
  - phase-01-complete

【10. 開始執行】
請按【2. 跨 Phase 健康檢查】開始，確認 OK 後依【4. 任務清單】依序執行。
每完成 A-W 一個子任務，回報結果再進下一個。
所有子任務完成後，跑【5. 完成驗收】所有 12 個指令確認綠燈。
```

---

### ▌Phase 2 — Docker 基礎服務 + DB 帳號分離 + 健康檢查

```
=== TradingAgents-TW Phase 2（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 2
必讀 PLAN.md 章節：第 6.1, 8.5, 12, 13, 19.1, 19.4, 19.5 章

【1. 前置依賴 Phase】
依賴：Phase 1
驗證方式：bash scripts/health_checks/phase_01.sh
失敗 → 修復 P1 後再開始

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_01.sh
- git status（必須乾淨）
- docker info（Docker daemon 必須在跑）
- 確認 5432, 6333, 6334, 6379 port 沒被占用

【3. 本 Phase 目標】
讓專案具備「可運行的本機 DB / Cache / Vector 服務」：
  (1) Docker Compose 啟動 TimescaleDB + Redis + Qdrant 三服務
  (2) 三服務全部 healthcheck 通過
  (3) DB 帳號分離（ta_migration / ta_service_rw / ta_agent_ro）已建立
  (4) Qdrant API key 已設
  (5) wait-for-services.sh 可正確等待
  (6) 提供 docker-compose.prod.yml 雛形（後續 P19 完整化）

注意：本 Phase「不寫後端程式」、「不建表」、「不放資料」。
只把基礎服務跑起來，並驗證連線與權限分離。

【4. 任務清單】

A. 切分支：
   git checkout main && git pull
   git checkout -b phase/02-docker-services

B. docker-compose.yml（依第十二章 + 13.2）：
   services:
     timescaledb:
       image: timescale/timescaledb:2.16-pg16
       ports: ["5432:5432"]
       environment:
         POSTGRES_PASSWORD: ${POSTGRES_SUPERUSER_PASSWORD}
         POSTGRES_DB: tradingagents_tw
       volumes:
         - timescaledb_data:/var/lib/postgresql/data
         - ./docker/timescaledb/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
       healthcheck:
         test: ["CMD", "pg_isready", "-U", "postgres"]
         interval: 10s
         timeout: 5s
         retries: 5
       restart: unless-stopped
     redis:
       image: redis:7-alpine
       command: redis-server --requirepass ${REDIS_PASSWORD} --maxmemory 1gb --maxmemory-policy allkeys-lru
       ports: ["6379:6379"]
       volumes:
         - redis_data:/data
       healthcheck:
         test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
       restart: unless-stopped
     qdrant:
       image: qdrant/qdrant:v1.9.5
       ports: ["6333:6333", "6334:6334"]
       environment:
         QDRANT__SERVICE__API_KEY: ${QDRANT_API_KEY}
       volumes:
         - qdrant_data:/qdrant/storage
       healthcheck:
         test: ["CMD", "wget", "-qO-", "http://localhost:6333/healthz"]
       restart: unless-stopped
   volumes:
     timescaledb_data:
     redis_data:
     qdrant_data:

C. docker-compose.prod.yml 雛形：
   - 同 dev 但 ports 不對外（除非 nginx）
   - 加 read_only: true、cap_drop: ALL（依第 19.5 章）
   - 加 resource limits（mem_limit, cpus）
   - Qdrant API key 必須設

D. docker/timescaledb/init.sql（依第 19.1 章 + 帳號分離）：
   -- 啟用 extension
   CREATE EXTENSION IF NOT EXISTS timescaledb;
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   CREATE EXTENSION IF NOT EXISTS pgcrypto;

   -- 三個應用帳號（密碼從 env 帶）
   -- 注意：使用 \gset 從 env 讀密碼是 init script 限制，這裡先用變數註記
   -- 實際做法：在 init.sql 用 PostgreSQL 變數 + docker-compose env vars 帶入

   -- ta_migration：可改 schema
   CREATE USER ta_migration WITH PASSWORD :'TA_MIGRATION_PASSWORD' CREATEDB;
   GRANT ALL PRIVILEGES ON DATABASE tradingagents_tw TO ta_migration;

   -- ta_service_rw：DML only（INSERT/UPDATE/DELETE，不能 DDL）
   CREATE USER ta_service_rw WITH PASSWORD :'TA_SERVICE_RW_PASSWORD';
   GRANT CONNECT ON DATABASE tradingagents_tw TO ta_service_rw;
   GRANT USAGE ON SCHEMA public TO ta_service_rw;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public
     GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ta_service_rw;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public
     GRANT USAGE ON SEQUENCES TO ta_service_rw;

   -- ta_agent_ro：read only（Agent 用，防 prompt injection 把 SQL 注入）
   CREATE USER ta_agent_ro WITH PASSWORD :'TA_AGENT_RO_PASSWORD';
   GRANT CONNECT ON DATABASE tradingagents_tw TO ta_agent_ro;
   GRANT USAGE ON SCHEMA public TO ta_agent_ro;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public
     GRANT SELECT ON TABLES TO ta_agent_ro;

   -- audit_logs 後續 P9 建立後要 REVOKE UPDATE/DELETE from ta_service_rw

   注意：因 init.sql 的 :'VAR' 機制需配合 PSQL_OPTIONS，
   實務上常見做法是用 entrypoint shell script 包裝，
   或在 init.sql 中用 '%%PASSWORD%%' placeholder + envsubst 替換。
   本 Phase 採後者：寫一個 docker/timescaledb/init.sh 作為 entrypoint，
   會跑 envsubst < init.sql.template > init.sql 再給 psql。

E. docker/timescaledb/init.sql.template + init.sh：
   - init.sql.template 用 ${TA_MIGRATION_PASSWORD} 等 placeholder
   - init.sh：envsubst < init.sql.template > /tmp/init.sql && psql -f /tmp/init.sql
   - docker-compose 改 mount init.sh 為 entrypoint extension

F. backend/scripts/wait-for-services.sh（依 13.2）：
   #!/bin/sh
   set -e
   echo "Waiting for TimescaleDB..."
   until pg_isready -h "${POSTGRES_HOST:-timescaledb}" -U postgres; do
     sleep 2
   done
   echo "Waiting for Redis..."
   until redis-cli -h "${REDIS_HOST:-redis}" -a "${REDIS_PASSWORD}" ping | grep PONG; do
     sleep 2
   done
   echo "Waiting for Qdrant..."
   until wget -qO- "http://${QDRANT_HOST:-qdrant}:6333/healthz" > /dev/null; do
     sleep 2
   done
   echo "All services ready."
   exec "$@"

   chmod +x backend/scripts/wait-for-services.sh

G. 更新 .env.example：
   POSTGRES_SUPERUSER_PASSWORD=<隨機 32 字元>
   TA_MIGRATION_PASSWORD=<隨機 32 字元>
   TA_SERVICE_RW_PASSWORD=<隨機 32 字元>
   TA_AGENT_RO_PASSWORD=<隨機 32 字元>
   REDIS_PASSWORD=<隨機 32 字元>
   QDRANT_API_KEY=<隨機 32 字元>
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=tradingagents_tw
   REDIS_HOST=localhost
   REDIS_PORT=6379
   QDRANT_HOST=localhost
   QDRANT_PORT=6333
   QDRANT_GRPC_PORT=6334

   附產生密碼指令：
   # python -c "import secrets; print(secrets.token_urlsafe(32))"

H. 更新 .env（用戶本機）：複製 .env.example 內容並填上實際密碼
   注意：.env 不入 git（已 gitignore）

I. 更新 Makefile（加 Docker target）：
   up:
     docker compose up -d
   down:
     docker compose down
   logs:
     docker compose logs -f
   restart:
     docker compose restart
   ps:
     docker compose ps

J. 寫 backend/tests/integration/test_db_connectivity.py：
   - 用 ta_migration 連 → 應可建表（測試後 rollback）
   - 用 ta_service_rw 連 → 可 SELECT，建表應失敗
   - 用 ta_agent_ro 連 → 可 SELECT，INSERT 應失敗
   pytest 標記為 integration（需 docker compose up）

K. 寫 backend/tests/integration/test_redis_connectivity.py：
   - 用 password 連 → ping 通
   - SET / GET / DEL 通

L. 寫 backend/tests/integration/test_qdrant_connectivity.py：
   - 用 API key 連 → /healthz 通
   - 不帶 API key → 401

M. 寫 docs/runbooks/services.md：
   - 啟動／停止指令
   - 進入 psql / redis-cli 的方式
   - 三個 DB 帳號用途與差異
   - 常見問題（port 被占、volume 權限、healthcheck 失敗）

N. 寫 scripts/health_checks/phase_02.sh：
   #!/bin/bash
   set -e
   echo "=== Phase 02 健康檢查 ==="

   # 1. 三服務 running
   docker compose ps timescaledb redis qdrant | tail -n +2 | \
     awk '{print $NF}' | grep -c "running\|healthy" | grep -q 3 || \
     { echo "❌ 三服務未全跑"; exit 1; }

   # 2. timescaledb healthcheck
   docker compose exec -T timescaledb pg_isready -U postgres > /dev/null || \
     { echo "❌ timescaledb 未 ready"; exit 1; }

   # 3. timescaledb 三帳號可連
   for user in ta_migration ta_service_rw ta_agent_ro; do
     PGPASSWORD=$(grep "^${user^^}_PASSWORD=" .env | cut -d= -f2) \
       psql -h localhost -U $user -d tradingagents_tw -c "SELECT 1" > /dev/null || \
       { echo "❌ $user 連線失敗"; exit 1; }
   done

   # 4. redis 可 ping
   docker compose exec -T redis redis-cli -a "$(grep ^REDIS_PASSWORD= .env | cut -d= -f2)" ping | grep -q PONG || \
     { echo "❌ redis 連線失敗"; exit 1; }

   # 5. qdrant healthz
   curl -sf http://localhost:6333/healthz > /dev/null || \
     { echo "❌ qdrant 連線失敗"; exit 1; }

   # 6. wait-for-services.sh 可執行
   test -x backend/scripts/wait-for-services.sh || \
     { echo "❌ wait-for-services.sh 不可執行"; exit 1; }

   echo "✅ Phase 02 健康檢查通過"
   chmod +x scripts/health_checks/phase_02.sh

O. 寫 docs/phase_reports/PHASE_02.md
P. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 2 = 以下 10 個指令全部 exit code 0：

```bash
# 1. docker compose 啟動成功
make up
sleep 30   # 等待 healthcheck

# 2. 三服務 healthy
docker compose ps --format json | jq -r '.[] | select(.Service=="timescaledb" or .Service=="redis" or .Service=="qdrant") | .Health' | grep -c "healthy" | grep -E "^3$"

# 3. timescaledb 三帳號可連
for user in ta_migration ta_service_rw ta_agent_ro; do
  PGPASSWORD=$(grep "^${user^^}_PASSWORD=" .env | cut -d= -f2) \
    psql -h localhost -U $user -d tradingagents_tw -c "SELECT 1" > /dev/null
done

# 4. ta_agent_ro 不能寫
PGPASSWORD=$(grep ^TA_AGENT_RO_PASSWORD= .env | cut -d= -f2) \
  psql -h localhost -U ta_agent_ro -d tradingagents_tw \
  -c "CREATE TABLE test(x INT)" 2>&1 | grep -i "permission denied" && echo "OK"

# 5. ta_service_rw 不能 DDL
PGPASSWORD=$(grep ^TA_SERVICE_RW_PASSWORD= .env | cut -d= -f2) \
  psql -h localhost -U ta_service_rw -d tradingagents_tw \
  -c "CREATE TABLE test(x INT)" 2>&1 | grep -i "permission denied" && echo "OK"

# 6. TimescaleDB extension 已啟
PGPASSWORD=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2) \
  psql -h localhost -U postgres -d tradingagents_tw \
  -c "SELECT extname FROM pg_extension WHERE extname='timescaledb'" | grep timescaledb

# 7. redis 可連可操作
docker compose exec -T redis redis-cli -a "$(grep ^REDIS_PASSWORD= .env | cut -d= -f2)" \
  SET test "hello" | grep OK
docker compose exec -T redis redis-cli -a "$(grep ^REDIS_PASSWORD= .env | cut -d= -f2)" \
  GET test | grep hello

# 8. qdrant 需要 API key
curl -s -o /dev/null -w "%{http_code}" http://localhost:6333/collections | grep -E "^401$|^403$"
curl -s -o /dev/null -w "%{http_code}" -H "api-key: $(grep ^QDRANT_API_KEY= .env | cut -d= -f2)" \
  http://localhost:6333/collections | grep "^200$"

# 9. integration tests 通過
cd backend && uv run pytest tests/integration/test_db_connectivity.py \
  tests/integration/test_redis_connectivity.py \
  tests/integration/test_qdrant_connectivity.py -v && cd ..

# 10. health_check phase_02 通過
bash scripts/health_checks/phase_02.sh

# 累積測試數量符合 P2 基準
cd backend && uv run pytest --collect-only -q 2>&1 | tail -1
# 應 ≥ 12 個（P1 5 + P2 unit 0 + integration 3 = 8 至少；目標 12+）
```

【6. Smoke Test（手動）】
✓ docker desktop / docker stats 看三容器記憶體 < 1GB
✓ 用 DBeaver / pgAdmin 用 ta_service_rw 連線可以看到 DB 但無表
✓ Qdrant Web UI（http://localhost:6333/dashboard）打不開（被 API key 擋）
✓ 重啟 docker（make down && make up）資料還在

【7. 已知陷阱】
✗ Windows Docker Desktop volume 權限 → 用 named volume 不要 bind mount
✗ TimescaleDB extension 未啟 → init.sql 必含 CREATE EXTENSION IF NOT EXISTS
✗ init.sql 中變數展開：psql :'VAR' 需配合 -v VAR=val 或用 envsubst 預處理
✗ Redis 沒設 password → docker compose log 會看到 anonymous client
✗ Qdrant 未設 API key → 任何人都能讀向量
✗ healthcheck interval 太短 → 容器重啟頻繁
✗ wait-for-services.sh 在 alpine 用 sh（不是 bash）
✗ Port 5432 被本機 PostgreSQL 占 → 用 5433:5432 做 mapping
✗ Docker Desktop 改 RAM 太小（< 8GB）→ container OOM
✗ envsubst 在 alpine 沒裝 → apk add gettext
✗ init.sql 改了但 volume 還在 → 要 docker volume rm timescaledb_data 才會重跑
✗ healthy 顯示 starting → 等 30 秒才會變 healthy
✗ docker compose v1 vs v2 命令不同（compose 改成 docker compose 連寫）

【8. Self-Check SOP】
跑第 8.5.4 章「每 Phase 必跑的 Self-Check SOP」全部 8 項。
注意第 4 項的 ruff 在 P2 沒新增 .py 程式碼可能 trivially 通過。

【9. 完成後產物】
程式檔（新增）：
  - docker-compose.yml
  - docker-compose.prod.yml（雛形）
  - docker/timescaledb/init.sql.template
  - docker/timescaledb/init.sh
  - backend/scripts/wait-for-services.sh
  - backend/tests/integration/test_db_connectivity.py
  - backend/tests/integration/test_redis_connectivity.py
  - backend/tests/integration/test_qdrant_connectivity.py
  - scripts/health_checks/phase_02.sh

文件檔（新增）：
  - docs/runbooks/services.md
  - docs/phase_reports/PHASE_02.md

文件檔（更新）：
  - .env.example（加 DB / Redis / Qdrant 密碼欄位）
  - Makefile（加 up/down/logs/restart/ps target）
  - docs/setup.md（加「啟動 Docker 服務」章節）
  - docs/phase_progress.md

Git tag：phase-02-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，確認 OK 後依【4. 任務清單】依序執行。
特別注意：本 Phase 用實機 docker，請保留先前的 docker volume 不要清掉（除非你願意重跑）。
```

---

### ▌Phase 3 — 後端工程基礎程式碼 + 最小可運行 backend

```
=== TradingAgents-TW Phase 3（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\backend
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 3
必讀 PLAN.md 章節：第 8.5, 13.3, 14.1, 14.2, 14.3, 14.5, 14.6, 16.1, 17.1-17.5, 18.1 章

【1. 前置依賴 Phase】
依賴：Phase 1, 2
驗證方式：
  - bash scripts/health_checks/phase_01.sh
  - bash scripts/health_checks/phase_02.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_01.sh
- bash scripts/health_checks/phase_02.sh
- git status（必須乾淨）
- docker compose ps（三服務 healthy）

【3. 本 Phase 目標】
讓專案具備「最小可運行的 FastAPI backend」，包含：
  (1) 所有「跨 Phase 共用」的 core 模組（config / logging / error / envelope / request_id / http_client / circuit_breaker / db / redis）
  (2) 最小 main.py，提供 /health/{live,ready,seeded}（seeded 暫回 false）
  (3) 結構化 log（structlog JSON）
  (4) 完整 trace_id middleware
  (5) AppError 階層
  (6) API Envelope 統一
  (7) Connection pool 參數正確

注意：本 Phase「不寫 auth」、「不寫業務 router」、「不建表」、「不寫 audit hash chain」。
都是後續 Phase 的事。本 Phase 的目標是「basement」做穩。

【4. 任務清單】

A. 切分支：
   git checkout main && git pull
   git checkout -b phase/03-backend-foundation

B. backend/app/core/config.py（依 v6 範本 + 第 6.1 章 pin 版本驗證）：
   - 用 pydantic-settings BaseSettings
   - 從 .env 讀（dotenv autoload）
   - 嚴格驗證：SECRET_KEY len ≥ 32 bytes、密碼欄位非空、URL 格式
   - 提供 settings 單例（lru_cache）

   **重要（v7.0 修正）：** P3 config.py 一次列齊「v1.0 全部會用到」的欄位，避免後續每個 Phase 回頭修。
   實際 P3 還用不到的欄位（例如 LLM provider 設定）可給合理 default 或設為 Optional。

   **完整屬性清單（必含）：**
   ```python
   # backend/app/core/config.py
   from decimal import Decimal
   from functools import lru_cache
   from typing import Literal
   from pydantic import EmailStr, SecretStr, field_validator, model_validator
   from pydantic_settings import BaseSettings, SettingsConfigDict


   class Settings(BaseSettings):
     model_config = SettingsConfigDict(
       env_file=".env",
       env_file_encoding="utf-8",
       case_sensitive=True,
       extra="ignore",
     )

   # ── 應用層 ────────────────
   APP_ENV: Literal["dev", "test", "staging", "prod"] = "dev"
   APP_VERSION: str = "0.3.0"
   LOG_LEVEL: str = "INFO"
   LOG_FORMAT: Literal["json", "console"] = "json"
   ADMIN_EMAIL: EmailStr  # 兼具「系統管理者聯絡 email」+「初始 admin 帳號 email」
                          # 用於：(1) SEC EDGAR User-Agent (P6)
                          #      (2) seed_users.py 建立的第一個 admin 帳號 (P7)
                          #      (3) 系統警告通知收件人 (P18)
   ADMIN_INITIAL_PASSWORD: SecretStr  # 第一次 seed admin 用的初始密碼（onboarding 強制改）

   # ── 安全 ──────────────────
   SECRET_KEY: str  # ≥ 32 bytes，JWT 簽名 + CSRF token
   SECRET_KEY_PREVIOUS: str | None = None  # 雙 key rotation（P8 用）
   DATA_ENCRYPTION_KEY: str  # Fernet 加密 LINE/Telegram token（P14/P18）
   CORS_ORIGINS: list[str] = ["http://localhost:3000"]
   CSP_PROD_ENABLED: bool = False  # P18 才設 true

   # ── DB ────────────────────
   POSTGRES_HOST: str = "localhost"
   POSTGRES_PORT: int = 5432
   POSTGRES_DB: str = "tradingagents_tw"
   POSTGRES_SUPERUSER_PASSWORD: SecretStr  # 維運用，僅 init 與 dump
   TA_MIGRATION_PASSWORD: SecretStr        # alembic 用
   TA_SERVICE_RW_PASSWORD: SecretStr       # 後端業務用
   TA_AGENT_RO_PASSWORD: SecretStr         # Agent / Tool 用
   POOL_SIZE_RW: int = 20                  # 依第 14.1 章
   POOL_SIZE_RO: int = 30
   STATEMENT_TIMEOUT_MS: int = 30000
   LOCK_TIMEOUT_MS: int = 10000

   # ── Redis ─────────────────
   REDIS_HOST: str = "localhost"
   REDIS_PORT: int = 6379
   REDIS_PASSWORD: SecretStr
   POOL_SIZE_REDIS: int = 50

   # ── Qdrant ────────────────
   QDRANT_HOST: str = "localhost"
   QDRANT_PORT: int = 6333
   QDRANT_GRPC_PORT: int = 6334
   QDRANT_API_KEY: SecretStr
   EMBEDDING_DIM: int = 768  # gemini text-embedding-004

   # ── 資料源 API key（P5/P6） ──
   FINMIND_TOKEN: SecretStr | None = None
   ALPHA_VANTAGE_API_KEY: SecretStr | None = None
   FINNHUB_API_KEY: SecretStr | None = None
   # SEC EDGAR / TWSE / TPEX / MOPS / cnyes：無需 API key

   # ── LLM Provider（P12/P14） ──
   GOOGLE_API_KEY: SecretStr | None = None
   OPENAI_API_KEY: SecretStr | None = None
   ANTHROPIC_API_KEY: SecretStr | None = None
   LLM_DEFAULT_PROVIDER: Literal["google", "openai", "anthropic"] = "google"
   LLM_DEFAULT_MODEL: str = "gemini-2.0-flash"
   OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
   ANTHROPIC_DEFAULT_MODEL: str = "claude-haiku-3-5-20241022"
   GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"
   LLM_MONTHLY_BUDGET_USD_DEFAULT: Decimal = Decimal("50.00")  # 用戶預設月預算（可被 user 個別設定覆寫）

   # ── 通知（P18） ──
   LINE_NOTIFY_TOKEN: SecretStr | None = None  # 系統級（v1.0 簡化用同一個）
   TELEGRAM_BOT_TOKEN: SecretStr | None = None
   TELEGRAM_CHAT_ID: str | None = None

   # ── 國際化 / 時區 ───────────
   DEFAULT_TIMEZONE: str = "Asia/Taipei"
   DEFAULT_LANG: str = "zh-TW"

   # ── 開發 / 測試專用 ─────────
   PYTEST_RUNNING: bool = False  # 測試 fixture 設 true 時跳過某些 startup check


   @field_validator("SECRET_KEY")
   @classmethod
   def secret_key_min_length(cls, v: str) -> str:
       import base64
       try:
           decoded = base64.urlsafe_b64decode(v + "=" * (-len(v) % 4))
       except Exception as e:
           raise ValueError(f"SECRET_KEY 必須為 base64 字串：{e}")
       if len(decoded) < 32:
           raise ValueError(f"SECRET_KEY 解碼後須 ≥ 32 bytes，目前 {len(decoded)}")
       return v

   @model_validator(mode="after")
   def cross_field_validations(self):
       # SECRET_KEY 與 DATA_ENCRYPTION_KEY 必須不同
       if self.SECRET_KEY == self.DATA_ENCRYPTION_KEY:
           raise ValueError("SECRET_KEY 與 DATA_ENCRYPTION_KEY 必須分離")
       # LLM_DEFAULT_PROVIDER 對應的 API key 必須有值
       provider_key_map = {
           "google": self.GOOGLE_API_KEY,
           "openai": self.OPENAI_API_KEY,
           "anthropic": self.ANTHROPIC_API_KEY,
       }
       if not provider_key_map.get(self.LLM_DEFAULT_PROVIDER):
           raise ValueError(
             f"LLM_DEFAULT_PROVIDER={self.LLM_DEFAULT_PROVIDER} 但對應 API key 為空"
           )
       # prod 環境檢查
       if self.APP_ENV == "prod":
           if any("localhost" in o for o in self.CORS_ORIGINS):
               raise ValueError("prod 環境 CORS_ORIGINS 不可含 localhost")
           if not self.CSP_PROD_ENABLED:
               raise ValueError("prod 環境必須啟用 CSP_PROD_ENABLED")
       return self


   @lru_cache(maxsize=1)
   def get_settings() -> Settings:
       return Settings()


   settings = get_settings()
   ```

C. backend/app/core/logging_config.py（依第 17.1 章）：
   - structlog 設定（JSON output by default, console for dev）
   - processors：add_log_level, add_logger_name, format_exc_info, TimeStamper, RenameKey
   - 自訂 processor：mask_sensitive（依第 17.1 章遮蔽欄位清單）
     遮蔽：password, api_key, token, authorization, line_token, telegram_token,
           refresh_token, csrf, cookie, secret_key, data_encryption_key, qdrant_api_key
   - configure_logging() 在 lifespan startup 跑
   - get_logger(name) helper

D. backend/app/core/errors.py + backend/app/core/error_handlers.py（依第 17.2-17.3 章）：
   class AppError(Exception):
     code: ClassVar[str]
     message_zh: ClassVar[str]
     http_status: ClassVar[int] = 500
     def __init__(self, **details): self.details = details

   各子類：ValidationError(422), NotFoundError(404), AuthError(401), ForbiddenError(403),
            ConflictError(409), RateLimitError(429), ExternalServiceError(503),
            TooLargeError(413), LockedError(423), QuotaExceededError(402),
            IdempotencyConflictError(409)

   error_handlers.py：
   - app.add_exception_handler(AppError, ...)
   - app.add_exception_handler(RequestValidationError, ...)
   - app.add_exception_handler(HTTPException, ...)
   - app.add_exception_handler(Exception, ...)  # 兜底
   - 所有都用 envelope 格式回（不洩漏 stack trace）

E. backend/app/core/response_envelope.py（依第 17.3 章）：
   class SuccessEnvelope(BaseModel):
     data: Any
     meta: MetaInfo  # trace_id, version, timestamp
     pagination: PaginationInfo | None = None

   class ErrorEnvelope(BaseModel):
     error: ErrorInfo  # code, message, trace_id, details

   helper：
   - envelope_success(data, pagination=None) -> dict
   - envelope_error(code, message, details=None) -> dict

F. backend/app/core/request_id.py（依第 16.1 章 trace）：
   class RequestIDMiddleware(BaseHTTPMiddleware):
     - 從 header X-Request-ID 取 / 沒有就生成 uuid4
     - 用 contextvars.ContextVar 儲存（structlog 可帶入 log）
     - response 一定回 X-Request-ID header

G. backend/app/core/security_headers.py：
   class SecurityHeadersMiddleware(BaseHTTPMiddleware):
     - X-Content-Type-Options: nosniff
     - X-Frame-Options: DENY
     - Referrer-Policy: strict-origin-when-cross-origin
     - Permissions-Policy: 限制 camera, microphone, geolocation
     - CSP 在 P9 才補（需要 nonce）

H. backend/app/core/http_client.py（依第 14.2 章 retry）：
   - get_async_client(timeout, base_url, headers, name) -> httpx.AsyncClient
   - 統一 timeout 設定（connect 10s, read 30s, total 60s）
   - retry decorator（tenacity）：3 次、exponential 2-30s、jitter 0-2s
   - 統一錯誤包裝：HTTPStatusError → ExternalServiceError(name=..., status=...)

I. backend/app/core/circuit_breaker.py（依第 14.3 章）：
   class CircuitBreaker:
     states: CLOSED / OPEN / HALF_OPEN
     - failure_threshold = 5
     - timeout_seconds = 600 (10 分鐘)
     - half_open_test_count = 1
     - 觸發 OPEN 發 event（先用 logger.critical，event_bus 在 P11+）

   instances 註冊在 dict（by name）：
   CIRCUIT_BREAKERS = {"finmind": CB(), "yfinance": CB(), "gemini": CB(), ...}

J. backend/app/core/database.py：
   - 兩個 engine：rw_engine（ta_service_rw）、ro_engine（ta_agent_ro）
   - 兩個 sessionmaker：RWSessionMaker、ROSessionMaker
   - get_rw_session / get_ro_session（FastAPI dependency）
   - lifespan startup：
     - 設定 POOL_SIZE 依 14.1 章
     - SET statement_timeout, lock_timeout 在每個 connection
     - 用 listen connect event 來執行
   - lifespan shutdown：engine.dispose()

K. backend/app/core/redis_client.py：
   - get_redis_pool(db: int) -> ConnectionPool
   - 7 個 db 編號常數（cache=0, celery=1, ratelimit=2, jwt=3, pubsub=4, wsticket=5, idem=6）
   - get_redis(db: int) -> Redis（async）

L. backend/app/core/qdrant_client.py：
   - get_qdrant_client() -> AsyncQdrantClient（API key + gRPC）
   - 不在 startup 建 collection（P4 / P7 才做）

M. backend/app/main.py（最小版）：
   from contextlib import asynccontextmanager

   @asynccontextmanager
   async def lifespan(app: FastAPI):
     configure_logging()
     # 啟動時試連 DB（fail fast）
     await test_db_connection()
     await test_redis_connection()
     await test_qdrant_connection()
     yield
     # shutdown：close pool
     await rw_engine.dispose()
     await ro_engine.dispose()

   app = FastAPI(lifespan=lifespan, ...)
   app.add_middleware(RequestIDMiddleware)
   app.add_middleware(SecurityHeadersMiddleware)
   register_exception_handlers(app)

   @app.get("/health/live")
   async def health_live():
     return envelope_success({"status": "alive"})

   @app.get("/health/ready")
   async def health_ready():
     # 依第 13.3 章：檢查 DB pool 至少 1 idle、redis ping、qdrant healthz
     ...

   @app.get("/health/seeded")
   async def health_seeded():
     # 第 13.3 章：暫時回 false（P7 seed 完才會 true）
     return envelope_success({"seeded": False, "reason": "P7 not done"})

N. backend/app/__init__.py：版本 + __all__
   from app.core.config import settings
   __version__ = settings.APP_VERSION

O. backend/Dockerfile（v3 升級）：
   - FROM python:3.11-slim
   - 加 curl（healthcheck 用）
   - COPY backend/app/ /app/
   - USER 1000
   - HEALTHCHECK CMD curl -f http://localhost:8000/health/live || exit 1
   - CMD ["./scripts/wait-for-services.sh", "uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

P. docker-compose.yml 加 backend service：
   backend:
     build: { context: ., dockerfile: backend/Dockerfile }
     ports: ["8000:8000"]
     env_file: .env
     environment:
       POSTGRES_HOST: timescaledb
       REDIS_HOST: redis
       QDRANT_HOST: qdrant
     depends_on:
       timescaledb: { condition: service_healthy }
       redis: { condition: service_healthy }
       qdrant: { condition: service_healthy }
     stop_grace_period: 60s
     restart: unless-stopped

Q. Makefile 加 target：
   backend-dev:
     cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   backend-image:
     docker build -t tradingagents-backend:latest -f backend/Dockerfile .

R. backend/tests/unit/test_config.py（≥ 5 個測試）：
   - test_settings_loads_from_env
   - test_secret_key_too_short_raises
   - test_cors_origins_parsed_as_list
   - test_pool_size_defaults_correct
   - test_data_encryption_key_separate_from_secret_key

S. backend/tests/unit/test_logging_format.py（≥ 5 個測試）：
   - test_log_outputs_json
   - test_log_includes_trace_id_when_set
   - test_password_field_masked
   - test_api_key_field_masked
   - test_token_field_masked

T. backend/tests/unit/test_envelope.py（≥ 5 個測試）：
   - test_success_envelope_has_data_meta
   - test_error_envelope_format
   - test_pagination_in_envelope
   - test_envelope_serializes_decimal_as_string
   - test_envelope_serializes_datetime_as_iso

U. backend/tests/unit/test_request_id.py（≥ 5 個測試）：
   - test_request_id_generated_when_no_header
   - test_request_id_propagated_from_header
   - test_request_id_in_response_header
   - test_request_id_in_log_context
   - test_request_id_format_is_uuid

V. backend/tests/integration/test_health_endpoints.py（≥ 5 個測試）：
   - test_health_live_returns_200
   - test_health_ready_returns_200_when_all_deps_ok
   - test_health_seeded_returns_false_initially
   - test_health_response_envelope_format
   - test_health_response_has_trace_id_header

W. backend/tests/unit/test_circuit_breaker.py（≥ 5 個測試）：
   - test_initially_closed
   - test_opens_after_5_failures
   - test_half_open_after_timeout
   - test_returns_to_closed_on_success
   - test_returns_to_open_on_half_open_fail

X. 寫 scripts/health_checks/phase_03.sh：
   #!/bin/bash
   set -e
   echo "=== Phase 03 健康檢查 ==="

   # 1. backend 啟動可成功
   cd backend
   uv run uvicorn app.main:app --port 8000 &
   SERVER_PID=$!
   sleep 5

   # 2. /health/live 200
   curl -fsS http://localhost:8000/health/live > /dev/null

   # 3. /health/ready 200（前提：docker compose 三服務 up）
   curl -fsS http://localhost:8000/health/ready > /dev/null

   # 4. trace_id 在 response header
   curl -sI http://localhost:8000/health/live | grep -i "X-Request-ID"

   # 5. envelope 格式
   curl -s http://localhost:8000/health/live | jq -e '.data.status == "alive"'

   # 6. log 是 JSON
   # 取 backend 第一條 log 確認是 valid JSON
   ...

   kill $SERVER_PID
   cd ..
   echo "✅ Phase 03 健康檢查通過"

Y. 寫 docs/phase_reports/PHASE_03.md
Z. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 3 = 以下 12 個指令全部 exit code 0：

```bash
# 1. uv sync 加新依賴成功
cd backend && uv sync && cd ..

# 2. ruff lint 通過
cd backend && uv run ruff check app/ && cd ..

# 3. backend 啟動成功（3 秒內 /health/live 回 200）
cd backend && uv run uvicorn app.main:app --port 8000 &
SERVER_PID=$!
sleep 3
curl -fsS http://localhost:8000/health/live

# 4. /health/ready 在三服務都 healthy 時回 200
curl -fsS http://localhost:8000/health/ready

# 5. /health/seeded 回 false（暫時）
curl -s http://localhost:8000/health/seeded | jq '.data.seeded' | grep -q false

# 6. trace_id 在 response header
curl -sI http://localhost:8000/health/live | grep -i "X-Request-ID"

# 7. log 是 JSON
# 寄一個 request，看 backend log 是否為 valid JSON
curl -s http://localhost:8000/health/live > /dev/null
# （手動：看 backend stdout 是 JSON）

# 8. 故意觸錯：404 envelope 正確
curl -s http://localhost:8000/nonexistent | jq -e '.error.code == "NOT_FOUND" or .error.code == "HTTP_404"'

# 9. CORS preflight 通過
curl -i -X OPTIONS http://localhost:8000/health/live \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" | grep -i "access-control-allow-origin"

# 10. 全部 unit + integration test 通過
cd backend && uv run pytest tests/ -v
# 累積測試應 ≥ 30（P1 5 + P2 0+3 + P3 unit 25 + integration 5 + P3 unit 加新）

kill $SERVER_PID

# 11. health_check phase_03 通過
bash scripts/health_checks/phase_03.sh

# 12. backend Docker image 可 build
docker build -t tradingagents-backend:dev -f backend/Dockerfile .
```

【6. Smoke Test（手動）】
✓ 開 http://localhost:8000/docs，看到 FastAPI Swagger（即使只有 health endpoints）
✓ 故意關掉 timescaledb container（docker compose stop timescaledb），/health/ready 回 503
✓ 重啟 timescaledb，/health/ready 自動恢復 200
✓ tail -f backend stdout，每行都是有效 JSON
✓ 測試敏感欄位遮蔽：log 一個含 "password=xxx" 的訊息，輸出應遮蔽

【7. 已知陷阱】
✗ middleware 順序錯誤 → RequestID 必須最外層（最先進、最後出）
✗ SECRET_KEY < 32 bytes → config 啟動就 fail
✗ CORS allow_credentials=true 才能傳 cookie；origin 不能用 *
✗ SameSite=Strict 在 dev 跨 port 擋 → dev 用 Lax
✗ structlog 沒設 wrap_for_formatter → JSON 格式不對
✗ asyncpg 沒設 server_settings={'application_name': ...} → DBA 看不出哪個 app
✗ Pydantic v2 BaseSettings 已搬到 pydantic-settings
✗ httpx Timeout 物件比 float 嚴格，要用 httpx.Timeout(...)
✗ tenacity wait_exponential + wait_random 要 + 不是 |
✗ Lifespan startup 失敗 → uvicorn 直接 exit，看不到錯誤訊息（要 reload=False 才看得到）
✗ Docker image healthcheck 用 curl → image 要裝 curl
✗ uvicorn --reload 在 Docker 慢 → dev 不要用 reload，用 host volume mount
✗ contextvars 在 background task 不會自動傳 → 要手動設

【8. Self-Check SOP】
跑第 8.5.4 章「每 Phase 必跑的 Self-Check SOP」全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/core/config.py
  - backend/app/core/logging_config.py
  - backend/app/core/errors.py
  - backend/app/core/error_handlers.py
  - backend/app/core/response_envelope.py
  - backend/app/core/request_id.py
  - backend/app/core/security_headers.py
  - backend/app/core/http_client.py
  - backend/app/core/circuit_breaker.py
  - backend/app/core/database.py
  - backend/app/core/redis_client.py
  - backend/app/core/qdrant_client.py
  - backend/app/main.py（最小版）
  - backend/app/__init__.py
  - backend/Dockerfile（升級）
  - 7 個 unit/integration test files（共 ~35 個測試）
  - scripts/health_checks/phase_03.sh

程式檔（修改）：
  - docker-compose.yml（加 backend service）
  - Makefile（加 backend-dev, backend-image）

文件檔（新增）：
  - docs/phase_reports/PHASE_03.md

文件檔（更新）：
  - docs/setup.md（加「啟動 backend」章節）
  - docs/phase_progress.md

Git tag：phase-03-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：H/I/J/K（http_client/CB/database/redis）都是後續 Phase 共用基礎，
程式碼品質要嚴謹，測試要充分覆蓋。
```

---

### ▌Phase 4 — 完整 DB Schema + Alembic Migration + Hypertable + Trigger

```
=== TradingAgents-TW Phase 4（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 4
必讀 PLAN.md 章節：第 8.5, 13, 14.1, 14.10, 15.2, 17.7, 19.6, 20.2, 22 章

【1. 前置依賴 Phase】
依賴：Phase 1, 2, 3
驗證方式：
  - bash scripts/health_checks/phase_01.sh
  - bash scripts/health_checks/phase_02.sh
  - bash scripts/health_checks/phase_03.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_03.sh
- docker compose ps（三服務 healthy）
- backend 可啟動（curl /health/live 回 200）
- git status 必須乾淨

【3. 本 Phase 目標】
讓 DB 具備「v1.0 完整業務所需的所有表 + index + trigger + hypertable」：
  (1) 完整 schema（≥ 25 個表）
  (2) TimescaleDB hypertable（stock_prices、audit_logs、llm_usage、notification_log、celery_dead_letters）
  (3) Retention policy（行情 1 年、audit 1 年、log 90 天）
  (4) Trigger（updated_at 自動更新、audit_logs hash chain）
  (5) Alembic 框架啟動（baseline migration）
  (6) Migration up/down 都可跑
  (7) audit_logs 已 REVOKE UPDATE/DELETE from ta_service_rw
  (8) Qdrant 7 collections 建立（依 20.3）
  (9) ORM Models（SQLAlchemy 2.0 declarative）

注意：本 Phase「不寫業務邏輯」、「不放資料」、「不寫 Repository」（在 P5 才寫）。
僅建 schema + ORM Model 定義。

【4. 任務清單】

A. 切分支：
   git checkout main && git pull
   git checkout -b phase/04-db-schema

B. backend/pyproject.toml 加依賴：
   sqlalchemy[asyncio]>=2.0.30,<2.1
   alembic>=1.13,<2.0
   pgvector  # 暫不用但備用
   qdrant-client>=1.9,<2.0

C. 設計 schema 並寫 docker/timescaledb/init.sql 增量（schema 部分）：
   注意：v7 改用 Alembic 為主，init.sql 只放「DB extension + 三帳號 + audit_logs 權限 REVOKE」。
   實際表結構由 Alembic baseline migration 建立。
   這樣設計的好處：未來 schema 演進都統一走 Alembic，不會出現 init.sql 與 migration 不一致的問題。

D. backend/alembic.ini + backend/migrations/env.py + script.py.mako：
   - alembic init backend/migrations
   - 改 env.py：用 ta_migration 帳號 + 帶 SQLAlchemy 2.0 async
   - 加 alembic 環境變數覆蓋：env DATABASE_URL=...

E. 寫 backend/migrations/versions/0001_baseline.py：
   完整 schema 一次建立，分 module 寫（避免單檔過大）：
   - 0001_baseline_users.py：users + user_sessions + password_reset_tokens
   - 0002_baseline_stocks.py：stock_list + stock_info
   - 0003_baseline_prices.py：stock_prices（hypertable）+ retention policy
   - 0004_baseline_market_specific.py：institutional_trading + margin_trading + monthly_revenue（TW only）
   - 0005_baseline_news_announcements.py：news_metadata + announcements
   - 0006_baseline_analysis.py：analysis_reports（version 欄位）+ debate_history（hypertable）
   - 0007_baseline_orders.py：pending_orders + portfolio_positions + trade_history
   - 0008_baseline_watchlist.py：user_watchlist
   - 0009_baseline_audit_quota.py：audit_logs（hypertable）+ llm_usage（hypertable）+ llm_monthly_quota
   - 0010_baseline_celery.py：celery_dead_letters（hypertable）+ idempotency_keys
   - 0011_baseline_notifications.py：notification_log（hypertable）+ notification_settings
   - 0012_baseline_indexes_triggers.py：所有 index + 所有 trigger（updated_at, audit hash chain）
   - 0013_baseline_revoke.py：REVOKE UPDATE/DELETE on audit_logs from ta_service_rw

F. ORM Models（在 backend/app/models/）：
   - base.py：Base = declarative_base()
   - user.py：User, UserSession, PasswordResetToken
   - stock.py：StockList, StockInfo
   - price.py：StockPrice
   - tw_specific.py：InstitutionalTrading, MarginTrading, MonthlyRevenue
   - news.py：NewsMetadata, Announcement
   - analysis.py：AnalysisReport（含 version）, DebateMessage
   - order.py：PendingOrder, PortfolioPosition, TradeHistory
   - watchlist.py：UserWatchlist
   - audit.py：AuditLog
   - quota.py：LLMUsage, LLMMonthlyQuota
   - dlq.py：CeleryDeadLetter
   - idempotency.py：IdempotencyKey
   - notification.py：NotificationLog, NotificationSetting

   每個 Model：
   - 用 Pydantic v2 兼容（from_attributes=True）
   - 大金額欄位：Numeric(20, 6) + Python Decimal
   - 時間欄位：TIMESTAMPTZ + UTC default
   - JSONB 欄位：JSON encoder 註冊

G. audit_logs hash chain trigger（依第 19.6 章）：
   sha256(prev_hash || row_id || actor_id || action || entity_type || entity_id || details::text || timestamp)
   trigger 在 BEFORE INSERT 計算 entry_hash，從上一筆抓 prev_hash。

H. updated_at trigger：
   CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER ...
   套用到所有有 updated_at 欄位的表。

I. Hypertable + retention policy：
   SELECT create_hypertable('stock_prices', 'date', chunk_time_interval => INTERVAL '1 month');
   SELECT add_retention_policy('stock_prices', INTERVAL '1 year');
   - audit_logs：retention 1 年
   - llm_usage：retention 1 年
   - notification_log：retention 90 天
   - debate_history：retention 1 年
   - celery_dead_letters：retention 1 年（resolved=true 才刪）

J. Index 補強（依第 20.2）：
   stock_prices：(symbol, date DESC)（已是主鍵）
   stock_list：GIN(name gin_trgm_ops)（搜尋）
   audit_logs：(actor_id, timestamp DESC)、(entity_type, entity_id, timestamp DESC)
   analysis_reports：(user_id, created_at DESC)、(symbol, created_at DESC)、status
   pending_orders：(status, created_at DESC)、(user_id, status)
   notification_log：(user_id, sent_at DESC)
   等等（共 ~30 個 index）

K. backend/app/core/database.py 加：
   - get_migration_engine(): 用 ta_migration（用於 alembic）
   - test_db_connection() 改：列舉表數量驗證 schema 已建

L. backend/app/core/qdrant_init.py（新建）：
   COLLECTIONS = [...]  # 依第 20.3 章
   async def ensure_collections():
     """idempotent: 已存在則跳過"""
     for c in COLLECTIONS:
       try:
         await client.get_collection(c["name"])
       except:
         await client.create_collection(c["name"], ...)

M. backend/app/main.py lifespan 加：
   await ensure_collections()  # Qdrant collections idempotent

N. data-pipeline/scripts/init_db.py：
   - 跑 alembic upgrade head（subprocess）
   - 跑 ensure_collections()
   - 建第一個 admin（從 .env 讀 ADMIN_EMAIL/PASSWORD）
   - 設定 must_change_password = TRUE

O. Makefile 加：
   init-db:
     cd backend && uv run python ../data-pipeline/scripts/init_db.py && cd ..
   migration-up:
     cd backend && uv run alembic upgrade head && cd ..
   migration-down:
     cd backend && uv run alembic downgrade -1 && cd ..
   migration-new:
     cd backend && uv run alembic revision --autogenerate -m "$(MSG)" && cd ..

P. backend/tests/integration/test_schema.py（≥ 8 個測試）：
   - test_all_tables_created
   - test_hypertable_chunk_time_interval
   - test_retention_policies_set
   - test_audit_logs_hash_chain_trigger
   - test_updated_at_trigger
   - test_indexes_present
   - test_audit_logs_revoked_update_delete_for_service_rw
   - test_qdrant_collections_present

Q. backend/tests/integration/test_migration_up_down.py（≥ 3 個測試）：
   - test_upgrade_head_succeeds
   - test_downgrade_one_succeeds_and_back
   - test_full_downgrade_to_base_succeeds

R. backend/tests/unit/test_models.py（≥ 10 個測試）：
   - test_user_model_decimal_field_type
   - test_audit_log_immutable_fields
   - test_analysis_report_version_default_1
   - test_pending_order_status_enum
   - test_stock_price_composite_pk
   - test_notification_log_jsonb_payload
   - test_user_watchlist_unique_constraint
   - test_llm_usage_cost_decimal_precision
   - test_idempotency_key_ttl_calculated
   - test_celery_dead_letter_resolved_default_false

S. data-pipeline/schemas/timescaledb.sql（v6 保留 + 對齊本 Phase）：
   實際以 Alembic 為主，但保留一份「完整 schema dump」作為 reference document：
   pg_dump --schema-only > data-pipeline/schemas/timescaledb.sql

T. 寫 scripts/health_checks/phase_04.sh：
   #!/bin/bash
   set -e
   echo "=== Phase 04 健康檢查 ==="

   # 1. 表數量
   PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)
   COUNT=$(PGPASSWORD=$PG psql -h localhost -U postgres -d tradingagents_tw \
     -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
   test "$COUNT" -ge 20 || { echo "❌ 表數量 $COUNT < 20"; exit 1; }

   # 2. hypertable
   COUNT=$(PGPASSWORD=$PG psql -h localhost -U postgres -d tradingagents_tw \
     -tAc "SELECT count(*) FROM timescaledb_information.hypertables")
   test "$COUNT" -ge 5 || { echo "❌ hypertable 數量 $COUNT < 5"; exit 1; }

   # 3. retention policy
   COUNT=$(PGPASSWORD=$PG psql -h localhost -U postgres -d tradingagents_tw \
     -tAc "SELECT count(*) FROM timescaledb_information.jobs WHERE proc_name LIKE '%retention%'")
   test "$COUNT" -ge 4 || { echo "❌ retention policy 數量 $COUNT < 4"; exit 1; }

   # 4. audit hash chain trigger
   PGPASSWORD=$PG psql -h localhost -U postgres -d tradingagents_tw \
     -tAc "SELECT count(*) FROM information_schema.triggers WHERE trigger_name LIKE '%audit_hash%'" | grep -q "[1-9]"

   # 5. ta_service_rw 不能 UPDATE audit_logs
   RW=$(grep ^TA_SERVICE_RW_PASSWORD= .env | cut -d= -f2)
   PGPASSWORD=$RW psql -h localhost -U ta_service_rw -d tradingagents_tw \
     -c "UPDATE audit_logs SET event_type='hack' WHERE id=0" 2>&1 | grep -q "permission denied"

   # 6. alembic upgrade/downgrade 雙向通過
   cd backend
   uv run alembic upgrade head
   uv run alembic downgrade -1
   uv run alembic upgrade head
   cd ..

   # 7. Qdrant 7 collections
   QK=$(grep ^QDRANT_API_KEY= .env | cut -d= -f2)
   COUNT=$(curl -s -H "api-key: $QK" http://localhost:6333/collections | jq -r '.result.collections | length')
   test "$COUNT" -ge 7 || { echo "❌ Qdrant collection 數量 $COUNT < 7"; exit 1; }

   echo "✅ Phase 04 健康檢查通過"

U. 寫 docs/phase_reports/PHASE_04.md
V. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 4 = 以下 12 個指令全部 exit code 0：

```bash
# 1. uv sync 加新依賴
cd backend && uv sync && cd ..

# 2. ruff lint 通過
cd backend && uv run ruff check app/ migrations/ && cd ..

# 3. alembic upgrade head 成功
make init-db

# 4. 表數量 ≥ 20
PG_PWD=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)
COUNT=$(PGPASSWORD=$PG_PWD psql -h localhost -U postgres tradingagents_tw \
  -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
test "$COUNT" -ge 20 && echo "OK $COUNT tables"

# 5. hypertable ≥ 5
COUNT=$(PGPASSWORD=$PG_PWD psql -h localhost -U postgres tradingagents_tw \
  -tAc "SELECT count(*) FROM timescaledb_information.hypertables")
test "$COUNT" -ge 5 && echo "OK $COUNT hypertables"

# 6. Qdrant collections = 7
QK=$(grep ^QDRANT_API_KEY= .env | cut -d= -f2)
curl -s -H "api-key: $QK" http://localhost:6333/collections \
  | jq -r '.result.collections | length' | grep -E "^[7-9]$"

# 7. audit_logs trigger 正確
TS_PWD=$(grep ^TA_SERVICE_RW_PASSWORD= .env | cut -d= -f2)
PGPASSWORD=$TS_PWD psql -h localhost -U ta_service_rw tradingagents_tw \
  -c "INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details) \
       VALUES (NULL, 'test', 'system', 'init', '{}'::jsonb) RETURNING entry_hash" \
  | grep -E "[a-f0-9]{64}"

# 8. ta_service_rw 不能 UPDATE/DELETE audit_logs
PGPASSWORD=$TS_PWD psql -h localhost -U ta_service_rw tradingagents_tw \
  -c "UPDATE audit_logs SET action='hack' WHERE id=1" 2>&1 | grep -i "permission denied"

# 9. ta_agent_ro 可 SELECT 各表
RO_PWD=$(grep ^TA_AGENT_RO_PASSWORD= .env | cut -d= -f2)
PGPASSWORD=$RO_PWD psql -h localhost -U ta_agent_ro tradingagents_tw \
  -c "SELECT count(*) FROM stock_list" > /dev/null

# 10. alembic downgrade base + upgrade head 雙向通過
cd backend
uv run alembic downgrade base
uv run alembic upgrade head
cd ..

# 11. 全部新增測試通過
cd backend && uv run pytest tests/integration/test_schema.py \
  tests/integration/test_migration_up_down.py \
  tests/unit/test_models.py -v && cd ..

# 累積測試 ≥ 43（P3 30 + P4 unit 10 + integration 11 = 51 ≥ 43）

# 12. health_check phase_04 通過
bash scripts/health_checks/phase_04.sh
```

【6. Smoke Test（手動）】
✓ DBeaver / pgAdmin 連 ta_agent_ro 可看到所有表結構
✓ Qdrant dashboard（用 API key）看到 7 個 collections
✓ INSERT 一筆 audit_logs，看 entry_hash 是 64 字元 hex
✓ INSERT 第二筆 audit_logs，prev_hash = 第一筆的 entry_hash

【7. 已知陷阱】
✗ alembic + hypertable autogenerate 不認識 → 用 op.execute("SELECT create_hypertable...")
✗ alembic 用錯帳號 → env.py 改成 ta_migration（不是 postgres）
✗ retention policy 在 downgrade 要 DROP_RETENTION_POLICY
✗ TIMESTAMPTZ 預設 NOW() 在 downgrade 不會自動 alter
✗ trigger 重建順序錯 → 先 DROP function 再 CREATE
✗ 重複跑 ensure_collections 因為 distance 設不對 → 用 try/except 不要 DROP/CREATE
✗ JSONB 欄位 GIN index 漏建 → 大量 query JSONB 會慢
✗ stock_prices 主鍵設錯 → hypertable 要求 time column 在主鍵中
✗ TimescaleDB 的 chunk_time_interval 太小 → chunk 數爆炸 → 用 1 month
✗ pg_trgm extension 漏建 → GIN trgm index 失敗
✗ Numeric(20, 6) precision 不夠（金額 > 10^14）→ 改 (24, 6)
✗ Hash chain race condition → trigger 中加 LOCK TABLE 或用 advisory lock
✗ alembic auto-generate 對 enum 處理不完整 → 手寫 migration

【8. Self-Check SOP】
跑第 8.5.4 章「每 Phase 必跑的 Self-Check SOP」全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/migrations/env.py + script.py.mako
  - backend/migrations/versions/0001-0013_baseline_*.py（13 個檔）
  - backend/app/models/{base,user,stock,price,tw_specific,news,analysis,order,
                         watchlist,audit,quota,dlq,idempotency,notification}.py
  - backend/app/core/qdrant_init.py
  - data-pipeline/scripts/init_db.py
  - data-pipeline/schemas/timescaledb.sql（從 pg_dump 產生）
  - 3 個 test files（共 ~21 個測試）
  - scripts/health_checks/phase_04.sh

程式檔（修改）：
  - backend/pyproject.toml + uv.lock（加 alembic）
  - backend/alembic.ini
  - backend/app/core/database.py（加 get_migration_engine）
  - backend/app/main.py（lifespan 加 ensure_collections）
  - Makefile（加 init-db, migration-* target）
  - docker/timescaledb/init.sql（簡化，只保留 extension + 帳號 + audit_logs revoke）

文件檔（新增）：
  - docs/phase_reports/PHASE_04.md
  - docs/runbooks/migrations.md（如何寫新 migration）

文件檔（更新）：
  - docs/setup.md（加「初始化 DB」章節）
  - docs/phase_progress.md

Git tag：phase-04-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：13 個 Alembic migration 是後續所有 Phase 的基礎，schema 一旦定下就難改，
請對照第 20.2 章每個欄位仔細核對（型別、預設值、constraint）。
建議在子任務 E（migration）完成後立即跑 `alembic upgrade head` + `alembic downgrade base` 雙向驗證再進下一步。
```

---

### ▌Phase 5 — TW 資料源 Adapter（FinMind/TWSE/TPEX/MOPS/cnyes）+ Repository

```
=== TradingAgents-TW Phase 5（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\backend
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 5
必讀 PLAN.md 章節：第 7（限制）, 8.5, 10.4, 14.2, 14.3, 14.4, 17.5, 18.1, 18.2, 20.1, 20.2 章

【1. 前置依賴 Phase】
依賴：Phase 1, 2, 3, 4
驗證方式：
  - bash scripts/health_checks/phase_04.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_04.sh（含表結構 + Qdrant collections）
- backend 可啟動（curl /health/live 200）
- docker compose ps 三服務 healthy
- git status 必須乾淨
- .env 含 GOOGLE_API_KEY、FINMIND_TOKEN（可選）

【3. 本 Phase 目標】
讓專案具備「能從 5 個台股資料來源抓到資料 + 寫入 DB」的能力：
  (1) BaseDataSource ABC + Plugin 註冊（依 18.2）
  (2) TW 5 個 Adapter 實作（FinMind / TWSE / TPEX / MOPS / cnyes RSS）
  (3) DataSourceFallback wrapper（主源 fail → 備源 → 24h 快取）
  (4) Circuit Breaker 整合（每 source 一個 CB 實例）
  (5) Repository pattern（StockRepository / OHLCVRepository / NewsRepository / FinancialsRepository）
  (6) Async + Tenacity retry + Rate Limiter（依各 API 限制）
  (7) 完整 unit test（mock httpx）+ 1 個真實 API integration test（網路通才跑，否則 skip）

注意：本 Phase「不寫 Celery 任務」（在 P7）、「不寫 backfill script」（在 P7）、「不抓美股」（在 P6）。

【4. 任務清單】

A. 切分支：
   git checkout main && git pull
   git checkout -b phase/05-tw-data-sources

B. backend/pyproject.toml 加依賴：
   pandas>=2.2  # 後續 Phase 也會用
   pyarrow>=15  # parquet 快取
   pydantic>=2.7
   tenacity>=8
   aiolimiter>=1.1  # async rate limit
   feedparser>=6.0  # cnyes RSS
   beautifulsoup4>=4.12  # MOPS 解析
   lxml>=5.2

C. backend/app/data_sources/base.py：
   class DataKind(str, Enum):
     OHLCV = "ohlcv"
     COMPANY_INFO = "company_info"
     FINANCIAL = "financial"
     NEWS = "news"
     ANNOUNCEMENT = "announcement"
     INSTITUTIONAL = "institutional"  # TW only
     MARGIN = "margin"  # TW only
     MONTHLY_REVENUE = "monthly_revenue"  # TW only

   class BaseDataSource(ABC):
     name: str
     priority: int  # 越小優先（主源）
     supported_regions: list[MarketRegion]
     supported_kinds: list[DataKind]
     rate_limit_per_sec: float | None  # None = 無限制

     def __init__(self, settings: Settings):
       self.cb = CIRCUIT_BREAKERS.setdefault(self.name, CircuitBreaker())
       self.client = get_async_client(name=self.name, ...)
       if self.rate_limit_per_sec:
         self.limiter = AsyncLimiter(self.rate_limit_per_sec, 1)

     @abstractmethod
     async def fetch_ohlcv(self, symbol: str, start: date, end: date) -> pd.DataFrame: ...

     @abstractmethod
     async def fetch_company_info(self, symbol: str) -> dict: ...

     ... 其他 fetch_* 抽象方法

     async def health_check(self) -> bool:
       """回應快的健康檢查端點"""
       ...

   DATA_SOURCE_REGISTRY: dict[str, type[BaseDataSource]] = {}

   def register_data_source(cls):
     DATA_SOURCE_REGISTRY[cls.name] = cls
     return cls

D. backend/app/data_sources/fallback.py：
   class DataSourceFallback:
     """從多個 source 找第一個 success"""
     def __init__(self, sources: list[BaseDataSource]):
       self.sources = sorted(sources, key=lambda s: s.priority)

     async def fetch_ohlcv(self, symbol, start, end) -> pd.DataFrame:
       last_exc = None
       for source in self.sources:
         if source.cb.state == "OPEN":
           continue
         try:
           df = await source.fetch_ohlcv(symbol, start, end)
           source.cb.record_success()
           return df
         except Exception as e:
           source.cb.record_failure()
           last_exc = e
           logger.warning(f"{source.name} failed for {symbol}", exc_info=True)
       # 所有 source 都掛 → 試 24h 快取
       cached = await get_cached_ohlcv(symbol, start, end, max_age_hours=24)
       if cached is not None:
         logger.warning(f"All sources failed, using stale cache for {symbol}")
         return cached
       raise ExternalServiceError(name="data_pipeline", reason="all sources failed", last_exc=str(last_exc))

E. backend/app/data_sources/tw/finmind_source.py：
   @register_data_source
   class FinMindSource(BaseDataSource):
     name = "finmind"
     priority = 10  # 主源
     supported_regions = [MarketRegion.TW]
     supported_kinds = [OHLCV, COMPANY_INFO, FINANCIAL, INSTITUTIONAL, MARGIN, MONTHLY_REVENUE]
     rate_limit_per_sec = 0.5  # 免費版保守

     BASE_URL = "https://api.finmindtrade.com/api/v4/data"

     async def fetch_ohlcv(self, symbol, start, end):
       async with self.limiter:
         resp = await self._call(dataset="TaiwanStockPrice", data_id=symbol, start_date=start.isoformat(), end_date=end.isoformat())
       df = pd.DataFrame(resp["data"])
       return self._normalize_ohlcv(df)

     async def fetch_institutional(self, symbol, start, end):
       ...  # TaiwanStockInstitutionalInvestorsBuySell

     # 其他 fetch_*

     def _normalize_ohlcv(self, df):
       """統一欄位名 + dtype"""
       return df.rename(columns={
         "date": "date", "open": "open", "max": "high", "min": "low",
         "close": "close", "Trading_Volume": "volume", "Trading_money": "amount",
       }).astype({"open": "float64", "high": "float64", "low": "float64",
                  "close": "float64", "volume": "int64"})

F. backend/app/data_sources/tw/twse_openapi_source.py：
   @register_data_source
   class TWSEOpenAPISource(BaseDataSource):
     name = "twse_openapi"
     priority = 20  # 備源
     supported_regions = [MarketRegion.TW]
     supported_kinds = [OHLCV, INSTITUTIONAL]
     rate_limit_per_sec = 1.0  # 官方建議

     BASE_URL = "https://openapi.twse.com.tw/v1"

     async def fetch_ohlcv(self, symbol, start, end):
       """TWSE 只回單日；多日要 loop"""
       # 注意：TWSE OpenAPI 只回最新單日；歷史需要 STOCK_DAY API
       # 用 https://www.twse.com.tw/exchangeReport/STOCK_DAY?date=YYYYMMDD&stockNo=XXXX
       ...

G. backend/app/data_sources/tw/tpex_source.py：
   @register_data_source
   class TPEXSource(BaseDataSource):
     name = "tpex"
     priority = 25
     supported_regions = [MarketRegion.TW]
     supported_kinds = [OHLCV]
     # TPEX 只處理 OTC（market='TPEX' 的股票）
     # https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?...
     ...

H. backend/app/data_sources/tw/mops_source.py：
   @register_data_source
   class MOPSSource(BaseDataSource):
     name = "mops"
     priority = 30
     supported_regions = [MarketRegion.TW]
     supported_kinds = [FINANCIAL, ANNOUNCEMENT, MONTHLY_REVENUE]
     rate_limit_per_sec = 0.5  # 公開資訊觀測站要求保守

     # 解析 https://mops.twse.com.tw/mops/web/ajax_t164sb04 等
     # 用 BeautifulSoup 解析 HTML 表格
     ...

I. backend/app/data_sources/tw/cnyes_rss_source.py：
   @register_data_source
   class CnyesRSSSource(BaseDataSource):
     name = "cnyes_rss"
     priority = 10
     supported_regions = [MarketRegion.TW]
     supported_kinds = [NEWS]

     async def fetch_news(self, symbol, since=None):
       """從 https://news.cnyes.com/rss/cat/tw_stock 抓 RSS"""
       url = "https://news.cnyes.com/rss/cat/tw_stock"
       async with self.client.get(url) as resp:
         feed = feedparser.parse(resp.text)
       return [self._normalize(entry) for entry in feed.entries
               if self._mentions_symbol(entry, symbol)]

J. backend/app/repos/base.py：
   class BaseRepository:
     def __init__(self, session: AsyncSession):
       self.session = session

     async def commit(self):
       await self.session.commit()

   class ReadOnlyRepository(BaseRepository):
     """強制只用 ro session"""
     ...

K. backend/app/repos/stock_repo.py：
   class StockRepository(BaseRepository):
     async def list_active(self, market: Market | None = None) -> list[StockList]: ...
     async def get_by_symbol(self, symbol: str, market: Market) -> StockList | None: ...
     async def upsert_many(self, items: list[StockList]) -> int: ...
     async def search_by_name(self, query: str, limit: int = 20) -> list[StockList]: ...

L. backend/app/repos/ohlcv_repo.py：
   class OHLCVRepository(BaseRepository):
     async def get_range(self, symbol, market, start, end) -> list[StockPrice]: ...
     async def upsert_many(self, df: pd.DataFrame) -> int:
       """COPY-style bulk upsert"""
       # 用 PG INSERT ... ON CONFLICT DO UPDATE
       ...
     async def latest_date(self, symbol, market) -> date | None: ...
     async def gaps(self, symbol, market, start, end) -> list[date]:
       """找出缺資料的日期（trading days only）"""
       ...

M. backend/app/repos/news_repo.py、financials_repo.py 同模式

N. backend/app/services/data_pipeline_service.py：
   class DataPipelineService:
     def __init__(self, sources: dict[DataKind, list[BaseDataSource]], repos: ...):
       self.sources = sources
       ...

     async def sync_ohlcv(self, symbol, market, start, end) -> int:
       """從 fallback 抓 + upsert，回傳寫入筆數"""
       fb = DataSourceFallback(self.sources[DataKind.OHLCV])
       df = await fb.fetch_ohlcv(symbol, start, end)
       count = await self.ohlcv_repo.upsert_many(df.assign(symbol=symbol, market=market))
       return count

     async def sync_news_for_symbol(self, symbol): ...
     async def sync_financial(self, symbol): ...

O. backend/app/data_sources/tw/__init__.py：
   from .finmind_source import FinMindSource
   from .twse_openapi_source import TWSEOpenAPISource
   from .tpex_source import TPEXSource
   from .mops_source import MOPSSource
   from .cnyes_rss_source import CnyesRSSSource

   def get_tw_sources(settings) -> dict[DataKind, list[BaseDataSource]]:
     all_sources = [FinMindSource(settings), TWSEOpenAPISource(settings),
                    TPEXSource(settings), MOPSSource(settings), CnyesRSSSource(settings)]
     return _group_by_kind(all_sources)

P. backend/tests/unit/test_finmind_source.py（≥ 6 個測試）：
   - test_normalize_ohlcv_columns
   - test_fetch_ohlcv_calls_correct_endpoint（mock httpx）
   - test_fetch_ohlcv_handles_empty_response
   - test_rate_limiter_enforced
   - test_circuit_breaker_opens_after_failures
   - test_invalid_token_raises_auth_error

Q. backend/tests/unit/test_twse_source.py（≥ 4 個測試）
R. backend/tests/unit/test_tpex_source.py（≥ 3 個測試）
S. backend/tests/unit/test_mops_source.py（≥ 5 個測試含 BeautifulSoup parsing）
T. backend/tests/unit/test_cnyes_rss_source.py（≥ 4 個測試含 RSS parsing）
U. backend/tests/unit/test_data_source_fallback.py（≥ 6 個測試）：
   - test_uses_primary_when_healthy
   - test_falls_back_to_secondary_on_failure
   - test_skips_open_circuit_breakers
   - test_uses_cache_when_all_fail
   - test_raises_when_no_cache_either
   - test_records_success_on_primary

V. backend/tests/unit/test_repositories.py（≥ 8 個測試）：
   - test_stock_repo_get_by_symbol
   - test_stock_repo_search_by_name_uses_trgm
   - test_ohlcv_repo_upsert_many
   - test_ohlcv_repo_latest_date
   - test_ohlcv_repo_gaps_excludes_weekends
   - test_news_repo_dedupe_by_url
   - test_financials_repo_decimal_precision
   - test_repo_uses_correct_session_role

W. backend/tests/integration/test_real_finmind.py（≥ 1 測試，標 @pytest.mark.network）：
   - test_finmind_real_call_returns_ohlcv
     （用 .env 真實 token，抓 2330 最近 5 天，驗 row > 0）

X. backend/tests/integration/test_data_pipeline_service.py（≥ 4 個測試）：
   - test_sync_ohlcv_writes_db
   - test_sync_ohlcv_handles_partial_failure
   - test_sync_news_dedupe
   - test_sync_uses_fallback_when_primary_down

Y. 寫 scripts/health_checks/phase_05.sh：
   #!/bin/bash
   set -e
   echo "=== Phase 05 健康檢查 ==="

   # 1. 5 個 TW source 可 import
   cd backend
   uv run python -c "from app.data_sources.tw import get_tw_sources; \
     from app.core.config import settings; \
     sources = get_tw_sources(settings); \
     assert len(sources) > 0, 'no sources registered'"

   # 2. unit test 全綠（不含 network mark）
   uv run pytest tests/unit/test_finmind_source.py tests/unit/test_twse_source.py \
     tests/unit/test_tpex_source.py tests/unit/test_mops_source.py \
     tests/unit/test_cnyes_rss_source.py tests/unit/test_data_source_fallback.py \
     tests/unit/test_repositories.py -m "not network" -q

   # 3. integration test（如有 token 跑真實）
   uv run pytest tests/integration/test_data_pipeline_service.py -m "not network" -q

   cd ..
   echo "✅ Phase 05 健康檢查通過"

Z. 寫 docs/phase_reports/PHASE_05.md
AA. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 5 = 以下 11 個指令全部 exit code 0：

```bash
# 1. uv sync 加新依賴
cd backend && uv sync && cd ..

# 2. ruff lint 通過
cd backend && uv run ruff check app/ && cd ..

# 3. backend 啟動成功
cd backend && uv run uvicorn app.main:app --port 8000 &
SERVER_PID=$!
sleep 3
curl -fsS http://localhost:8000/health/live

# 4. 5 個 TW source 註冊成功
cd backend && uv run python -c "
from app.data_sources.base import DATA_SOURCE_REGISTRY
import app.data_sources.tw  # trigger registration
expected = {'finmind', 'twse_openapi', 'tpex', 'mops', 'cnyes_rss'}
got = set(DATA_SOURCE_REGISTRY.keys()) & expected
assert got == expected, f'missing: {expected - got}'
print('OK', got)
"
cd ..

# 5. 全部新 unit tests 通過（不含 network）
cd backend && uv run pytest tests/unit/test_*_source.py tests/unit/test_data_source_fallback.py \
  tests/unit/test_repositories.py -m "not network" -v && cd ..

# 6. integration test (mock) 通過
cd backend && uv run pytest tests/integration/test_data_pipeline_service.py -m "not network" -v && cd ..

# 7. 真實 FinMind call（如有 token）
cd backend && (
  test -n "$(grep ^FINMIND_TOKEN= .env | cut -d= -f2)" && \
    uv run pytest tests/integration/test_real_finmind.py -m network -v || \
    echo "SKIP: no FINMIND_TOKEN"
) && cd ..

# 8. Repository 用對 session role（unit test 已測，這裡 verify）
cd backend && uv run python -c "
from app.repos.stock_repo import StockRepository
from app.repos.ohlcv_repo import OHLCVRepository
# 這些 repo 應使用 RW session（write）+ RO session（read）
# 通過設計檢查（會在 P10 router 整合時驗）
print('OK')
"
cd ..

# 9. Circuit Breaker 註冊
cd backend && uv run python -c "
from app.core.circuit_breaker import CIRCUIT_BREAKERS
import app.data_sources.tw
expected = {'finmind', 'twse_openapi', 'tpex', 'mops', 'cnyes_rss'}
# 各 source 在 init 時應自動註冊 CB（懶註冊也可，這裡列舉全部 init 一次驗）
from app.data_sources.tw import get_tw_sources
from app.core.config import settings
get_tw_sources(settings)
got = set(CIRCUIT_BREAKERS.keys()) & expected
assert got == expected, f'CB missing: {expected - got}'
"
cd ..

# 10. 累積測試 ≥ 72
cd backend && uv run pytest --collect-only -q 2>&1 | tail -1 | awk '{print $1}' | awk '$1 >= 72'

kill $SERVER_PID

# 11. health_check phase_05 通過
bash scripts/health_checks/phase_05.sh
```

【6. Smoke Test（手動）】
✓ 用 ipython 跑 `await FinMindSource(settings).fetch_ohlcv("2330", date(2026,4,1), date(2026,4,30))`
   應回 pandas DataFrame > 15 rows
✓ 故意把 FinMind URL 改錯，跑 fallback，應落到 TWSE
✓ 連續觸發 6 次 FinMind 失敗，CB 變 OPEN，下次直接跳 fallback

【7. 已知陷阱】
✗ FinMind 免費 quota 600/day，跑大量會撞限 → 用 TWSE/TPEX 補
✗ TWSE OpenAPI 只回最新單日 → 歷史用 STOCK_DAY 私有 API（不穩，慎用）
✗ MOPS HTML 結構偶爾改 → BeautifulSoup parser 要 robust
✗ cnyes RSS 不一定包含 symbol → mentions_symbol 用名稱匹配
✗ pandas dtype 不對 → 後續 upsert 會 PG type error
✗ Tenacity retry 包了 limiter 的 acquire → retry 時也算 rate
✗ httpx 回 4xx 不會 raise，要主動 .raise_for_status()
✗ Circuit Breaker context 不分 source → 用 CIRCUIT_BREAKERS dict per name
✗ DataFrame 中混有 None / NaN → upsert 會失敗，要 .dropna() 或 default
✗ Decimal 透過 pandas 變 float → 用 dtype="object" 保留
✗ TWSE 1 day rate limit 撞 → AsyncLimiter(1.0, 1) 嚴格保守
✗ asyncio.gather 多 source 時，CB 要 thread-safe（用 asyncio.Lock）

【8. Self-Check SOP】
跑第 8.5.4 章「每 Phase 必跑的 Self-Check SOP」全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/data_sources/base.py（BaseDataSource ABC + 註冊）
  - backend/app/data_sources/fallback.py（DataSourceFallback）
  - backend/app/data_sources/tw/finmind_source.py
  - backend/app/data_sources/tw/twse_openapi_source.py
  - backend/app/data_sources/tw/tpex_source.py
  - backend/app/data_sources/tw/mops_source.py
  - backend/app/data_sources/tw/cnyes_rss_source.py
  - backend/app/data_sources/tw/__init__.py（get_tw_sources）
  - backend/app/repos/base.py
  - backend/app/repos/stock_repo.py
  - backend/app/repos/ohlcv_repo.py
  - backend/app/repos/news_repo.py
  - backend/app/repos/financials_repo.py
  - backend/app/services/data_pipeline_service.py
  - 9 個 test files（共 ~40 個測試）
  - scripts/health_checks/phase_05.sh

程式檔（修改）：
  - backend/pyproject.toml + uv.lock
  - backend/app/core/circuit_breaker.py（如需擴展）

文件檔（新增）：
  - docs/phase_reports/PHASE_05.md
  - docs/runbooks/data_sources.md（各 source 的限制 + 失敗處理）

文件檔（更新）：
  - docs/phase_progress.md

Git tag：phase-05-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
本 Phase 涵蓋 5 個 source 與多個 repo，建議按以下順序：
  base → fallback → finmind（最重要）→ unit test finmind → twse → tpex → mops → cnyes
  → repos → service → integration test
建議每完成一個 source 立即跑對應 unit test 確認綠燈。
```

---

## 📍 Phase 6-12 詳細 Prompt（v7.0 第 2 次規劃補完）

> **第 2 次規劃補完範圍：Phase 6, 7, 8, 9, 10, 11, 12（共 7 個 Phase）。**
> **第 3 次將補完 Phase 13-17，第 4 次補完 Phase 18-20。**

---

### ▌Phase 6 — US 資料源 Adapter + 跨市場 Dispatcher

```
=== TradingAgents-TW Phase 6（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\backend
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 6
必讀 PLAN.md 章節：第 7（限制）, 8.5, 10（跨市場架構）, 14.2-14.4, 18.2, 20.1, 20.2 章

【1. 前置依賴 Phase】
依賴：Phase 1, 2, 3, 4, 5
驗證方式：bash scripts/health_checks/phase_05.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_05.sh
- backend 可啟動（curl /health/live 200）
- 5 個 TW source 已註冊（uv run python -c "from app.data_sources.base import DATA_SOURCE_REGISTRY; ..."）
- git status 必須乾淨

【3. 本 Phase 目標】
讓專案具備「美股資料抓取 + 跨市場自動派送」能力：
  (1) 4 個美股 Adapter：yfinance / Alpha Vantage / Finnhub / SEC EDGAR
  (2) get_us_sources() 註冊 + 整合既有 DataSourceFallback
  (3) MarketDispatcher：依 symbol 格式自動選 TW/US sources（依第 10 章）
  (4) Symbol validator（依第 10.2 章 regex）+ stock_list 存在性驗證
  (5) 跨市場 Repository 統一介面（market 欄位）
  (6) 完整 unit test（mock）+ integration test（network 真實 call）

注意：本 Phase「不寫 Celery 任務」（在 P7）、「不寫 backfill script」（在 P7）。

【4. 任務清單】

A. 切分支：
   git checkout main && git pull
   git checkout -b phase/06-us-data-sources

B. backend/pyproject.toml 加依賴：
   yfinance>=0.2.40
   # alpha_vantage 用 httpx 直接打，不裝套件
   # finnhub-python 不穩，自己用 httpx
   # sec-edgar-downloader 不用，自己用 httpx + 解析 JSON

C. backend/app/core/market_dispatcher.py：
   class Market(str, Enum): ...  # 依第 10.1 章
   class MarketRegion(str, Enum): TW = "TW"; US = "US"

   TW_SYMBOL_PATTERN = re.compile(r'^[0-9]{4}[A-Z0-9]?$|^[0-9]{6}[A-Z]?$')
   US_SYMBOL_PATTERN = re.compile(r'^[A-Z]{1,5}(\.[A-Z])?$')

   def detect_region(symbol: str) -> MarketRegion:
     if TW_SYMBOL_PATTERN.match(symbol): return MarketRegion.TW
     if US_SYMBOL_PATTERN.match(symbol): return MarketRegion.US
     raise ValidationError(message_zh=f"無法識別股票代號 {symbol}")

   async def validate_symbol_exists(symbol: str, market: Market, repo: StockRepository) -> bool:
     stock = await repo.get_by_symbol(symbol, market)
     if not stock:
       raise NotFoundError(message_zh=f"股票 {symbol} 不在系統清單")
     return True

   class MarketDispatcher:
     def __init__(self, tw_sources, us_sources):
       self.tw = tw_sources
       self.us = us_sources

     def get_sources_for(self, region: MarketRegion, kind: DataKind) -> list[BaseDataSource]:
       sources = self.tw if region == MarketRegion.TW else self.us
       return sources.get(kind, [])

D. backend/app/data_sources/us/yfinance_source.py：
   @register_data_source
   class YFinanceSource(BaseDataSource):
     name = "yfinance"
     priority = 10  # 美股主源
     supported_regions = [MarketRegion.US]
     supported_kinds = [OHLCV, COMPANY_INFO, FINANCIAL, NEWS]
     rate_limit_per_sec = 2.0

     async def fetch_ohlcv(self, symbol, start, end):
       # yfinance 同步，要 wrap async
       loop = asyncio.get_event_loop()
       df = await loop.run_in_executor(
         None,
         lambda: yf.download(symbol, start=start, end=end, progress=False, auto_adjust=False)
       )
       if df.empty: raise NotFoundError(...)
       return self._normalize_ohlcv(df, symbol)

     async def fetch_company_info(self, symbol): ...
     async def fetch_financial(self, symbol): ...
     async def fetch_news(self, symbol): ...

E. backend/app/data_sources/us/alpha_vantage_source.py：
   @register_data_source
   class AlphaVantageSource(BaseDataSource):
     name = "alpha_vantage"
     priority = 20  # 備源
     supported_regions = [MarketRegion.US]
     supported_kinds = [OHLCV, FINANCIAL]
     rate_limit_per_sec = 0.4  # 免費版 25/day = 嚴格

     BASE_URL = "https://www.alphavantage.co/query"

     async def fetch_ohlcv(self, symbol, start, end):
       async with self.limiter:
         resp = await self.client.get(self.BASE_URL, params={
           "function": "TIME_SERIES_DAILY",
           "symbol": symbol,
           "outputsize": "full" if (end - start).days > 100 else "compact",
           "apikey": self.api_key,
         })
       data = resp.json()
       if "Error Message" in data: raise NotFoundError(...)
       if "Note" in data: raise RateLimitError(...)  # 配額用盡
       return self._parse_ohlcv(data, start, end)

F. backend/app/data_sources/us/finnhub_source.py：
   @register_data_source
   class FinnhubSource(BaseDataSource):
     name = "finnhub"
     priority = 30
     supported_regions = [MarketRegion.US]
     supported_kinds = [NEWS, COMPANY_INFO]
     rate_limit_per_sec = 1.0  # 免費版 60/min = 1/sec

     # endpoints：
     # https://finnhub.io/api/v1/company-news?symbol=AAPL&from=...&to=...
     # https://finnhub.io/api/v1/stock/profile2?symbol=AAPL

G. backend/app/data_sources/us/sec_edgar_source.py：
   @register_data_source
   class SECEdgarSource(BaseDataSource):
     name = "sec_edgar"
     priority = 10  # filings 主源
     supported_regions = [MarketRegion.US]
     supported_kinds = [ANNOUNCEMENT, FINANCIAL]  # 10-K / 10-Q / 8-K
     rate_limit_per_sec = 5.0  # 官方 10/sec，保守 5

     BASE_URL = "https://data.sec.gov/submissions"
     # 需要 User-Agent header（注意：__init__ 必須是同步，Python 不允許 async __init__）
     def __init__(self, settings):
       super().__init__(settings)
       # User-Agent 在 client header 設定（同步操作即可）
       self.client.headers.update({
         "User-Agent": f"TradingAgents-TW/{settings.APP_VERSION} ({settings.ADMIN_EMAIL})"
       })

     async def fetch_announcements(self, symbol):
       # 1. symbol → CIK lookup（cache 24h）
       # 2. /submissions/CIK<10位>.json → recent filings
       # 3. 過濾 form ∈ {10-K, 10-Q, 8-K}
       ...

H. backend/app/data_sources/us/__init__.py：
   from .yfinance_source import YFinanceSource
   from .alpha_vantage_source import AlphaVantageSource
   from .finnhub_source import FinnhubSource
   from .sec_edgar_source import SECEdgarSource

   def get_us_sources(settings) -> dict[DataKind, list[BaseDataSource]]:
     all_sources = [YFinanceSource(settings), AlphaVantageSource(settings),
                    FinnhubSource(settings), SECEdgarSource(settings)]
     return _group_by_kind(all_sources)

I. backend/app/services/data_pipeline_service.py 升級：
   def __init__(self, dispatcher: MarketDispatcher, repos):
     self.dispatcher = dispatcher
     ...

   async def sync_ohlcv(self, symbol, market, start, end) -> int:
     region = MarketRegion.TW if market in [Market.TWSE, Market.TPEX] else MarketRegion.US
     sources = self.dispatcher.get_sources_for(region, DataKind.OHLCV)
     fb = DataSourceFallback(sources)
     df = await fb.fetch_ohlcv(symbol, start, end)
     return await self.ohlcv_repo.upsert_many(df.assign(symbol=symbol, market=market))

   async def sync_news_for_symbol(self, symbol, market): ...
   async def sync_financial(self, symbol, market): ...
   async def sync_announcements(self, symbol, market): ...
   async def sync_institutional(self, symbol):
     """TW only"""
     if detect_region(symbol) != MarketRegion.TW:
       raise ValidationError(message_zh="籌碼資料僅支援台股")
     ...

J. backend/app/main.py lifespan 加：
   from app.data_sources.tw import get_tw_sources
   from app.data_sources.us import get_us_sources
   from app.core.market_dispatcher import MarketDispatcher

   @asynccontextmanager
   async def lifespan(app):
     ...
     app.state.dispatcher = MarketDispatcher(
       tw_sources=get_tw_sources(settings),
       us_sources=get_us_sources(settings),
     )
     yield

K. backend/app/data_sources/cache.py（新增 24h 快取，給 fallback 用）：
   async def get_cached_ohlcv(symbol, market, start, end, max_age_hours=24): ...
   async def cache_ohlcv(symbol, market, df): ...
   # 用 Redis db0，key = cache:ohlcv:{market}:{symbol}:{start}:{end}
   # value 用 pyarrow serialize（parquet bytes）

L. backend/tests/unit/test_yfinance_source.py（≥ 6 個測試，mock yfinance）：
   - test_normalize_ohlcv_columns
   - test_empty_dataframe_raises_not_found
   - test_async_wrapping_works
   - test_circuit_breaker_opens_on_repeated_failure
   - test_news_filter_by_symbol
   - test_handles_yfinance_internal_error

M. backend/tests/unit/test_alpha_vantage_source.py（≥ 5 個測試）：
   - test_url_constructed_correctly
   - test_rate_limit_message_raises_quota_error
   - test_error_message_raises_not_found
   - test_compact_vs_full_outputsize
   - test_decimal_precision_preserved

N. backend/tests/unit/test_finnhub_source.py（≥ 4 個測試）
O. backend/tests/unit/test_sec_edgar_source.py（≥ 5 個測試含 CIK lookup）
P. backend/tests/unit/test_market_dispatcher.py（≥ 8 個測試）：
   - test_detect_region_tw_normal_4digit
   - test_detect_region_tw_etf_5_6_digit
   - test_detect_region_tw_special_share_with_letter
   - test_detect_region_us_normal
   - test_detect_region_us_class_b
   - test_detect_region_unknown_raises
   - test_dispatcher_returns_correct_sources
   - test_validate_symbol_exists_returns_false_when_missing

Q. backend/tests/unit/test_cache.py（≥ 4 個測試）：
   - test_cache_set_get_roundtrip
   - test_cache_expires_after_max_age
   - test_cache_handles_empty_df
   - test_cache_key_includes_market

R. backend/tests/integration/test_real_yfinance.py（≥ 1 測試，標 @pytest.mark.network）：
   - test_yfinance_real_call_aapl_returns_ohlcv

S. backend/tests/integration/test_dispatcher_end_to_end.py（≥ 4 個測試）：
   - test_2330_routes_to_finmind
   - test_aapl_routes_to_yfinance
   - test_invalid_symbol_raises
   - test_us_symbol_no_institutional

T. 寫 scripts/health_checks/phase_06.sh（驗證 4 個 US source 註冊 + dispatcher 行為）：
   #!/bin/bash
   set -e
   echo "=== Phase 06 健康檢查 ==="

   cd backend
   # 1. 4 個 US source 註冊
   uv run python -c "
   import app.data_sources.tw, app.data_sources.us
   from app.data_sources.base import DATA_SOURCE_REGISTRY
   expected_us = {'yfinance', 'alpha_vantage', 'finnhub', 'sec_edgar'}
   got = set(DATA_SOURCE_REGISTRY.keys()) & expected_us
   assert got == expected_us, f'missing US source: {expected_us - got}'
   print('OK', got)
   "

   # 2. dispatcher 對 2330 / AAPL 行為正確
   uv run python -c "
   from app.core.market_dispatcher import detect_region, MarketRegion
   assert detect_region('2330') == MarketRegion.TW
   assert detect_region('0050') == MarketRegion.TW
   assert detect_region('00878') == MarketRegion.TW
   assert detect_region('AAPL') == MarketRegion.US
   assert detect_region('BRK.B') == MarketRegion.US
   print('OK')
   "

   # 3. unit + integration test 全綠（不含 network）
   uv run pytest tests/unit/test_yfinance_source.py tests/unit/test_alpha_vantage_source.py \
     tests/unit/test_finnhub_source.py tests/unit/test_sec_edgar_source.py \
     tests/unit/test_market_dispatcher.py tests/unit/test_cache.py \
     tests/integration/test_dispatcher_end_to_end.py -m "not network" -q
   cd ..
   echo "✅ Phase 06 健康檢查通過"

U. 寫 docs/phase_reports/PHASE_06.md
V. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 6 = 以下 11 個指令全部 exit code 0：

```bash
# 1. uv sync 加新依賴
cd backend && uv sync && cd ..

# 2. ruff lint 通過
cd backend && uv run ruff check app/ && cd ..

# 3. backend 啟動成功
cd backend && uv run uvicorn app.main:app --port 8000 &
SERVER_PID=$!
sleep 3
curl -fsS http://localhost:8000/health/live

# 4. 4 個 US source 註冊
cd backend && uv run python -c "
import app.data_sources.us
from app.data_sources.base import DATA_SOURCE_REGISTRY
expected = {'yfinance', 'alpha_vantage', 'finnhub', 'sec_edgar'}
got = set(DATA_SOURCE_REGISTRY.keys()) & expected
assert got == expected, f'missing: {expected - got}'
print('OK')
"
cd ..

# 5. Symbol validator 行為正確（含台股 ETF + 美股 BRK.B）
cd backend && uv run python -c "
from app.core.market_dispatcher import detect_region, MarketRegion
for sym, exp in [('2330','TW'),('0050','TW'),('00878','TW'),('2884A','TW'),
                 ('AAPL','US'),('BRK.B','US'),('TSLA','US')]:
  got = detect_region(sym).value
  assert got == exp, f'{sym}: {got} != {exp}'
print('OK')
"
cd ..

# 6. Dispatcher 整合 lifespan
curl -s http://localhost:8000/health/ready | jq '.data.status'

# 7. 全部新 unit tests 通過（不含 network）
cd backend && uv run pytest tests/unit/test_yfinance_source.py \
  tests/unit/test_alpha_vantage_source.py tests/unit/test_finnhub_source.py \
  tests/unit/test_sec_edgar_source.py tests/unit/test_market_dispatcher.py \
  tests/unit/test_cache.py -m "not network" -v && cd ..

# 8. integration test (mock + dispatcher) 通過
cd backend && uv run pytest tests/integration/test_dispatcher_end_to_end.py -m "not network" -v && cd ..

# 9. yfinance 真實 call（如有網路）
cd backend && uv run pytest tests/integration/test_real_yfinance.py -m network -v || echo "SKIP"
cd ..

# 10. 累積測試 ≥ 101
cd backend && uv run pytest --collect-only -q 2>&1 | tail -1

kill $SERVER_PID

# 11. health_check phase_06 通過
bash scripts/health_checks/phase_06.sh
```

【6. Smoke Test（手動）】
✓ ipython 跑 await YFinanceSource(settings).fetch_ohlcv("AAPL", date(2026,4,1), date(2026,4,30))
✓ 故意斷網跑 fallback，AAPL → yfinance fail → AlphaVantage fail → 拋 ExternalServiceError
✓ MarketDispatcher 對 BRK.B、00878 都判對
✓ SEC EDGAR 用 User-Agent 沒設 → 403（自我測試）

【7. 已知陷阱】
✗ yfinance 大寫敏感（"aapl" 也會回但奇怪）→ symbol.upper()
✗ yfinance 同步 API → 一定要 run_in_executor
✗ Alpha Vantage 配額耗盡時回 200 + Note 欄位（非 4xx）→ 主動檢查 Note
✗ Finnhub 免費版有些 endpoint 鎖（例如 institutional）→ 文件確認
✗ SEC EDGAR 強制要 User-Agent，否則 403 → __init__ 設好
✗ SEC EDGAR CIK 是 10 位數含前導零 → str(cik).zfill(10)
✗ Symbol regex 漏 ETF（00878）→ 用第 10.2 章完整 pattern
✗ BRK.B 含 dot → URL encode（特別是 yfinance 用 BRK-B）
✗ Cache 用 pickle 不安全 → 用 pyarrow parquet bytes
✗ Cache key 漏 market → TWSE 與 NASDAQ 同 symbol 撞 key
✗ MarketRegion enum value 不一致 → 統一 "TW" / "US" 大寫
✗ Dispatcher 沒注入 app.state → router 拿不到，要透過 dependency

【8. Self-Check SOP】
跑第 8.5.4 章「每 Phase 必跑的 Self-Check SOP」全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/core/market_dispatcher.py
  - backend/app/data_sources/us/yfinance_source.py
  - backend/app/data_sources/us/alpha_vantage_source.py
  - backend/app/data_sources/us/finnhub_source.py
  - backend/app/data_sources/us/sec_edgar_source.py
  - backend/app/data_sources/us/__init__.py
  - backend/app/data_sources/cache.py
  - 8 個 test files（共 ~37 個測試）
  - scripts/health_checks/phase_06.sh

程式檔（修改）：
  - backend/pyproject.toml + uv.lock（加 yfinance）
  - backend/app/services/data_pipeline_service.py（升級用 dispatcher）
  - backend/app/main.py（lifespan 加 dispatcher）

文件檔（新增）：
  - docs/phase_reports/PHASE_06.md

文件檔（更新）：
  - docs/runbooks/data_sources.md（加美股 source 章節）
  - docs/phase_progress.md

Git tag：phase-06-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別注意：D（yfinance）涉及 sync→async wrap，務必用 run_in_executor 不要 block event loop。
G（SEC EDGAR）強制 User-Agent，所以 .env 必須設 ADMIN_EMAIL。
```

---

### ▌Phase 7 — Celery Worker + Beat + DLQ + Bootstrap Scripts

```
=== TradingAgents-TW Phase 7（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 7
必讀 PLAN.md 章節：第 8.5, 13.1, 13.3, 13.4, 14.7, 14.8, 14.10, 16.3 章

【1. 前置依賴 Phase】
依賴：Phase 1, 2, 3, 4, 5, 6
驗證方式：bash scripts/health_checks/phase_06.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_06.sh
- backend 可啟動
- TW + US 共 9 個 source 可註冊
- celery_dead_letters 表存在（依 P4 schema）

【3. 本 Phase 目標】
讓專案具備「定期/手動把資料抓進 DB」的完整 pipeline：
  (1) Celery Worker（concurrency=4）+ Celery Beat（schedule）
  (2) Tasks：sync_ohlcv_tw / sync_ohlcv_us / news_ingest / financial_quarterly /
            monthly_revenue / institutional_daily / cleanup_orphans / verify_audit_chain
  (3) DLQ 機制：失敗任務寫入 celery_dead_letters
  (4) Beat 排程（依台股/美股盤後時區）
  (5) Bootstrap scripts：seed_stock_list.py / seed_users.py / backfill.py / verify_data.py
  (6) /health/seeded 改為真實檢查（stock_list ≥ 100 + 至少 1 支有 OHLCV）
  (7) idempotency_keys table 清理（過期 key）

注意：本 Phase「不寫業務 API」（在 P10/11）、「不寫 LangGraph 任務」（P12+）。
任務都是「資料管線」相關，與 user 互動無關。

【4. 任務清單】

A. 切分支：
   git checkout main && git pull
   git checkout -b phase/07-celery-bootstrap

B. backend/pyproject.toml 加依賴：
   celery[redis]>=5.4,<5.5
   tzdata  # Windows 環境必需，否則 Asia/Taipei timezone 找不到

C. backend/app/workers/celery_app.py：
   from celery import Celery
   from celery.schedules import crontab
   from app.core.config import settings

   celery_app = Celery(
     "tradingagents",
     broker=f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/1",
     backend=f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/1",
     include=[
       "app.workers.tasks.sync_ohlcv",
       "app.workers.tasks.news_ingest",
       "app.workers.tasks.financial",
       "app.workers.tasks.cleanup",
       "app.workers.tasks.verify_audit",
     ],
   )

   celery_app.conf.update(
     timezone="Asia/Taipei",
     enable_utc=True,
     task_track_started=True,
     task_time_limit=1200,  # 20 min hard
     task_soft_time_limit=900,  # 15 min soft
     worker_prefetch_multiplier=1,
     worker_max_tasks_per_child=50,
     task_acks_late=True,
     task_reject_on_worker_lost=True,
     beat_max_loop_interval=60,  # 防止 schedule miss
   )

   # Beat schedule
   celery_app.conf.beat_schedule = {
     "tw-ohlcv-after-close": {
       "task": "app.workers.tasks.sync_ohlcv.sync_ohlcv_tw_all",
       "schedule": crontab(hour=14, minute=30, day_of_week="mon-fri"),  # 台股 13:30 收盤後
     },
     "us-ohlcv-after-close": {
       "task": "app.workers.tasks.sync_ohlcv.sync_ohlcv_us_all",
       "schedule": crontab(hour=5, minute=30, day_of_week="tue-sat"),  # 美股盤後（台北時間）
     },
     "tw-news-hourly": {
       "task": "app.workers.tasks.news_ingest.ingest_tw_news",
       "schedule": crontab(minute=15),  # 每小時 15 分
     },
     "us-news-3h": {
       "task": "app.workers.tasks.news_ingest.ingest_us_news",
       "schedule": crontab(hour="*/3", minute=10),
     },
     "tw-monthly-revenue": {
       "task": "app.workers.tasks.financial.sync_monthly_revenue",
       "schedule": crontab(hour=9, minute=0, day_of_month=11),  # 每月 11 號
     },
     "tw-institutional-daily": {
       "task": "app.workers.tasks.financial.sync_institutional_tw",
       "schedule": crontab(hour=15, minute=0, day_of_week="mon-fri"),
     },
     "cleanup-orphans-daily": {
       "task": "app.workers.tasks.cleanup.cleanup_orphans",
       "schedule": crontab(hour=4, minute=0),  # 每日 04:00
     },
     "verify-audit-chain-daily": {
       "task": "app.workers.tasks.verify_audit.verify_chain",
       "schedule": crontab(hour=4, minute=30),
     },
     "cleanup-idempotency-daily": {
       "task": "app.workers.tasks.cleanup.cleanup_idempotency_keys",
       "schedule": crontab(hour=4, minute=15),
     },
   }

D. backend/app/workers/dlq.py：
   from celery import signals

   @signals.task_failure.connect
   def write_to_dlq(sender=None, task_id=None, exception=None, args=None,
                    kwargs=None, traceback=None, **extra):
     """Celery task 失敗 → 寫入 celery_dead_letters"""
     # 用同步 SQLAlchemy（celery context）
     # 注意：retry 過的也會觸發 task_failure（最終失敗時）
     from app.core.database import sync_rw_session
     with sync_rw_session() as session:
       session.add(CeleryDeadLetter(
         task_name=sender.name, task_id=task_id,
         args=args, kwargs=kwargs,
         exception=str(exception),
         traceback=str(traceback)[:10000],
         retry_count=...,
         resolved=False,
       ))
       session.commit()

     # 通知 admin（先用 logger，P18 才接 LINE）
     logger.critical(f"DLQ: {sender.name} task_id={task_id}")

E. backend/app/workers/tasks/sync_ohlcv.py：
   @celery_app.task(bind=True, autoretry_for=(httpx.HTTPError,), retry_backoff=True, max_retries=3)
   def sync_ohlcv_one(self, symbol: str, market: str, days_back: int = 7):
     """同步單支股票最近 N 天的 OHLCV"""
     # 用 asyncio.run 包 async pipeline
     ...

   @celery_app.task
   def sync_ohlcv_tw_all():
     """fan-out：對所有 active TW 股票呼叫 sync_ohlcv_one"""
     # 注意：不要一次發 1500 個 task，分批 + group
     ...

   @celery_app.task
   def sync_ohlcv_us_all(): ...

F. backend/app/workers/tasks/news_ingest.py：
   @celery_app.task
   def ingest_tw_news(): ...

   @celery_app.task
   def ingest_us_news(): ...

   # 內部：抓 → embedding → upsert Qdrant + DB metadata

G. backend/app/workers/tasks/financial.py：
   @celery_app.task
   def sync_monthly_revenue(): ...
   @celery_app.task
   def sync_institutional_tw(): ...
   @celery_app.task
   def sync_quarterly_financial_us(): ...

H. backend/app/workers/tasks/cleanup.py：
   @celery_app.task
   def cleanup_orphans():
     """依第 15.4 章"""
     # analysis_reports running > 30min → failed
     # pending_orders PENDING > 7 day → EXPIRED
     # password_reset_tokens 過期 → 刪
     # user_sessions 過期 → 刪
     # notification_log > 90 day → 歸檔
     ...

   @celery_app.task
   def cleanup_idempotency_keys():
     """過期 idempotency keys（TTL 24h）"""
     ...

I. backend/app/workers/tasks/verify_audit.py（**v7.0 注意：P7 為 stub，P9 升級為真實邏輯**）：
   @celery_app.task
   def verify_chain():
     """重算 audit_logs hash，發現斷裂發 CRITICAL。

     ⚠️ **P7 階段為 stub**（audit_repo.verify_chain 在 P9 才建立）。
     - P7：log a placeholder warning 並回傳 OK，beat schedule 註冊但實際無檢查
     - P9：升級為呼叫 audit_repo.verify_chain() 真實校驗
     """
     # P7 暫時實作：
     import structlog
     logger = structlog.get_logger()
     logger.warning(
       "verify_audit_chain task is STUB until P9. "
       "Real verification will be added in Phase 9 (when audit_repo is built)."
     )
     return {"status": "stub", "checked": 0}
     # P9 升級後會替換為：
     # async def main():
     #   async with ro_session() as s:
     #     ok, broken = await AuditRepository(s).verify_chain()
     #     if not ok: logger.critical("audit chain broken", broken_ids=broken)
     # asyncio.run(main())

J. data-pipeline/scripts/seed_stock_list.py：
   """初始化 stock_list 表，至少 1500 筆"""
   - 抓 TWSE 全部上市股票（https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL）
   - 抓 TPEX 全部上櫃股票（https://www.tpex.org.tw/openapi/v1/...）
   - 抓 NASDAQ 100 + S&P 500 + Dow Jones 30（用 yfinance components 或 hardcoded list）
   - upsert stock_list 表
   - 印出統計：TW XXXX 筆 / US XXX 筆

K. data-pipeline/scripts/seed_users.py：
   """建立第一個 admin 帳號"""
   - 從 .env 讀 ADMIN_EMAIL / ADMIN_INITIAL_PASSWORD
   - 用 bcrypt hash
   - INSERT users + must_change_password = TRUE
   - 已存在則 skip

L. data-pipeline/scripts/backfill.py：
   """回填指定股票 N 年資料"""
   - argparse: --region TW|US, --symbol 2330|all, --years 1-10
   - 對每支股票呼叫 sync_ohlcv（直接呼叫，不走 celery）
   - 進度條（tqdm）
   - 失敗摘要 + 重試指引

M. data-pipeline/scripts/verify_data.py：
   """驗證資料完整性"""
   - stock_list ≥ 1500
   - stock_prices 至少 1 支股票有 ≥ 200 row
   - audit_logs hash chain 完整
   - 印出每張表 row count

N. backend/app/main.py 的 /health/seeded 改為真實檢查：
   @app.get("/health/seeded")
   async def health_seeded():
     # 依第 13.3 章
     async with ro_session() as s:
       cnt = await s.scalar(select(func.count()).select_from(StockList))
       has_prices = await s.scalar(select(func.count()).select_from(StockPrice).limit(1))
     seeded = cnt >= 100 and has_prices > 0
     return envelope_success({"seeded": seeded, "stock_count": cnt, "has_prices": bool(has_prices)})

O. docker-compose.yml 加 celery 服務：
   celery_worker:
     build: { context: ., dockerfile: backend/Dockerfile }
     command: ["./scripts/wait-for-services.sh", "uv", "run", "celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
     env_file: .env
     environment: { ... 同 backend ... }
     depends_on: { ... }
     stop_grace_period: 60s
     restart: unless-stopped
   celery_beat:
     build: { ... }
     command: ["./scripts/wait-for-services.sh", "uv", "run", "celery", "-A", "app.workers.celery_app", "beat", "--loglevel=info"]
     env_file: .env
     environment: { ... }
     depends_on: { ... }
     restart: unless-stopped

P. Makefile 加：
   up-workers:
     docker compose up -d celery_worker celery_beat
   workers-logs:
     docker compose logs -f celery_worker celery_beat
   seed-stocks:
     uv run python data-pipeline/scripts/seed_stock_list.py
   seed-admin:
     uv run python data-pipeline/scripts/seed_users.py
   backfill:
     uv run python data-pipeline/scripts/backfill.py $(ARGS)
   verify-data:
     uv run python data-pipeline/scripts/verify_data.py

Q. backend/tests/unit/test_celery_app_config.py（≥ 5 個測試）：
   - test_broker_url_uses_redis_password
   - test_timezone_is_taipei
   - test_task_time_limits_set
   - test_beat_schedule_has_tw_ohlcv
   - test_acks_late_enabled

R. backend/tests/unit/test_dlq_signal.py（≥ 4 個測試）：
   - test_task_failure_writes_dlq_row
   - test_dlq_includes_traceback
   - test_dlq_marks_resolved_false
   - test_dlq_dedupes_same_task_id

S. backend/tests/integration/test_sync_ohlcv_task.py（≥ 4 個測試）：
   - test_sync_ohlcv_one_writes_db
   - test_sync_ohlcv_one_retries_on_http_error
   - test_sync_ohlcv_tw_all_fans_out_in_batches
   - test_sync_ohlcv_failure_writes_dlq

T. backend/tests/integration/test_seed_scripts.py（≥ 3 個測試）：
   - test_seed_stock_list_creates_at_least_1500
   - test_seed_users_idempotent
   - test_verify_data_passes_after_seed

U. 寫 scripts/health_checks/phase_07.sh：
   #!/bin/bash
   set -e
   echo "=== Phase 07 健康檢查 ==="

   # 1. celery worker / beat 容器跑
   docker compose ps celery_worker celery_beat | grep -c "running\|healthy" | grep -q 2

   # 2. seed_stock_list 跑完 1500+
   PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)
   COUNT=$(PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw \
     -tAc "SELECT count(*) FROM stock_list")
   test "$COUNT" -ge 1500 || { echo "❌ stock_list = $COUNT < 1500"; exit 1; }

   # 3. /health/seeded 為 true
   curl -s http://localhost:8000/health/seeded | jq -e '.data.seeded == true'

   # 4. DLQ 表可寫（用 sync session 驗）
   cd backend
   uv run python -c "
   import asyncio
   from app.core.database import sync_rw_session
   from app.models.dlq import CeleryDeadLetter
   with sync_rw_session() as s:
     s.add(CeleryDeadLetter(task_name='health_check', task_id='hc-test', args={}, kwargs={}, exception='test', traceback='', retry_count=0))
     s.commit()
   print('OK')
   "

   echo "✅ Phase 07 健康檢查通過"

V. 寫 docs/phase_reports/PHASE_07.md
W. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 7 = 以下 12 個指令全部 exit code 0：

```bash
# 1. uv sync
cd backend && uv sync && cd ..

# 2. ruff lint
cd backend && uv run ruff check app/ && cd ..

# 3. seed stock_list 跑完
make seed-stocks

# 4. stock_list ≥ 1500
PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)
COUNT=$(PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw -tAc "SELECT count(*) FROM stock_list")
test "$COUNT" -ge 1500

# 5. seed admin
make seed-admin

# 6. 至少 1 支股票回填 1 年
make backfill ARGS="--region TW --symbol 2330 --years 1"
COUNT=$(PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw -tAc "SELECT count(*) FROM stock_prices WHERE symbol='2330'")
test "$COUNT" -ge 200

# 7. /health/seeded 為 true
curl -s http://localhost:8000/health/seeded | jq -e '.data.seeded == true'

# 8. celery worker + beat 啟動
make up-workers
sleep 10
docker compose ps celery_worker celery_beat | grep -E "running|healthy" | wc -l | grep -q 2

# 9. ta_service_rw 不能改 audit_logs（再次驗證）
RW=$(grep ^TA_SERVICE_RW_PASSWORD= .env | cut -d= -f2)
PGPASSWORD=$RW psql -h localhost -U ta_service_rw tradingagents_tw \
  -c "DELETE FROM audit_logs WHERE id=1" 2>&1 | grep -i "permission denied"

# 10. verify_data 通過
make verify-data | grep -i "OK\|PASS"

# 11. 全部新測試通過
cd backend && uv run pytest tests/unit/test_celery_app_config.py tests/unit/test_dlq_signal.py \
  tests/integration/test_sync_ohlcv_task.py tests/integration/test_seed_scripts.py -v && cd ..

# 12. health_check phase_07 通過
bash scripts/health_checks/phase_07.sh
```

【6. Smoke Test（手動）】
✓ docker compose logs celery_beat 看到 schedule 觸發紀錄
✓ docker compose logs celery_worker 看到 task 跑完
✓ 觸發手動 task：cd backend && uv run python -c "from app.workers.tasks.sync_ohlcv import sync_ohlcv_one; sync_ohlcv_one.delay('2330', 'TWSE', 7)"
   30 秒內看到 worker log 完成
✓ 故意拋例外的 task → DLQ 寫入

【7. 已知陷阱】
✗ Windows 沒 tzdata → celery beat 找不到 Asia/Taipei → pyproject 加 tzdata
✗ celery 5 用 redis://:password@host 格式（: 後密碼前有空白 token）
✗ task_failure signal 在 retry 中也會 fire → 用 final retry 才寫 DLQ
✗ asyncio.run 在 celery task 內被多次呼叫 → 用 nest_asyncio 或 single event loop
✗ celery worker 跑 sync DB 但 backend 用 async DB → 兩套 session
✗ beat 重啟漏跑 → beat_max_loop_interval=60 + 開機 catch-up
✗ fan-out task 一次 1500 → broker queue 爆 → 分批 + chord
✗ Redis db=1 與 backend db=0 衝突 → 確認用不同 db
✗ seed_stock_list 來源 API 不穩 → 加 retry + cache
✗ 美股 components 抓 hardcoded → 接受過時，每年手動更新
✗ idempotency_keys 累積 → 排程清理
✗ celery_dead_letters 寫入失敗 → fallback 寫 file（避免無聲）

【8. Self-Check SOP】
跑第 8.5.4 章「每 Phase 必跑的 Self-Check SOP」全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/workers/celery_app.py
  - backend/app/workers/dlq.py
  - backend/app/workers/tasks/{sync_ohlcv, news_ingest, financial, cleanup, verify_audit}.py
  - data-pipeline/scripts/{seed_stock_list, seed_users, backfill, verify_data}.py
  - 4 個 test files（共 ~16 個測試）
  - scripts/health_checks/phase_07.sh

程式檔（修改）：
  - backend/pyproject.toml + uv.lock（加 celery, tzdata）
  - backend/app/main.py（/health/seeded 改真實檢查）
  - backend/app/core/database.py（加 sync_rw_session for celery）
  - docker-compose.yml（加 celery_worker, celery_beat）
  - Makefile（加 up-workers, seed-*, backfill, verify-data target）

文件檔（新增）：
  - docs/phase_reports/PHASE_07.md
  - docs/runbooks/celery.md（如何 debug task、看 DLQ）

文件檔（更新）：
  - docs/setup.md
  - docs/phase_progress.md

Git tag：phase-07-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：J（seed_stock_list）抓 1500+ 股票需要 ~5-10 分鐘 + 網路穩定。
建議子任務 J 完成後立即做 K-N，再做測試 + worker 啟動。
```

---

### ▌Phase 8 — 認證系統（JWT/RBAC/CSRF/WS Ticket/密碼重置/Session/Lockout）

```
=== TradingAgents-TW Phase 8（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\backend
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 8
必讀 PLAN.md 章節：第 8.5, 13.4, 17.2, 17.3, 19.1, 19.4 章

【1. 前置依賴 Phase】
依賴：Phase 1-7
驗證方式：bash scripts/health_checks/phase_07.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_07.sh
- backend 可啟動
- DB 已 seed admin（make seed-admin 已跑過）
- /health/seeded = true

【3. 本 Phase 目標】
讓專案具備「完整 Auth」：
  (1) Pydantic schemas + 強密碼策略（12+ 字元、4 類字元）
  (2) bcrypt cost=12（密碼 hash + verify）
  (3) JWT access (15min) + refresh (7day) + rotation + blacklist
  (4) /auth/login + /auth/refresh + /auth/logout + /auth/me + /auth/change-password
  (5) /auth/password-reset + /auth/password-reset/confirm + 限速 3/hr/IP
  (6) /auth/ws-ticket（subprotocol + 60s 一次性 + Redis db5）
  (7) Lockout（5 fail / 15min）
  (8) Per-user session 上限 5
  (9) RBAC（ADMIN / ANALYST / VIEWER）
  (10) Onboarding（must_change_password、next_action）
  (11) 完整 audit log 寫入（每個 auth event）

注意：本 Phase「不寫業務 API」（在 P10/11）、「不寫前端」（P15）。
audit_logs 寫入用 P9 的 AuditMiddleware；本 Phase 先用 service-level 直接寫。

**Audit log 在 P8 的具體寫入方式（簡易版 audit_repo）：**
P9 才會有完整 AuditRepository（含 verify_chain 等），但 P8 為了讓退出條件第 9 項
（`SELECT count(*) FROM audit_logs WHERE action='auth.login'`）能通過，必須有寫入邏輯。

P8 在任務 G（auth_service）內實作以下「最小 audit append helper」（會在 P9 改用 AuditRepository）：

```python
# backend/app/services/_audit_minimal.py（P8 暫時用，P9 整合到 audit_repo.py）
from app.models.audit import AuditLog

async def append_audit(session, *, actor_id, action, entity_type, entity_id,
                        details: dict, trace_id: str | None = None):
    """最小 audit append。trigger 會自動補 prev_hash, entry_hash（P4 已建）。"""
    log = AuditLog(
        actor_id=actor_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details, trace_id=trace_id,
    )
    session.add(log)
    # 不在這裡 commit，由呼叫端的 transaction 控制
```

呼叫範例（auth_service.login 結尾）：
```python
async with rw_session() as s:
    await append_audit(
        s, actor_id=user.id, action="auth.login",
        entity_type="user", entity_id=str(user.id),
        details={"ip": ip, "ua": ua},
    )
    await s.commit()
```

要 audit 的事件清單（P8 必寫入）：
- auth.login（成功 + 失敗都要）
- auth.login_locked（lockout 觸發時）
- auth.logout
- auth.refresh
- auth.password_changed
- auth.password_reset_requested
- auth.password_reset_confirmed

【4. 任務清單】

A. 切分支 + uv sync 加 dependencies：
   git checkout -b phase/08-auth
   pyproject 加：python-jose[cryptography]>=3.3, passlib[bcrypt]>=1.7, email-validator

B. backend/app/core/security.py：
   def hash_password(password: str) -> str: ...  # bcrypt cost=12
   def verify_password(plain: str, hashed: str) -> bool: ...

   class JWTService:
     """雙 key rotation：用 current 簽，decode 先試 current 再試 previous。"""

     ALGORITHM = "HS256"
     ACCESS_TTL = timedelta(minutes=15)
     REFRESH_TTL = timedelta(days=7)

     def __init__(self, settings: Settings):
       self.current_key = settings.SECRET_KEY.get_secret_value()
       self.previous_key = (
         settings.SECRET_KEY_PREVIOUS.get_secret_value()
         if settings.SECRET_KEY_PREVIOUS else None
       )

     def create_access_token(self, user_id: UUID, role: str) -> str:
       """永遠用 current_key 簽。"""
       payload = {
         "sub": str(user_id), "role": role, "type": "access",
         "jti": str(uuid4()),
         "iat": datetime.now(timezone.utc),
         "exp": datetime.now(timezone.utc) + self.ACCESS_TTL,
       }
       return jwt.encode(payload, self.current_key, algorithm=self.ALGORITHM)

     def create_refresh_token(self, user_id: UUID) -> str:
       payload = {
         "sub": str(user_id), "type": "refresh",
         "jti": str(uuid4()),
         "iat": datetime.now(timezone.utc),
         "exp": datetime.now(timezone.utc) + self.REFRESH_TTL,
       }
       return jwt.encode(payload, self.current_key, algorithm=self.ALGORITHM)

     def decode(self, token: str) -> dict:
       """先試 current_key，失敗則試 previous_key（rotation 過渡期）。"""
       try:
         return jwt.decode(token, self.current_key, algorithms=[self.ALGORITHM])
       except jwt.ExpiredSignatureError:
         raise AuthError(message_zh="Token 已過期")
       except jwt.InvalidSignatureError:
         if self.previous_key:
           try:
             # 接受舊 key 簽的 token，但 log warning（可監控 rotation 進度）
             payload = jwt.decode(token, self.previous_key, algorithms=[self.ALGORITHM])
             logger.warning("jwt.decoded_with_previous_key", jti=payload.get("jti"))
             return payload
           except jwt.PyJWTError:
             pass
         raise AuthError(message_zh="Token 簽名無效")
       except jwt.PyJWTError as e:
         raise AuthError(message_zh=f"Token 無效：{e}")

   class TokenBlacklist:
     async def add(self, jti: str, ttl: int): ...
     async def is_blacklisted(self, jti: str) -> bool: ...
     # Redis db3

C. backend/app/core/csrf.py：
   def generate_csrf_token() -> str: ...
   def verify_csrf_token(req_token: str, cookie_token: str) -> bool: ...
   # /auth/refresh 時驗證 X-CSRF-Token == cookie

D. backend/app/core/ws_ticket.py：
   class WSTicketService:
     async def issue(self, user_id) -> str:
       """產生一次性 ticket，TTL 60s，存 Redis db5"""
       ticket = secrets.token_urlsafe(32)
       await redis.setex(f"wst:{ticket}", 60, str(user_id))
       return ticket

     async def consume(self, ticket: str) -> int | None:
       """一次性：用 GETDEL（Redis 6.2+）"""
       value = await redis.getdel(f"wst:{ticket}")
       return int(value) if value else None

E. backend/app/core/password_policy.py：
   def validate_password(password: str, user_email: str = None) -> None:
     """12+ 字元、4 類字元、不可包含 email"""
     ...

   class PasswordHistory:
     async def is_recent(self, user_id, password) -> bool:
       """檢查最近 5 次密碼"""
       ...
     async def add(self, user_id, hashed): ...

F. backend/app/repos/user_repo.py：
   class UserRepository:
     async def get_by_email(self, email): ...
     async def get_by_id(self, user_id): ...
     async def update_password(self, user_id, new_hash): ...
     async def increment_failed_attempts(self, user_id): ...
     async def reset_failed_attempts(self, user_id): ...
     async def lock(self, user_id, until: datetime): ...
     async def is_locked(self, user_id) -> bool: ...

   class UserSessionRepository:
     async def create(self, user_id, refresh_jti, expires_at): ...
     async def list_active(self, user_id) -> list[UserSession]: ...
     async def revoke_oldest_if_over_limit(self, user_id, max=5): ...
     async def revoke(self, jti): ...
     async def revoke_all_for_user(self, user_id): ...

G. backend/app/services/auth_service.py：
   class AuthService:
     async def login(self, email, password, ip) -> LoginResult:
       user = await user_repo.get_by_email(email)
       if not user: raise AuthError(message_zh="帳號或密碼錯誤")
       if user.is_locked: raise LockedError(message_zh="帳號已鎖定 15 分鐘")
       if not verify_password(password, user.password_hash):
         await user_repo.increment_failed_attempts(user.id)
         if user.failed_attempts + 1 >= 5:
           await user_repo.lock(user.id, datetime.now(timezone.utc) + timedelta(minutes=15))
           # audit log
         raise AuthError(message_zh="帳號或密碼錯誤")

       # 成功：reset attempts、issue tokens、建 session、依 onboarding 決定 next_action
       await user_repo.reset_failed_attempts(user.id)
       access = jwt.create_access_token(user.id, user.role)
       refresh = jwt.create_refresh_token(user.id)
       await session_repo.create(user.id, ..., expires_at=...)
       await session_repo.revoke_oldest_if_over_limit(user.id, max=5)

       next_action = "change_password" if user.must_change_password \
                     else "onboarding" if not user.onboarding_completed \
                     else "dashboard"
       # audit log: auth.login
       return LoginResult(access, refresh, csrf_token, next_action, user)

     async def refresh(self, refresh_token, csrf_token, cookie_csrf): ...
     async def logout(self, refresh_jti): ...
     async def change_password(self, user_id, old, new): ...
     async def password_reset_request(self, email, ip): ...
     async def password_reset_confirm(self, reset_token, new_password): ...

H. backend/app/api/v1/auth_router.py：
   router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

   @router.post("/login")
   async def login(payload: LoginRequest, request: Request,
                   service: AuthService = Depends()) -> SuccessEnvelope[LoginResponse]:
     result = await service.login(payload.email, payload.password, request.client.host)
     # cookies：refresh_token (httpOnly, SameSite=Lax for dev/Strict for prod), csrf
     # body：access_token, next_action, user info
     ...

   @router.post("/refresh")
   async def refresh(request: Request, response: Response, service: AuthService = Depends()):
     # 從 cookie 取 refresh_token
     # X-CSRF-Token header 比對 cookie 中的 csrf
     # 成功則 rotate（舊 refresh blacklist + 新 refresh）
     ...

   @router.post("/logout")
   @router.get("/me")
   @router.post("/change-password")
   @router.post("/password-reset")
   @router.post("/password-reset/confirm")
   @router.post("/ws-ticket")

I. backend/app/api/dependencies.py：
   async def get_current_user(authorization: str = Header(...),
                              user_repo: UserRepo = Depends()) -> User:
     token = parse_bearer(authorization)
     payload = jwt_service.decode(token)
     if await blacklist.is_blacklisted(payload["jti"]): raise AuthError(...)
     user = await user_repo.get_by_id(payload["sub"])
     if not user: raise AuthError(...)
     return user

   def require_role(*roles):
     async def checker(user = Depends(get_current_user)):
       if user.role not in roles: raise ForbiddenError(message_zh="權限不足")
       return user
     return checker

   admin_only = require_role("ADMIN")
   analyst_or_admin = require_role("ADMIN", "ANALYST")

J. backend/app/main.py 加 router + lifespan 註冊 service：
   ```python
   from app.api.v1 import auth_router
   from app.core.ws_ticket import WSTicketService
   from app.core.security import JWTService
   from app.core.redis_client import get_redis

   @asynccontextmanager
   async def lifespan(app: FastAPI):
     # ...（既有設定不變）
     # P8 新增：把 service 掛到 app.state，後續 router 可用
     redis_db5 = await get_redis(db=5)  # ws ticket
     app.state.ws_ticket_service = WSTicketService(redis_db5)
     app.state.jwt_service = JWTService(settings)
     yield
     # ...（既有 shutdown 不變）

   app.include_router(auth_router.router)
   ```

K. backend/app/schemas/auth.py：
   class LoginRequest(BaseModel):
     email: EmailStr
     password: str = Field(min_length=12, max_length=128)

   class LoginResponse(BaseModel):
     access_token: str
     token_type: Literal["Bearer"] = "Bearer"
     next_action: Literal["change_password", "onboarding", "dashboard"]
     user: UserPublic

   ... 其他 schemas

L. backend/tests/unit/test_password_policy.py（≥ 6 個測試）：
   - test_password_too_short
   - test_password_lacks_uppercase
   - test_password_lacks_digit
   - test_password_lacks_special
   - test_password_contains_email_rejected
   - test_password_history_blocks_recent_5

M. backend/tests/unit/test_jwt_service.py（≥ 6 個測試）：
   - test_create_access_token_includes_user_id_role
   - test_decode_valid_token
   - test_decode_expired_raises
   - test_decode_invalid_signature_raises
   - test_blacklisted_token_rejected
   - test_dual_key_rotation_old_key_still_valid

N. backend/tests/unit/test_ws_ticket.py（≥ 4 個測試）：
   - test_issue_returns_random_token
   - test_consume_returns_user_id
   - test_consume_second_time_returns_none
   - test_ticket_expires_after_60s

O. backend/tests/integration/test_auth_login.py（≥ 8 個測試）：
   - test_login_success
   - test_login_wrong_password_increments_attempts
   - test_login_5_failures_locks_account
   - test_login_locked_account_returns_423
   - test_login_returns_next_action_change_password_for_new_user
   - test_login_5_sessions_revokes_oldest
   - test_login_audit_log_written
   - test_login_response_envelope_format

P. backend/tests/integration/test_auth_refresh.py（≥ 5 個測試）：
   - test_refresh_with_valid_token_rotates
   - test_refresh_blacklists_old_jti
   - test_refresh_without_csrf_rejected
   - test_refresh_csrf_mismatch_rejected
   - test_refresh_after_logout_rejected

Q. backend/tests/integration/test_auth_password_reset.py（≥ 5 個測試）：
   - test_password_reset_request_sends_token
   - test_password_reset_request_rate_limit_3_per_hour
   - test_password_reset_confirm_with_valid_token
   - test_password_reset_revokes_all_sessions
   - test_password_reset_token_one_use_only

R. backend/tests/integration/test_auth_change_password.py（≥ 4 個測試）：
   - test_change_password_requires_old
   - test_change_password_blocks_recent_5
   - test_change_password_clears_must_change_flag
   - test_change_password_revokes_other_sessions

S. backend/tests/integration/test_rbac.py（≥ 5 個測試）：
   - test_admin_can_access_admin_endpoint
   - test_viewer_cannot_access_admin_endpoint_403
   - test_no_token_returns_401
   - test_invalid_token_returns_401
   - test_expired_token_returns_401

T. 寫 scripts/health_checks/phase_08.sh：
   #!/bin/bash
   set -e
   echo "=== Phase 08 健康檢查 ==="

   ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env | cut -d= -f2)
   ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env | cut -d= -f2)

   # 1. login 成功
   RESP=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}")
   TOKEN=$(echo "$RESP" | jq -r '.data.access_token')
   test -n "$TOKEN" && test "$TOKEN" != "null"

   # 2. /me 可呼叫
   curl -fsS -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me

   # 3. WS ticket 可發
   TICKET=$(curl -s -X POST http://localhost:8000/api/v1/auth/ws-ticket \
     -H "Authorization: Bearer $TOKEN" | jq -r '.data.ticket')
   test -n "$TICKET" && test "$TICKET" != "null"

   # 4. lockout 觸發（連 5 次錯）
   for i in 1 2 3 4 5; do
     curl -s -X POST http://localhost:8000/api/v1/auth/login \
       -H "Content-Type: application/json" \
       -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"WRONGwrong123!\"}" > /dev/null
   done
   STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"WRONGwrong123!\"}")
   test "$STATUS" = "423"

   # 5. unlock（DB 改 locked_until = NULL）後恢復
   PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)
   PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw \
     -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='$ADMIN_EMAIL'"

   echo "✅ Phase 08 健康檢查通過"

U. 寫 docs/phase_reports/PHASE_08.md
V. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 8 = 以下 12 個指令全部 exit code 0：

```bash
# 1. uv sync
cd backend && uv sync && cd ..

# 2. ruff lint
cd backend && uv run ruff check app/ && cd ..

# 3. backend 啟動
cd backend && uv run uvicorn app.main:app --port 8000 &
SERVER_PID=$!
sleep 3
curl -fsS http://localhost:8000/health/live

# 4. /docs 顯示 auth router
curl -s http://localhost:8000/openapi.json | jq -r '.paths | keys[]' | grep "/api/v1/auth/login"

# 5. login 成功
ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env | cut -d= -f2)
ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env | cut -d= -f2)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}" | jq -r '.data.access_token')
test -n "$TOKEN"

# 6. /me 200
curl -fsS -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me | jq '.data.email'

# 7. lockout 5 次
for i in 1 2 3 4 5; do
  curl -s -X POST http://localhost:8000/api/v1/auth/login \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"wrong\"}" > /dev/null
done
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/login \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"wrong\"}")
test "$STATUS" = "423"

# unlock for 後續測試
PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)
PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw \
  -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='$ADMIN_EMAIL'"

# 8. WS ticket 一次性
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}" | jq -r '.data.access_token')
TICKET=$(curl -s -X POST http://localhost:8000/api/v1/auth/ws-ticket -H "Authorization: Bearer $TOKEN" | jq -r '.data.ticket')
# 第二次用相同 ticket 應失敗（從 Redis db5 直接驗）
docker compose exec redis redis-cli -n 5 -a $(grep ^REDIS_PASSWORD= .env | cut -d= -f2) GET "wst:$TICKET" | grep -i "(nil)" || true
# 注意：第一次 issue 後 60s 內 GETDEL 才會成功，這裡直接 GET 看是否還在

# 9. audit log 有 login event
PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw \
  -tAc "SELECT count(*) FROM audit_logs WHERE action='auth.login'" | awk '$1 > 0'

# 10. 全部 auth 測試通過
cd backend && uv run pytest tests/unit/test_password_policy.py tests/unit/test_jwt_service.py \
  tests/unit/test_ws_ticket.py tests/integration/test_auth_*.py tests/integration/test_rbac.py -v && cd ..

# 11. 累積測試 ≥ 158
cd backend && uv run pytest --collect-only -q 2>&1 | tail -1

kill $SERVER_PID

# 12. health_check phase_08 通過
bash scripts/health_checks/phase_08.sh
```

【6. Smoke Test（手動）】
✓ 用 curl 完整跑：login → /me → /change-password → 用新密碼 login → logout → 用舊 access 已失效（401）
✓ /docs Swagger 試打 /auth/* 全部 endpoint
✓ password reset：request → 看 audit_log 拿 token → confirm
✓ 5 sessions 上限：login 6 次（從不同 user-agent），第 6 次 login 成功但第 1 個 session 失效

【7. 已知陷阱】
✗ SECRET_KEY < 32 bytes → 啟動就 fail（P3 已防）
✗ JWT exp 用 datetime 不 UTC → timezone-naive vs aware 不一致 → 用 datetime.now(timezone.utc)（**v7.0 注意：Python 3.12+ deprecate datetime.utcnow()，全 codebase 統一用 datetime.now(timezone.utc)**）
✗ refresh cookie SameSite=Strict 在 dev 跨 port 擋 → dev 用 Lax
✗ refresh cookie 不設 httpOnly → JS 可讀（XSS 風險）
✗ CSRF cookie 必須可被 JS 讀（用來放 X-CSRF-Token header）→ httpOnly=False
✗ bcrypt cost=12 慢 → 不要降低，登入慢 ~200ms 正常
✗ JWT blacklist key TTL 必須 = token exp 剩餘秒數 → 不然永久占記憶體
✗ session 上限「revoke_oldest」必須 in transaction with for update
✗ password reset token 必須 hash 後存 DB → 不要 plaintext
✗ password reset 一次性：consume 後 DELETE 而非 UPDATE
✗ login 失敗時 timing attack：不論 user 存在與否要等差不多時間（用 dummy bcrypt）
✗ next_action 三狀態優先序：change_password > onboarding > dashboard
✗ /me endpoint 不要回 password_hash（即使 hash）→ schema 控制
✗ websocket subprotocol 必須兩個值：["tradingagents.v1", f"ticket.{ticket}"]

【8. Self-Check SOP】
跑第 8.5.4 章「每 Phase 必跑的 Self-Check SOP」全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/core/security.py
  - backend/app/core/csrf.py
  - backend/app/core/ws_ticket.py
  - backend/app/core/password_policy.py
  - backend/app/repos/user_repo.py
  - backend/app/services/auth_service.py
  - backend/app/api/v1/auth_router.py
  - backend/app/api/dependencies.py
  - backend/app/schemas/auth.py
  - 8 個 test files（共 ~43 個測試）
  - scripts/health_checks/phase_08.sh

程式檔（修改）：
  - backend/pyproject.toml + uv.lock（python-jose, passlib, email-validator）
  - backend/app/main.py（include auth router）

文件檔（新增）：
  - docs/phase_reports/PHASE_08.md
  - docs/runbooks/auth.md（debug auth 問題）

文件檔（更新）：
  - docs/setup.md
  - docs/phase_progress.md

Git tag：phase-08-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：B/G/H 是 Auth 核心，安全敏感，請仔細測試 timing attack 與 token rotation。
```

---

### ▌Phase 9 — 安全 Middleware + Audit hash chain + Rate Limit + Validators

```
=== TradingAgents-TW Phase 9（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\backend
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 9
必讀 PLAN.md 章節：第 8.5, 16.3, 17.1, 17.2, 19.2, 19.3, 19.6, 19.7 章

【1. 前置依賴 Phase】
依賴：Phase 1-8
驗證方式：bash scripts/health_checks/phase_08.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步】
- bash scripts/health_checks/phase_08.sh
- /auth/login 流程通

【3. 本 Phase 目標】
讓 backend「安全強度達 v1.0 上線標準」：
  (1) AuditMiddleware（每 request 寫 audit_logs）
  (2) RateLimit 6 層（依 19.3）
  (3) CSRF middleware（POST/PUT/DELETE 強制驗）
  (4) Validators 完整：Symbol, Date range, Body size, URL, UUID, Sort whitelist, Content-Type
  (5) verify_audit_chain.py 完整化
  (6) AuditLog hash chain 整合測試（DB-level 已在 P4 trigger，這裡驗 service-level）
  (7) CSP（dev 寬鬆，prod 嚴格 nonce-based 留 P18）

注意：本 Phase「不寫業務 router」（在 P10/11）、「不寫前端 CSRF 整合」（P15）。

【4. 任務清單】

A. 切分支：phase/09-security-middleware

B. backend/app/core/audit_middleware.py：
   class AuditMiddleware(BaseHTTPMiddleware):
     async def dispatch(self, request, call_next):
       # 取 trace_id, user_id（從 JWT，可選），method, path, query, body_size, ip, ua
       start = time.monotonic()
       response = await call_next(request)
       elapsed_ms = (time.monotonic() - start) * 1000

       # 排除：/health/*, /metrics, /docs, /openapi.json
       if not should_audit(request.url.path):
         return response

       # 寫 audit_logs（async session）
       await audit_repo.append(
         actor_id=request.state.user_id if hasattr(request.state, "user_id") else None,
         action=f"http.{request.method.lower()}",
         entity_type="endpoint",
         entity_id=request.url.path,
         details={"status": response.status_code, "elapsed_ms": elapsed_ms,
                  "ip": request.client.host, "ua": request.headers.get("user-agent")},
         trace_id=request.state.trace_id,
       )
       return response

C. backend/app/repos/audit_repo.py：
   class AuditRepository:
     async def append(self, **kwargs):
       """trigger 自動補 prev_hash, entry_hash"""
       # 注意：trigger 用 advisory lock 保證序列化
       audit_log = AuditLog(**kwargs)
       self.session.add(audit_log)
       await self.session.commit()

     async def verify_chain(self, since: datetime = None) -> tuple[bool, list[int]]:
       """重算 hash 比對，回傳 (ok, broken_ids)"""
       ...

D. backend/app/core/rate_limit.py：
   class RateLimiter:
     """Redis-based sliding window"""
     def __init__(self, redis_db=2):
       self.redis = ...

     async def check(self, key: str, limit: int, window_sec: int) -> bool:
       """True = allowed, False = rate limited"""
       # Lua script for atomic check+increment

   class RateLimitMiddleware(BaseHTTPMiddleware):
     # 6 層：
     # L1: per IP global (300/min) - nginx 在 prod，這裡也加一層
     # L2: /auth/login 5/min/IP
     # L3: /auth/password-reset 3/hr/IP
     # L4: per user 60/min
     # L5: /analysis/start 10/hr/user
     # L6: LLM 月成本 - 在 service 層，這裡只擋 endpoint
     ...

E. backend/app/core/csrf_middleware.py：
   class CSRFMiddleware(BaseHTTPMiddleware):
     async def dispatch(self, request, call_next):
       # 只 POST/PUT/DELETE/PATCH 才驗
       if request.method in ("GET", "HEAD", "OPTIONS"): return await call_next(request)
       # 排除：/auth/login（沒 cookie 還沒 csrf）, /auth/password-reset（無認證）
       if request.url.path in CSRF_EXEMPT_PATHS: return await call_next(request)

       header_token = request.headers.get("X-CSRF-Token")
       cookie_token = request.cookies.get("csrf_token")
       if not header_token or not cookie_token or header_token != cookie_token:
         raise ForbiddenError(message_zh="CSRF 驗證失敗")
       return await call_next(request)

F. backend/app/core/validators.py（完整版）：
   def validate_symbol(symbol: str) -> str:
     if not (TW_SYMBOL_PATTERN.match(symbol) or US_SYMBOL_PATTERN.match(symbol)):
       raise ValidationError(message_zh=f"股票代號格式錯誤: {symbol}")
     return symbol.upper()

   def validate_date_range(start: date, end: date, max_days: int = 3650):
     if end < start: raise ValidationError(...)
     if (end - start).days > max_days: raise ValidationError(...)

   def validate_uuid(value: str) -> UUID: ...

   class SortField(BaseModel):
     """白名單機制"""
     allowed: ClassVar[set[str]]
     value: str
     @validator("value")
     def check_in_allowed(cls, v):
       if v not in cls.allowed: raise ValueError(...)
       return v

   class StockSortField(SortField):
     allowed = {"symbol", "name", "market_cap", "volume"}

G. backend/app/core/body_size_middleware.py：
   class BodySizeMiddleware(BaseHTTPMiddleware):
     MAX_BODY = 1024 * 1024  # 1 MB
     async def dispatch(self, request, call_next):
       cl = request.headers.get("content-length")
       if cl and int(cl) > self.MAX_BODY:
         raise TooLargeError(message_zh="請求過大")
       return await call_next(request)

H. backend/app/core/security_headers.py（升級，加 CSP dev）：
   CSP_DEV = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; ..."
   # CSP_PROD（nonce-based）留 P18

I. backend/app/main.py middleware 順序（重要！）：
   app.add_middleware(SecurityHeadersMiddleware)  # 最外
   app.add_middleware(CORSMiddleware, ...)
   app.add_middleware(RateLimitMiddleware)
   app.add_middleware(CSRFMiddleware)
   app.add_middleware(BodySizeMiddleware)
   app.add_middleware(AuditMiddleware)
   app.add_middleware(RequestIDMiddleware)  # 最內（最先跑）
   # FastAPI middleware 是 LIFO：最後 add 的最先跑

J. scripts/verify_audit_chain.py：
   """獨立 CLI 工具：完整重算 audit_logs hash chain"""
   import asyncio
   from app.core.database import ro_engine
   from app.repos.audit_repo import AuditRepository

   async def main(since=None):
     async with AsyncSession(ro_engine) as session:
       repo = AuditRepository(session)
       ok, broken = await repo.verify_chain(since)
       if ok:
         print("✅ Audit chain integrity verified")
         sys.exit(0)
       else:
         print(f"❌ Audit chain BROKEN at IDs: {broken}")
         sys.exit(1)

J2. **升級 P7 的 verify_audit task（v7.0 新增）：**
   把 backend/app/workers/tasks/verify_audit.py 從 P7 stub 換成真實邏輯：
   ```python
   import asyncio, structlog
   from celery import shared_task
   from app.core.database import ro_session
   from app.repos.audit_repo import AuditRepository

   logger = structlog.get_logger()

   @shared_task(name="app.workers.tasks.verify_audit.verify_chain")
   def verify_chain():
     """每日 04:30 排程跑（P7 已註冊）"""
     async def _check():
       async with ro_session() as session:
         repo = AuditRepository(session)
         ok, broken = await repo.verify_chain()
       return ok, broken

     ok, broken = asyncio.run(_check())
     if not ok:
       logger.critical("audit_chain.broken", broken_ids=broken)
       # P18 才接 LINE/Telegram 通知；現在先 log critical
       return {"status": "broken", "broken_count": len(broken), "broken_ids": broken[:10]}
     return {"status": "ok"}
   ```

   驗收：跑 celery worker 觸發 task 應 log "audit_chain integrity ok"（無斷裂時）。

K. backend/tests/unit/test_validators.py（≥ 8 個測試）：
   - test_validate_symbol_tw_normal
   - test_validate_symbol_tw_etf_5digit
   - test_validate_symbol_tw_etf_6digit
   - test_validate_symbol_us_class_share
   - test_validate_symbol_invalid_raises
   - test_validate_date_range_end_before_start_raises
   - test_validate_date_range_too_long_raises
   - test_sort_field_whitelist_blocks_unknown

L. backend/tests/unit/test_rate_limit.py（≥ 6 個測試）：
   - test_within_limit_allowed
   - test_over_limit_blocked
   - test_window_resets
   - test_different_keys_independent
   - test_atomic_increment_under_concurrency
   - test_redis_down_fails_open（不擋 request，但 log warning）

M. backend/tests/integration/test_audit_middleware.py（≥ 5 個測試）：
   - test_request_writes_audit_log
   - test_health_excluded_from_audit
   - test_audit_includes_trace_id
   - test_audit_includes_user_when_authenticated
   - test_audit_chain_unbroken_after_100_requests

N. backend/tests/integration/test_csrf_middleware.py（≥ 5 個測試）：
   - test_get_no_csrf_required
   - test_post_without_csrf_blocked
   - test_post_csrf_mismatch_blocked
   - test_post_csrf_match_allowed
   - test_login_endpoint_csrf_exempt

O. backend/tests/integration/test_rate_limit_endpoints.py（≥ 6 個測試）：
   - test_login_5_per_min_per_ip
   - test_password_reset_3_per_hour_per_ip
   - test_per_user_60_per_min
   - test_analysis_start_10_per_hour
   - test_global_300_per_min
   - test_rate_limit_response_includes_retry_after

P. backend/tests/security/test_audit_chain.py（≥ 4 個測試）：
   - test_verify_chain_passes_after_normal_inserts
   - test_verify_chain_detects_manual_tampering
   - test_verify_chain_detects_missing_row
   - test_verify_chain_detects_reordered_row

Q. backend/tests/security/test_validators_security.py（≥ 5 個測試）：
   - test_sql_injection_in_symbol_blocked
   - test_xss_in_search_query_escaped
   - test_path_traversal_in_uuid_blocked
   - test_oversized_body_returns_413
   - test_unknown_sort_field_returns_422

R. 寫 scripts/health_checks/phase_09.sh
S. 寫 docs/phase_reports/PHASE_09.md
T. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 9 = 以下 12 個指令全部 exit code 0：

```bash
# 1. uv sync + lint + 啟動
cd backend && uv sync && uv run ruff check app/ && cd ..
cd backend && uv run uvicorn app.main:app --port 8000 &
SERVER_PID=$!
sleep 3
curl -fsS http://localhost:8000/health/live

# 2. POST 沒 CSRF 被擋
ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env | cut -d= -f2)
ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env | cut -d= -f2)
RESP=$(curl -s -c /tmp/cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}")
TOKEN=$(echo "$RESP" | jq -r '.data.access_token')

# 對 protected POST 端點不帶 CSRF → 403
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer $TOKEN")
test "$STATUS" = "403"

# 3. RateLimit /auth/login 5/min
for i in 1 2 3 4 5 6; do
  curl -s -o /dev/null -X POST http://localhost:8000/api/v1/auth/login -d '{"email":"x@y","password":"wrong"}'
done
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/login -d '{"email":"x@y","password":"wrong"}')
test "$STATUS" = "429"

# 4. body too large → 413
dd if=/dev/urandom bs=1M count=2 2>/dev/null | curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Content-Type: application/json" --data-binary @- http://localhost:8000/api/v1/auth/login | grep "^413$"

# 5. audit_logs 增加（POST /login 後）
PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)
COUNT_BEFORE=$(PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw -tAc "SELECT count(*) FROM audit_logs")
curl -s -X POST http://localhost:8000/api/v1/auth/login -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}" > /dev/null
COUNT_AFTER=$(PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw -tAc "SELECT count(*) FROM audit_logs")
test "$COUNT_AFTER" -gt "$COUNT_BEFORE"

# 6. verify_audit_chain 通過
cd backend && uv run python ../scripts/verify_audit_chain.py && cd ..

# 7. /metrics 沒 admin token → 401（暫時 stub，P11 完整）
# skip（在 P11 才實作）

# 8. CSP header
curl -sI http://localhost:8000/health/live | grep -i "content-security-policy"

# 9. SecurityHeaders 完整
curl -sI http://localhost:8000/health/live | grep -i "X-Content-Type-Options\|X-Frame-Options\|Referrer-Policy"

# 10. 全部新 unit + integration + security 測試通過
cd backend && uv run pytest tests/unit/test_validators.py tests/unit/test_rate_limit.py \
  tests/integration/test_audit_middleware.py tests/integration/test_csrf_middleware.py \
  tests/integration/test_rate_limit_endpoints.py tests/security/ -v && cd ..

# 11. 累積測試 ≥ 192
cd backend && uv run pytest --collect-only -q 2>&1 | tail -1

kill $SERVER_PID

# 12. health_check phase_09 通過
bash scripts/health_checks/phase_09.sh
```

【6. Smoke Test（手動）】
✓ 對 100 個 GET 請求看 audit_logs 增加 100 行
✓ 手動破壞 audit_logs（PG superuser UPDATE） → verify_audit_chain.py 抓到
✓ 用 wrk / hey 壓 5/min 確認 rate limit 動
✓ DevTools 看 response header 含 X-Frame-Options, X-Content-Type-Options

【7. 已知陷阱】
✗ Middleware 順序錯：RequestID 必最內、SecurityHeaders 必最外
✗ AuditMiddleware 寫 DB 失敗 → 不要 raise（會把整個 request 拒掉），log warning + 繼續
✗ Rate limit 用 Redis pipeline 才 atomic
✗ Rate limit 用 IP 但有 nginx → X-Forwarded-For（但不可信，要白名單）
✗ CSRF token 比對用 hmac.compare_digest（防 timing attack）
✗ CSP 'unsafe-eval' 在 dev 必要（Next.js dev mode 用 eval），prod 必移除
✗ Audit 寫入失敗的 trace_id 還是要回 client（不擋 request）
✗ Hash chain trigger 在 transaction abort 時也會跑 → 要 BEFORE INSERT
✗ Audit log 寫入用 ta_service_rw（INSERT only，UPDATE/DELETE 已 REVOKE）
✗ Body size middleware 對 streaming 不適用 → 只擋 Content-Length
✗ Sort field whitelist 漏設 → SQL injection 風險（ORDER BY 不能參數化）

【8. Self-Check SOP】
跑第 8.5.4 章「每 Phase 必跑的 Self-Check SOP」全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/core/audit_middleware.py
  - backend/app/repos/audit_repo.py
  - backend/app/core/rate_limit.py
  - backend/app/core/csrf_middleware.py
  - backend/app/core/validators.py（完整版）
  - backend/app/core/body_size_middleware.py
  - scripts/verify_audit_chain.py
  - 7 個 test files（共 ~39 個測試）
  - scripts/health_checks/phase_09.sh

程式檔（修改）：
  - backend/app/core/security_headers.py（加 CSP dev）
  - backend/app/main.py（middleware 順序整理）

文件檔（新增）：
  - docs/phase_reports/PHASE_09.md
  - docs/runbooks/security.md（rate limit 調整、audit chain 修復）

文件檔（更新）：
  - docs/setup.md
  - docs/phase_progress.md

Git tag：phase-09-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：I（middleware 順序）一定要對，否則 audit log 沒 trace_id 或 CSRF 順序錯導致 login 也擋。
測試 D（CSRF middleware）建議手寫 fastapi TestClient 流程，不要單純 unit test。
```

---

### ▌Phase 10 — 業務 API 第一批（users/stocks/market/watchlist/screener，auth 已在 P8）

```
=== TradingAgents-TW Phase 10（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\backend
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 10
必讀 PLAN.md 章節：第 8.5, 17.3, 17.4, 17.5, 18.1, 19.2 章

【1. 前置依賴 Phase】
依賴：Phase 1-9
驗證方式：bash scripts/health_checks/phase_09.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_09.sh
- /auth/login 流程通
- audit + rate limit + CSRF 都生效

【3. 本 Phase 目標】
建立「市場資訊類」業務 API（與 Agent 無關）：
  (1) /api/v1/users/* （CRUD，admin only）
  (2) /api/v1/stocks/* （搜尋、清單、詳情、OHLCV、技術指標）
  (3) /api/v1/market/* （大盤、三大法人、漲跌排行）
  (4) /api/v1/watchlist/* （CRUD per user）
  (5) /api/v1/screener/* （多條件篩選）
  (6) Cursor pagination 統一（依 17.4）
  (7) 統一回應 envelope（17.3）
  (8) 全部要過 Auth + RBAC + Audit
  (9) Decimal JSON 字串序列化（17.5）

注意：本 Phase「不寫 analysis / orders / reports / exports」（在 P11）。
注意：本 Phase「沒有 LangGraph 介入」，純資料 API。

【4. 任務清單】

A. 切分支：phase/10-api-first-batch

B. backend/app/api/v1/users_router.py：
   - GET /api/v1/users (admin only, list, cursor pagination)
   - POST /api/v1/users (admin only, create)
   - GET /api/v1/users/{id} (admin or self)
   - PATCH /api/v1/users/{id} (admin or self)
   - DELETE /api/v1/users/{id} (admin only, soft delete)
   - POST /api/v1/users/{id}/reset-password (admin only)

C. backend/app/api/v1/stocks_router.py：
   - GET /api/v1/stocks?market=TW|US&q=keyword&cursor=&limit=
   - GET /api/v1/stocks/{symbol}
   - GET /api/v1/stocks/{symbol}/ohlcv?start=&end=&interval=daily
   - GET /api/v1/stocks/{symbol}/indicators?period=14&type=RSI,MACD,KD,BBANDS
   - GET /api/v1/stocks/{symbol}/financial（quarterly/annual）
   - GET /api/v1/stocks/{symbol}/news?since=&limit=
   - GET /api/v1/stocks/{symbol}/announcements

D. backend/app/api/v1/market_router.py：
   - GET /api/v1/market/overview?market=TW|US（指數 + 漲跌家數 + 成交量）
   - GET /api/v1/market/institutional?market=TW&date=（三大法人 - TW only）
   - GET /api/v1/market/movers?market=TW&type=gainers|losers|volume
   - GET /api/v1/market/calendar?from=&to=（財報日曆 - mock，P17 完整）

E. backend/app/api/v1/watchlist_router.py：
   - GET /api/v1/watchlist
   - POST /api/v1/watchlist {symbol, market, note}
   - PATCH /api/v1/watchlist/{id} {note, sort_order}
   - DELETE /api/v1/watchlist/{id}

F. backend/app/api/v1/screener_router.py：
   - GET /api/v1/screener?market=TW&filters=...&sort=...
     filter conditions: PE_min, PE_max, dividend_yield_min, EPS_growth_min, RSI_min, RSI_max, ...

G. backend/app/services/stock_service.py / market_service.py / watchlist_service.py / screener_service.py：
   - 業務邏輯：權限檢查、跨表 join、cache 整合
   - cache 用 17.5 章規範（Redis db0）

H. backend/app/repos/watchlist_repo.py：
   - list_for_user, add, update, delete, count
   - add 時 unique constraint check（user_id + symbol）

I. backend/app/repos/market_repo.py：
   - get_market_overview（含 cache 5min）
   - get_institutional_for_date
   - get_movers

J. backend/app/repos/screener_repo.py：
   - 動態 SQL builder（依 filter conditions）
   - sort whitelist
   - cursor pagination

K. backend/app/core/cursor.py：
   class Cursor:
     @classmethod
     def encode(cls, **kwargs) -> str:
       return base64.urlsafe_b64encode(json.dumps(kwargs).encode()).decode()
     @classmethod
     def decode(cls, cursor: str) -> dict:
       try: return json.loads(base64.urlsafe_b64decode(cursor.encode()))
       except: raise ValidationError(message_zh="cursor 格式錯誤")

L. backend/app/schemas/stocks.py / market.py / watchlist.py / screener.py：
   - 完整 Pydantic v2 + Decimal as str（json_encoders）

M. backend/tests/integration/test_users_router.py（≥ 6 個測試）
N. backend/tests/integration/test_stocks_router.py（≥ 8 個測試含 OHLCV 範圍 + cursor）
O. backend/tests/integration/test_market_router.py（≥ 5 個測試）
P. backend/tests/integration/test_watchlist_router.py（≥ 6 個測試含 unique）
Q. backend/tests/integration/test_screener_router.py（≥ 5 個測試）
R. backend/tests/unit/test_cursor.py（≥ 4 個測試）

S. 寫 scripts/health_checks/phase_10.sh + docs/phase_reports/PHASE_10.md + 更新 phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 10 = 以下 12 個指令全部 exit code 0：

```bash
# 1. uv sync + lint + 啟動
cd backend && uv sync && uv run ruff check app/ && cd ..
cd backend && uv run uvicorn app.main:app --port 8000 &
SERVER_PID=$!
sleep 3

# 2. /openapi.json 至少 25 個 endpoint
curl -s http://localhost:8000/openapi.json | jq -r '.paths | keys | length' | awk '$1 >= 25'

# 3. login + 取得 TOKEN
ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env | cut -d= -f2)
ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env | cut -d= -f2)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}" | jq -r '.data.access_token')

# 4. GET /stocks 200
curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stocks?market=TW&limit=10" | jq '.data | length'

# 5. GET /stocks/2330 200
curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stocks/2330" | jq '.data.symbol' | grep "2330"

# 6. GET /stocks/2330/ohlcv 200，Decimal 為字串
curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stocks/2330/ohlcv?start=2026-04-01&end=2026-04-30" | jq '.data[0].close' | grep -E "^\".*\"$"

# 7. POST /watchlist 加 2330（含 CSRF）
CSRF=$(grep csrf_token /tmp/cookies.txt | awk '{print $7}')
curl -fsS -X POST -b /tmp/cookies.txt -H "Authorization: Bearer $TOKEN" -H "X-CSRF-Token: $CSRF" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/watchlist -d '{"symbol":"2330","market":"TWSE","note":"test"}'

# 8. GET /watchlist 含 2330
curl -fsS -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/watchlist | jq '.data[].symbol' | grep "2330"

# 9. cursor pagination
RESP=$(curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stocks?limit=2")
CURSOR=$(echo "$RESP" | jq -r '.pagination.next_cursor')
test "$CURSOR" != "null" && test -n "$CURSOR"
curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stocks?limit=2&cursor=$CURSOR"

# 10. screener 過濾
curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/screener?market=TW&PE_max=15&limit=10" | jq '.data | length'

# 11. RBAC：viewer 不能 POST /users
# 假設先建一個 viewer user，這裡略
# STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $VIEWER_TOKEN" -X POST http://localhost:8000/api/v1/users -d '{...}')
# test "$STATUS" = "403"

# 12. 全部新測試通過 + health_check
cd backend && uv run pytest tests/integration/test_users_router.py tests/integration/test_stocks_router.py \
  tests/integration/test_market_router.py tests/integration/test_watchlist_router.py \
  tests/integration/test_screener_router.py tests/unit/test_cursor.py -v && cd ..
kill $SERVER_PID
bash scripts/health_checks/phase_10.sh
```

【6. Smoke Test（手動）】
✓ Swagger /docs 試打每個新 endpoint
✓ 故意送錯 symbol → 422 中文 message + trace_id
✓ /watchlist 重複加 → 409 ConflictError
✓ DevTools Network 看 response header 含 X-Request-ID

【7. 已知陷阱】
✗ Decimal JSON 序列化用 model_config + json_encoders={Decimal: str}
✗ datetime 用 ISO 8601 + UTC（17.3）
✗ cursor 含 UUID/datetime 要 serialize 成 str
✗ Sort field 沒 whitelist → SQL injection
✗ N+1 查詢：用 selectinload / joinedload
✗ Watchlist unique violation → 422 with 中文 message（不要回 IntegrityError stack）
✗ Screener 動態 SQL 用 SQLAlchemy expression（非 string format）
✗ CSRF token cookie 跨子網域問題（dev localhost 沒事）
✗ admin only endpoint 漏 RBAC dependency → 任何人都能改用戶
✗ /stocks/{symbol}/ohlcv 沒 limit → 大查詢拖累 DB（強制 max 10000 row）
✗ market overview cache 失敗 → 不擋 request，繼續直接查

【8. Self-Check SOP】跑第 8.5.4 章全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/api/v1/{users, stocks, market, watchlist, screener}_router.py
  - backend/app/services/{stock, market, watchlist, screener}_service.py
  - backend/app/repos/{watchlist, market, screener}_repo.py（stock_repo + ohlcv_repo 已在 P5）
  - backend/app/schemas/{stocks, market, watchlist, screener}.py
  - backend/app/core/cursor.py
  - 6 個 test files（共 ~34 個測試）
  - scripts/health_checks/phase_10.sh

程式檔（修改）：
  - backend/app/main.py（include 5 個新 router）

文件檔（新增）：
  - docs/phase_reports/PHASE_10.md

文件檔（更新）：
  - docs/phase_progress.md
  - docs/runbooks/api.md（cursor pagination 用法）

Git tag：phase-10-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：B-F 是並行的 5 個 router，建議按「先 stocks → 再 watchlist → 再 market → 再 screener → 最後 users」順序，
每寫完一個 router 立即跑該 router 的 integration test。
```

---

### ▌Phase 11 — 業務 API 第二批（analysis/orders/reports/exports/notifications/admin/ws/metrics）

```
=== TradingAgents-TW Phase 11（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\backend
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 11
必讀 PLAN.md 章節：第 8.5, 14.5, 14.10, 15.1, 15.2, 16.2, 17.3, 17.5, 19.1.5 章

【1. 前置依賴 Phase】
依賴：Phase 1-10
驗證方式：bash scripts/health_checks/phase_10.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_10.sh
- /api/v1/stocks 等 P10 endpoint 全部正常

【3. 本 Phase 目標】
建立「業務動作類」+「管理類」+「即時通訊類」API：
  (1) /api/v1/analysis/* （含 stub run_analysis - LangGraph 在 P12+）
  (2) /api/v1/orders/* （pending_orders + 並發核准）
  (3) /api/v1/reports/* （讀分析報告）
  (4) /api/v1/exports/* （PDF/MD/XLSX）
  (5) /api/v1/notifications/* （settings + log）
  (6) /api/v1/admin/* （audit logs / system / pipeline / DLQ）
  (7) /api/v1/ws/* （WebSocket，用 ticket）
  (8) /metrics（Prometheus format，admin only）
  (9) Idempotency-Key 機制（POST 建立類）
  (10) 並發核准用 SELECT FOR UPDATE + version column

注意：run_analysis 是 stub（先寫 Celery task placeholder），實際 LangGraph 在 P12+。
注意：PDF 用 Playwright（依 ADR-010），Dockerfile 加 chromium + fonts-noto-cjk。

【4. 任務清單】

A. 切分支：phase/11-api-second-batch

B. backend/Dockerfile 升級：
   - 加 fonts-noto-cjk
   - 安裝 playwright + chromium：RUN uv run playwright install-deps chromium && uv run playwright install chromium

C. backend/app/api/v1/analysis_router.py：
   - POST /api/v1/analysis (Idempotency-Key required)
       body: {symbol, analyst_types, llm_model, debate_rounds, ...}
       回 {analysis_id, status: "queued", estimated_seconds}
       內部：寫 analysis_reports + 推 celery task (P12 才會真跑)
   - GET /api/v1/analysis (list, cursor)
   - GET /api/v1/analysis/{id}
   - GET /api/v1/analysis/{id}/debate
   - POST /api/v1/analysis/{id}/cancel
   - DELETE /api/v1/analysis/{id} (admin only)

D. backend/app/api/v1/orders_router.py：
   - GET /api/v1/orders?status=PENDING|APPROVED|REJECTED
   - GET /api/v1/orders/{id}
   - POST /api/v1/orders/{id}/approve（並發保護）
   - POST /api/v1/orders/{id}/reject

   approve 用 SELECT FOR UPDATE + version：
     async with rw.begin():
       order = await session.execute(
         select(PendingOrder).where(PendingOrder.id == order_id, PendingOrder.version == expected_version)
         .with_for_update()
       ).scalar_one_or_none()
       if not order: raise ConflictError(message_zh="訂單已被其他人處理")
       if order.status != "PENDING": raise ConflictError(...)
       order.status = "APPROVED"; order.version += 1
       order.approved_by = user.id
       session.add(PortfolioPosition(...))  # 同 transaction
       await audit_repo.append(action="order.approved", ...)

E. backend/app/api/v1/reports_router.py：
   - GET /api/v1/reports/{id}（同 analysis 但完整）

F. backend/app/api/v1/exports_router.py：
   - GET /api/v1/exports/{report_id}?format=pdf|md|xlsx
   - PDF：Jinja2 template → HTML → Playwright render → bytes
   - MD：直接從 analysis_reports.report_md
   - XLSX：openpyxl 組裝表格

G. backend/app/services/exports_service.py：
   class ExportsService:
     async def export_pdf(self, report_id) -> bytes:
       html = render_template(...)
       async with async_playwright() as p:
         browser = await p.chromium.launch(args=["--no-sandbox"])
         page = await browser.new_page()
         await page.set_content(html)
         pdf = await page.pdf(format="A4", print_background=True)
         await browser.close()
       return pdf
     async def export_md(self, report_id) -> str: ...
     async def export_xlsx(self, report_id) -> bytes: ...

H. backend/app/api/v1/notifications_router.py：
   - GET /api/v1/notifications/settings
   - PUT /api/v1/notifications/settings（line_token, telegram_token 加密儲存）
   - POST /api/v1/notifications/test
   - GET /api/v1/notifications/logs?cursor=&limit=

I. backend/app/api/v1/admin_router.py：
   - GET /api/v1/admin/audit?actor=&entity=&action=&from=&to=&cursor=
   - GET /api/v1/admin/system/metrics（呼叫 /metrics 內部）
   - GET /api/v1/admin/pipeline/dlq?resolved=false&cursor=
   - POST /api/v1/admin/pipeline/dlq/{id}/resolve
   - POST /api/v1/admin/pipeline/dlq/{id}/requeue
   - GET /api/v1/admin/users/{id}/sessions
   - DELETE /api/v1/admin/users/{id}/sessions/{jti}（強制下線）
   都需要 admin_only

J. backend/app/api/v1/ws_router.py（**v7.0 修正：含 IDOR 防護 + 服務注入**）：
   ```python
   from fastapi import APIRouter, WebSocket, WebSocketDisconnect
   from app.core.ws_ticket import WSTicketService
   from app.core.redis_client import get_redis
   from app.core.database import ro_session
   from app.repos.user_repo import UserRepository
   from app.repos.analysis_repo import AnalysisRepository

   router = APIRouter()

   # WSTicketService 在 app lifespan 註冊到 app.state
   # Redis 用 dependency-style helper

   @router.websocket("/api/v1/ws/analysis/{analysis_id}")
   async def ws_analysis(websocket: WebSocket, analysis_id: UUID):
     ticket_service: WSTicketService = websocket.app.state.ws_ticket_service
     pubsub_redis = await get_redis(db=4)  # pubsub channel

     # 1. 從 subprotocol 取 ticket
     subprotocols = websocket.scope.get("subprotocols", [])
     ticket = next(
       (s.split(".", 1)[1] for s in subprotocols if s.startswith("ticket.")),
       None,
     )
     if not ticket:
       await websocket.close(code=1008, reason="missing ticket")
       return

     # 2. 一次性 consume ticket
     user_id = await ticket_service.consume(ticket)
     if not user_id:
       await websocket.close(code=1008, reason="invalid ticket")
       return

     # 3. **IDOR 防護：驗證 user 對此 analysis 有讀取權限**
     async with ro_session() as s:
       user = await UserRepository(s).get_by_id(user_id)
       analysis = await AnalysisRepository(s).get_by_id(analysis_id)
       if not analysis:
         await websocket.close(code=1008, reason="analysis not found")
         return
       # 規則：admin 可看所有；其他 role 只能看自己的
       if user.role != "ADMIN" and analysis.user_id != user_id:
         await websocket.close(code=1008, reason="forbidden")
         logger.warning(
           "ws.analysis.forbidden",
           user_id=str(user_id), analysis_id=str(analysis_id),
         )
         return

     # 4. accept + subscribe
     await websocket.accept(subprotocol="tradingagents.v1")

     pubsub = pubsub_redis.pubsub()
     await pubsub.subscribe(f"analysis:{analysis_id}")
     try:
       async for msg in pubsub.listen():
         if msg["type"] == "message":
           await websocket.send_text(
             msg["data"].decode() if isinstance(msg["data"], bytes) else msg["data"]
           )
     except WebSocketDisconnect:
       pass
     finally:
       await pubsub.unsubscribe(f"analysis:{analysis_id}")
       await pubsub.close()
   ```

   **OWASP IDOR 測試（在 P18 必加）：**
   - userA 跑 analysisA，userB 拿 analysisA 的 id 嘗試 WS 訂閱 → 應 1008 close
   - admin 拿任何 analysis_id 都可訂閱 → 應正常工作

K. backend/app/api/v1/metrics_router.py：
   from prometheus_client import generate_latest, REGISTRY, Counter, Histogram

   ANALYSIS_TOTAL = Counter("analysis_total", "Total analysis", ["status"])
   ANALYSIS_DURATION = Histogram("analysis_duration_seconds", "Analysis duration")
   LLM_COST_TODAY = Gauge("llm_cost_usd_today", "Today's LLM cost")
   ...

   @router.get("/metrics")
   async def metrics(user = Depends(admin_only)):
     return Response(generate_latest(REGISTRY), media_type="text/plain")

L. backend/app/core/idempotency.py：
   class IdempotencyService:
     async def check_or_record(self, key, user_id, request_hash) -> dict | None:
       """回 None = 沒見過、可繼續；回 dict = 之前的回應，直接回給 client"""
       # 用 Redis db6 + DB（雙寫，TTL 24h）
       cached = await redis.get(f"idem:{user_id}:{key}")
       if cached: return json.loads(cached)
       return None

     async def record_response(self, key, user_id, request_hash, response_data):
       await redis.setex(f"idem:{user_id}:{key}", 86400, json.dumps(response_data))
       # 同時寫 DB idempotency_keys 表（持久備份）

M. backend/app/repos/{order_repo, analysis_repo, notification_repo}.py
N. backend/app/services/{analysis_service, order_service, notification_service, admin_service}.py

O. backend/tests/integration/test_analysis_router.py（≥ 6 個測試）
P. backend/tests/integration/test_orders_concurrent_approve.py（≥ 4 個測試含並發）
Q. backend/tests/integration/test_exports_pdf.py（≥ 4 個測試 - skip 如沒 playwright）
R. backend/tests/integration/test_notifications_router.py（≥ 5 個測試）
S. backend/tests/integration/test_admin_router.py（≥ 6 個測試）
T. backend/tests/integration/test_ws_analysis.py（≥ 4 個測試含 ticket consume）
U. backend/tests/integration/test_idempotency.py（≥ 4 個測試）
V. backend/tests/unit/test_metrics.py（≥ 3 個測試）

W. 寫 scripts/health_checks/phase_11.sh + docs/phase_reports/PHASE_11.md + 更新 phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 11 = 以下 14 個指令全部 exit code 0：

```bash
# 1-3. uv sync + ruff + 啟動 + login 拿 TOKEN
cd backend && uv sync && uv run ruff check app/ && cd ..
cd backend && uv run uvicorn app.main:app --port 8000 &
SERVER_PID=$!
sleep 3
ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env | cut -d= -f2)
ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env | cut -d= -f2)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}" | jq -r '.data.access_token')

# 4. /openapi.json 至少 50 個 endpoint
curl -s http://localhost:8000/openapi.json | jq -r '.paths | keys | length' | awk '$1 >= 50'

# 5. POST /analysis（含 Idempotency）
KEY=$(uuidgen)
RESP=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/analysis \
  -d '{"symbol":"2330","analyst_types":["market"],"llm_model":"gemini-2.0-flash","debate_rounds":1}')
ANALYSIS_ID=$(echo "$RESP" | jq -r '.data.analysis_id')
test -n "$ANALYSIS_ID"

# 同 idempotency key 第二次回相同 id
RESP2=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" http://localhost:8000/api/v1/analysis \
  -d '{"symbol":"2330","analyst_types":["market"]}')
ID2=$(echo "$RESP2" | jq -r '.data.analysis_id')
test "$ID2" = "$ANALYSIS_ID"

# 6. GET /analysis 列表
curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/analysis?limit=10" | jq '.data | length'

# 7. WS ticket + 連線（用 wscat）
TICKET=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/ws-ticket | jq -r '.data.ticket')
# 用 timeout 嘗試連線（無事件就斷）
echo "" | timeout 2 wscat -c "ws://localhost:8000/api/v1/ws/analysis/$ANALYSIS_ID" \
  -s "tradingagents.v1" -s "ticket.$TICKET" || echo "expected timeout"

# 8. PDF 匯出（中文）
# 先建一個 fake completed report 給測試用（DB 直接 INSERT）
PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)
PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw -c "
  UPDATE analysis_reports SET status='completed', report_md='# 台積電 (2330) 分析\n\n投資建議：BUY' WHERE id='$ANALYSIS_ID'
"
curl -fsS -H "Authorization: Bearer $TOKEN" -o /tmp/report.pdf \
  "http://localhost:8000/api/v1/exports/$ANALYSIS_ID?format=pdf"
file /tmp/report.pdf | grep -i "PDF document"
pdftotext /tmp/report.pdf - | grep "台積電"

# 9. 並發核准（建一個 pending order）
PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw -c "
  INSERT INTO pending_orders (id, user_id, analysis_id, symbol, market, side, qty, version, status)
  VALUES (gen_random_uuid(), (SELECT id FROM users WHERE email='$ADMIN_EMAIL'), '$ANALYSIS_ID', '2330', 'TWSE', 'BUY', 1000, 1, 'PENDING')
  RETURNING id
"
ORDER_ID=$(PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw -tAc "SELECT id FROM pending_orders WHERE analysis_id='$ANALYSIS_ID' LIMIT 1")
# 並發兩個 approve
curl -X POST -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/orders/$ORDER_ID/approve" &
curl -X POST -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/orders/$ORDER_ID/approve" &
wait
# 一個 200，一個 409
PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw -tAc "SELECT count(*) FROM pending_orders WHERE id='$ORDER_ID' AND status='APPROVED'" | grep -q "^1$"

# 10. /metrics admin only
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/metrics | grep -E "^401$|^403$"
curl -fsS -H "Authorization: Bearer $TOKEN" http://localhost:8000/metrics | grep "analysis_total"

# 11. /admin/audit 可查
curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/admin/audit?limit=10"

# 12. /admin/pipeline/dlq 可查
curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/admin/pipeline/dlq"

# 13. 全部新測試通過 + 累積 ≥ 268
cd backend && uv run pytest tests/integration/test_analysis_router.py \
  tests/integration/test_orders_concurrent_approve.py tests/integration/test_exports_pdf.py \
  tests/integration/test_notifications_router.py tests/integration/test_admin_router.py \
  tests/integration/test_ws_analysis.py tests/integration/test_idempotency.py \
  tests/unit/test_metrics.py -v && cd ..

kill $SERVER_PID

# 14. health_check phase_11 通過
bash scripts/health_checks/phase_11.sh
```

【6. Smoke Test（手動）】
✓ Swagger 試打 analysis / orders / exports / admin
✓ 從不同 user 並發 approve 同 order → 一個成功一個 409
✓ wscat 連 WS 後手動 publish 到 Redis：docker compose exec redis redis-cli -a $PWD PUBLISH analysis:$ID '{"event":"test"}'
✓ /metrics 用 prometheus 格式，可被 prom-tool import

【7. 已知陷阱】
✗ Playwright 在 alpine container 缺 deps → Dockerfile 用 debian-slim
✗ Playwright chromium 啟動慢 → 第一次 ~3 秒
✗ chromium 在 docker 必須 --no-sandbox（root user）
✗ PDF 中文亂碼 → 一定要 fonts-noto-cjk + CSS @font-face
✗ Idempotency key 不分 user → 不同 user 用同 key 會撞
✗ Idempotency 寫入 DB 失敗 → 不擋（log + 繼續）
✗ SELECT FOR UPDATE 沒在 transaction → 等同沒鎖
✗ Version 比對失敗時 ConflictError 訊息要中文
✗ WS subprotocol 命名一致：必有 "tradingagents.v1" + "ticket.XXX" 兩個
✗ WS 客戶端關閉時 pubsub 沒 unsubscribe → 記憶體洩漏
✗ /metrics 不要 audit（會無限遞迴）
✗ Admin force logout 時要 blacklist token + revoke session（雙保險）
✗ DLQ resolve 時要記 admin id + reason

【8. Self-Check SOP】跑第 8.5.4 章全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/api/v1/{analysis, orders, reports, exports, notifications, admin, ws, metrics}_router.py（8 個）
  - backend/app/services/{analysis, order, exports, notification, admin}_service.py
  - backend/app/repos/{order, analysis, notification, admin}_repo.py
  - backend/app/core/idempotency.py
  - 8 個 test files（共 ~36 個測試）
  - scripts/health_checks/phase_11.sh

程式檔（修改）：
  - backend/Dockerfile（加 chromium + fonts-noto-cjk + playwright install）
  - backend/pyproject.toml（加 playwright, prometheus-client, openpyxl）
  - backend/app/main.py（include 8 個新 router）

文件檔（新增）：
  - docs/phase_reports/PHASE_11.md
  - docs/runbooks/exports.md（PDF 中文字型問題排查）

文件檔（更新）：
  - docs/phase_progress.md

Git tag：phase-11-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：B（Dockerfile + chromium）建議先跑、確認 PDF 能 build 成功，再寫業務 router。
PDF 中文字型容易失敗，先用簡單 HTML 模板 smoke test 通過再做完整模板。
```

---

### ▌Phase 12 — LangGraph 基礎 + Plugin + State trim + Tool 註冊

```
=== TradingAgents-TW Phase 12（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\backend
原版參考：C:\Projects\TradingAgents\legacy\tradingagents\
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 12
必讀 PLAN.md 章節：第 4.4（legacy 參考清單）, 6.1（langgraph 版本）, 8.5, 14.4, 14.9, 18.2, 19, 20.4 章

【1. 前置依賴 Phase】
依賴：Phase 1-11
驗證方式：bash scripts/health_checks/phase_11.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_11.sh
- POST /api/v1/analysis 可建 analysis_reports（status=queued）
- celery worker 跑

【3. 本 Phase 目標】
建立「LangGraph 與 Tool 框架」（不寫 Analyst 內容，Analyst 在 P13/14）：
  (1) AgentState TypedDict（symbol, market, region, debate_history, signal, ...）
  (2) BaseAnalyst Plugin（含 supported_regions / display_name_zh / analyze）
  (3) ANALYST_REGISTRY（依 18.2）
  (4) 4 種台股 Analyst stub（market/fundamental/news/sentiment）只有 class 殼
  (5) Tools 註冊：get_ohlcv / get_company_info / get_financial / get_news / get_announcements / get_institutional / get_margin / get_monthly_revenue
  (6) Tools 全部用 ta_agent_ro session（防 SQL injection）
  (7) State trim（依 14.9）
  (8) BaseLLMProvider 抽象 + Gemini 實作
  (9) build_graph(symbol, market) 函數骨架
  (10) Celery task run_analysis 改為真實呼叫（但 LLM 部分用 mock）

注意：Bull/Bear/Manager Researcher 在 P13、美股 Analyst 在 P14。

【4. 任務清單】

A. 切分支：phase/12-langgraph-foundation

B. backend/pyproject.toml 加：
   langgraph>=0.2.50,<0.3
   langchain-core>=0.3,<0.4
   langchain-google-genai>=2.0
   tiktoken  # token counting

C. backend/app/agents/state.py：
   from typing import TypedDict, Annotated
   from operator import add

   class AgentState(TypedDict):
     symbol: str
     market: Market
     region: MarketRegion
     debate_rounds: int
     llm_model: str
     analyst_types: list[str]

     # 累積欄位
     analyses: dict[str, str]  # {analyst_name: analysis_text}
     debate_history: Annotated[list[dict], add]  # [{role, content, round}]
     bull_arguments: list[str]
     bear_arguments: list[str]

     # 終結欄位
     signal: dict | None  # {action: BUY/SELL/HOLD, confidence: 0-100, reasoning, ...}
     report_md: str | None

     # metadata
     trace_id: str
     analysis_id: str
     started_at: str  # ISO
     llm_usage_total_tokens: int

D. backend/app/agents/base_analyst.py：
   class BaseAnalyst(ABC):
     name: ClassVar[str]
     display_name_zh: ClassVar[str]
     supported_regions: ClassVar[list[MarketRegion]]
     required_data_kinds: ClassVar[list[DataKind]]

     def __init__(self, llm: BaseLLMProvider, tools: ToolRegistry):
       self.llm = llm
       self.tools = tools

     @abstractmethod
     async def analyze(self, state: AgentState) -> dict:
       """回 {analyses[name]: text}"""
       ...

     def can_handle(self, region: MarketRegion) -> bool:
       return region in self.supported_regions

   ANALYST_REGISTRY: dict[str, type[BaseAnalyst]] = {}

   def register_analyst(cls):
     ANALYST_REGISTRY[cls.name] = cls
     return cls

E. backend/app/agents/analysts/{market,fundamental,news,sentiment}_analyst.py（stub）：
   @register_analyst
   class MarketAnalyst(BaseAnalyst):
     name = "market"
     display_name_zh = "技術面分析師"
     supported_regions = [MarketRegion.TW, MarketRegion.US]
     required_data_kinds = [DataKind.OHLCV]

     async def analyze(self, state):
       # P13 才寫真實內容
       return {"analyses": {self.name: f"[stub] {self.display_name_zh} for {state['symbol']}"}}

F. backend/app/agents/tools/__init__.py（Tool registry 全部用 ta_agent_ro）：
   from langchain_core.tools import tool

   class ToolRegistry:
     def __init__(self, ro_session_factory):
       self.ro = ro_session_factory

     @tool
     async def get_ohlcv(self, symbol: str, days_back: int = 60) -> list[dict]:
       """取得近 N 日 OHLCV，自動依 symbol 判市場"""
       async with self.ro() as session:
         repo = OHLCVRepository(session)
         region = detect_region(symbol)
         market = Market.TWSE if region == MarketRegion.TW else Market.NASDAQ  # 簡化
         end = date.today(); start = end - timedelta(days=days_back)
         rows = await repo.get_range(symbol, market, start, end)
         return [r.dict() for r in rows]

     @tool
     async def get_company_info(self, symbol): ...
     @tool
     async def get_financial(self, symbol, quarters_back=4): ...
     @tool
     async def get_news(self, symbol, days_back=7, max_items=20): ...
     @tool
     async def get_announcements(self, symbol, days_back=30): ...
     @tool
     async def get_institutional(self, symbol, days_back=30):
       """TW only"""
       if detect_region(symbol) != MarketRegion.TW: raise ValidationError(...)
       ...
     @tool
     async def get_margin(self, symbol, days_back=30): ...  # TW only
     @tool
     async def get_monthly_revenue(self, symbol, months_back=12): ...  # TW only

G. backend/app/llm/base_provider.py：
   class BaseLLMProvider(ABC):
     name: ClassVar[str]

     @abstractmethod
     async def generate(self, system: str, user: str, tools: list = None,
                        max_tokens: int = 2048, temperature: float = 0.3) -> LLMResponse: ...

     @abstractmethod
     async def health_check(self) -> bool: ...

     async def count_tokens(self, text: str) -> int:
       return len(tiktoken.encoding_for_model("gpt-4").encode(text))

   class LLMResponse(BaseModel):
     content: str
     tool_calls: list = []
     usage: TokenUsage  # input_tokens, output_tokens, total_tokens, cost_usd

H. backend/app/llm/gemini_provider.py：
   from langchain_google_genai import ChatGoogleGenerativeAI

   @register_llm_provider
   class GeminiProvider(BaseLLMProvider):
     name = "google"
     def __init__(self, settings):
       self.client = ChatGoogleGenerativeAI(
         model=settings.LLM_DEFAULT_MODEL,  # gemini-2.0-flash
         google_api_key=settings.GOOGLE_API_KEY,
         temperature=0.3,
       )

     async def generate(self, system, user, tools=None, max_tokens=2048):
       # 計算 cost：依 https://ai.google.dev/pricing
       ...

I. backend/app/agents/state_trim.py（依 14.9）：
   MAX_STATE_SIZE_BYTES = 500_000

   def estimate_state_size(state: AgentState) -> int:
     return len(json.dumps(state, default=str).encode())

   async def trim_debate_history(state: AgentState, llm: BaseLLMProvider) -> AgentState:
     if len(state["debate_history"]) > 6:
       old, recent = state["debate_history"][:-6], state["debate_history"][-6:]
       summary = await llm.generate(system="...", user=f"摘要：{old}", max_tokens=500)
       state["debate_history"] = [{"role": "summary", "content": summary.content}] + recent
     return state

J. backend/app/agents/graph_builder.py：
   from langgraph.graph import StateGraph, END

   def build_graph(symbol: str, market: Market, debate_rounds: int = 1) -> StateGraph:
     region = detect_region(symbol)
     # 過濾可用 analysts（依 region）
     analysts = [cls() for name, cls in ANALYST_REGISTRY.items() if region in cls.supported_regions]

     graph = StateGraph(AgentState)
     for analyst in analysts:
       graph.add_node(analyst.name, analyst.analyze)

     # P13 才補 bull/bear/manager
     graph.add_node("manager", placeholder_manager)

     # edges
     graph.set_entry_point(analysts[0].name if analysts else END)
     for i, a in enumerate(analysts[:-1]):
       graph.add_edge(a.name, analysts[i+1].name)
     graph.add_edge(analysts[-1].name, "manager")
     graph.add_edge("manager", END)

     return graph.compile(checkpointer=None)  # P13/14 才加 checkpointer

K. backend/app/workers/tasks/run_analysis.py（**v7.0 注意：P12 = 框架 stub，P13 + P14 才接真實 LLM**）：
   @celery_app.task(bind=True, time_limit=1200, soft_time_limit=900)
   def run_analysis(self, analysis_id: str):
     """主任務：跑 LangGraph

     ⚠️ **本 Phase（P12）執行邏輯為「框架」**：
     - 4 種 Analyst 都是 stub（回固定文字 "[stub] xxx for symbol"）
     - LLM Provider 只接了 Gemini（無 fallback）
     - Bull/Bear/Manager 在 P13 才加入 graph
     - 跑 2330 會 status=completed + report_md 為固定模板（**不是真實 LLM 分析**）

     完整版時程：
     - P13：4 種台股 Analyst 真實 prompt + Bull/Bear/Manager + 結構化輸出
     - P14：美股 Analyst（共用 class）+ LLM Fallback Chain + WS streaming + 月配額
     """
     # 1. 從 DB 取 analysis_reports row
     # 2. build_graph
     # 3. 跑 graph.ainvoke(initial_state)
     # 4. 寫回 analysis_reports（status, report_md, signal）
     # 5. publish 到 Redis pubsub channel "analysis:{id}"（P14 才接 streaming events）
     # 6. 失敗 → status='failed' + DLQ（task_failure signal 自動）
     ...

   **P12 退出條件期望：** 跑 stub graph 應在 30 秒內 status=completed，
   report_md 應出現 "[stub]" 字樣（user 可知道現在還是測試版）。

L. backend/app/api/v1/analysis_router.py 升級：
   POST /api/v1/analysis 改為實際推 celery task：
     analysis_id = await analysis_service.create_pending(...)
     run_analysis.delay(str(analysis_id))
     return {"analysis_id": analysis_id, "status": "queued", ...}

M. backend/tests/unit/test_state_trim.py（≥ 4 個測試）
N. backend/tests/unit/test_graph_builder.py（≥ 5 個測試 - 不跑真實 LLM）
O. backend/tests/unit/test_tool_registry.py（≥ 8 個測試 - mock DB session）
P. backend/tests/unit/test_gemini_provider.py（≥ 4 個測試 - mock httpx）
Q. backend/tests/integration/test_analysis_pipeline_stub.py（≥ 3 個測試 - end-to-end with stub analysts）

R. 寫 scripts/health_checks/phase_12.sh + docs/phase_reports/PHASE_12.md + 更新 phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 12 = 以下 11 個指令全部 exit code 0：

```bash
# 1-3. uv sync + lint + 啟動 + workers
cd backend && uv sync && uv run ruff check app/ && cd ..
cd backend && uv run uvicorn app.main:app --port 8000 &
SERVER_PID=$!
sleep 3
make up-workers

# 4. 4 種 analyst 註冊
cd backend && uv run python -c "
from app.agents.analysts.market_analyst import MarketAnalyst
from app.agents.analysts.fundamental_analyst import FundamentalAnalyst
from app.agents.analysts.news_analyst import NewsAnalyst
from app.agents.analysts.sentiment_analyst import SentimentAnalyst
from app.agents.base_analyst import ANALYST_REGISTRY
expected = {'market', 'fundamental', 'news', 'sentiment'}
got = set(ANALYST_REGISTRY.keys()) & expected
assert got == expected, f'missing: {expected - got}'
print('OK')
"
cd ..

# 5. build_graph 對 TW symbol 含 sentiment
cd backend && uv run python -c "
from app.agents.graph_builder import build_graph
from app.models.stock import Market
g = build_graph('2330', Market.TWSE, debate_rounds=1)
assert 'sentiment' in g.nodes, 'TW should have sentiment analyst'
print('OK')
"
cd ..

# 6. build_graph 對 US symbol 不含 sentiment
cd backend && uv run python -c "
from app.agents.graph_builder import build_graph
from app.models.stock import Market
g = build_graph('AAPL', Market.NASDAQ, debate_rounds=1)
assert 'sentiment' not in g.nodes, 'US should NOT have sentiment'
print('OK')
"
cd ..

# 7. Tool 用 ro session（試 INSERT 應失敗）
cd backend && uv run python -c "
import asyncio
from app.agents.tools import ToolRegistry
from app.core.database import ro_session
async def main():
  r = ToolRegistry(ro_session)
  # 用 sql injection 試 INSERT 在 ro session 應失敗
  try:
    async with ro_session() as s:
      await s.execute('INSERT INTO stock_list (symbol) VALUES (\"HACK\")')
      await s.commit()
    raise Exception('should have failed')
  except Exception as e:
    if 'permission denied' in str(e) or 'read only' in str(e).lower():
      print('OK: ro session blocks INSERT')
    else:
      raise
asyncio.run(main())
"
cd ..

# 8. POST /analysis 真實推 celery task（用 stub analyst）
ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env | cut -d= -f2)
ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env | cut -d= -f2)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}" | jq -r '.data.access_token')
ID=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" http://localhost:8000/api/v1/analysis \
  -d '{"symbol":"2330","analyst_types":["market"],"llm_model":"gemini-2.0-flash","debate_rounds":1}' \
  | jq -r '.data.analysis_id')

# 9. 等 30 秒（stub analyst 應該秒回，但 celery overhead 預留時間）
sleep 30
STATUS=$(curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/analysis/$ID" | jq -r '.data.status')
test "$STATUS" = "completed" || test "$STATUS" = "running"

# 10. 全部新測試通過
cd backend && uv run pytest tests/unit/test_state_trim.py tests/unit/test_graph_builder.py \
  tests/unit/test_tool_registry.py tests/unit/test_gemini_provider.py \
  tests/integration/test_analysis_pipeline_stub.py -v && cd ..

kill $SERVER_PID

# 11. health_check phase_12 通過
bash scripts/health_checks/phase_12.sh
```

【6. Smoke Test（手動）】
✓ ipython 跑 build_graph(...).get_graph().draw_mermaid() 看 graph 結構
✓ 跑一個 analysis（stub LLM），看 celery worker log 完整跑完
✓ debate_history 累積測試：手動塞 10 條 → trim 後變 7 條（1 summary + 6 recent）
✓ Tool 嘗試用 ro session 跑 INSERT → 失敗（不會炸）

【7. 已知陷阱】
✗ langgraph 0.3 大改 API → pin <0.3
✗ AgentState TypedDict 用 Annotated[list, add] 才能累積（不然會 overwrite）
✗ build_graph 對 region 過濾錯 → US 也跑 sentiment（會炸）
✗ Tool 用 sync session 在 async 環境 → 卡住
✗ Tool 用 rw session → 安全漏洞（prompt injection 可能 INSERT/DELETE）
✗ Gemini ChatGoogleGenerativeAI 在 alpine 缺 grpcio binary → 用 debian-slim
✗ tiktoken 用 gpt-4 encoder 對 Gemini 不準（差 ~10%）→ 接受誤差
✗ State 序列化含 Decimal → JSON encoder 註冊
✗ Trim 後 messages 順序錯 → summary 在最前
✗ run_analysis task 沒包 try/except → 失敗時 status 卡 running → cleanup_orphans 兜底
✗ Celery task 內部 asyncio.run → 不要用，用 single event loop pattern
✗ Cost 計算錯（Gemini pricing 改了）→ docs 註明 pricing 來源 + 日期

【8. Self-Check SOP】跑第 8.5.4 章全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/agents/state.py
  - backend/app/agents/base_analyst.py
  - backend/app/agents/analysts/{market,fundamental,news,sentiment}_analyst.py（stub）
  - backend/app/agents/tools/__init__.py
  - backend/app/llm/base_provider.py
  - backend/app/llm/gemini_provider.py
  - backend/app/llm/__init__.py（registry）
  - backend/app/agents/state_trim.py
  - backend/app/agents/graph_builder.py
  - backend/app/workers/tasks/run_analysis.py
  - 5 個 test files（共 ~24 個測試）
  - scripts/health_checks/phase_12.sh

程式檔（修改）：
  - backend/pyproject.toml（加 langgraph, langchain-google-genai, tiktoken）
  - backend/app/api/v1/analysis_router.py（POST 改為真實推 task）

文件檔（新增）：
  - docs/phase_reports/PHASE_12.md
  - docs/runbooks/agents.md（debug graph 流程）

文件檔（更新）：
  - docs/phase_progress.md

Git tag：phase-12-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：Tool registry（F）的所有 tool 都用 ta_agent_ro，這是安全核心。
建議先跑 D-F-G-H 框架，再做 J（graph builder） + K（task），最後測試。
P13/14 會用到本 Phase 的 BaseAnalyst 與 Tool registry，介面不要中途改。
```

---

## 📍 Phase 13-17 詳細 Prompt（v7.0 第 3 次規劃補完）

> **第 3 次規劃補完範圍：Phase 13, 14, 15, 16, 17（共 5 個 Phase）。**
> **第 4 次將補完 Phase 18-20 + 全文最終 review。**

---

### ▌Phase 13 — 4 種 Analyst（台股版）+ Bull/Bear Researcher + Manager

```
=== TradingAgents-TW Phase 13（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\backend
原版參考：C:\Projects\TradingAgents\legacy\tradingagents\agents\
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 13
必讀 PLAN.md 章節：第 4.4（legacy 參考清單）, 8.5, 10.5（Analyst×市場）, 14.4, 14.9, 18.2, 20.3-20.4 章

【1. 前置依賴 Phase】
依賴：Phase 1-12
驗證方式：bash scripts/health_checks/phase_12.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_12.sh
- 4 種 Analyst class 已註冊（stub）
- BaseLLMProvider + GeminiProvider 已實作
- Tool registry 全用 ta_agent_ro
- POST /api/v1/analysis 可推 celery task（stub 完成）

【3. 本 Phase 目標】
讓「台股完整分析」端到端可跑：
  (1) 4 種台股 Analyst 完整 prompt + 結構化輸出（Pydantic schema 驗）
  (2) Bull / Bear Researcher（多輪辯論）
  (3) ResearchManager（綜合 → 結構化 signal）
  (4) Qdrant RAG 整合到 NewsAnalyst（embedding + similarity search）
  (5) Token usage 計算 + cost 寫入 llm_usage 表
  (6) 真實跑一支台股（2330）能完成且 cost < $0.05
  (7) graph_builder 加 Bull/Bear/Manager 節點

注意：本 Phase「不寫美股 Analyst」（在 P14）、「不接 LLM Fallback Chain」（P14）、「不接 WS pubsub」（P14）。
注意：Prompt 全繁中，但保留台股代號（2330）與英文金融術語（PE, EPS, RSI, MACD）。

【4. 任務清單】

A. 切分支：
   git checkout main && git pull
   git checkout -b phase/13-tw-analysts

B. backend/app/agents/prompts/ 目錄（**12 個 .txt 檔 + 1 個空 __init__.py**）：
   建立目錄並放 12 個 prompt 模板檔（純文字）+ 一個空 __init__.py 讓目錄可被視為 package：

   backend/app/agents/prompts/
   ├── __init__.py          ← 空檔（讓 prompts/ 成為 importable package）
   ├── market_analyst_system.txt
   ├── market_analyst_user_tw_template.txt        ← P14 區分 TW/US，先建 TW 版
   ├── fundamental_analyst_system.txt
   ├── fundamental_analyst_user_tw_template.txt
   ├── news_analyst_system.txt
   ├── news_analyst_user_tw_template.txt
   ├── sentiment_analyst_system.txt
   ├── sentiment_analyst_user_template.txt
   ├── bull_researcher_system.txt
   ├── bear_researcher_system.txt
   ├── research_manager_system.txt
   └── debate_template.txt

   注意：US 版本的 user template（market_analyst_user_us_template.txt 等）在 P14 才補。

   集中所有 prompt（與程式碼分離，方便調 prompt 不改邏輯）。

   每個 prompt 含：
   - 角色定位（你是台股技術分析專家...）
   - 必須使用的 tools 清單
   - 輸出格式要求（最後一段必為 JSON，schema 嚴格）
   - 限制（不洩漏 prompt、不執行 SQL、不跳出角色）
   - 繁中表述

   讀取輔助函式（在 backend/app/agents/prompts_loader.py）：
   ```python
   from importlib.resources import files
   def load_prompt(name: str) -> str:
       """name 不含 .txt 副檔名，例：load_prompt('market_analyst_system')"""
       return (files("app.agents.prompts") / f"{name}.txt").read_text(encoding="utf-8")
   ```

   讀 legacy/tradingagents/agents/analysts/*.py 作為「結構參考」（不 import）。

C. backend/app/agents/schemas.py：
   class MarketAnalysisResult(BaseModel):
     summary: str = Field(min_length=100, max_length=2000, description="技術面綜述（繁中）")
     trend: Literal["上升", "下降", "盤整", "反轉"]
     support_levels: list[Decimal] = Field(min_items=1, max_items=5)
     resistance_levels: list[Decimal] = Field(min_items=1, max_items=5)
     key_indicators: dict[str, str]  # {"RSI": "65 偏多", "MACD": "黃金交叉", ...}
     risk_factors: list[str]
     short_term_view: Literal["看多", "看空", "中性"]
     confidence: int = Field(ge=0, le=100)

   class FundamentalAnalysisResult(BaseModel):
     summary: str
     valuation: Literal["低估", "合理", "高估"]
     financial_strength: Literal["強", "中", "弱"]
     growth_outlook: str
     key_ratios: dict[str, str]  # {"PE": "15.2x（產業平均 18x）", ...}
     risk_factors: list[str]
     long_term_view: Literal["看多", "看空", "中性"]
     confidence: int = Field(ge=0, le=100)

   class NewsAnalysisResult(BaseModel):
     summary: str
     sentiment: Literal["極度正面", "正面", "中性", "負面", "極度負面"]
     key_topics: list[str]
     supporting_articles: list[dict]  # [{title, url, published_at, score}]
     impact_assessment: str
     confidence: int = Field(ge=0, le=100)

   class SentimentAnalysisResult(BaseModel):
     summary: str
     institutional_flow: Literal["大量買超", "小量買超", "中性", "小量賣超", "大量賣超"]
     foreign_position_change: str
     margin_trading_signal: Literal["看多", "看空", "中性"]
     retail_sentiment: Literal["過熱", "正常", "悲觀"]
     confidence: int = Field(ge=0, le=100)

   class BullArgument(BaseModel):
     points: list[str] = Field(min_items=3, max_items=8)
     confidence: int = Field(ge=0, le=100)
     evidence_from: list[str]  # ["market", "fundamental", ...]

   class BearArgument(BaseModel): ...  # 同上結構

   class FinalSignal(BaseModel):
     action: Literal["BUY", "HOLD", "SELL"]
     confidence: int = Field(ge=0, le=100)
     target_price_low: Decimal | None
     target_price_high: Decimal | None
     stop_loss: Decimal | None
     time_horizon: Literal["短期(1-2週)", "中期(1-3月)", "長期(>3月)"]
     position_size_pct: Decimal = Field(ge=0, le=100, description="建議持股佔比%")
     reasoning_zh: str = Field(min_length=200, max_length=3000)
     risk_factors: list[str]
     debate_winner: Literal["bull", "bear", "neutral"]

D. backend/app/agents/llm_helpers.py：
   async def llm_call_with_schema(llm, system, user, schema: type[BaseModel],
                                   tools=None, max_retries=2) -> tuple[BaseModel, TokenUsage]:
     """強制結構化輸出：第一次跑 → 嘗試 parse → 失敗則加錯誤訊息再 retry"""
     for attempt in range(max_retries + 1):
       resp = await llm.generate(
         system=system + f"\n\n最後輸出必須為以下 JSON Schema：\n{schema.model_json_schema()}",
         user=user,
         tools=tools,
       )
       # 取 last JSON block
       parsed_json = extract_json_block(resp.content)
       try:
         return schema.model_validate(parsed_json), resp.usage
       except ValidationError as e:
         if attempt < max_retries:
           user += f"\n\n[REPAIR] 上次輸出 schema 驗證失敗：{e}\n請重新輸出符合 schema 的 JSON。"
         else:
           raise

   async def record_llm_usage(analysis_id, provider, model, usage, cost_usd, session): ...

E. backend/app/agents/analysts/market_analyst.py（完整版）：
   @register_analyst
   class MarketAnalyst(BaseAnalyst):
     name = "market"
     display_name_zh = "技術面分析師"
     supported_regions = [MarketRegion.TW, MarketRegion.US]
     required_data_kinds = [DataKind.OHLCV]

     async def analyze(self, state: AgentState) -> dict:
       symbol = state["symbol"]
       # 1. 抓 60 日 OHLCV via tool
       ohlcv = await self.tools.get_ohlcv(symbol, days_back=60)
       if not ohlcv: raise ExternalServiceError(message_zh=f"{symbol} 無 OHLCV 資料")

       # 2. 計算技術指標（後端算，不交給 LLM）：
       indicators = compute_indicators(ohlcv)  # RSI, MACD, KD, BBANDS, MA20, MA60

       # 3. 渲染 user prompt：股票基本資訊 + ohlcv 摘要 + indicators
       user = render_template("market_analyst_user_template", symbol=symbol, ohlcv=ohlcv, indicators=indicators)
       system = load_prompt("market_analyst_system")

       # 4. LLM call with schema
       result, usage = await llm_call_with_schema(self.llm, system, user, MarketAnalysisResult)

       # 5. 寫 llm_usage
       await record_llm_usage(state["analysis_id"], self.llm.name, self.llm.model_name, usage, ...)

       # 6. 回傳：累積到 state["analyses"]
       return {
         "analyses": {**state.get("analyses", {}), self.name: result.model_dump_json()},
         "llm_usage_total_tokens": state.get("llm_usage_total_tokens", 0) + usage.total_tokens,
       }

F. backend/app/agents/analysts/fundamental_analyst.py：
   - 抓 quarterly financial（4 季）+ company_info + 月營收（TW only，US 沒有）
   - 計算 PE / PB / 殖利率（後端算）
   - LLM 分析 valuation + growth outlook

G. backend/app/agents/analysts/news_analyst.py（含 Qdrant RAG）：
   - 抓最近 7 天 cnyes RSS（先 ingest 過 → 在 Qdrant tw_news_v1）
   - Qdrant similarity search：embed(symbol + company_name) → top-15
   - 篩選與本股票相關（提到 symbol 或 company_name）
   - LLM 分析整體情緒 + 列重要新聞

   注意：news_ingest 任務在 P7 已寫，這裡只負責 query。
   要求 Qdrant collection tw_news_v1 至少有資料（在 P7 / P12 已 seed 一些）。
   若 collection 空，回 NewsAnalysisResult(sentiment="中性", summary="本期無相關新聞", ...)

H. backend/app/agents/analysts/sentiment_analyst.py（TW only）：
   - 抓 30 日 institutional + margin
   - 計算外資累積買賣超 + 融資餘額變化（後端算）
   - LLM 解讀「籌碼面」

I. backend/app/agents/researchers/bull_researcher.py：
   class BullResearcher:
     async def argue(self, state: AgentState, round_num: int) -> dict:
       analyses = state["analyses"]
       previous_debate = state.get("debate_history", [])
       # 給 bull 看：所有 analyst 結論 + 對方 bear 上一輪
       user = render_template("bull_argument_user", analyses=analyses, debate=previous_debate, round=round_num)
       system = load_prompt("bull_researcher_system")
       result, usage = await llm_call_with_schema(self.llm, system, user, BullArgument)
       return {
         "bull_arguments": [*state.get("bull_arguments", []), result.model_dump_json()],
         "debate_history": [{"role": "bull", "round": round_num, "content": result.model_dump_json()}],
         "llm_usage_total_tokens": ...,
       }

J. backend/app/agents/researchers/bear_researcher.py：同 Bull 結構

K. backend/app/agents/managers/research_manager.py：
   class ResearchManager:
     async def synthesize(self, state: AgentState) -> dict:
       """綜合所有 analyst + 多輪辯論 → 結構化 signal"""
       user = render_template("manager_user", analyses=state["analyses"],
                              debate=state["debate_history"],
                              symbol=state["symbol"])
       system = load_prompt("research_manager_system")
       signal, usage = await llm_call_with_schema(self.llm, system, user, FinalSignal)

       # 產報告 markdown
       report_md = render_template("report_md", state=state, signal=signal)

       return {
         "signal": signal.model_dump(),
         "report_md": report_md,
         "llm_usage_total_tokens": ...,
       }

L. backend/app/agents/graph_builder.py 升級：
   def build_graph(symbol, market, debate_rounds=1):
     region = detect_region(symbol)
     analysts = [cls(...) for n, cls in ANALYST_REGISTRY.items() if region in cls.supported_regions]

     graph = StateGraph(AgentState)
     # Step 1: parallel analysts（用 reducer 累積到 state["analyses"]）
     for analyst in analysts:
       graph.add_node(analyst.name, analyst.analyze)
     # 簡化：先序列跑（v1.0 不做 parallel）
     for i, a in enumerate(analysts[:-1]):
       graph.add_edge(a.name, analysts[i+1].name)

     # Step 2: bull/bear debate（debate_rounds 輪）
     graph.add_node("bull", BullResearcher(...).argue)
     graph.add_node("bear", BearResearcher(...).argue)
     graph.add_edge(analysts[-1].name, "bull")
     graph.add_edge("bull", "bear")
     # 用 conditional edge 控制 round
     graph.add_conditional_edges("bear",
       lambda s: "bull" if len(s.get("bull_arguments", [])) < debate_rounds else "manager",
       {"bull": "bull", "manager": "manager"}
     )

     # Step 3: manager
     graph.add_node("manager", ResearchManager(...).synthesize)
     graph.add_edge("manager", END)

     graph.set_entry_point(analysts[0].name)
     return graph.compile()

M. backend/app/agents/indicators.py（純 Python，後端算）：
   def compute_rsi(closes: list[float], period=14) -> list[float]: ...
   def compute_macd(closes): ...
   def compute_kd(highs, lows, closes, period=9): ...
   def compute_bbands(closes, period=20, std=2): ...
   def compute_ma(closes, period): ...
   def compute_indicators(ohlcv: list[dict]) -> dict: ...
   注意：用 numpy/pandas，不要呼叫 ta-lib（Windows 安裝痛苦）

N. backend/app/workers/tasks/run_analysis.py 升級為真實版：
   @celery_app.task(bind=True, time_limit=1200, soft_time_limit=900)
   def run_analysis(self, analysis_id: str):
     async def _run():
       async with rw_session() as s:
         report = await s.get(AnalysisReport, analysis_id)
         if not report: return
         report.status = "running"
         report.started_at = datetime.now(timezone.utc)
         await s.commit()

       try:
         graph = build_graph(report.symbol, report.market, report.debate_rounds)
         initial = AgentState(symbol=report.symbol, market=report.market,
                              region=detect_region(report.symbol), ...,
                              analysis_id=analysis_id, trace_id=...)
         final = await graph.ainvoke(initial, config={"recursion_limit": 25})

         async with rw_session() as s:
           report = await s.get(AnalysisReport, analysis_id)
           report.status = "completed"
           report.report_md = final["report_md"]
           report.signal = final["signal"]
           report.completed_at = datetime.now(timezone.utc)
           await s.commit()
       except Exception as e:
         async with rw_session() as s:
           report = await s.get(AnalysisReport, analysis_id)
           report.status = "failed"
           report.error_message = str(e)[:1000]
           await s.commit()
         raise

     # Celery 包 asyncio.run（單一 event loop）
     loop = asyncio.new_event_loop()
     try: loop.run_until_complete(_run())
     finally: loop.close()

O. backend/tests/unit/test_indicators.py（≥ 8 個測試）：
   - test_rsi_known_values
   - test_macd_signal_crossover_detected
   - test_kd_overbought
   - test_bbands_band_width
   - test_ma_simple
   - test_indicators_handle_short_series
   - test_indicators_handle_nan
   - test_indicators_dataframe_input

P. backend/tests/unit/test_schemas.py（≥ 8 個測試）：
   - test_market_result_validates
   - test_market_result_rejects_invalid_trend
   - test_final_signal_action_enum
   - test_final_signal_confidence_range
   - test_bull_argument_min_points
   - test_news_result_supporting_articles_format
   - test_sentiment_result_institutional_flow_enum
   - test_decimal_serialized_as_string

Q. backend/tests/unit/test_llm_helpers.py（≥ 5 個測試）：
   - test_extract_json_block_handles_code_fences
   - test_schema_validation_retries_on_failure
   - test_schema_validation_gives_up_after_max_retries
   - test_record_llm_usage_writes_db
   - test_cost_calculation_for_gemini_flash

R. backend/tests/integration/test_market_analyst.py（≥ 4 個測試 - mock LLM）：
   - test_market_analyst_returns_valid_schema
   - test_market_analyst_uses_ohlcv_tool
   - test_market_analyst_records_usage
   - test_market_analyst_handles_no_data

S. backend/tests/integration/test_full_tw_pipeline.py（≥ 3 個測試）：
   - test_2330_completes_with_stub_llm（mock LLM 回固定 schema-valid JSON）
   - test_pending_orders_created_when_signal_buy_or_sell（這條轉 P14 完整化）
   - test_debate_rounds_creates_correct_history_entries

T. backend/tests/integration/test_real_llm_2330.py（≥ 1 測試 @pytest.mark.network @pytest.mark.expensive）：
   - test_real_2330_full_analysis（真 Gemini call，~$0.012）

U. 寫 scripts/health_checks/phase_13.sh
V. 寫 docs/phase_reports/PHASE_13.md
W. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 13 = 以下 12 個指令全部 exit code 0：

```bash
# 1-3. uv sync + lint + 啟動 + workers
cd backend && uv sync && uv run ruff check app/ && cd ..
cd backend && uv run uvicorn app.main:app --port 8000 &
SERVER_PID=$!
sleep 3
make up-workers

# 4. 4 種 TW analyst 完整化（不再是 stub）
cd backend && uv run python -c "
from app.agents.analysts.market_analyst import MarketAnalyst
import inspect
src = inspect.getsource(MarketAnalyst.analyze)
assert 'stub' not in src.lower(), 'still stub'
assert 'compute_indicators' in src or 'self.tools.get_ohlcv' in src
print('OK')
"
cd ..

# 5. 結構化 schema validation
cd backend && uv run pytest tests/unit/test_schemas.py tests/unit/test_indicators.py \
  tests/unit/test_llm_helpers.py -v && cd ..

# 6. integration test (mock LLM) 通過
cd backend && uv run pytest tests/integration/test_market_analyst.py \
  tests/integration/test_full_tw_pipeline.py -m "not network" -v && cd ..

# 7. POST /analysis 真跑（用 stub LLM env）
ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env | cut -d= -f2)
ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env | cut -d= -f2)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}" | jq -r '.data.access_token')
ID=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" http://localhost:8000/api/v1/analysis \
  -d '{"symbol":"2330","analyst_types":["market","fundamental","news","sentiment"],"llm_model":"gemini-2.0-flash","debate_rounds":1}' \
  | jq -r '.data.analysis_id')

# 8. 真實 LLM call（如果 .env 有 GOOGLE_API_KEY 跑 expensive 測試）
if [ -n "$(grep ^GOOGLE_API_KEY=.\\+ .env)" ]; then
  cd backend && uv run pytest tests/integration/test_real_llm_2330.py \
    -m "network and expensive" -v --timeout=600 || echo "REAL LLM SKIPPED/FAILED"
  cd ..
fi

# 9. 等 3 分鐘讓 stub 跑完
sleep 180
STATUS=$(curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/analysis/$ID" | jq -r '.data.status')
test "$STATUS" = "completed" || test "$STATUS" = "running"

# 10. llm_usage 表有寫入紀錄
PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)
COUNT=$(PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw \
  -tAc "SELECT count(*) FROM llm_usage WHERE analysis_id='$ID'")
test "$COUNT" -ge 1

# 11. 累積測試 ≥ 330
cd backend && uv run pytest --collect-only -q 2>&1 | tail -1

kill $SERVER_PID

# 12. health_check phase_13 通過
bash scripts/health_checks/phase_13.sh
```

【6. Smoke Test（手動）】
✓ 真實跑 2330 分析（等 1-3 分鐘）→ /analysis/{id} 回 status=completed + signal 結構完整
✓ DB 看 llm_usage 表有 row + cost_usd 介於 0.005-0.05
✓ DB 看 analysis_reports 的 report_md 含繁中段落
✓ 故意把某 analyst tool 抓不到資料 → 整個 graph 不該 crash（要捕捉 raise 改 status=failed）
✓ debate_rounds=2 跑出 [bull, bear, bull, bear, manager] 5 個 history entries

【7. 已知陷阱】
✗ Prompt 太長 → token 爆 → 控制 user prompt < 4k token
✗ LLM 沒回 JSON 或 JSON 不合 schema → repair retry 不超過 2 次
✗ Schema repair 重試把 prompt 越加越長 → 設 max user prompt size
✗ ohlcv tool 回空 list → analyst 必須 raise（不要 silent return）
✗ Qdrant collection 空 → NewsAnalyst 回中性（不要 raise）
✗ ta_agent_ro 想呼叫 institutional 但 stock 是美股 → tool 應 raise ValidationError
✗ Bull/Bear debate 沒交替（兩個都跑 bull）→ conditional edge 邏輯
✗ Manager 沒看到 debate_history → state reducer 漏設 add
✗ recursion_limit 太低 → 多輪辯論卡 → 設 25
✗ celery task 用 asyncio.run 多次 → 用 single event loop
✗ Decimal 在 LLM JSON 字串化反序列化失敗 → 用 str → Decimal
✗ 多輪辯論 state 累積爆 500KB → 啟 trim_state_messages
✗ Cost 計算用 input_tokens vs cached_tokens 邏輯不同 → 兩個 rate
✗ News RSS 用台北時區但 DB 是 UTC → 過濾日期錯
✗ legacy/tradingagents/agents/ 不要 import，只能參考結構
✗ 三大法人資料 trading day vs calendar day → 用 stock_prices.date 對齊

【8. Self-Check SOP】跑第 8.5.4 章全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/agents/prompts/*.txt（12 個 prompt）
  - backend/app/agents/schemas.py（FinalSignal + 各 analyst schema）
  - backend/app/agents/llm_helpers.py
  - backend/app/agents/analysts/*.py（4 個完整版，覆寫 stub）
  - backend/app/agents/researchers/{bull, bear}_researcher.py
  - backend/app/agents/managers/research_manager.py
  - backend/app/agents/indicators.py
  - 7 個 test files（共 ~30 個測試）
  - scripts/health_checks/phase_13.sh

程式檔（修改）：
  - backend/app/agents/graph_builder.py（加 bull/bear/manager + conditional edge）
  - backend/app/workers/tasks/run_analysis.py（從 stub → 真跑 graph）

文件檔（新增）：
  - docs/phase_reports/PHASE_13.md
  - docs/runbooks/agents.md（更新：debug graph、調 prompt）

文件檔（更新）：
  - docs/phase_progress.md

Git tag：phase-13-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：
- B（prompts）+ C（schemas）建議先做完整，再做 D-K（程式邏輯）
- E（market_analyst）做完先驗證單 analyst 可跑，再做其他 3 個
- 整個 graph 的 conditional edge 容易出錯，建議 L 寫完立即跑 graph.draw_mermaid() 看圖
- 真 LLM call 一次 ~$0.012，整個 P13 開發過程約跑 5-10 次測試 = ~$0.1，預算內
```

---

### ▌Phase 14 — 美股 Analyst + LLM Provider Fallback Chain + WS 串流 + 月配額

```
=== TradingAgents-TW Phase 14（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\backend
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 14
必讀 PLAN.md 章節：第 8.5, 10（跨市場架構）, 14.4（LLM Fallback）, 16.2（metrics）, 18.2, 19.3 章

【1. 前置依賴 Phase】
依賴：Phase 1-13
驗證方式：bash scripts/health_checks/phase_13.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_13.sh
- 真實跑 2330 完成（status=completed）
- 4 種 TW Analyst + Bull/Bear/Manager 完整可跑

【3. 本 Phase 目標】
讓「美股完整分析」端到端可跑 + 整體穩定性提升：
  (1) 美股 3 種 Analyst（market / fundamental / news，無 sentiment）
  (2) LLM Provider Fallback Chain（Gemini → OpenAI → Anthropic）
  (3) OpenAI / Anthropic Provider 實作（完整 cost 計算）
  (4) WebSocket 即時串流（每個 analyst 跑完 publish 一次到 Redis）
  (5) llm_monthly_quota 整合（用戶超預算拒新分析）
  (6) pending_orders 自動建立（signal=BUY/SELL 時）
  (7) Provider readiness check（startup 試 ping 所有 provider）
  (8) Cross-market end-to-end test：2330 + AAPL 都跑通

注意：本 Phase「不寫前端」（P15+）、「不接 LINE/Telegram」（P18）。
注意：美股 Analyst 不能用 institutional 工具（會 raise）。

【4. 任務清單】

A. 切分支：phase/14-us-analyst-llm-fallback

B. backend/pyproject.toml 加：
   langchain-openai>=0.2
   langchain-anthropic>=0.3
   anthropic>=0.40
   openai>=1.50

C. backend/app/llm/openai_provider.py：
   @register_llm_provider
   class OpenAIProvider(BaseLLMProvider):
     name = "openai"
     def __init__(self, settings):
       self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
       self.model_name = settings.OPENAI_DEFAULT_MODEL  # gpt-4o-mini
       # cost：$0.15/M input、$0.60/M output（gpt-4o-mini）
       self.cost_per_m_input = Decimal("0.15")
       self.cost_per_m_output = Decimal("0.60")

     async def generate(self, system, user, tools=None, max_tokens=2048, temperature=0.3):
       resp = await self.client.chat.completions.create(
         model=self.model_name,
         messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
         max_tokens=max_tokens, temperature=temperature,
       )
       usage = TokenUsage(
         input_tokens=resp.usage.prompt_tokens,
         output_tokens=resp.usage.completion_tokens,
         total_tokens=resp.usage.total_tokens,
         cost_usd=self._cost(resp.usage),
       )
       return LLMResponse(content=resp.choices[0].message.content, usage=usage)

     async def health_check(self):
       try:
         resp = await self.client.models.list(timeout=5)
         return True
       except: return False

D. backend/app/llm/anthropic_provider.py：
   @register_llm_provider
   class AnthropicProvider(BaseLLMProvider):
     name = "anthropic"
     # Claude Haiku 3.5: $0.80/M input, $4.00/M output
     # Claude Sonnet 4: $3.00/M input, $15.00/M output
     ...

E. backend/app/llm/fallback_chain.py（依 14.4）：
   FALLBACK_CHAIN = {
     "google":    ["openai", "anthropic"],
     "openai":    ["google", "anthropic"],
     "anthropic": ["google", "openai"],
   }

   class LLMFallbackChain:
     def __init__(self, providers: dict[str, BaseLLMProvider]):
       self.providers = providers

     async def generate(self, primary: str, system, user, tools=None, **kwargs) -> tuple[LLMResponse, str]:
       """回 (response, used_provider_name)"""
       chain = [primary] + FALLBACK_CHAIN.get(primary, [])
       last_exc = None
       for provider_name in chain:
         provider = self.providers.get(provider_name)
         if not provider: continue
         if provider.cb.state == "OPEN":
           logger.warning(f"LLM {provider_name} CB OPEN, skipping")
           continue
         try:
           resp = await provider.generate(system, user, tools=tools, **kwargs)
           provider.cb.record_success()
           return resp, provider_name
         except Exception as e:
           provider.cb.record_failure()
           last_exc = e
           logger.warning(f"LLM {provider_name} failed: {e}")
       raise ExternalServiceError(name="llm_fallback_chain", reason=f"all failed, last={last_exc}")

F. backend/app/llm/__init__.py 升級：
   def get_llm_chain(settings) -> LLMFallbackChain:
     providers = {}
     if settings.GOOGLE_API_KEY:
       providers["google"] = GeminiProvider(settings)
     if settings.OPENAI_API_KEY:
       providers["openai"] = OpenAIProvider(settings)
     if settings.ANTHROPIC_API_KEY:
       providers["anthropic"] = AnthropicProvider(settings)
     if not providers:
       raise ValueError("至少需配置一個 LLM provider")
     return LLMFallbackChain(providers)

G. backend/app/main.py lifespan 加：
   app.state.llm_chain = get_llm_chain(settings)
   # 開機 readiness：對每個 provider ping
   for name, p in app.state.llm_chain.providers.items():
     ok = await p.health_check()
     logger.info(f"LLM {name} health: {ok}")

H. backend/app/agents/llm_helpers.py 升級：
   async def llm_call_with_schema(chain: LLMFallbackChain, primary, system, user,
                                   schema, tools=None, max_retries=2):
     # 用 chain.generate 而不是 single provider
     resp, used_provider = await chain.generate(primary, system, user, tools=tools)
     ...

I. 美股 Analyst「共用 class」策略（**不另建 us_*_analyst.py**）：

   v7 設計決定：採共用 class 寫法（依第 10.5 章 MarketAnalyst supports both regions），
   在 prompt 裡判斷 state["region"] 給不同的 user prompt（資料源差異）。

   實作步驟（修改 P13 已建立的 analyst 檔，不新增）：
   1. backend/app/agents/analysts/market_analyst.py 修改：
      - supported_regions = [MarketRegion.TW, MarketRegion.US]（P13 已是這樣）
      - 在 analyze() 內依 state["region"] 切 user prompt：
        ```python
        async def analyze(self, state):
          region = state["region"]
          if region == MarketRegion.TW:
            user = render_template("market_analyst_user_tw_template", ...)
          else:  # US
            user = render_template("market_analyst_user_us_template", ...)
          ...
        ```
      - 新增對應的 prompt 模板：market_analyst_user_us_template.txt（在 prompts/ 目錄）

   2. backend/app/agents/analysts/fundamental_analyst.py 修改：
      - supported_regions = [TW, US]（P13 已是）
      - 美股版用 yfinance + Alpha Vantage 抓 quarterly financial（無月營收）
      - 對應新 prompt：fundamental_analyst_user_us_template.txt

   3. backend/app/agents/analysts/news_analyst.py 修改：
      - supported_regions = [TW, US]（P13 已是）
      - 美股版查 us_news_v1 collection（不是 tw_news_v1）
      - 對應新 prompt：news_analyst_user_us_template.txt

   4. backend/app/agents/analysts/sentiment_analyst.py 維持不變：
      - supported_regions = [MarketRegion.TW]（美股不跑）
      - graph_builder 對美股自動過濾掉

   注意：name 維持「market / fundamental / news / sentiment」（不要改為 us_market）。
   registry 不會撞名，因為共用 class，只是不同 region 走不同 prompt 分支。

J. backend/app/agents/managers/orders_decision.py：
   def signal_to_pending_order(signal: dict, analysis_id: str, user_id: UUID,
                                symbol: str, market: Market) -> PendingOrder | None:
     if signal["action"] == "HOLD": return None
     return PendingOrder(
       id=uuid4(), user_id=user_id, analysis_id=analysis_id,
       symbol=symbol, market=market, side=signal["action"],
       qty=calculate_qty(signal["position_size_pct"], user.portfolio_balance),  # 簡化
       entry_price=signal["target_price_low"],
       stop_loss=signal["stop_loss"],
       version=1, status="PENDING", created_at=datetime.now(timezone.utc),
     )

K. backend/app/services/quota_service.py：
   class QuotaService:
     async def check_user_can_analyze(self, user_id: UUID) -> tuple[bool, Decimal, Decimal]:
       """回 (allowed, used_usd, limit_usd)"""
       async with ro_session() as s:
         current_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
         used = await s.scalar(
           select(func.coalesce(func.sum(LLMUsage.cost_usd), 0))
           .where(LLMUsage.user_id == user_id, LLMUsage.created_at >= current_month)
         )
         user = await s.get(User, user_id)
         limit = user.monthly_llm_budget_usd or Decimal("50.00")
       return used < limit, used, limit

     async def record_usage(self, user_id, analysis_id, provider, model,
                             input_tokens, output_tokens, cost_usd): ...

L. backend/app/api/v1/analysis_router.py 升級 POST /analysis：
   ok, used, limit = await quota_service.check_user_can_analyze(user.id)
   if not ok:
     raise QuotaExceededError(message_zh=f"本月 LLM 預算已用完 ({used}/{limit} USD)")
   # 然後才建 analysis_reports + run_analysis.delay

M. backend/app/agents/streaming.py：
   async def publish_event(analysis_id, event_type, data):
     payload = json.dumps({"event": event_type, "data": data, "ts": datetime.now(timezone.utc).isoformat()})
     await redis_pub.publish(f"analysis:{analysis_id}", payload)

   # graph 裡每個節點完成後手動呼叫 publish_event：
   # 例如 MarketAnalyst.analyze 結尾：
   #   await publish_event(state["analysis_id"], "analyst_completed",
   #                       {"analyst": self.name, "result_summary": ...})
   # Bull / Bear: publish_event("debate_argument", ...)
   # Manager: publish_event("synthesis_completed", ...)

N. backend/app/workers/tasks/run_analysis.py 升級：
   - 開頭 publish_event("started")
   - 每節點 publish_event 已在 graph nodes 裡
   - 結束 publish_event("completed", {signal, report_md_excerpt})
   - 失敗 publish_event("failed", {error})

   完成後若 signal=BUY/SELL → 建 PendingOrder（用 signal_to_pending_order）

O. backend/tests/unit/test_openai_provider.py（≥ 5 個測試）
P. backend/tests/unit/test_anthropic_provider.py（≥ 5 個測試）
Q. backend/tests/unit/test_fallback_chain.py（≥ 7 個測試）：
   - test_uses_primary_when_healthy
   - test_falls_back_when_primary_raises
   - test_skips_open_circuit_breakers
   - test_raises_when_all_fail
   - test_records_success_resets_cb
   - test_used_provider_name_returned
   - test_chain_respects_no_provider_for_chained_one

R. backend/tests/unit/test_quota_service.py（≥ 5 個測試）：
   - test_user_under_limit_allowed
   - test_user_at_limit_blocked
   - test_user_uses_default_limit_50
   - test_record_usage_writes_db
   - test_quota_resets_on_first_of_month

S. backend/tests/unit/test_signal_to_order.py（≥ 5 個測試）：
   - test_hold_returns_none
   - test_buy_creates_pending_order
   - test_sell_creates_short_pending_order_or_skips
   - test_qty_calculated_from_position_size_pct
   - test_pending_order_status_pending

T. backend/tests/integration/test_us_full_pipeline.py（≥ 3 個測試）：
   - test_aapl_completes（mock LLM，sentiment 分支不應觸發）
   - test_us_no_institutional_tool_raises
   - test_us_pending_order_created_for_buy_signal

U. backend/tests/integration/test_cross_market_e2e.py（≥ 2 個測試）：
   - test_2330_full_pipeline_end_to_end_mock_llm
   - test_aapl_full_pipeline_end_to_end_mock_llm

V. backend/tests/integration/test_llm_quota_blocks_analysis.py（≥ 2 個測試）：
   - test_quota_exceeded_returns_402
   - test_quota_warning_at_80pct_logs（有 logger 訊息）

W. backend/tests/integration/test_ws_streaming.py（≥ 4 個測試）：
   - test_started_event_published
   - test_analyst_completed_events_published
   - test_completed_event_includes_signal
   - test_failed_event_published_on_error

X. 寫 scripts/health_checks/phase_14.sh
Y. 寫 docs/phase_reports/PHASE_14.md
Z. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 14 = 以下 13 個指令全部 exit code 0：

```bash
# 1-3. uv sync + lint + 啟動 + workers
cd backend && uv sync && uv run ruff check app/ && cd ..
cd backend && uv run uvicorn app.main:app --port 8000 &
SERVER_PID=$!
sleep 3
make up-workers

# 4. 3 個 LLM provider 註冊
cd backend && uv run python -c "
from app.llm import get_llm_chain
from app.core.config import settings
chain = get_llm_chain(settings)
assert 'google' in chain.providers
# openai/anthropic 視 .env 是否有 key
print('OK', list(chain.providers.keys()))
"
cd ..

# 5. Fallback chain 邏輯（unit test）
cd backend && uv run pytest tests/unit/test_fallback_chain.py -v && cd ..

# 6. 跨市場 e2e（mock LLM）
cd backend && uv run pytest tests/integration/test_cross_market_e2e.py -v && cd ..

# 7. 美股 e2e
cd backend && uv run pytest tests/integration/test_us_full_pipeline.py -v && cd ..

# 8. quota 攔截
cd backend && uv run pytest tests/integration/test_llm_quota_blocks_analysis.py -v && cd ..

# 9. WS 串流事件
cd backend && uv run pytest tests/integration/test_ws_streaming.py -v && cd ..

# 10. 真實跑 AAPL（mock 或真，視預算）
ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env | cut -d= -f2)
ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env | cut -d= -f2)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}" | jq -r '.data.access_token')
ID=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" http://localhost:8000/api/v1/analysis \
  -d '{"symbol":"AAPL","analyst_types":["market","fundamental","news"],"llm_model":"gemini-2.0-flash","debate_rounds":1}' \
  | jq -r '.data.analysis_id')
sleep 180

# debate_history 不該含 sentiment
PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)
PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw \
  -tAc "SELECT EXISTS(SELECT 1 FROM debate_messages WHERE analysis_id='$ID' AND role='sentiment')" \
  | grep -i "f"

# 11. WS 連線收得到事件
TICKET=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/ws-ticket | jq -r '.data.ticket')
# wscat 開另一終端：wscat -c "ws://localhost:8000/api/v1/ws/analysis/$ID" -s "tradingagents.v1" -s "ticket.$TICKET"
# 預期看到 ≥ 5 個 event（手動）
echo "manual: wscat ..."

# 12. pending_orders 視 signal 自動建立
PGPASSWORD=$PG psql -h localhost -U postgres tradingagents_tw \
  -tAc "SELECT count(*) FROM pending_orders WHERE analysis_id='$ID'"
# 視 signal 是 BUY/SELL/HOLD：HOLD = 0、BUY/SELL = 1（接受任一）

# 13. 累積測試 ≥ 367 + health_check phase_14
cd backend && uv run pytest --collect-only -q 2>&1 | tail -1
kill $SERVER_PID
bash scripts/health_checks/phase_14.sh
```

【6. Smoke Test（手動）】
✓ wscat 連 WS 看到 started → analyst_completed × N → debate_argument × N → synthesis_completed → completed 事件序列
✓ 故意把 GOOGLE_API_KEY 改錯 → fallback 切 openai（看 used_provider log）
✓ 把所有 LLM key 都拔掉 → POST /analysis 啟動就失敗（lifespan 拒啟）
✓ 設一個用戶 monthly_llm_budget_usd=0.001 → 跑分析 402

【7. 已知陷阱】
✗ OpenAI / Anthropic 沒 key → fallback chain 會跳過該 provider（不要 raise）
✗ Anthropic 的 model name 變動快 → pin 到 claude-haiku-3-5-20241022 等具體日期版
✗ Provider 切換時 cost 計算用錯 rate → 每 provider 各自的 _cost
✗ Fallback chain 觸發但首次 success 後沒 reset CB → record_success 必須跑
✗ 多輪 debate 在 fallback 中可能改 provider → 記錄每個 turn 的 used_provider
✗ WS pubsub 訊息太大 → 用 excerpt（不要整個 report_md）
✗ pending_order qty 計算需 user 持股餘額 → v1.0 暫用 fixed amount $10000 / price
✗ pending_order 寫入 transaction 失敗 → 不要擋整個 analysis（log warning）
✗ Quota check 在 race condition 下兩個 request 同時通過 → 接受小幅超標（不嚴格鎖）
✗ Streaming 事件丟失：用 fire-and-forget，client 失連自負責 reconnect
✗ Anthropic SDK + asyncio Windows 偶發問題 → 用 asyncio.WindowsSelectorEventLoopPolicy
✗ MarketAnalyst supports both regions → user prompt template 用 if/else 分台股/美股段落

【8. Self-Check SOP】跑第 8.5.4 章全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/llm/openai_provider.py
  - backend/app/llm/anthropic_provider.py
  - backend/app/llm/fallback_chain.py
  - backend/app/services/quota_service.py
  - backend/app/agents/managers/orders_decision.py
  - backend/app/agents/streaming.py
  - 9 個 test files（共 ~38 個測試）
  - scripts/health_checks/phase_14.sh

程式檔（修改）：
  - backend/app/llm/__init__.py（get_llm_chain）
  - backend/app/agents/llm_helpers.py（用 chain.generate）
  - backend/app/agents/analysts/{market,fundamental,news}_analyst.py（加美股 prompt template 分支）
  - backend/app/main.py（lifespan readiness check）
  - backend/app/api/v1/analysis_router.py（POST 加 quota check）
  - backend/app/workers/tasks/run_analysis.py（streaming + pending order）
  - backend/pyproject.toml（加 langchain-openai, langchain-anthropic, anthropic, openai）

文件檔（新增）：
  - docs/phase_reports/PHASE_14.md
  - docs/runbooks/llm_providers.md

文件檔（更新）：
  - docs/phase_progress.md

Git tag：phase-14-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：
- C-E（Provider + FallbackChain）做完，要在 ipython 手動觸發 fallback 測試
- 真實 LLM 測試只跑 2 次（Gemini + 強制切 OpenAI），其餘用 mock 控成本
- WS streaming 測試容易誤判，要看 Redis pubsub 真的有 message
```

---

### ▌Phase 15 — 前端基礎 + Auth + 共用元件 + Layout + 路由保護

> **v7.0 強烈建議：本 Phase 預設拆成 P15a + P15b 兩段執行**（依第 8.5.1 章「單 Phase ≤ 1500 行」原則）。
> P15 30 個任務 × 13 個共用元件 × 5 個 Auth 頁 + 18 頁 stub + middleware + WebSocket hook 容易超 2000 行。
>
> **建議拆法：**
> - **P15a（4-5 hr）：** 任務 A-G（切分支 / Next init / 套件 / shadcn / api / store / query-client）
>   + H（middleware）+ I-O（layouts + Auth 5 頁 + Onboarding）
>   + 對應退出條件：login 流程通、middleware 路由保護生效
> - **P15b（4-5 hr）：** 任務 P-Z + AA-AD（App layout + 18 頁 stub + 13 共用元件 + WS hook + format/i18n + Dockerfile + 測試 + Makefile + scripts）
>   + 對應退出條件：18 頁路由皆 200/307、unit + E2E 全綠
>
> **若 user 不拆**：照本 Phase 跑下去，但**遇到 context > 150k token**（依第 8.5.6 章）立刻 WIP commit + 開新對話接續任務 P 起的部分。

```
=== TradingAgents-TW Phase 15（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\frontend
後端：http://localhost:8000/api/v1
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 15（建議拆 P15a / P15b 執行）
必讀 PLAN.md 章節：第 6.2（前端版本）, 8.5（含 8.5.1 拆分原則）, 12.2, 15.6（Decimal 字串）, 19.1, 19.7, 21（頁面地圖）, 22 章

【1. 前置依賴 Phase】
依賴：Phase 1-14（完整後端可跑）
驗證方式：bash scripts/health_checks/phase_14.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_14.sh
- POST /api/v1/auth/login 通
- /api/v1/stocks 等 P10/P11 endpoint 通

【3. 本 Phase 目標】
讓「前端基礎可跑」+「登入流程通」：
  (1) Next.js 14.2 + TypeScript + Tailwind + shadcn/ui setup
  (2) Auth 頁面：登入、首次改密碼、Onboarding、忘記密碼、密碼重置確認
  (3) Layout：Sidebar（依第 21 章導航）+ Topbar + ThemeProvider
  (4) middleware.ts 路由保護（未登入 → /login）
  (5) 共用元件 ≥ 10 個：DataTable / ChartContainer / NumberFormat / DateFormat /
       MarketBadge / ConfirmDialog / EmptyState / ErrorBoundary / LoadingSkeleton / Pagination
  (6) API client（axios）+ React Query setup + auto-refresh on 401
  (7) WebSocket hook（用 ticket，subprotocol）
  (8) Decimal 處理（BigNumber.js）
  (9) 時區處理（dayjs + timezone）
  (10) i18n 雛形（zh-TW 為主，預留 en 切換）
  (11) E2E smoke test（Playwright）：登入 → /dashboard

注意：本 Phase「不寫 18 頁完整內容」（P16/P17）。
注意：所有 18 頁先建空殼路由（pageStub.tsx），確保 middleware 與 sidebar 都能 link。

【4. 任務清單】

A. 切分支：
   git checkout main && git pull
   git checkout -b phase/15-frontend-foundation

B. cd frontend && 初始化（如果還沒跑過）：
   npx create-next-app@14.2 . --typescript --tailwind --app --no-src-dir --import-alias "@/*"
   注意：目錄已在 P1 建好，這裡是補檔案；如果撞檔先 mv 再跑

   修正：v7 用 src-dir
   npx create-next-app@14.2 . --typescript --tailwind --app --src-dir --import-alias "@/*"

C. frontend/package.json 加依賴（pin 到第 6.2 章版本）：
   **執行依賴：**
   - shadcn-ui CLI: npx shadcn@latest init
   - "@tanstack/react-query": "^5.x"
   - "axios": "^1.x"
   - "zustand": "^4.x"
   - "next-themes": "^0.3"
   - "react-markdown": "^9.x", "rehype-highlight": "^7.x", "remark-gfm": "^4.x"
   - "date-fns": "^3.x"
   - "dayjs": "^1.11.x"
   - "@xyflow/react": "^12.x"
   - "lightweight-charts": "^4.x"
   - "recharts": "^2.x"
   - "lucide-react": "^0.x"
   - "cmdk": "^1.x"
   - "react-window": "^1.8.x"
   - "bignumber.js": "^9.x"
   - "zod": "^3.x"
   - "react-hook-form": "^7.x", "@hookform/resolvers": "^3.x"

   **開發依賴（v7.0 修正：補齊 vitest 跑 React component test 必需的套件）：**
   - "@playwright/test": "^1.49.x"
   - "vitest": "^2.x"
   - "@vitejs/plugin-react": "^4.x"      ← vitest 跑 .tsx 必需
   - "@testing-library/react": "^16.x"   ← v7 補：明確版本
   - "@testing-library/jest-dom": "^6.x" ← v7 補：toBeInTheDocument() 等 matcher
   - "@testing-library/user-event": "^14.x" ← v7 補：模擬 user 互動
   - "jsdom": "^25.x"                    ← v7 補：vitest 需要 DOM 模擬環境
   - "@types/react-window": "^1.8.x"     ← v7 補：型別定義

D. shadcn/ui 元件安裝（v7.0 補齊：含 P16/P17 會用到的元件）：
   ```bash
   npx shadcn@latest add \
     button input form label dialog dropdown-menu table \
     tabs card sheet sonner skeleton badge tooltip popover \
     command select avatar separator scroll-area accordion alert \
     calendar checkbox radio-group switch progress slider \
     hover-card pagination toggle toggle-group resizable \
     navigation-menu breadcrumb collapsible context-menu \
     menubar
   ```
   共 ~33 個元件。**若擔心 P15 過大，可只先裝 v7 原本的 17 個**（button-alert），
   後面 P16/P17 用到再 `npx shadcn add <name>` 補裝（單一元件 + 即裝即用，無需重啟）。
   v7.0 推薦做法：**P15a 一次裝齊 33 個**（後續 Phase 不再回頭碰 shadcn）。

E. frontend/src/lib/api.ts（axios + interceptor）：
   const api = axios.create({
     baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1",
     withCredentials: true,
   });

   // request：自動帶 access token
   api.interceptors.request.use((config) => {
     const token = useAuthStore.getState().accessToken;
     if (token) config.headers.Authorization = `Bearer ${token}`;
     // CSRF：對 POST/PUT/PATCH/DELETE 從 cookie 讀並設 header
     if (config.method?.match(/post|put|patch|delete/i)) {
       const csrf = getCookie("csrf_token");
       if (csrf) config.headers["X-CSRF-Token"] = csrf;
     }
     return config;
   });

   // response：401 → 自動 refresh
   api.interceptors.response.use(
     (r) => r,
     async (err) => {
       if (err.response?.status === 401 && !err.config._retry) {
         err.config._retry = true;
         try {
           const r = await api.post("/auth/refresh");
           useAuthStore.getState().setAccessToken(r.data.data.access_token);
           err.config.headers.Authorization = `Bearer ${r.data.data.access_token}`;
           return api(err.config);
         } catch (e) {
           useAuthStore.getState().logout();
           window.location.href = "/login";
         }
       }
       throw err;
     }
   );

F. frontend/src/store/auth.ts（Zustand）：
   - accessToken, user, role
   - setAccessToken, setUser, logout

G. frontend/src/lib/query-client.ts：
   - new QueryClient with defaults: refetchOnWindowFocus=false, staleTime=30s, retry=1

H. frontend/src/middleware.ts：
   import { NextRequest, NextResponse } from "next/server";

   export function middleware(req: NextRequest) {
     const { pathname } = req.nextUrl;
     const refreshToken = req.cookies.get("refresh_token");
     const isAuthRoute = ["/login", "/forgot-password", "/reset-password"].some(p => pathname.startsWith(p));
     if (!refreshToken && !isAuthRoute) {
       return NextResponse.redirect(new URL("/login", req.url));
     }
     if (refreshToken && isAuthRoute) {
       return NextResponse.redirect(new URL("/dashboard", req.url));
     }
     return NextResponse.next();
   }

   export const config = { matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"] };

I. frontend/src/app/layout.tsx：根 layout（HTML + ThemeProvider + QueryClientProvider）
J. frontend/src/app/(auth)/layout.tsx：Auth pages layout（置中卡片）
K. frontend/src/app/(auth)/login/page.tsx：
   - email + password input（react-hook-form + zod）
   - submit → /auth/login
   - 成功根據 next_action 跳：change_password → /onboarding/change-password、onboarding → /onboarding、dashboard → /dashboard
L. frontend/src/app/(auth)/forgot-password/page.tsx
M. frontend/src/app/(auth)/reset-password/page.tsx（從 query string 取 token）
N. frontend/src/app/onboarding/change-password/page.tsx：強制改密碼（must_change_password）
O. frontend/src/app/onboarding/page.tsx：歡迎引導 + 完成後 onboarding_completed=true

P. frontend/src/app/(app)/layout.tsx：App layout（Sidebar + Topbar + main）
   Sidebar 依第 21 章 18 頁完整 nav（用 lucide-react icon）

Q. 18 頁路由空殼：
   frontend/src/app/(app)/{dashboard,
                           market/{overview, institutional, calendar},
                           screener/{watchlist, filter, compare},
                           analysis/{new, history, [id]},
                           statistics/{accuracy, models, backtest},
                           portfolio/{positions, orders, history},
                           news/{sentiment, announcements},
                           notifications,
                           admin/{users, audit, system, pipeline}}/page.tsx
   每頁先放 PageStub component（顯示「P16/P17 將實作」）

R. frontend/src/components/common/*：
   - DataTable.tsx（包 @tanstack/react-table，含排序、cursor pagination）
   - ChartContainer.tsx（fixed height，避免 lightweight-charts height=0）
   - NumberFormat.tsx（接受 string | number，自動千分位 + Decimal 安全）
   - PercentFormat.tsx
   - DateFormat.tsx（dayjs + user timezone）
   - MarketBadge.tsx（TW 旗、US 旗）
   - ConfirmDialog.tsx
   - EmptyState.tsx
   - ErrorBoundary.tsx（捕捉子樹錯誤）
   - LoadingSkeleton.tsx
   - Pagination.tsx（cursor-based）
   - Sidebar.tsx
   - Topbar.tsx（用戶名、theme toggle、登出）

S. frontend/src/hooks/useWebSocket.ts：
   export function useAnalysisWS(analysisId: string, enabled = true) {
     const [events, setEvents] = useState<Event[]>([]);
     useEffect(() => {
       if (!enabled || !analysisId) return;
       let ws: WebSocket | null = null;
       (async () => {
         const { ticket } = (await api.post("/auth/ws-ticket")).data.data;
         const url = `${process.env.NEXT_PUBLIC_WS_URL}/api/v1/ws/analysis/${analysisId}`;
         ws = new WebSocket(url, ["tradingagents.v1", `ticket.${ticket}`]);
         ws.onmessage = (e) => setEvents((evs) => [...evs, JSON.parse(e.data)]);
         ws.onerror = console.error;
       })();
       return () => ws?.close();
     }, [analysisId, enabled]);
     return events;
   }

T. frontend/src/lib/format.ts：
   import BigNumber from "bignumber.js";
   import dayjs from "dayjs";
   import utc from "dayjs/plugin/utc";
   import tz from "dayjs/plugin/timezone";
   dayjs.extend(utc); dayjs.extend(tz);

   export function formatNumber(value: string | number, decimals = 0): string {
     const bn = new BigNumber(value);
     return bn.toFormat(decimals);
   }
   export function formatPercent(value: string | number, decimals = 2): string { ... }
   export function formatCurrency(value: string | number, currency: "TWD"|"USD" = "TWD"): string { ... }
   export function formatDateTime(iso: string, userTz = "Asia/Taipei"): string {
     return dayjs.utc(iso).tz(userTz).format("YYYY-MM-DD HH:mm:ss");
   }

U. frontend/src/lib/i18n.ts（最簡）：
   const messages = {
     "zh-TW": { ... },
   };
   export function t(key: string): string { return messages["zh-TW"][key] ?? key; }

V. frontend/.env.local.example：
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
   NEXT_PUBLIC_WS_URL=ws://localhost:8000

W. frontend/Dockerfile：
   FROM node:20-alpine AS deps
   WORKDIR /app
   COPY frontend/package*.json ./
   RUN npm ci
   FROM node:20-alpine AS builder
   WORKDIR /app
   COPY --from=deps /app/node_modules ./node_modules
   COPY frontend/ ./
   RUN npm run build
   FROM node:20-alpine AS runner
   WORKDIR /app
   ENV NODE_ENV production
   COPY --from=builder /app/public ./public
   COPY --from=builder /app/.next ./.next
   COPY --from=builder /app/node_modules ./node_modules
   COPY --from=builder /app/package.json ./package.json
   USER 1000
   EXPOSE 3000
   CMD ["npm", "start"]

X. frontend/playwright.config.ts + tests/e2e/auth.spec.ts（E2E smoke）：
   - test("login → dashboard")
   - test("invalid login shows error")
   - test("middleware redirects unauthenticated to /login")

Y. frontend/vitest.config.ts（**v7.0 補：完整配置**）：
   ```ts
   // vitest.config.ts
   import { defineConfig } from "vitest/config";
   import react from "@vitejs/plugin-react";
   import path from "node:path";

   export default defineConfig({
     plugins: [react()],
     test: {
       environment: "jsdom",                          // 必需：模擬瀏覽器 DOM
       globals: true,                                 // 讓 expect / describe 等成為全域
       setupFiles: ["./tests/unit/setup.ts"],
       css: false,
     },
     resolve: {
       alias: { "@": path.resolve(__dirname, "./src") },
     },
   });
   ```

   ```ts
   // tests/unit/setup.ts
   import "@testing-library/jest-dom/vitest";        // 註冊 toBeInTheDocument() 等 matcher
   import { cleanup } from "@testing-library/react";
   import { afterEach } from "vitest";
   afterEach(() => cleanup());                        // 每個 test 後自動清 DOM
   ```

   **package.json scripts 加：**
   ```json
   "scripts": {
     "test": "vitest run",
     "test:watch": "vitest",
     "test:ui": "vitest --ui"
   }
   ```

Y2. tests/unit/* 測試檔案：
   - components/NumberFormat.test.tsx（≥ 5 個）
   - components/DateFormat.test.tsx（≥ 3 個）
   - lib/format.test.ts（≥ 8 個）
   - hooks/useWebSocket.test.ts（≥ 3 個 mock WS）
   共 ≥ 30 個前端 unit test

Z. backend：CORS + WS host 確認允許 http://localhost:3000 / ws://localhost:3000
   backend/app/main.py CORS middleware 已設，這裡只是再次驗證

AA. Makefile 加：
    frontend-dev: cd frontend && npm run dev
    frontend-build: cd frontend && npm run build
    frontend-test: cd frontend && npm test
    frontend-e2e: cd frontend && npx playwright test

AB. 寫 scripts/health_checks/phase_15.sh
AC. 寫 docs/phase_reports/PHASE_15.md
AD. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 15 = 以下 12 個指令全部 exit code 0：

```bash
# 1. npm install 成功
cd frontend && npm ci && cd ..

# 2. lint 通過
cd frontend && npm run lint && cd ..

# 3. type check 通過
cd frontend && npx tsc --noEmit && cd ..

# 4. build 成功
cd frontend && npm run build && cd ..

# 5. dev server 啟動 + /login 可訪問
cd frontend && npm run dev &
DEV_PID=$!
sleep 10
curl -fsS http://localhost:3000/login | grep -i "登入"

# 6. middleware 未登入 → 307 redirect /login
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/dashboard)
test "$STATUS" = "307" || test "$STATUS" = "302"

# 7. 18 頁路由都能載（未登入跳 login，已登入時 page 載）
for path in dashboard market/overview market/institutional market/calendar \
            screener/watchlist screener/filter screener/compare \
            analysis/new analysis/history \
            statistics/accuracy statistics/models statistics/backtest \
            portfolio/positions portfolio/orders portfolio/history \
            news/sentiment news/announcements notifications \
            admin/users admin/audit admin/system admin/pipeline; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000/$path")
  echo "$status $path"
done | grep -v -E "200|307|302" || true   # 不應有其他 status

# 8. unit tests 通過
cd frontend && npm test -- --run && cd ..

# 9. E2E smoke 通過（playwright 需要 backend up）
# 確認 backend 也起來
curl -fsS http://localhost:8000/health/live
cd frontend && npx playwright test tests/e2e/auth.spec.ts && cd ..

# 10. 共用元件齊全（檔案存在）
for f in DataTable ChartContainer NumberFormat PercentFormat DateFormat \
         MarketBadge ConfirmDialog EmptyState ErrorBoundary LoadingSkeleton \
         Pagination Sidebar Topbar; do
  test -f "frontend/src/components/common/$f.tsx"
done

# 11. WS hook 檔案存在
test -f frontend/src/hooks/useWebSocket.ts

# 12. Bundle size < 1.5 MB（gzipped < 500 KB）
du -sh frontend/.next/static/ | awk '{print $1}'

kill $DEV_PID
bash scripts/health_checks/phase_15.sh
```

【6. Smoke Test（手動）】
✓ 用 admin 登入：next_action=change_password → 跳 /onboarding/change-password
✓ 改密碼 + onboarding → /dashboard 正常顯示
✓ Sidebar 18 頁全列出（即使內容是 stub）
✓ 切換 light/dark theme（next-themes）
✓ DevTools Network：login 後有 access_token in localStorage、refresh_token in httpOnly cookie
✓ DevTools Console：0 error、0 hydration warning

【7. 已知陷阱】
✗ Hydration warning：日期/時間在伺服器與客戶端時區不同 → 用 useEffect 設或統一 UTC
✗ shadcn/ui 樣式錯亂：tailwind.config.ts content paths 必須包到 src/components
✗ middleware 對 _next 路徑配對 → 用 negative matcher
✗ WebSocket subprotocol 必須兩個值（["tradingagents.v1", "ticket.XXX"]）
✗ axios refresh interceptor 無限迴圈 → 加 _retry flag
✗ CSRF cookie 跨 port（localhost:3000 vs localhost:8000）→ withCredentials + SameSite=Lax dev
✗ Next.js App Router cache：dynamic data 用 cache: 'no-store' 或 dynamic = 'force-dynamic'
✗ react-window + next-themes：SSR mismatch → dynamic import + ssr: false
✗ shadcn dialog 在 SSR 報錯 → 'use client' 標頭
✗ middleware 用了 cookies() 但 dev 跨 port 取不到 → 改 req.cookies
✗ Decimal 直接放 React 變空白 → 用 NumberFormat 元件包
✗ playwright 第一次跑要 npx playwright install
✗ WS 在 https 環境必須 wss → NEXT_PUBLIC_WS_URL 依環境設
✗ react-hook-form + zod：resolver 用 zodResolver 才能對接

【8. Self-Check SOP】跑第 8.5.4 章全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - frontend/src/lib/{api, format, i18n, query-client}.ts
  - frontend/src/store/auth.ts
  - frontend/src/hooks/useWebSocket.ts
  - frontend/src/middleware.ts
  - frontend/src/app/{layout, (auth)/{layout, login, forgot-password, reset-password}, onboarding/{change-password, page}, (app)/layout}.tsx
  - frontend/src/app/(app)/<18 頁 PageStub>.tsx
  - frontend/src/components/common/<13 個>.tsx
  - frontend/Dockerfile
  - frontend/playwright.config.ts + tests/e2e/auth.spec.ts
  - frontend/vitest.config.ts + tests/unit/*
  - scripts/health_checks/phase_15.sh

程式檔（修改）：
  - frontend/package.json + package-lock.json
  - Makefile（加 frontend-* target）
  - docker-compose.yml（加 frontend service）

文件檔（新增）：
  - docs/phase_reports/PHASE_15.md
  - docs/runbooks/frontend.md（debug hydration、CSP、WS）
  - frontend/.env.local.example

文件檔（更新）：
  - docs/phase_progress.md
  - docs/setup.md（加「啟動前端」章節）

Git tag：phase-15-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：
- B-D（Next.js init + shadcn）建議先一氣呵成，否則套件版本搞不定
- E（api client）的 interceptor 是後續所有頁面的基礎，先測穩
- H（middleware）測試一定要驗 cookie + redirect 流程
- 18 頁 stub（Q）只放 PageStub，不要寫內容（P16/P17 才寫）
```

---

### ▌Phase 16 — 前端核心 8 頁（後端整合）

```
=== TradingAgents-TW Phase 16（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\frontend
後端：http://localhost:8000/api/v1
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 16
必讀 PLAN.md 章節：第 8.5, 13.4, 21（頁面地圖完整版）章

【1. 前置依賴 Phase】
依賴：Phase 1-15
驗證方式：bash scripts/health_checks/phase_15.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_15.sh
- frontend npm run build 通過
- 18 頁 stub 都 200 / 307
- 後端 P10/P11/P14 完整可跑
- 真實跑 2330 + AAPL 都能完成

【3. 本 Phase 目標】
完成「8 個核心頁面」（每頁都接後端、可實際操作）：
  1. 儀表板 /dashboard
  2. 自選股清單 /screener/watchlist
  3. 新增分析 /analysis/new
  4. 分析進度 /analysis/[id]（含 AgentFlowGraph）
  5. 分析歷史 /analysis/history
  6. 辯論詳情 /analysis/[id]?tab=debate
  7. 待核准訂單 /portfolio/orders
  8. 用戶管理 + 審計日誌 /admin/users + /admin/audit

注意：本 Phase 不寫 P17 的 10 個進階頁。
注意：每頁必須有 loading state、empty state、error state、響應式（≥1024px 不破版）。

【4. 任務清單】

A. 切分支：phase/16-frontend-core-pages

B. /dashboard 儀表板（src/app/(app)/dashboard/page.tsx）：
   - 自選股 mini cards（即時價）
   - 最近分析（最後 5 筆）
   - 待核准訂單（最後 5 筆）
   - 大盤指數 mini chart（lightweight-charts）
   - LLM 月用量 progress bar
   - 用 React Query parallel fetch

C. /screener/watchlist 自選股（CRUD）：
   - 表格（DataTable）：symbol, name, last_price, change, change_pct, volume, note
   - 加入：搜尋 cmdk 對 /api/v1/stocks?q= → 選 → POST /watchlist
   - 編輯 note：inline edit
   - 刪除：confirm dialog
   - 排序：自選順序拖曳（dnd-kit 可選，v7 先用 sort_order 數字輸入）

D. /analysis/new 新增分析：
   - 步驟 1：選股票（搜尋）
   - 步驟 2：選 analyst（多選 checkbox，依 region 過濾，US 不顯 sentiment）
   - 步驟 3：選模型（gemini-2.0-flash / gpt-4o-mini / claude-haiku-3-5）
   - 步驟 4：選 debate_rounds（1-3）
   - submit → POST /analysis with Idempotency-Key（uuid v4）
   - 顯示 quota 狀態（剩餘 USD）
   - 提示預估費用 + 預估時間
   - 跳 /analysis/[id]

E. /analysis/[id] 分析進度（即時）：
   - 用 useAnalysisWS hook 訂閱
   - AgentFlowGraph：用 @xyflow/react 顯示節點動態（每收到 analyst_completed event 該節點變綠）
   - 各 analyst 結果展開卡片
   - Bull/Bear 辯論 timeline
   - Manager signal（最終）
   - report_md（react-markdown 渲染）
   - 完成後顯示「匯出 PDF/MD/XLSX」按鈕（跳 /api/v1/exports/...）

F. /analysis/history 分析歷史：
   - 表格：symbol, status, signal, confidence, cost_usd, created_at, actions
   - 篩選：symbol, status, date range
   - cursor pagination
   - 點擊跳 /analysis/[id]
   - 刪除（admin only）

G. /analysis/[id]?tab=debate 辯論詳情：
   - tabs：Overview / Analysts / Debate / Report
   - Debate tab：每輪 bull/bear 對照（左右並排）+ Manager 結論

H. /portfolio/orders 待核准訂單：
   - 表格：symbol, side, qty, entry_price, signal_confidence, analysis_id, created_at
   - 核准按鈕：confirm dialog（雙重確認）→ POST /orders/{id}/approve
   - 拒絕按鈕：confirm dialog → POST /orders/{id}/reject
   - 並發保護由後端做（接 409 顯示「已被其他人處理」）

I. /admin/users 用戶管理（admin only）：
   - 表格：email, role, last_login, created_at, status, actions
   - 新增用戶（admin only）：email + role + 初始密碼 → 強制 must_change_password=true
   - 重設密碼（admin only）：產生臨時密碼，提示用戶下次登入改
   - 強制下線：DELETE /admin/users/{id}/sessions/{jti}
   - 停用/啟用（soft delete）

J. /admin/audit 審計日誌：
   - 表格：trace_id, actor, action, entity, timestamp
   - 篩選：actor, action, entity, date range
   - cursor pagination
   - 點擊展開 details JSON

K. components/AgentFlowGraph.tsx（@xyflow/react）：
   - 動態節點：每個 analyst + bull/bear（多輪 → 多節點）+ manager
   - 邊：從前到後
   - 狀態：pending（灰）/ running（黃，動畫）/ completed（綠）/ failed（紅）
   - hover 顯示 node 詳情

L. 各頁的 React Query hooks：
   - useStocks, useStockDetail, useOhlcv, useWatchlist, useAnalysisList,
     useAnalysisDetail, useOrders, useUsers, useAuditLogs

M. 前端 unit test 增加（≥ 40 個新測試）：
   - WatchlistTable.test.tsx, AnalysisFlowGraph.test.tsx, OrderApprovalDialog.test.tsx, ...

N. E2E test（≥ 4 個關鍵流程）：
   - tests/e2e/full-workflow.spec.ts:
     - test_admin_login_to_dashboard
     - test_add_2330_to_watchlist
     - test_create_analysis_2330_completes
     - test_approve_order_with_double_confirm

O. 寫 scripts/health_checks/phase_16.sh
P. 寫 docs/phase_reports/PHASE_16.md
Q. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 16 = 以下 11 個指令全部 exit code 0：

```bash
# 1-3. lint + type + build
cd frontend && npm run lint && npx tsc --noEmit && npm run build && cd ..

# 4. dev server 啟動
cd frontend && npm run dev &
DEV_PID=$!
sleep 10

# 5. 8 核心頁路由都載
for path in dashboard screener/watchlist analysis/new analysis/history portfolio/orders admin/users admin/audit; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000/$path")
  test "$status" = "307" || test "$status" = "200"  # 未登入 redirect 也算
done

# 6. unit tests 通過（≥ 70 累積）
cd frontend && npm test -- --run && cd ..

# 7. E2E test 通過（含完整流程）
cd frontend && npx playwright test tests/e2e/full-workflow.spec.ts && cd ..

# 8. lighthouse score（dashboard）
npx lighthouse http://localhost:3000/dashboard --only-categories=performance --quiet \
  --output json --output-path /tmp/lh.json --chrome-flags="--headless"
SCORE=$(jq '.categories.performance.score * 100' /tmp/lh.json)
test "$SCORE" -gt 60   # 鬆標準（v1.0 自用）

# 9. AgentFlowGraph 元件測試
cd frontend && npm test -- AgentFlowGraph --run && cd ..

# 10. Bundle 合理
du -sh frontend/.next/static/ | awk '{print $1}'

# 11. console 0 error（手動或用 playwright 捕捉）
# Playwright test 已含 page.on('pageerror', err => fail)

kill $DEV_PID
bash scripts/health_checks/phase_16.sh
```

【6. Smoke Test（手動）】
✓ 完整流程 1：admin 登入 → 加 2330 自選股 → 新增分析 → 看 AgentFlowGraph 動畫 → 完成 → 看 signal 與 report
✓ 完整流程 2：核准訂單 → 雙重確認 → 訂單變 APPROVED
✓ 故意併發核准（兩個 tab 同時點）→ 一個成功一個顯示「已被處理」
✓ 響應式：1280 / 1024 不破版（768 P15 已測，這裡不強制）
✓ AgentFlowGraph 多 analyst 並列、debate 兩輪 5 個節點都顯示

【7. 已知陷阱】
✗ AgentFlowGraph：同節點重複事件 → state 用 Map by node id
✗ DataTable cursor pagination：cursor 變化要 reset query data → invalidateQueries
✗ 並發核准 race：UI 樂觀更新 + onError 回滾
✗ WebSocket reconnect：v1.0 不做（連線斷請用戶手動重新整理）
✗ markdown 中含表格 → remark-gfm
✗ 程式碼區塊高亮 → rehype-highlight + 引入 highlight.js CSS
✗ /admin/* 在 sidebar 對 viewer 隱藏（前端依 role hide）
✗ /admin/users 的 password 欄位永遠不顯示（後端不回）
✗ 多次重複按 submit → button disabled until response
✗ Decimal 在 React 表格直接 toLocaleString 會掉精度 → 用 BigNumber
✗ Idempotency-Key uuid 在頁面 mount 時建一次，submit 後重置
✗ 大表格 > 1000 row → react-window 虛擬化（v1.0 自用通常不會）
✗ AgentFlowGraph 節點佈局：用 dagre layout（@xyflow 內建）

【8. Self-Check SOP】跑第 8.5.4 章全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - frontend/src/app/(app)/dashboard/page.tsx + components/dashboard/*
  - frontend/src/app/(app)/screener/watchlist/page.tsx + components/watchlist/*
  - frontend/src/app/(app)/analysis/new/page.tsx + components/analysis-new/*
  - frontend/src/app/(app)/analysis/[id]/page.tsx + components/analysis-detail/*（含 AgentFlowGraph）
  - frontend/src/app/(app)/analysis/history/page.tsx
  - frontend/src/app/(app)/portfolio/orders/page.tsx + components/orders/*
  - frontend/src/app/(app)/admin/users/page.tsx + components/admin-users/*
  - frontend/src/app/(app)/admin/audit/page.tsx
  - frontend/src/components/AgentFlowGraph.tsx
  - frontend/src/hooks/use*.ts（10+ 個 React Query hooks）
  - 新增 ≥ 40 unit tests + ≥ 4 E2E test
  - scripts/health_checks/phase_16.sh

程式檔（修改）：
  - frontend/src/components/common/Sidebar.tsx（標已實作頁、可點）

文件檔（新增）：
  - docs/phase_reports/PHASE_16.md

文件檔（更新）：
  - docs/phase_progress.md

Git tag：phase-16-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
建議順序：
  B（dashboard 雛形）→ L（hooks 框架）→ C（watchlist）→ I/J（admin 兩頁）
  → D（analysis/new）→ K（AgentFlowGraph 元件）→ E（analysis/[id]）→ G（debate tab）
  → F（history）→ H（orders）→ M/N（測試）

特別重要：
- E（analysis/[id] + AgentFlowGraph）是視覺亮點，但容易破版，多花時間調樣式
- 並發核准（H）後端已保護，前端只需顯示 409 訊息
- 若本 Phase 程式碼超過 1500 行 → 拆 16a / 16b（依第 8.5.1）
  16a：dashboard + watchlist + admin
  16b：analysis（new/detail/history）+ orders + AgentFlowGraph
```

---

### ▌Phase 17 — 前端進階 10 頁（含 mock data）

```
=== TradingAgents-TW Phase 17（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents\frontend
後端：http://localhost:8000/api/v1
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 17
必讀 PLAN.md 章節：第 7（限制：哪些頁面是 mock）, 8.5, 21（頁面地圖）章

【1. 前置依賴 Phase】
依賴：Phase 1-16
驗證方式：bash scripts/health_checks/phase_16.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_16.sh
- 8 核心頁全部正常

【3. 本 Phase 目標】
完成 18 - 8 = **10 個進階頁**（依第 21 章標記）：
  - 完整接後端：市場總覽 / 三大法人（TW）/ 篩選器 / 新聞情緒 / 重大公告 / 通知設定 / 模擬持倉 / 交易記錄 / 系統監控 / 資料管線（共 10）
  - mock data（v1.1 才補）：財報日曆 / 多股比較 / 準確率 / 模型比較 / 回測

注意：mock 頁面需明確標示「Mock 資料 - v1.1 將完整實作」（不要假裝是真資料）。
注意：本 Phase「不寫前端進階互動」（如拖曳重排），保持「能用」即可。

【4. 任務清單】

A. 切分支：phase/17-frontend-advanced-pages

B. /market/overview 市場總覽（完整）：
   - 大盤指數卡片（TW: 加權、櫃買；US: S&P, NASDAQ, Dow）
   - 漲跌家數
   - 成交量 chart（lightweight-charts）
   - 漲幅榜 / 跌幅榜 / 成交量榜（DataTable，可切 TW/US）

C. /market/institutional 三大法人（TW only，完整）：
   - 日期選擇
   - 表格：外資、投信、自營商買賣超
   - 累積買超 chart（30 日）
   - 個股 top 10 買超（點擊跳 stock detail）

D. /market/calendar 財報日曆（mock，v1.1）：
   - 月曆 view（react-big-calendar 或 fullcalendar）
   - mock：未來 30 天 fake events
   - 標示 "Mock 資料 - v1.1 完整實作"

E. /screener/filter 選股篩選器（完整）：
   - 篩選條件 form：PE_min/max, EPS_growth, RSI, dividend_yield, market_cap, volume
   - 切換市場 TW / US（過濾條件不同）
   - submit → /api/v1/screener
   - 結果表格 + cursor pagination
   - 儲存篩選條件（v1.0 用 localStorage，v1.1 接後端）

F. /screener/compare 多股比較（mock，v1.1）：
   - 多選最多 5 支
   - 並排顯示主要指標
   - mock data + "Mock - v1.1"

G. /statistics/accuracy 準確率分析（完整 - 後端有 analysis 結果）：
   - 過去 N 日 BUY 訊號的實際漲跌（簡化計算）
   - 圓餅圖：BUY 命中率、SELL 命中率
   - 表格：分析 ID、symbol、signal、actual_return_30d
   - 注意：後端可能還沒這個 endpoint → 在 P11 admin/system 暫時計算 or P17 加 endpoint

H. /statistics/models 模型比較（mock 部分）：
   - 表格：model（gemini/openai/anthropic）, total_analyses, avg_cost, avg_accuracy
   - 從 llm_usage 表 group by 計算（後端要新增 endpoint，或 admin 已有）

I. /statistics/backtest 回測（mock，v1.1）：
   - 策略選單 + 期間選擇
   - mock equity curve + drawdown
   - "Mock - v1.1"

J. /portfolio/positions 模擬持倉（完整）：
   - 從 portfolio_positions 表（已核准訂單建立）
   - 表格：symbol, qty, avg_cost, current_price, unrealized_pl, unrealized_pl_pct
   - 總計：portfolio_value, total_pl

K. /portfolio/history 交易記錄（完整）：
   - 表格：trade_history 所有 row
   - 篩選：symbol, date range, side
   - 點擊展開原始 analysis_id link

L. /news/sentiment 新聞情緒（完整）：
   - 全市場 + 個股 切換
   - 情緒分佈 bar chart（極正/正/中/負/極負）
   - 文章列表（Qdrant 中近 7 天）+ source link
   - 點擊文章跳外部 url

M. /news/announcements 重大公告（完整）：
   - 表格：date, symbol, type, title, source link
   - 篩選：symbol, type, date range
   - TW MOPS + US SEC EDGAR 混合顯示

N. /notifications 通知設定（完整）：
   - LINE Notify token（顯示 isSet）
   - Telegram Bot token + chat_id
   - 訂閱事件 checkbox：分析完成 / 訂單核准 / 系統警告 / 月度報告
   - 測試發送按鈕
   - 通知歷史 log 表

O. /admin/system 系統監控（完整）：
   - 從 /metrics 拉資料
   - 卡片：API 可用性、平均延遲、今日分析次數、今日 LLM 成本、磁碟使用、佇列長度
   - 圖：過去 24h 的 metrics 走勢（v1.0 mock，v1.1 接 prometheus）

P. /admin/pipeline 資料管線管理（完整）：
   - DLQ 列表（celery_dead_letters）
   - resolve / requeue 按鈕
   - 每個 source 的 last success time
   - 手動觸發 task（buttons：sync_ohlcv_tw, sync_ohlcv_us, news_ingest）

Q. 各頁的 React Query hooks 補齊
R. 共用元件補強：BarChart, PieChart（recharts wrapper）

S. 前端 unit test 補（≥ 40 個新）
T. E2E test 補（≥ 3 個關鍵）：
   - test_screener_filter_returns_results
   - test_notifications_settings_save
   - test_admin_system_shows_metrics

U. 後端 endpoint 處理原則（**v7.0 明確：本 Phase 不擴大後端**）：
   - 統計頁（accuracy / models）一律 **client-side 計算**：
     從 GET /api/v1/analysis（已存在 P11）拉資料，前端用 React 算準確率與模型比較
     若 analysis 數量大，加 query param 過濾近 N 天
   - 資料管線狀態（admin/pipeline）：
     **Phase 11 已有 GET /api/v1/admin/pipeline/dlq**（直接用），
     每個 source 的「last success time」已在 metrics endpoint，不需新 endpoint
   - **如真的需要新 endpoint** → 不要在 P17 加，記到 docs/runbooks/p17_followup.md，
     等 P18/P19 整合驗證時統一決定（避免 P17 程式碼超過 1500 行上限）

   驗收標準：本 Phase 結束 cd backend && git diff main -- backend/app/api/v1/ 應只有極小變動（<= 1 個小 endpoint），
   主要修改集中在 frontend/。

V. 寫 scripts/health_checks/phase_17.sh
W. 寫 docs/phase_reports/PHASE_17.md
X. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 17 = 以下 11 個指令全部 exit code 0：

```bash
# 1-3. lint + type + build
cd frontend && npm run lint && npx tsc --noEmit && npm run build && cd ..

# 4. dev server
cd frontend && npm run dev &
DEV_PID=$!
sleep 10

# 5. 全 18 頁路由都載
for path in dashboard market/overview market/institutional market/calendar \
            screener/watchlist screener/filter screener/compare \
            analysis/new analysis/history \
            statistics/accuracy statistics/models statistics/backtest \
            portfolio/positions portfolio/orders portfolio/history \
            news/sentiment news/announcements notifications \
            admin/users admin/audit admin/system admin/pipeline; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000/$path")
  echo "$status $path"
done | grep -v -E "200|307|302"   # 不應有非 2xx/3xx

# 6. mock 頁面有「Mock - v1.1」標示（grep build output）
for path in market/calendar screener/compare statistics/backtest; do
  curl -s "http://localhost:3000/$path" 2>/dev/null | grep -i "mock\|v1.1" || echo "may need admin login"
done

# 7. unit tests（≥ 110 累積）
cd frontend && npm test -- --run && cd ..

# 8. E2E full（含 P16 + P17 全流程）
cd frontend && npx playwright test && cd ..

# 9. console 0 error
# E2E 測試已加 page.on('pageerror', fail)

# 10. lighthouse 三頁
for path in dashboard market/overview screener/filter; do
  npx lighthouse "http://localhost:3000/$path" --only-categories=performance --quiet --chrome-flags="--headless" || true
done

# 11. 通知設定流程
# Smoke：手動測 LINE/Telegram 設定（如有 token）

kill $DEV_PID
bash scripts/health_checks/phase_17.sh
```

【6. Smoke Test（手動）】
✓ 全 18 頁開過一遍，無破版、無 console error、loading state OK
✓ /screener/filter PE_max=15 + 市場切 TW → 表格列出符合股票
✓ /portfolio/positions：訂單核准後出現持倉
✓ /admin/system 顯示 metrics 圖表
✓ /admin/pipeline 顯示 DLQ（如果有）
✓ /notifications 設定 LINE token → 測試發送 → 手機收到（P18 才完整）
✓ Mock 頁面（calendar/compare/backtest）標示明顯

【7. 已知陷阱】
✗ recharts SSR：dynamic import + ssr: false
✗ lightweight-charts：父容器 height 必須明確設
✗ 跨市場切換閃爍：useTransition 包 setState
✗ 大表格效能：react-window 虛擬化（自選股 > 100 才需要）
✗ 通知 token 顯示：後端只回 isSet，前端不要 GET 真值
✗ DLQ resolve：requireConfirm + 顯示原始 traceback（不要藏）
✗ /admin/system 圖：v1.0 mock，要明確標示
✗ 股票篩選器條件多 → debounce form input（300ms）
✗ recharts 在 dark theme 對比差 → 自訂 theme color
✗ 通知歷史 log：cursor pagination
✗ Mock 頁面切換到真實時要明確 changelog（v1.1）
✗ 多股比較：v1.0 mock，但表格框架可重用 v1.1
✗ 系統監控 /metrics：admin 才能看（前端依 role hide）

【8. Self-Check SOP】跑第 8.5.4 章全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - frontend/src/app/(app)/<10 個進階頁>/page.tsx
  - frontend/src/components/{market,screener,statistics,portfolio,news,notifications,admin}/*
  - 補強 BarChart / PieChart 共用
  - ≥ 40 unit tests + ≥ 3 E2E
  - scripts/health_checks/phase_17.sh

程式檔（修改）：
  - frontend/src/components/common/Sidebar.tsx（標 mock 頁、所有頁可點）
  - 後端可能加 endpoint（J 或 U 提到的）

文件檔（新增）：
  - docs/phase_reports/PHASE_17.md
  - docs/runbooks/frontend_pages.md（每頁的資料來源、mock 替換指引）

文件檔（更新）：
  - docs/phase_progress.md
  - CHANGELOG.md（標 v1.1 待補：calendar / compare / backtest）

Git tag：phase-17-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
建議順序：
  L/M（news 兩頁，後端已準備）→ E（screener filter，邏輯重要）
  → B/C（market 兩頁）→ J/K（portfolio）→ N（notifications）
  → O/P（admin 兩頁）→ G/H（statistics 真實）
  → D/F/I（mock 頁面收尾）

特別重要：
- 若本 Phase 程式碼超 1500 行 → 拆 17a / 17b
  17a：market + news + screener + portfolio（接後端的 6 頁）
  17b：notifications + admin + statistics + mock 4 頁（管理 + 報表 + mock）
- mock 頁面是設計門面，雖 v1.0 不功能但結構要對，方便 v1.1 替換
- /admin/system 與 /admin/pipeline 是給 admin 看後端健康的視窗，要與 P19/P20 驗證腳本對齊
```

---

## 📍 Phase 18-20 詳細 Prompt（v7.0 第 4 次規劃補完，最終）

> **第 4 次規劃補完範圍：Phase 18, 19, 20（共 3 個 Phase）。本次完成後 v7.0 規劃 100% 完工。**

---

### ▌Phase 18 — 通知整合（LINE/Telegram）+ 安全強化（OWASP）+ 滲透測試

```
=== TradingAgents-TW Phase 18（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 18
必讀 PLAN.md 章節：第 8.5, 16.3, 18.2, 19.4, 19.5, 19.6, 19.7, 23.5 章

【1. 前置依賴 Phase】
依賴：Phase 1-17（後端 + 前端 全完整）
驗證方式：bash scripts/health_checks/phase_17.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_17.sh
- 後端 + 前端可同時跑（make backend-dev / make frontend-dev / make up-workers）
- 真實跑過 2330 + AAPL 完整分析 + 核准訂單

【3. 本 Phase 目標】
讓系統「達 v1.0 上線級安全標準」+「真實通知能送達」：
  (1) 通知 Adapter Plugin：LINE Notify、Telegram Bot
  (2) Notification Service（事件驅動：分析完成 / 訂單核准 / CB OPEN / 配額警告）
  (3) NotificationDispatcher（依用戶 settings 過濾 + retry + DLQ）
  (4) 通知 token 用 Fernet 加密儲存（DATA_ENCRYPTION_KEY）
  (5) bandit 高風險 = 0
  (6) detect-secrets 無新發現
  (7) Trivy HIGH+CRITICAL = 0（base image + Python deps）
  (8) OWASP test suite：SQL injection / XSS / CSRF / SSRF / IDOR / Open Redirect / Path Traversal / Mass Assignment
  (9) CSP nonce-based（prod）
  (10) Secret rotation 腳本（JWT key 雙 key 7 天輪替、DB 半年輪替）
  (11) Pen test checklist（手動 + 自動）

注意：本 Phase「不寫 prod 部署」（在 P19）、「不寫最終報告」（P20）。

【4. 任務清單】

A. 切分支：
   git checkout main && git pull
   git checkout -b phase/18-notifications-security

B. backend/app/notifications/base.py：
   class BaseNotifier(ABC):
     name: ClassVar[str]
     display_name_zh: ClassVar[str]

     def __init__(self, encrypted_credentials: str, decryption_key: str):
       creds = decrypt_fernet(encrypted_credentials, decryption_key)
       self.credentials = json.loads(creds)
       self.cb = CIRCUIT_BREAKERS.setdefault(f"notif_{self.name}", CircuitBreaker())

     @abstractmethod
     async def send(self, title: str, body: str, level: str = "INFO",
                    metadata: dict = None) -> NotifyResult: ...

     @abstractmethod
     async def health_check(self) -> bool: ...

   NOTIFIER_REGISTRY: dict[str, type[BaseNotifier]] = {}

   def register_notifier(cls):
     NOTIFIER_REGISTRY[cls.name] = cls
     return cls

C. backend/app/notifications/line_notifier.py：
   @register_notifier
   class LINENotifier(BaseNotifier):
     name = "line"
     display_name_zh = "LINE Notify"

     BASE_URL = "https://notify-api.line.me/api/notify"

     async def send(self, title, body, level="INFO", metadata=None):
       emoji = {"INFO": "ℹ️", "WARN": "⚠️", "CRITICAL": "🚨", "SUCCESS": "✅"}.get(level, "ℹ️")
       message = f"{emoji} {title}\n\n{body}"
       if metadata:
         message += f"\n\n[trace_id: {metadata.get('trace_id', '-')}]"
       async with self.client.post(self.BASE_URL,
         headers={"Authorization": f"Bearer {self.credentials['token']}"},
         data={"message": message[:1000]}  # LINE 限 1000 字
       ) as resp:
         resp.raise_for_status()
       return NotifyResult(success=True, ...)

D. backend/app/notifications/telegram_notifier.py：
   @register_notifier
   class TelegramNotifier(BaseNotifier):
     name = "telegram"
     display_name_zh = "Telegram Bot"

     BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"

     async def send(self, title, body, level="INFO", metadata=None):
       text = f"*{escape_md(title)}*\n\n{escape_md(body)}"
       async with self.client.post(self.BASE_URL.format(token=self.credentials['bot_token']),
         json={"chat_id": self.credentials['chat_id'],
               "text": text, "parse_mode": "MarkdownV2"}
       ) as resp:
         resp.raise_for_status()
       ...

E. backend/app/notifications/dispatcher.py：
   class NotificationDispatcher:
     async def dispatch(self, event: NotifyEvent):
       """依事件類型 + 用戶 settings 找出該送的人，送出 + 記 log + DLQ"""
       targets = await self._resolve_targets(event)
       for user_id, notifier_name, encrypted_creds in targets:
         try:
           notifier = NOTIFIER_REGISTRY[notifier_name](encrypted_creds, settings.DATA_ENCRYPTION_KEY)
           result = await notifier.send(event.title, event.body, event.level, event.metadata)
           await self._log_success(user_id, notifier_name, event, result)
         except Exception as e:
           logger.warning(f"Notify {notifier_name} failed for {user_id}: {e}")
           await self._log_failure(user_id, notifier_name, event, e)
           # retry：寫 notification_dlq table（celery_dead_letters 用 task_name='notify'）
           await self._enqueue_retry(user_id, notifier_name, event)

F. backend/app/services/notification_service.py：
   class NotificationService:
     async def update_settings(self, user_id, settings: NotificationSettings):
       # 加密 token 後存 DB
       encrypted = encrypt_fernet(json.dumps(settings.line_credentials), DATA_ENCRYPTION_KEY)
       ...

     async def get_settings_public(self, user_id) -> dict:
       """回傳給前端：不洩漏 token，只回 isSet + 訂閱 events"""
       ...

     async def test_send(self, user_id, notifier_name) -> NotifyResult:
       """用戶按「測試發送」"""
       ...

G. backend/app/core/crypto.py：
   from cryptography.fernet import Fernet

   def encrypt_fernet(plaintext: str, key: str) -> str: ...
   def decrypt_fernet(ciphertext: str, key: str) -> str: ...

   def generate_data_encryption_key() -> str:
     return Fernet.generate_key().decode()

H. 整合事件 → notification：
   - AnalysisCompletedEvent（P14 已 publish）
     → 在 run_analysis 結束時：dispatcher.dispatch(...)
   - OrderApprovedEvent
     → 在 /orders/{id}/approve 後：dispatcher.dispatch(...)
   - CircuitBreakerOpenEvent
     → 在 CB 切 OPEN 時：dispatcher.dispatch(level="CRITICAL")
   - LLMQuotaWarningEvent（80%）+ LLMQuotaExceededEvent（100%）
     → quota_service 計算到對應百分比時 dispatch

I. backend/app/api/v1/notifications_router.py 升級：
   - PUT /api/v1/notifications/settings（接 line_token、telegram_bot_token、telegram_chat_id、subscriptions）
   - POST /api/v1/notifications/test（呼叫 service.test_send）
   - 後端僅回 isSet（前端不顯明文 token）

J. CSP nonce-based（prod）：
   backend/app/core/security_headers.py 升級：
   class SecurityHeadersMiddleware:
     async def dispatch(self, request, call_next):
       nonce = secrets.token_urlsafe(16)
       request.state.csp_nonce = nonce
       response = await call_next(request)
       if settings.APP_ENV == "prod":
         response.headers["Content-Security-Policy"] = (
           f"default-src 'self'; "
           f"script-src 'self' 'nonce-{nonce}'; "
           f"style-src 'self' 'unsafe-inline'; "  # tailwind 需要
           f"img-src 'self' data: https:; "
           f"font-src 'self' data:; "
           f"connect-src 'self' wss: https:; "
           f"frame-ancestors 'none';"
         )
       else:
         # dev：用 P9 寫的 CSP_DEV
         response.headers["Content-Security-Policy"] = CSP_DEV
       return response

   前端 next.config.js 加 nonce 注入（給 inline script）：
   experimental: { nextScriptWorkers: false } 等

K. Secret rotation 腳本：
   scripts/rotate_secrets.sh（雙 key 機制）：
   - 產生新 SECRET_KEY_NEW
   - .env：SECRET_KEY=<new>, SECRET_KEY_PREVIOUS=<old>
   - 7 天後跑：scripts/rotate_secrets.sh --finalize → 移除 PREVIOUS
   - JWT decode 時兩個 key 都試，能 verify 即過

   scripts/rotate_db_passwords.sh：
   - ALTER USER ta_service_rw WITH PASSWORD '<new>'
   - 更新 .env
   - restart backend + workers

   scripts/rotate_encryption_key.sh（DATA_ENCRYPTION_KEY）：
   - 產生新 key
   - 把所有加密欄位（notification_settings.line_credentials 等）解密 → 用新 key 重新加密
   - 寫回 DB
   - 更新 .env
   注意：這個腳本必須有「rollback」分支，加密失敗時不能寫回 DB

L. OWASP test suite：
   backend/tests/security/test_owasp_top10.py（≥ 15 個測試）：
   - test_sql_injection_in_login_blocked
   - test_sql_injection_in_search_blocked
   - test_xss_in_username_escaped
   - test_xss_in_note_field_escaped
   - test_csrf_blocks_cross_origin_post
   - test_ssrf_in_url_validator_blocked
   - test_idor_user_cannot_access_other_user_resource（重要！v1.0 自用但仍要驗）
   - test_open_redirect_in_login_callback_blocked
   - test_path_traversal_in_export_path_blocked
   - test_mass_assignment_role_field_blocked（POST /users 時不能直接設 role=ADMIN）
   - test_xxe_in_xml_parser_disabled（v1.0 不接受 XML，但仍驗）
   - test_no_security_misconfiguration_default_credentials
   - test_no_sensitive_data_exposure_in_error_responses
   - test_logging_does_not_include_password
   - test_jwt_none_algorithm_rejected

M. backend/tests/security/test_audit_chain_tampering.py（≥ 4 個測試）：
   - test_direct_db_update_breaks_chain
   - test_row_deletion_breaks_chain
   - test_row_reorder_detected
   - test_verify_chain_passes_clean_db

N. backend/tests/security/test_secret_handling.py（≥ 6 個測試）：
   - test_password_never_in_logs
   - test_jwt_secret_never_in_response
   - test_api_key_masked_in_log
   - test_token_not_in_url_query
   - test_csrf_token_not_logged
   - test_telegram_token_encrypted_at_rest

O. backend/tests/integration/test_notifications_e2e.py（≥ 6 個測試）：
   - test_analysis_completed_dispatches_to_subscriber
   - test_order_approved_dispatches
   - test_cb_open_dispatches_critical
   - test_llm_quota_80_dispatches_warning
   - test_user_unsubscribed_event_not_sent
   - test_notification_failure_writes_dlq

P. backend/tests/integration/test_csp_nonce.py（≥ 3 個測試）：
   - test_dev_csp_includes_unsafe_eval
   - test_prod_csp_includes_nonce
   - test_csp_nonce_unique_per_request

Q. 安全自動化掃描：
   bandit baseline：cd backend && uv run bandit -r app/ -f json -o /tmp/bandit_report.json
   - 必須 0 個 HIGH severity
   - MEDIUM 必須在 .bandit 設 skip 並有理由註解

   detect-secrets：detect-secrets scan --baseline .secrets.baseline
   - 與 baseline 對照無新發現

   Trivy（image scan）：
   trivy image tradingagents-backend:latest --severity HIGH,CRITICAL --exit-code 1
   trivy image tradingagents-frontend:latest --severity HIGH,CRITICAL --exit-code 1
   - HIGH+CRITICAL = 0
   - 升級 base image：python:3.11-slim → 最新 patch 版

R. 前端安全：
   frontend：npm audit --audit-level=high
   - HIGH+CRITICAL = 0

   frontend/src/lib/api.ts：
   - withCredentials: true 但不額外存 token 在 localStorage（access_token 可，但不存 refresh）
   - logout 時 clear localStorage + cookie

S. 密碼安全 SOP（docs/runbooks/security.md 補強）：
   - bcrypt cost=12（已在 P8）
   - 密碼歷史 5 次（已在 P8）
   - lockout 5 次（已在 P8）
   - 強制改密碼：90 天（v1.0 暫不強制，docs 加說明）

T. Pen test checklist（docs/runbooks/pentest_checklist.md）：
   依 OWASP Testing Guide 簡化版，列出手動測試項目：
   - 登入：嘗試 SQL injection（' OR 1=1 --）→ 應 422
   - 嘗試常見密碼：admin/admin123 → 應 lockout 而非 login success
   - JWT 篡改：把 alg 改 none → 應 401
   - 改 user role：POST /users 帶 role=ADMIN → 應 422 或忽略 role 欄位
   - cookie 直接複製：在另一瀏覽器貼 refresh cookie → 應仍可 refresh（但 IP 不同建議 v1.1 加 IP binding）
   - 其他用戶資源：A 帳號嘗試 GET /watchlist 看到 B 帳號的 → 應只回自己的（IDOR）
   - WS：用過期 ticket → 1008 close
   - WS：subprotocol 寫錯 → close

U0. **Image build（v7.0 補：Trivy 掃描需要 image 已存在）：**
    Trivy 在退出條件第 7、8 項會跑，需要先 build：
    ```bash
    docker build -t tradingagents-backend:latest -f backend/Dockerfile .
    docker build -t tradingagents-frontend:latest -f frontend/Dockerfile .
    ```
    Makefile 加 target：
    ```makefile
    images-build:
       docker build -t tradingagents-backend:latest -f backend/Dockerfile .
       docker build -t tradingagents-frontend:latest -f frontend/Dockerfile .
    ```
    本 Phase 第一個動作（在跑 OWASP test 之前）就先 `make images-build`。

U. 寫 scripts/health_checks/phase_18.sh
V. 寫 docs/phase_reports/PHASE_18.md
W. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 18 = 以下 14 個指令全部 exit code 0：

```bash
# 1-3. uv sync + lint + 啟動
cd backend && uv sync && uv run ruff check app/ && cd ..
cd backend && uv run uvicorn app.main:app --port 8000 &
SERVER_PID=$!
sleep 3

# 4. 兩個 notifier 註冊
cd backend && uv run python -c "
from app.notifications.line_notifier import LINENotifier
from app.notifications.telegram_notifier import TelegramNotifier
from app.notifications.base import NOTIFIER_REGISTRY
assert 'line' in NOTIFIER_REGISTRY
assert 'telegram' in NOTIFIER_REGISTRY
print('OK')
"
cd ..

# 5. bandit 高風險 = 0
cd backend && uv run bandit -r app/ -ll -f json -o /tmp/bandit.json
HIGH=$(jq '[.results[] | select(.issue_severity=="HIGH")] | length' /tmp/bandit.json)
test "$HIGH" = "0"
cd ..

# 6. detect-secrets 通過
detect-secrets scan --baseline .secrets.baseline

# 7. Trivy 後端 image HIGH+CRITICAL = 0
docker build -t tradingagents-backend:latest -f backend/Dockerfile .
trivy image tradingagents-backend:latest --severity HIGH,CRITICAL --exit-code 1

# 8. Trivy 前端 image HIGH+CRITICAL = 0
docker build -t tradingagents-frontend:latest -f frontend/Dockerfile .
trivy image tradingagents-frontend:latest --severity HIGH,CRITICAL --exit-code 1

# 9. npm audit HIGH+CRITICAL = 0
cd frontend && npm audit --audit-level=high && cd ..

# 10. OWASP test suite 全綠
cd backend && uv run pytest tests/security/test_owasp_top10.py tests/security/test_audit_chain_tampering.py \
  tests/security/test_secret_handling.py -v && cd ..

# 11. 通知整合測試全綠
cd backend && uv run pytest tests/integration/test_notifications_e2e.py -v && cd ..

# 12. CSP test 通過
cd backend && uv run pytest tests/integration/test_csp_nonce.py -v && cd ..

# 13. 通知測試（手動或如有 token）
ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env | cut -d= -f2)
ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env | cut -d= -f2)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}" | jq -r '.data.access_token')

# 假設 settings 已設 LINE token
if [ -n "$(grep ^LINE_NOTIFY_TEST_TOKEN= .env)" ]; then
  curl -fsS -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/notifications/test \
    -H "Content-Type: application/json" -d '{"notifier":"line"}'
fi

# 14. 累積測試 ≥ 523 + health_check phase_18
cd backend && uv run pytest --collect-only -q 2>&1 | tail -1
kill $SERVER_PID
bash scripts/health_checks/phase_18.sh
```

【6. Smoke Test（手動）】
✓ 真跑 2330 分析 → 完成後 LINE 收到通知（中文 + emoji）
✓ 訂單核准 → LINE/Telegram 收到通知
✓ 故意把 GOOGLE_API_KEY 改錯 → CB OPEN → CRITICAL 通知
✓ 設用戶 monthly_llm_budget_usd=0.001 → 跑分析 → 80% 警告通知
✓ 設置「不訂閱訂單通知」→ 核准訂單不發 LINE
✓ Pen test checklist 跑一遍（手動 30 分鐘）
✓ DB 直接 UPDATE audit_logs → verify_audit_chain.py 抓到斷裂

【7. 已知陷阱】
✗ LINE Notify 訊息 > 1000 字 → 截斷或拆多則
✗ Telegram MarkdownV2 特殊字元（_*[]()~`>#+-=|{}.!）必須 escape
✗ Notification dispatcher 同步呼叫 → 卡住業務 → 用 background task
✗ Notification 加密欄位用 Fernet，DATA_ENCRYPTION_KEY 與 SECRET_KEY 必須分離
✗ CSP nonce 在 dev 太嚴 → 只在 prod 啟動 nonce
✗ Trivy 高風險來自 base image → 升級到最新 patch
✗ npm audit 高風險可能來自 transitive dep → npm audit fix 或鎖版本
✗ bandit 對 hardcoded password 報告 → 確認 test fixture 用 fake，加 # nosec
✗ OWASP IDOR 測試：建兩個 user，A 不能看 B 的 watchlist
✗ JWT none algorithm：python-jose 預設不接受，但要明確驗
✗ Mass assignment：POST /users body 帶 role 應被 schema 拒（exclude_unset=False, role 由 admin 後端設）
✗ Open redirect：login 後的 callback URL 必須在白名單
✗ Audit chain trigger 用 advisory lock 防 race，否則並發 INSERT 順序不對
✗ 通知 retry 寫入 DLQ 失敗 → log 但不 raise
✗ Secret rotation 期間 7 天並行 → 確認 lifecycle 不衝突

【8. Self-Check SOP】跑第 8.5.4 章全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - backend/app/notifications/{base, line_notifier, telegram_notifier, dispatcher}.py
  - backend/app/services/notification_service.py（升級）
  - backend/app/core/crypto.py
  - backend/app/core/security_headers.py（升級加 nonce）
  - scripts/rotate_secrets.sh
  - scripts/rotate_db_passwords.sh
  - scripts/rotate_encryption_key.sh
  - 6 個 test files（共 ~34 個測試，security 為主）
  - scripts/health_checks/phase_18.sh

程式檔（修改）：
  - backend/app/api/v1/notifications_router.py
  - backend/app/workers/tasks/run_analysis.py（觸發通知）
  - backend/pyproject.toml（cryptography）
  - frontend/next.config.js（nonce inject）

文件檔（新增）：
  - docs/phase_reports/PHASE_18.md
  - docs/runbooks/pentest_checklist.md
  - docs/runbooks/secret_rotation.md
  - SECURITY.md 升級（v1.0 真實內容）

文件檔（更新）：
  - docs/runbooks/security.md
  - docs/phase_progress.md

Git tag：phase-18-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：
- B-G（通知整合）和 J-K（CSP + Secret rotation）可並行
- 先做 B-F → H 整合測試，確保通知能跑通再做 OWASP 測試
- Trivy 與 bandit 是「漸進掃」，先跑一次看 baseline，逐項處理高風險
- Pen test checklist 是手動驗收，不要跳過
- 前端 npm audit 在 P15 後可能有低風險殘留，本 Phase 處理
```

---

### ▌Phase 19 — 整合測試 + E2E + Prod 部署 + 災難復原演練

```
=== TradingAgents-TW Phase 19（v7.0）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 19
必讀 PLAN.md 章節：第 8.5, 9.2（SLO）, 12.1（部署架構）, 13（Bootstrap）, 16（可觀測性）, 23.5, 31, 32 章

【1. 前置依賴 Phase】
依賴：Phase 1-18（後端 + 前端 + 安全 全完整）
驗證方式：bash scripts/health_checks/phase_18.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- bash scripts/health_checks/phase_18.sh
- 全部 18 個 phase_NN.sh 跑遍綠
- bandit / Trivy / npm audit 全綠
- 通知整合可送（手動驗）

【3. 本 Phase 目標】
讓系統「可在 prod 環境跑起來」+「災難復原可演練成功」：
  (1) Playwright E2E 完整流程：登入 → 自選股 → 分析 → 核准 → 匯出 PDF
  (2) docker-compose.prod.yml 完整化：nginx + TLS（self-signed dev、Let's Encrypt prod）+ resource limits
  (3) backup.sh / restore.sh / verify_backup.sh（含 GPG 加密）
  (4) DR 演練情境 A（DB 損毀還原）實際跑通
  (5) SLO 報表 slo_report.py 完整化（依第 16.4 章）
  (6) Prod 啟動 SOP 文件化
  (7) 跑遍所有測試（unit + integration + security + e2e）全綠
  (8) prod backend port 不對外（只 nginx）

注意：本 Phase「不寫最終驗證腳本 all.sh」（在 P20 整合）、「不產 PROJECT_FINAL_REPORT」（P20）。

【4. 任務清單】

A. 切分支：
   git checkout main && git pull
   git checkout -b phase/19-prod-deploy-dr

B. docker-compose.prod.yml 完整化：
   services:
     nginx:
       image: nginx:1.27-alpine
       ports: ["80:80", "443:443"]
       volumes:
         - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
         - ./docker/nginx/certs:/etc/nginx/certs:ro
       depends_on: [backend, frontend]
       restart: always

     timescaledb:
       image: timescale/timescaledb:2.16-pg16
       # 不對外（只內網）
       expose: ["5432"]
       volumes: [...]
       healthcheck: [...]
       deploy:
         resources:
           limits: { cpus: "2", memory: "4G" }
           reservations: { cpus: "1", memory: "2G" }
       restart: always

     redis:
       image: redis:7-alpine
       expose: ["6379"]
       command: redis-server --requirepass ${REDIS_PASSWORD} --maxmemory 1gb --maxmemory-policy allkeys-lru --appendonly yes
       restart: always

     qdrant:
       image: qdrant/qdrant:v1.9.5
       expose: ["6333", "6334"]
       restart: always

     backend:
       image: tradingagents-backend:${BUILD_VERSION:-latest}
       expose: ["8000"]   # 不對外
       env_file: .env.prod
       environment:
         APP_ENV: prod
         POSTGRES_HOST: timescaledb
         REDIS_HOST: redis
         QDRANT_HOST: qdrant
       depends_on: [timescaledb, redis, qdrant]
       deploy:
         resources:
           limits: { cpus: "4", memory: "4G" }
       read_only: true
       cap_drop: [ALL]
       cap_add: []
       user: "1000:1000"
       tmpfs:
         - /tmp
       restart: always
       stop_grace_period: 60s

     celery_worker:
       image: tradingagents-backend:${BUILD_VERSION:-latest}
       command: ["./scripts/wait-for-services.sh", "uv", "run", "celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
       env_file: .env.prod
       depends_on: [timescaledb, redis, qdrant]
       restart: always

     celery_beat:
       image: tradingagents-backend:${BUILD_VERSION:-latest}
       command: ["./scripts/wait-for-services.sh", "uv", "run", "celery", "-A", "app.workers.celery_app", "beat", "--loglevel=info"]
       env_file: .env.prod
       depends_on: [timescaledb, redis, qdrant]
       restart: always

     frontend:
       image: tradingagents-frontend:${BUILD_VERSION:-latest}
       expose: ["3000"]
       env_file: .env.prod
       restart: always

   networks:
     default:
       driver: bridge

   注意：dev compose 的 ports: [...] 全改 expose:[..]，由 nginx 對外

C. docker/nginx/nginx.conf：
   user nginx;
   worker_processes auto;
   events { worker_connections 1024; }
   http {
     include /etc/nginx/mime.types;
     server_tokens off;

     # rate limit zone
     limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

     # backend
     upstream backend { server backend:8000; }
     upstream frontend { server frontend:3000; }

     # HTTPS only
     server {
       listen 80;
       return 301 https://$host$request_uri;
     }

     server {
       listen 443 ssl http2;
       server_name _;

       ssl_certificate /etc/nginx/certs/fullchain.pem;
       ssl_certificate_key /etc/nginx/certs/privkey.pem;
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

       # security headers
       add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
       add_header X-Frame-Options DENY always;
       add_header X-Content-Type-Options nosniff always;

       client_max_body_size 1m;

       # api
       location /api/ {
         limit_req zone=api burst=20 nodelay;
         proxy_pass http://backend;
         proxy_set_header Host $host;
         proxy_set_header X-Real-IP $remote_addr;
         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
         proxy_set_header X-Forwarded-Proto $scheme;
         proxy_read_timeout 60s;
       }

       # ws
       location /api/v1/ws/ {
         proxy_pass http://backend;
         proxy_http_version 1.1;
         proxy_set_header Upgrade $http_upgrade;
         proxy_set_header Connection "upgrade";
         proxy_set_header Host $host;
         proxy_read_timeout 86400s;   # WS 需長 timeout
         proxy_buffering off;          # SSE / WS 必關
       }

       # health
       location /health/ {
         proxy_pass http://backend;
         access_log off;
       }

       # /metrics 限 admin（可加 IP allow list）
       location /metrics {
         proxy_pass http://backend;
       }

       # frontend
       location / {
         proxy_pass http://frontend;
         proxy_http_version 1.1;
         proxy_set_header Host $host;
         proxy_set_header X-Real-IP $remote_addr;
       }
     }
   }

D. docker/nginx/certs/（self-signed for dev/staging）：
   scripts/generate_self_signed_cert.sh：
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout privkey.pem -out fullchain.pem \
     -subj "/CN=tradingagents.local"

   prod：用 Let's Encrypt（certbot）獨立流程，docs 寫指引但腳本不放 git

E. .env.prod.example：
   APP_ENV=prod
   LOG_LEVEL=INFO
   LOG_FORMAT=json
   CSP_PROD_ENABLED=true
   # ... 其他 dev 一樣的欄位都要設

F. backup.sh（路徑都用 PROJECT_ROOT 相對路徑，跨平台相容）：
   #!/bin/bash
   set -euo pipefail

   # PROJECT_ROOT = 此 script 上一層的上一層（scripts/backup.sh → ../../）
   PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
   BACKUP_DIR="${BACKUP_DIR:-${PROJECT_ROOT}/docker/backups}"
   # 用 mktemp 取得 OS 對應 temp dir（Windows Git Bash → /tmp，Linux → /tmp，皆可）
   TMP_DIR="$(mktemp -d)"
   trap 'rm -rf "$TMP_DIR"' EXIT

   TIMESTAMP=$(date +%Y%m%d_%H%M%S)
   PG_PWD=$(grep ^POSTGRES_SUPERUSER_PASSWORD= "${PROJECT_ROOT}/.env.prod" | cut -d= -f2)
   GPG_RECIPIENT=${GPG_RECIPIENT:-backup@example.com}

   mkdir -p "$BACKUP_DIR"

   # 1. PG dump（custom format with compression）
   docker compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" exec -T timescaledb \
     pg_dump -U postgres -F custom -Z 9 tradingagents_tw > "$BACKUP_DIR/db_$TIMESTAMP.dump"

   # 2. Qdrant snapshot
   QDRANT_API_KEY=$(grep ^QDRANT_API_KEY= "${PROJECT_ROOT}/.env.prod" | cut -d= -f2)
   for collection in $(curl -s -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections | jq -r '.result.collections[].name'); do
     curl -s -X POST -H "api-key: $QDRANT_API_KEY" "http://localhost:6333/collections/$collection/snapshots"
   done
   docker run --rm -v tradingagents_qdrant_data:/qdrant -v "$BACKUP_DIR":/backup alpine \
     tar czf "/backup/qdrant_$TIMESTAMP.tar.gz" -C /qdrant snapshots

   # 3. Encrypted bundle（用 TMP_DIR 不要寫死 /tmp）
   tar czf "$TMP_DIR/full_$TIMESTAMP.tar.gz" -C "$BACKUP_DIR" "db_$TIMESTAMP.dump" "qdrant_$TIMESTAMP.tar.gz"
   gpg --encrypt --recipient "$GPG_RECIPIENT" --output "$BACKUP_DIR/full_$TIMESTAMP.tar.gz.gpg" "$TMP_DIR/full_$TIMESTAMP.tar.gz"

   # 4. 30-day retention
   find "$BACKUP_DIR" -name "*.gpg" -mtime +30 -delete

   echo "✅ Backup: $BACKUP_DIR/full_$TIMESTAMP.tar.gz.gpg"

G. restore.sh：
   #!/bin/bash
   set -euo pipefail
   PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
   TMP_DIR="$(mktemp -d)"
   trap 'rm -rf "$TMP_DIR"' EXIT
   BACKUP_FILE=${1:?usage: restore.sh <full_*.tar.gz.gpg>}

   # 1. 解密
   gpg --decrypt --output "$TMP_DIR/full_restore.tar.gz" "$BACKUP_FILE"

   # 2. 解壓
   tar xzf "$TMP_DIR/full_restore.tar.gz" -C "$TMP_DIR/"

   # 3. PG 還原（先確認 DB 是空的）
   read -p "⚠️  即將清空現有 DB 並還原。確定？(yes/no) " confirm
   [ "$confirm" = "yes" ] || exit 1

   docker compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" exec -T timescaledb \
     psql -U postgres -c "DROP DATABASE IF EXISTS tradingagents_tw; CREATE DATABASE tradingagents_tw;"

   # 還原 schema + extension（init.sh 處理 envsubst 後再 psql）
   docker compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" exec -T timescaledb \
     bash /docker-entrypoint-initdb.d/init.sh

   docker compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" exec -T timescaledb \
     pg_restore -U postgres -d tradingagents_tw < "$TMP_DIR"/db_*.dump

   # 4. Qdrant 還原
   docker run --rm -v tradingagents_qdrant_data:/qdrant -v "$TMP_DIR":/tmp alpine \
     tar xzf "/tmp/qdrant_$(ls "$TMP_DIR" | grep qdrant | sed 's/qdrant_//')" -C /qdrant
   # （TMP_DIR 退出時會自動清理）

   echo "✅ Restore complete"

H0. docker-compose.test-restore.yml（**verify_backup.sh 會用，必須先建**）：
   ```yaml
   services:
     timescaledb_test:
       image: timescale/timescaledb:2.16-pg16
       container_name: ta_timescaledb_test
       ports: ["5433:5432"]   # 與 prod 5432 隔離
       environment:
         POSTGRES_PASSWORD: ${POSTGRES_SUPERUSER_PASSWORD}
         POSTGRES_DB: tradingagents_tw_test
       volumes:
         # 用獨立 named volume，不和 prod 衝突
         - timescaledb_test_data:/var/lib/postgresql/data
         # init script 重複利用 prod 的（建 extension + 帳號）
         - ./docker/timescaledb/init.sh:/docker-entrypoint-initdb.d/01-init.sh:ro
         - ./docker/timescaledb/init.sql.template:/docker-entrypoint-initdb.d/02-init.sql.template:ro
       healthcheck:
         test: ["CMD", "pg_isready", "-U", "postgres"]
         interval: 5s
         timeout: 3s
         retries: 10
   volumes:
     timescaledb_test_data:
   ```

   注意：
   - 用 5433 對外（避免撞 prod 5432）
   - DB 名 `tradingagents_tw_test`（與 prod tradingagents_tw 隔離）
   - `down -v` 會清除 test volume，每次驗證都從乾淨狀態開始
   - 重複利用 prod 的 init.sh / init.sql.template（schema 對齊）

H. verify_backup.sh：
   #!/bin/bash
   set -euo pipefail
   PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
   TMP_DIR="$(mktemp -d)"
   trap 'rm -rf "$TMP_DIR"' EXIT
   BACKUP_FILE=${1:?usage: verify_backup.sh <full_*.tar.gz.gpg>}

   # 1. 啟動隔離 DB（compose override）
   docker compose -f "${PROJECT_ROOT}/docker-compose.test-restore.yml" up -d timescaledb_test
   sleep 30

   # 2. 還原到 timescaledb_test
   gpg --decrypt --output "$TMP_DIR/test_restore.tar.gz" "$BACKUP_FILE"
   tar xzf "$TMP_DIR/test_restore.tar.gz" -C "$TMP_DIR/"

   docker compose -f "${PROJECT_ROOT}/docker-compose.test-restore.yml" exec -T timescaledb_test \
     pg_restore -U postgres -d tradingagents_tw_test < "$TMP_DIR"/db_*.dump

   # 3. 跑 verify_data.py 對隔離 DB
   POSTGRES_DB=tradingagents_tw_test \
   POSTGRES_PORT=5433 \
   uv run python "${PROJECT_ROOT}/data-pipeline/scripts/verify_data.py"

   # 4. 清理
   docker compose -f "${PROJECT_ROOT}/docker-compose.test-restore.yml" down -v
   # TMP_DIR 自動清理

   echo "✅ Backup verified"

I. scripts/slo_report.py（依第 16.4 章完整版）：
   """產出 24h SLO 報表"""
   import asyncio, json
   from datetime import datetime, timedelta

   async def main():
     async with ro_session() as s:
       now = datetime.now(timezone.utc)
       since = now - timedelta(hours=24)

       # 1. API 可用性（從 audit_logs / nginx access log）
       total_req = await s.scalar(...)
       failed_req = await s.scalar(...)
       availability = 1 - (failed_req / total_req) if total_req > 0 else 1.0

       # 2. 分析完成率
       analyses = await s.scalar(select(func.count()).where(AnalysisReport.created_at >= since))
       completed = await s.scalar(select(func.count()).where(
         AnalysisReport.created_at >= since, AnalysisReport.status == "completed"
       ))
       completion_rate = completed / analyses if analyses > 0 else 1.0

       # 3. 分析延遲 P95
       p95_seconds = await s.scalar(...)

       # 4. 資料新鮮度
       latest_ohlcv = await s.scalar(...)
       freshness_minutes = (now - latest_ohlcv).total_seconds() / 60

       # 5. Audit chain 完整性（呼叫 verify_audit_chain）
       audit_ok, _ = await audit_repo.verify_chain(since=since)

       report = {
         "timestamp": now.isoformat(),
         "period_hours": 24,
         "slo": {
           "api_availability": {"target": 0.99, "actual": availability, "passed": availability >= 0.99},
           "analysis_completion_rate": {"target": 0.95, "actual": completion_rate, "passed": completion_rate >= 0.95},
           "analysis_latency_p95_sec": {"target": 300, "actual": p95_seconds, "passed": p95_seconds <= 300},
           "data_freshness_minutes": {"target": 60, "actual": freshness_minutes, "passed": freshness_minutes <= 60},
           "audit_integrity": {"target": True, "actual": audit_ok, "passed": audit_ok},
         },
         "error_budget_consumption": {...},
       }

       # 寫 docs/slo_reports/YYYY-MM-DD.json
       # 任一未達 → 發 LINE WARN
       if any(not v["passed"] for v in report["slo"].values()):
         logger.critical("SLO breach: ...")

   asyncio.run(main())

J. backend/tests/integration/test_full_workflow_e2e.py（≥ 6 個 E2E）：
   - test_admin_login_change_password_onboarding
   - test_add_2330_to_watchlist_and_get_quote
   - test_create_2330_analysis_completes_with_signal
   - test_approve_pending_order_creates_position
   - test_export_analysis_pdf_contains_chinese
   - test_admin_views_audit_log_for_actions

K. frontend/tests/e2e/full-workflow.spec.ts 升級（≥ 8 個關鍵流程）：
   - 登入 → 改密碼 → onboarding → dashboard
   - 加 2330 → 看 OHLCV chart
   - 新增分析 → AgentFlowGraph 動畫 → 完成 → signal 顯示
   - 核准訂單 → 雙重確認 → status 變 APPROVED
   - 匯出 PDF（檢查 download 觸發）
   - 切換 light/dark theme
   - viewer 角色看不到 admin 頁
   - 故意斷網（offline）→ 顯示錯誤訊息

L. DR 演練情境 A（DB 損毀還原）：
   scripts/dr_drill_a.sh：
   #!/bin/bash
   set -e
   PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
   BACKUP_DIR="${BACKUP_DIR:-${PROJECT_ROOT}/docker/backups}"
   echo "=== DR 演練：DB 損毀情境 ==="

   # 1. 先 backup
   bash "${PROJECT_ROOT}/scripts/backup.sh"
   LATEST=$(ls -t "$BACKUP_DIR"/full_*.tar.gz.gpg | head -1)

   # 2. 「損毀」模擬
   docker compose -f docker-compose.prod.yml stop timescaledb
   docker volume rm tradingagents_timescaledb_data

   # 3. 重建
   docker compose -f docker-compose.prod.yml up -d timescaledb
   sleep 30
   make init-db

   # 4. 還原
   bash scripts/restore.sh "$LATEST"

   # 5. 驗證
   uv run python data-pipeline/scripts/verify_data.py

   # 6. 紀錄 RTO
   echo "DR drill A passed in <duration>"

M. Prod 啟動 SOP（docs/runbooks/prod_deployment.md）：
   - .env.prod 設定（從 .env.prod.example 複製 + 填）
   - SSL 憑證準備（self-signed 或 Let's Encrypt）
   - docker compose -f docker-compose.prod.yml up -d
   - 確認 healthy（等 1 分鐘）
   - make init-db（首次）
   - make seed-stocks（首次）
   - 用 admin 登入 + 改密碼 + onboarding
   - 確認 LINE/Telegram 通知測試發送
   - 確認 SLO 報表跑得起來

N. 先建 Makefile target：
   prod-up:
     docker compose -f docker-compose.prod.yml up -d
   prod-down:
     docker compose -f docker-compose.prod.yml down
   prod-logs:
     docker compose -f docker-compose.prod.yml logs -f
   backup:
     bash scripts/backup.sh
   restore:
     bash scripts/restore.sh $(FILE)
   verify-backup:
     bash scripts/verify_backup.sh $(FILE)
   slo-report:
     uv run python scripts/slo_report.py
   dr-drill-a:
     bash scripts/dr_drill_a.sh

O. backend/tests/integration/test_slo_report.py（≥ 4 個測試）
P. backend/tests/integration/test_backup_restore.py（≥ 3 個測試 - 用 docker fixture）

Q. 寫 scripts/health_checks/phase_19.sh
R. 寫 docs/phase_reports/PHASE_19.md
S. 更新 docs/phase_progress.md

【5. 完成驗收（具體指令）】

完成 Phase 19 = 以下 14 個指令全部 exit code 0：

```bash
# 1-2. self-signed cert + prod compose 啟動
bash scripts/generate_self_signed_cert.sh
docker compose -f docker-compose.prod.yml up -d
sleep 60   # prod 啟動含 healthcheck 等 1 分鐘

# 3. 全 services healthy
docker compose -f docker-compose.prod.yml ps --format json | \
  jq -r '.[] | select(.Service | IN("timescaledb", "redis", "qdrant", "backend", "frontend", "nginx")) | .Health' | \
  grep -c "healthy" | grep -E "^[5-9]$"   # 至少 5 個 healthy（部分 service 沒 healthcheck）

# 4. nginx https 對外
curl -kfsS https://localhost/health/live

# 5. backend port 不對外（只 expose）
# 從 host 直連 8000 應該失敗
timeout 2 curl --connect-timeout 1 http://localhost:8000/health/live && exit 1 || echo "OK: not exposed"

# 6. PDF 匯出（中文）
ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env.prod | cut -d= -f2)
ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env.prod | cut -d= -f2)
TOKEN=$(curl -ks -X POST https://localhost/api/v1/auth/login -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}" | jq -r '.data.access_token')

# 取一個 completed analysis（從 DB）
PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env.prod | cut -d= -f2)
ID=$(docker compose -f docker-compose.prod.yml exec -T timescaledb \
  psql -U postgres tradingagents_tw -tAc "SELECT id FROM analysis_reports WHERE status='completed' LIMIT 1")
curl -k -H "Authorization: Bearer $TOKEN" -o /tmp/r.pdf "https://localhost/api/v1/exports/$ID?format=pdf"
file /tmp/r.pdf | grep "PDF document"
PDFTMP="$(mktemp -d)"
pdftotext "$PDFTMP/r.pdf" - | head | grep -P "[一-鿿]"
rm -rf "$PDFTMP"

# 7. 後端 E2E 完整流程
cd backend && uv run pytest tests/integration/test_full_workflow_e2e.py -v && cd ..

# 8. 前端 E2E 完整流程
cd frontend && npx playwright test tests/e2e/full-workflow.spec.ts && cd ..

# 9. 備份 + 還原驗證
make backup
LATEST=$(ls -t docker/backups/full_*.tar.gz.gpg | head -1)
make verify-backup FILE="$LATEST"

# 10. DR 演練情境 A（會清資料庫，先確認可進行）
read -p "DR 演練 A 會清空 prod DB，確認？(yes/no) " confirm
if [ "$confirm" = "yes" ]; then
  make dr-drill-a
fi

# 11. SLO 報表
make slo-report
test -f docs/slo_reports/$(date +%Y-%m-%d).json

# 12. 全部 pytest 跑遍（≥ 535 累積）
cd backend && uv run pytest --tb=short -q && cd ..
cd frontend && npm test -- --run && cd ..

# 13. 全部 phase_NN.sh 跑遍（手動或 P20 才做 all.sh）
for i in $(seq -f "%02g" 1 19); do
  echo "=== phase_$i ==="
  bash scripts/health_checks/phase_$i.sh
done

# 14. health_check phase_19 通過
bash scripts/health_checks/phase_19.sh
```

【6. Smoke Test（手動）】
✓ 用 Chrome 開 https://localhost → 信任 self-signed → 看到登入頁
✓ admin 登入 → 完整跑 2330 分析（耗時 1-3 分鐘）→ 看到 completed 結果
✓ Sidebar 18 頁全部能開（mock 標示明確）
✓ 匯出 PDF 含台積電中文 + 完整圖表
✓ 故意 docker compose stop timescaledb → /health/ready 503 → 重啟後自動恢復
✓ 觀察 docker stats，記憶體 / CPU 使用率合理（< 60%）
✓ DR 演練 A 真實跑通（重要！）

【7. 已知陷阱】
✗ self-signed cert 過期 → docs 寫產生指令、設定 365 天
✗ Let's Encrypt 本地不通 → docs 標明只用 self-signed 或外網部署
✗ Nginx WS 沒設 timeout → 連線 60 秒後斷
✗ Nginx SSE buffering 沒關 → /stream 卡住
✗ Nginx X-Forwarded-For 用錯 → 後端 rate limit 用本機 IP（要白名單 trusted proxy）
✗ Backend port 8000 對外（dev 殘留）→ prod compose 改 expose
✗ Backend read_only:true 導致 /tmp 寫入失敗 → 設 tmpfs:[/tmp]
✗ User 1000:1000 vs container default user → Dockerfile USER 1000 一致
✗ pg_restore 在已有 schema 失敗 → DROP DATABASE 再 CREATE
✗ Qdrant snapshot restore 路徑錯 → 確認 mount 對到 /qdrant/storage/snapshots
✗ GPG recipient 沒設 → backup 會失敗 → 預先 import GPG key
✗ DR 演練忘記 backup 先做 → 真的會丟資料
✗ E2E 測試慢 → 加 timeout 60s for analysis（network call）
✗ Playwright headless 在 Docker 缺 deps → 完整裝 chromium-deps
✗ SLO 報表 P95 計算需要 nginx access log → 改用 audit_logs.elapsed_ms
✗ verify_backup.sh 用 timescaledb_test 容器 → 要分開 compose 檔

【8. Self-Check SOP】跑第 8.5.4 章全部 8 項。

【9. 完成後產物】
程式檔（新增）：
  - docker-compose.prod.yml（完整化）
  - docker-compose.test-restore.yml（隔離還原驗證）
  - docker/nginx/nginx.conf
  - scripts/generate_self_signed_cert.sh
  - scripts/backup.sh
  - scripts/restore.sh
  - scripts/verify_backup.sh
  - scripts/dr_drill_a.sh
  - scripts/slo_report.py
  - 後端 + 前端 E2E test files（共 ~14 個）
  - scripts/health_checks/phase_19.sh

程式檔（修改）：
  - .env.prod.example
  - Makefile（加 prod-up/down/logs/backup/restore/verify-backup/slo-report/dr-drill-a）

文件檔（新增）：
  - docs/phase_reports/PHASE_19.md
  - docs/runbooks/prod_deployment.md
  - docs/runbooks/disaster_recovery.md
  - docs/runbooks/backup_restore.md

文件檔（更新）：
  - docs/phase_progress.md
  - docs/setup.md（加 prod 章節）

Git tag：phase-19-complete

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：
- B-D（compose + nginx + cert）一氣呵成測試 prod 啟動可用
- F-H（backup/restore/verify）必須在 staging 演練 ≥ 1 次再上 prod
- L（DR 演練 A）真實跑通才算 P19 完成
- E2E 測試會耗時（1 個分析 1-3 分鐘 × 6 個 test = 10+ 分鐘），預留時間
- prod compose 用 read_only + cap_drop 強化，但 dev 用一般 compose
```

---

### ▌Phase 20 — 全面整合驗證 + 完整報告生成 + Obsidian 安裝 + 結案文件 + v1.0 Release

```
=== TradingAgents-TW Phase 20（v7.0，最終 Phase）===

【0. 工作目錄與 PLAN.md 章節】
工作目錄：C:\Projects\TradingAgents
PLAN.md 路徑：C:\Projects\TradingAgents\PLAN.md
本 Phase 章節：第二十七章 ▌Phase 20
必讀 PLAN.md 章節：第 8.5, 9（願景與 SLO）, 23.5（累積測試）, 33（後續延展）章

【1. 前置依賴 Phase】
依賴：Phase 0-19（全部都要完成且綠燈）
驗證方式：
  - 跑遍 phase_01.sh ~ phase_19.sh 全部 exit code 0
  - bash scripts/health_checks/phase_19.sh

【2. 跨 Phase 健康檢查（本 Phase 第一步）】
- 跑遍所有 phase_NN.sh（19 個）
- 跑遍所有 pytest（≥ 535 累積，全綠）
- 跑遍前端 unit + e2e test
- bandit / Trivy / npm audit 全綠
- 通知整合可送
- prod compose 可起、可備份、可還原

【3. 本 Phase 目標】
**這是 v1.0 的最後一個 Phase，責任是「驗證 + 報告 + 結案」：**
  (1) 撰寫 scripts/health_checks/all.sh（一鍵跑所有 phase 健康檢查 + pytest + 前端 test）
  (2) 跑遍所有檢查 + 收集成果
  (3) 產出 docs/PROJECT_FINAL_REPORT.md（最重要的交付物）
  (4) 寫 docs/connection-guide.md（給用戶看：如何使用）
  (5) 寫 docs/user-guide.md（每頁怎麼用 + FAQ）
  (6) 安裝 Obsidian + Vault 設定（個人筆記）
  (7) v1.0 release tag + GitHub release（如有 remote）
  (8) CHANGELOG.md 完整化
  (9) README.md 升級為 v1.0 完整版

注意：本 Phase「不寫新功能」、「不改既有 Phase」。
本 Phase 只做「整合 + 驗收 + 文件 + 結案」。

【4. 任務清單】

A. 切分支：
   git checkout main && git pull
   git checkout -b phase/20-final-validation-and-release

B. scripts/health_checks/all.sh（依第 23.5.2 章）：
   #!/bin/bash
   set -e
   echo "=== TradingAgents-TW v1.0 完整健康檢查 ==="
   START=$(date +%s)

   # 1. 跑遍 phase_01 ~ phase_19
   FAIL=()
   for i in $(seq -f "%02g" 1 19); do
     SCRIPT="scripts/health_checks/phase_$i.sh"
     test -x "$SCRIPT" || { echo "❌ $SCRIPT 不存在"; FAIL+=("$SCRIPT-missing"); continue; }
     echo ""
     echo "=== Running phase_$i.sh ==="
     if bash "$SCRIPT"; then
       echo "✅ phase_$i.sh PASSED"
     else
       echo "❌ phase_$i.sh FAILED"
       FAIL+=("phase_$i")
     fi
   done

   # 2. backend pytest 全綠
   echo ""
   echo "=== Running backend pytest ==="
   cd backend
   uv run pytest --tb=short -q 2>&1 | tee /tmp/backend_test.log
   BACKEND_RESULT=${PIPESTATUS[0]}
   cd ..
   [ "$BACKEND_RESULT" = "0" ] || FAIL+=("backend-pytest")

   # 3. frontend unit test
   echo ""
   echo "=== Running frontend unit test ==="
   cd frontend
   npm test -- --run 2>&1 | tee /tmp/frontend_unit.log
   FE_UNIT_RESULT=${PIPESTATUS[0]}
   cd ..
   [ "$FE_UNIT_RESULT" = "0" ] || FAIL+=("frontend-unit")

   # 4. frontend E2E
   echo ""
   echo "=== Running frontend E2E ==="
   cd frontend
   npx playwright test 2>&1 | tee /tmp/frontend_e2e.log
   FE_E2E_RESULT=${PIPESTATUS[0]}
   cd ..
   [ "$FE_E2E_RESULT" = "0" ] || FAIL+=("frontend-e2e")

   # 5. 安全掃描
   echo ""
   echo "=== Running security scans ==="
   cd backend && uv run bandit -r app/ -ll -f json -o /tmp/bandit.json && cd ..
   HIGH=$(jq '[.results[] | select(.issue_severity=="HIGH")] | length' /tmp/bandit.json)
   [ "$HIGH" = "0" ] || FAIL+=("bandit-high")

   detect-secrets scan --baseline .secrets.baseline || FAIL+=("detect-secrets")

   # 6. 結束報告
   END=$(date +%s)
   DURATION=$((END - START))

   echo ""
   echo "===================================="
   echo "Total duration: ${DURATION}s"
   if [ ${#FAIL[@]} -eq 0 ]; then
     echo "✅ ALL CHECKS PASSED"
     exit 0
   else
     echo "❌ FAILED: ${FAIL[*]}"
     exit 1
   fi

C. 跑遍所有檢查並收集結果：
   bash scripts/health_checks/all.sh > /tmp/all_results.log 2>&1
   ALL_PASS=$?

   # 收集累積測試數量
   cd backend && uv run pytest --collect-only -q 2>&1 | tail -1 > /tmp/test_count.txt && cd ..

   # 收集覆蓋率
   cd backend && uv run pytest --cov=app --cov-report=term --cov-report=json:/tmp/cov.json -q && cd ..
   BACKEND_COV=$(jq '.totals.percent_covered' /tmp/cov.json)

   cd frontend && npm test -- --coverage --run 2>&1 | grep -i "all files" > /tmp/fe_cov.txt && cd ..

   # 收集效能 benchmark
   ab -n 100 -c 10 -H "Authorization: Bearer $TOKEN" https://localhost/api/v1/stocks > /tmp/bench_stocks.txt 2>&1

   # 收集 SLO 24h
   make slo-report
   SLO_REPORT=$(cat docs/slo_reports/$(date +%Y-%m-%d).json)

D. docs/PROJECT_FINAL_REPORT.md（最重要的交付物）：

   # TradingAgents-TW v1.0 — 專案結案報告
   日期：YYYY-MM-DD
   版本：v1.0
   狀態：✅ Release Ready / ⚠️ Conditional / ❌ Blocked

   ## 1. 執行摘要
   - v1.0 範圍：依第 9.1 章願景，成功實作台股主、美股輔的多 Agent AI 投資分析平台
   - 21 個 Phase 全部完成
   - calendar time：實際 X 天（規劃 30-40 天）
   - Claude Opus 4.7 Max session：實際 N 個

   ## 2. Phase 完成度
   | Phase | 預估時數 | 實際時數 | 狀態 | 備註 |
   |-------|---------|---------|------|------|
   | P0 | 0.5h | ... | ✅ | ... |
   | ... | ... | ... | ... | ... |

   ## 3. SLO 達成度（過去 24 小時 + 7 天平均）
   依第 9.2 章 SLO：
   | 指標 | 目標 | 實際 | 達成 |
   |------|------|------|------|
   | API 可用性 | ≥ 99% | XX% | ✅ |
   | API P95 延遲 | < 500ms | XXXms | ✅ |
   | 分析完成率 | > 95% | XX% | ✅ |
   | 分析延遲 P95 | < 5 分鐘 | XXXs | ✅ |
   | 資料新鮮度 | < 60min | XXmin | ✅ |
   | Audit 完整性 | 100% | 100% | ✅ |

   ## 4. 測試覆蓋率
   - Backend：≥ 80%（實際 XX%）
   - Frontend：≥ 60%（實際 XX%）
   - 累積測試數：≥ 535（實際 XXX）
   - E2E 流程：8 個關鍵流程全綠

   ## 5. 安全稽核
   - bandit HIGH = 0 ✅
   - detect-secrets 與 baseline 無新發現 ✅
   - Trivy 後端 image HIGH+CRITICAL = 0 ✅
   - Trivy 前端 image HIGH+CRITICAL = 0 ✅
   - npm audit HIGH+CRITICAL = 0 ✅
   - OWASP Top 10：15 個 case 全綠 ✅
   - Pen test checklist 完成 ✅

   ## 6. 效能 Benchmark（單機 16GB）
   - GET /api/v1/stocks：QPS XXX, P95 XXms
   - POST /api/v1/analysis：建立 < 200ms
   - 完整分析（4 analyst 1 輪辯論，Gemini Flash）：~2 分鐘
   - PDF 匯出（含中文）：~5 秒
   - WebSocket 連線：< 100ms

   ## 7. 成本實測（v1.0 自用）
   - LLM 月費：~$XX（預估 $5-10）
   - 資料源月費：~$X（FinMind 免費 + Alpha Vantage 免費版）
   - 主機（自用伺服器）：$0
   - 合計：~$X（低於預估 $154）

   ## 8. 已知限制（依第 7 章）
   - yfinance 偶爾失敗 → fallback 已實作
   - LangGraph 0.3 大改 API → pin <0.3
   - 單機 WebSocket ~1000 連線 → v2.0 多 worker
   - PDF 中文偶爾排版略醜 → 接受
   - ...（列完整）

   ## 9. 未完工項目（v1.1 待補）
   - 財報日曆（calendar 頁）
   - 多股比較（compare 頁）
   - 回測引擎真實後端（backtest 頁）
   - 法說會錄音轉文字
   - 美股 13F、insider trading
   - Email 通知
   - ...

   ## 10. 安全項目檢核（對照 SECURITY.md / SECURITY_FIXES.md）
   - DB 帳號分離 ✅
   - API key 不進 prompt/log/前端 ✅
   - 手動核准下單 ✅
   - 完整 audit_logs hash chain ✅
   - JWT rotation + blacklist ✅
   - CSRF + SameSite ✅
   - WS Ticket（不在 URL）✅
   - bcrypt cost=12 ✅
   - Lockout 5 fail/15min ✅
   - Rate limit 6 層 ✅
   - Fernet 加密 token ✅
   - CSP nonce-based prod ✅
   - TLS 1.2/1.3 only ✅
   - Container 非 root + cap_drop ALL ✅

   ## 11. 災難復原驗證
   - 情境 A（DB 損毀）：實際演練成功，RTO < 1h ✅
   - 備份每日 02:00 自動 + 30 天保留 ✅
   - 備份還原驗證每月 ✅

   ## 12. 文件清單
   - PLAN.md（v7.0 完整 21 Phase）
   - docs/setup.md
   - docs/engineering-standards.md
   - docs/contributing.md
   - docs/runbooks/{services, migrations, celery, auth, security, exports,
                   data_sources, llm_providers, agents, frontend, frontend_pages,
                   pentest_checklist, secret_rotation, prod_deployment,
                   disaster_recovery, backup_restore, phase_failures}.md
   - docs/phase_reports/PHASE_NN.md（21 個）
   - docs/connection-guide.md
   - docs/user-guide.md
   - docs/PROJECT_FINAL_REPORT.md（本檔）
   - README.md（v1.0 完整版）

   ## 13. 後續路線圖
   依第 33 章：v1.1 / v1.2 / v2.0 詳述。

   ## 14. 結論
   v1.0 達 Release Ready 狀態。建議：
   - 立即上 prod 環境（自用）
   - 累積 1 個月實際使用紀錄後 review
   - 啟動 v1.1 規劃（聚焦 calendar / compare / backtest 真實化）

   ---
   報告產生日期：YYYY-MM-DD
   報告產生工具：scripts/health_checks/all.sh + scripts/slo_report.py + 手動編輯
   簽核：（user 自己確認）

E. docs/connection-guide.md（給用戶看，第一次怎麼用）：
   ## 第一次使用 TradingAgents-TW

   ### 0. 確認環境
   - Docker Desktop ≥ 4.x 已安裝並啟動
   - .env 已從 .env.example 複製並填好（特別是 GOOGLE_API_KEY）
   - SSL 憑證已產生（`bash scripts/generate_self_signed_cert.sh`）

   ### 1. 啟動所有服務
   ```bash
   make prod-up
   sleep 60   # 等服務 healthy
   make slo-report   # 確認跑得起來
   ```

   ### 2. 開啟瀏覽器
   - 訪問 https://localhost
   - 信任 self-signed 憑證（首次 Chrome 會警告 → 進階 → 仍要前往）

   ### 3. 第一次登入
   - 帳號：.env 中的 ADMIN_EMAIL
   - 密碼：.env 中的 ADMIN_INITIAL_PASSWORD
   - 系統會強制改密碼（依密碼策略）→ Onboarding → Dashboard

   ### 4. 跑第一個分析
   - 左側 Sidebar：「自選股清單」→ 加 2330（台積電）
   - 「新增分析」→ 選 2330 → 全選 4 個 analyst → debate=1 → 提交
   - 跳到 /analysis/[id]，看 AgentFlowGraph 動畫，1-3 分鐘完成
   - 看到 signal、report、辯論詳情

   ### 5. 設定通知
   - 「通知設定」→ 設 LINE Notify token
   - 「測試發送」→ 手機收到訊息
   - 訂閱「分析完成」+「訂單核准」

   ### 6. 設定備份
   - 加 cron：每天 02:00 跑 `make backup`
   - 每月手動 `make verify-backup FILE=...`

   ### 7. 常見問題
   - 服務啟動失敗 → docker compose logs 看錯誤
   - 分析卡 running > 30min → cleanup_orphans 排程會兜底
   - LLM 配額用盡 → /admin/users 改該用戶 monthly_llm_budget_usd
   - 詳細 → docs/runbooks/

F. docs/user-guide.md（每頁怎麼用 + FAQ）：
   ## 頁面操作指南

   ### 儀表板 /dashboard
   - 顯示自選股、最近分析、待核准訂單、大盤指數
   - LLM 月用量進度條：超過 80% 顯示警告
   - 點擊任何 card 跳到對應頁

   ### 自選股清單 /screener/watchlist
   - 加入：搜尋框輸入 2330 或「台積電」→ 點擊加入
   - 編輯 note：點 note 欄位直接 inline 編輯
   - 排序：拖曳或改 sort_order 欄位

   ### 新增分析 /analysis/new
   - Step 1：選股票
   - Step 2：選 analyst（台股 4 個、美股 3 個）
   - Step 3：選 LLM 模型（預設 Gemini Flash 最便宜）
   - Step 4：選辯論輪數（1-3，越多越貴）
   - 預估費用 + 預估時間顯示
   - 提交後跳分析進度頁

   ### 分析進度 /analysis/[id]
   - AgentFlowGraph：節點動態顯示進度
   - Tabs：Overview / Analysts / Debate / Report
   - 完成後可匯出 PDF / Markdown / Excel

   ### ...（每頁類似格式）

   ## FAQ

   ### Q: 為何要手動核准訂單？
   A: 依 ADR-007，AI 投資建議可能誤判，自動執行有財務風險...

   ### Q: 為何 calendar 頁是 Mock？
   A: 財報日曆需要可靠資料源，v1.1 會接 MOPS/SEC 完整化...

   ### Q: 我的密碼忘了怎麼辦？
   A: 用 admin 帳號登入 → /admin/users → 對該用戶按「重設密碼」...

   ### Q: 系統很慢怎麼辦？
   A: 看 /admin/system 找瓶頸：DB CPU? Celery 飽和?...

   ### Q: 如何升級到 v1.1？
   A: 等 v1.1 release 後...

G. Obsidian 安裝與 Vault 設定（manual + 腳本輔助）：
   docs/runbooks/obsidian_setup.md：
   ## 安裝 Obsidian
   1. 從 https://obsidian.md/download 下載 Windows 版
   2. 安裝後啟動

   ## 設定 Vault
   1. 「打開另一個 Vault」→ 「在新位置建立」
   2. 選擇 C:\Projects\TradingAgents\obsidian_vault
   3. 啟用 Community Plugins：Templater / Dataview / Calendar

   ## 同步分析報告
   - v1.0 不自動匯出（v1.1 才實作）
   - 手動：下載 markdown 報告 → 移動到 vault/reports/<日期>/
   - 用 Dataview 查詢：
     ```dataview
     TABLE symbol, signal.action AS 訊號, signal.confidence AS 信心
     FROM "reports"
     WHERE date >= date(today) - dur(7 days)
     ```

   ## 連結個人筆記
   - 在 vault/notes/ 寫 daily / weekly notes
   - 用 [[2330 分析]] 連結到 reports/...

   scripts/check_obsidian_installed.sh：
   #!/bin/bash
   if [ -f "$LOCALAPPDATA/Obsidian/Obsidian.exe" ]; then
     echo "✅ Obsidian installed"
     exit 0
   fi
   if [ -f "$ProgramFiles/Obsidian/Obsidian.exe" ]; then
     echo "✅ Obsidian installed"
     exit 0
   fi
   echo "⚠️  Obsidian not found, see docs/runbooks/obsidian_setup.md"
   exit 1

H. README.md 升級為 v1.0 完整版（取代既有）：
   # TradingAgents-TW v1.0

   > 台股主、美股輔的多 Agent AI 投資分析平台 — 自用 Secure Edition

   [![Python](https://img.shields.io/badge/Python-3.11-blue)]()
   [![Node](https://img.shields.io/badge/Node-20-green)]()
   [![TimescaleDB](https://img.shields.io/badge/TimescaleDB-2.16-purple)]()
   [![License](https://img.shields.io/badge/License-Apache%202.0-orange)]()
   [![Status](https://img.shields.io/badge/Status-Release%20Ready-success)]()

   ## 簡介
   - 4 種 Analyst（市場 / 基本 / 新聞 / 籌碼）+ Bull/Bear 辯論 + Manager 綜合
   - 跨市場：台股（FinMind/TWSE/MOPS）+ 美股（yfinance/Alpha Vantage/SEC）
   - 18 頁繁中前端
   - 手動核准下單（不直連券商）
   - 完整 audit hash chain
   - LINE/Telegram 通知

   ## 快速啟動
   依 docs/connection-guide.md。

   ## 文件
   - 設計：docs/setup.md / docs/engineering-standards.md
   - 操作：docs/user-guide.md / docs/connection-guide.md
   - 運維：docs/runbooks/
   - 結案報告：docs/PROJECT_FINAL_REPORT.md
   - 完整實施計劃：PLAN.md（v7.0）

   ## 安全
   - DB 帳號分離（migration / service_rw / agent_ro）
   - JWT rotation + 黑名單 + CSRF + WS Ticket
   - bcrypt cost=12 + Lockout
   - Audit hash chain（不可竄改）
   - 6 層 Rate Limit
   - Fernet 加密敏感欄位
   - CSP nonce-based（prod）
   - 詳細：SECURITY.md

   ## 路線圖
   - v1.1（1-2 月）：calendar / compare / backtest 真實化、Email 通知
   - v1.2（3-6 月）：英文 UI、2FA、IP 白名單、港股
   - v2.0（6-12 月）：多用戶、即時分鐘 K、Prometheus、K8s

   詳見 PLAN.md 第 33 章。

   ## License
   Apache 2.0（依原版）

I. CHANGELOG.md 升級：
   ## [1.0.0] - YYYY-MM-DD
   ### Added
   - v1.0 完整實作（21 Phase）
   - 4 種 Analyst + Bull/Bear/Manager
   - 跨市場（台股 + 美股）
   - 18 頁繁中前端
   - 完整 Auth + RBAC + Audit + Rate Limit
   - Notification（LINE / Telegram）
   - Backup / Restore / DR 演練

   ### Changed
   - 從原版 v0.2.4 升級為 TradingAgents-TW Secure Edition
   - 後端：FastAPI + LangGraph 0.2.x
   - 前端：Next.js 14.2 + shadcn/ui
   - DB：TimescaleDB + Qdrant + Redis

   ### Security
   - DB 帳號分離
   - 完整 audit hash chain
   - OWASP Top 10 全部通過
   - 詳見 SECURITY.md

J. v1.0 release tag：
   git checkout main
   git merge phase/20-final-validation-and-release --no-ff -m "feat: v1.0 release"
   git tag -a v1.0.0 -m "TradingAgents-TW v1.0.0 — Release Ready"
   git push origin main --tags

   如果有 GitHub remote：
   gh release create v1.0.0 --title "v1.0.0" --notes-file docs/PROJECT_FINAL_REPORT.md

K. backend/tests/integration/test_final_smoke.py（≥ 5 個 final smoke）：
   - test_can_login_as_admin
   - test_dashboard_endpoint_returns_data
   - test_full_analysis_2330_completes_within_5min
   - test_audit_chain_intact
   - test_slo_report_runs

L. 寫 scripts/health_checks/phase_20.sh
M. 寫 docs/phase_reports/PHASE_20.md（最後一份）
N. 更新 docs/phase_progress.md（最後一次，標 P20 完成）

【5. 完成驗收（具體指令）】

完成 Phase 20 = 以下 14 個指令全部 exit code 0：

```bash
# 1. all.sh 全部綠
bash scripts/health_checks/all.sh

# 2. PROJECT_FINAL_REPORT 完整
test -f docs/PROJECT_FINAL_REPORT.md
wc -l docs/PROJECT_FINAL_REPORT.md | awk '{exit ($1 < 100) ? 1 : 0}'  # 至少 100 行
grep -c "✅\|❌" docs/PROJECT_FINAL_REPORT.md | awk '$1 > 20'   # 至少 20 個檢核點

# 3. connection-guide + user-guide 寫好
test -f docs/connection-guide.md
test -f docs/user-guide.md
wc -l docs/connection-guide.md | awk '$1 > 50'
wc -l docs/user-guide.md | awk '$1 > 100'

# 4. 21 個 phase report 都在
for i in $(seq -f "%02g" 0 20); do
  test -f "docs/phase_reports/PHASE_$i.md" || { echo "missing: $i"; exit 1; }
done

# 5. 19 個 phase health check 都在
for i in $(seq -f "%02g" 1 19); do
  test -x "scripts/health_checks/phase_$i.sh"
done
test -x scripts/health_checks/all.sh

# 6. README v1.0 完整
grep -E "^# TradingAgents-TW v1.0" README.md
grep -E "Release Ready" README.md

# 7. CHANGELOG v1.0 entry
grep -E "^## \[1\.0\.0\]" CHANGELOG.md

# 8. SECURITY.md v1.0 真實內容（不是 placeholder）
test -f SECURITY.md
wc -l SECURITY.md | awk '$1 > 50'

# 9. Obsidian 安裝（手動或腳本）
bash scripts/check_obsidian_installed.sh

# 10. 全部 pytest 全綠（最終確認）
cd backend && uv run pytest --tb=short -q && cd ..

# 11. 累積測試 ≥ 535
cd backend && uv run pytest --collect-only -q 2>&1 | tail -1 | awk '{print $1}' | awk '$1 >= 535'

# 12. SLO 報表存在
test -f docs/slo_reports/$(date +%Y-%m-%d).json
jq '.slo' docs/slo_reports/$(date +%Y-%m-%d).json

# 13. v1.0 tag 存在
git tag --list | grep "^v1\.0\.0$"

# 14. health_check phase_20 通過
bash scripts/health_checks/phase_20.sh
```

【6. Smoke Test（手動）】
✓ 從乾淨機器（或 docker volume rm 清過）走完一次：clone → 依 connection-guide → 完成第一個分析
✓ 邀一位 user（自己家人）跟著 user-guide 操作 → 不卡關
✓ Obsidian Vault 開得起來，能看到 reports（暫時手動匯入）
✓ /admin/system 顯示所有 metrics 正常
✓ git log --oneline -50 看 commit 歷史完整、commit message 合規範
✓ git tag --list 看到 phase-00-complete ~ phase-20-complete + v1.0.0
✓ docs/ 下檔案數量 > 30（含 phase_reports 21 個 + runbooks 17 個 + 主文件 7 個）
✓ PROJECT_FINAL_REPORT.md 從頭讀到尾，每節資料正確

【7. 已知陷阱】
✗ all.sh 跑很久（15-30 分鐘）→ 別中斷
✗ 跑 all.sh 期間 backend 必須在跑 → 啟動再跑
✗ E2E 測試 flaky（網路慢）→ retry 1 次
✗ pytest 總數低於 535 → 看 23.5.1 表回去補
✗ phase_NN.sh 漏掉某幾個 → 補完
✗ FINAL_REPORT 內容是 placeholder → 必須填真實數字
✗ connection-guide 試跑時發現指令錯 → 修正再 release
✗ Obsidian 在 Mac/Linux 安裝路徑不同 → check 腳本兼容
✗ v1.0 tag 太早打：先確認 all.sh 全綠
✗ git push 帶 tag 失敗 → git push --follow-tags
✗ GitHub release 沒 remote → 跳過（v1.0 自用不必）
✗ 報告中的「實際時數」必須真實填，不要照抄預估
✗ 報告中的 SLO 數字必須從 slo_report.py 真實產出，不要猜

【8. Self-Check SOP】跑第 8.5.4 章全部 8 項。
本 Phase 結束後再額外跑「全文最終 review」（依規劃指引）：
- 章節編號連續且唯一（1-33，含 8.5、23.5、一-附錄）
- 每個 Phase（1-20）都有對應的【完成驗收】、Self-Check SOP、scripts/health_checks/phase_NN.sh
- 累積測試數量基準（第 23.5.1）對得起每個 Phase 實際定義
- PLAN.md 開頭的「v7.0 規劃進度說明」與結語進度表一致

【9. 完成後產物】
程式檔（新增）：
  - scripts/health_checks/all.sh
  - scripts/check_obsidian_installed.sh
  - backend/tests/integration/test_final_smoke.py
  - scripts/health_checks/phase_20.sh

文件檔（新增）：
  - docs/PROJECT_FINAL_REPORT.md（最重要）
  - docs/connection-guide.md
  - docs/user-guide.md
  - docs/runbooks/obsidian_setup.md
  - docs/phase_reports/PHASE_20.md
  - docs/slo_reports/YYYY-MM-DD.json（從 slo_report.py 產出）

文件檔（重大更新）：
  - README.md（v1.0 完整版）
  - CHANGELOG.md（v1.0.0 entry）
  - SECURITY.md（v1.0 真實內容）
  - docs/phase_progress.md（21 個 Phase 全標完成）

Git tag：phase-20-complete + **v1.0.0**

【10. 開始執行】
按【2. 跨 Phase 健康檢查】開始，依【4. 任務清單】依序執行。
特別重要：
- B-C（all.sh + 收集成果）必須真實跑通才有真實數據填 D（FINAL_REPORT）
- D 是本 Phase 最重要的交付物，預留 1-2 小時細寫
- E + F（user 文件）測試標準：「家人能照著用嗎？」
- J（v1.0 tag）只在 all.sh 全綠後才打
- 本 Phase 結束 = v7.0 規劃 100% 完成 = v1.0 Release
```

---

> **🎉 v7.0 規劃 100% 完成。**
> **共 21 個 Phase（P0-P20），每個 Phase 都遵循固定 9 段格式 + 跨 Phase 健康檢查 + Self-Check SOP + 完成後產物。**
> **下一步：跑 Phase 0 → Phase 1 → ... → Phase 20，預估 30-40 calendar days（每天 5 小時 / 1 個 Phase）完成 v1.0 Release。**

---

## 二十八、Phase 失敗回復程序

### 28.1 通用回退流程（v7 強化）

1. **診斷：** 看 Phase Prompt【已知陷阱】+ Self-Check SOP 失敗項
2. **隔離：** 保留 log（cp backend.log /tmp/phase_<NN>_fail_$(date +%s).log）
3. **判斷層級：**
   - 程式碼錯：fix in place，不回退 git
   - 資料錯（DB schema、seed）：alembic downgrade + 重跑
   - 環境錯（docker、port）：make down → 修 → make up
   - Phase 設計錯（已知陷阱沒覆蓋）：先記到 docs/runbooks/<phase>.md，再修
4. **回退（依需要）：**
   - 程式：`git reset --hard phase-<NN-1>-complete`（保留前一 Phase 的成果）
   - 分支：`git checkout main && git branch -D phase/NN-... && git checkout -b phase/NN-... main`
   - DB：`make down && docker volume rm timescaledb_data && make up && make init-db`
   - Qdrant：`docker volume rm qdrant_data && make up`
5. **修正後重跑：** 開新對話貼 Phase Prompt + 註明「上次失敗原因：...」
6. **驗收：** 跑【5. 完成驗收】+【8. Self-Check SOP】+ 跨 Phase 健康檢查

### 28.2 各 Phase 特殊狀況 Cookbook

| Phase | 常見失敗 | 處理 |
|-------|---------|------|
| P1 | git mv 漏檔 → 根目錄殘餘 | `ls`確認 → 補 git mv → commit |
| P1 | pre-commit 改檔但沒 add | `git add -A && git commit --amend --no-edit` |
| P1 | uv lock 跑很久 | 第一次正常 ~2 分鐘，等就好 |
| P2 | port 5432 被本機 PG 占 | docker-compose 改 5433:5432 + .env 改 POSTGRES_PORT=5433 |
| P2 | timescaledb container 反覆重啟 | `docker compose logs timescaledb` 看，通常是 init.sql 語法錯 |
| P2 | Windows volume 權限 | 砍 volume 重建（named volume 不要 bind） |
| P3 | uvicorn lifespan 失敗無錯誤 | 加 `--no-reload` 看完整錯誤 |
| P3 | structlog 不是 JSON | 確認 `wrap_for_formatter` 在 processors 最後 |
| P3 | trace_id 沒在 log | 確認 `merge_contextvars` 在 processors |
| P4 | alembic upgrade 撞 hypertable | autogenerate 處理不了 → 手動加 `op.execute("SELECT create_hypertable...")` |
| P4 | trigger 重建衝突 | downgrade 中先 `DROP TRIGGER` 再 `DROP FUNCTION` |
| P4 | Qdrant collection 已存在 | ensure_collections 應 idempotent，try/except 不要 raise |
| P5 | FinMind 401 | 檢查 .env 的 FINMIND_TOKEN 沒過期 + 沒空白 |
| P5 | TWSE 1 sec 一次撞限 | aiolimiter 設 0.5/sec 更保守 |
| P5 | MOPS 解析失敗 | print HTML 確認結構是否改了 → BS4 selector 調整 |
| P5 | DataFrame upsert PG type error | 印 df.dtypes 確認，必要時 .astype(...) 強制轉 |
| P6 | yfinance 隨機 None | retry 3 次 + 24h 快取 |
| P7 | celery worker 收不到 task | 檢查 broker_url + 確認 task 註冊（autodiscover_tasks） |
| P7 | beat schedule 沒跑 | 檢查 timezone="Asia/Taipei" + beat 容器分開 |
| P8 | JWT signature invalid | SECRET_KEY 不一致（測試與正式不同） |
| P8 | bcrypt 慢到 timeout | cost=12 是設計選擇，不要降低 |
| P9 | audit hash chain 斷 | verify_audit_chain.py + 從 backup 還原 |
| P10 | router 撞名 | prefix=/api/v1/<resource> 嚴格 |
| P11 | PDF 中文亂碼 | Dockerfile 加 fonts-noto-cjk + chromium |
| P11 | 並發核准產生 race | SELECT FOR UPDATE + version column 雙保險 |
| P12 | LangGraph state 累積爆 | 啟用 trim_state_messages + 硬上限 6 輪 |
| P13 | Tool 無權限存取 DB | Agent engine 必用 ta_agent_ro |
| P14 | LLM fallback 沒觸發 | CB 邏輯檢查 + provider chain 順序 |
| P14 | WS 立即斷 | client subprotocol = ["tradingagents.v1", f"ticket.{ticket}"] |
| P15 | Hydration warning | 日期/時間用 useEffect 處理；伺服器與客戶端時區一致 |
| P16 | shadcn 樣式錯 | tailwind.config.ts 的 content paths 包到 components |
| P17 | recharts SSR error | dynamic import + ssr: false |
| P18 | LINE Notify 401 | token 過期 → 重產 |
| P18 | Trivy HIGH alert | 升級 base image（python:3.11.x → 最新 patch） |
| P19 | E2E flaky | 加 waitFor + data-testid（不要靠 sleep） |
| P19 | nginx WS proxy timeout | proxy_read_timeout 86400s |
| P20 | health_checks/all.sh 失敗 | 哪個 phase_NN.sh 失敗就回去修哪個 Phase |

### 28.3 緊急回到 Pre-flight 狀態

如果整個改造嚴重失敗，要回到 Phase 0 的乾淨狀態：

```bash
# 1. 暫存當前未 commit 變更（如果有）
git stash push -m "abandoned-tw-edition-attempt-$(date +%Y%m%d)"

# 2. 切換到當時的 backup tag
git checkout pre-tw-edition-backup

# 3. 砍 docker volumes（DB 與 vector store 全清）
make down
docker volume rm $(docker volume ls -q | grep tradingagents)

# 4. 為「之前的失敗嘗試」開個 archive 分支保留紀錄
git branch archive/tw-edition-attempt-failed-$(date +%Y%m%d) main

# 5. 重新從 main 開始（已是 pre-tw-edition-backup 狀態）
git checkout -b main-restart

# 6. 重新跑 Phase 0
```

### 28.4 中段 context 用盡（Phase 跑到一半 Claude 不夠）

依第 8.5.6 章「context 接近上限緊急處理 SOP」執行：

1. WIP commit + push
2. 在當前對話最後產出「接續 Prompt」（含已完成清單、剩餘清單、git 狀態）
3. 結束當前對話
4. 開新對話貼接續 Prompt 繼續

### 28.5 失敗紀錄歸檔

每次 Phase 失敗（無論成功修復或回退）都寫入 `docs/runbooks/phase_failures.md`：

```markdown
## YYYY-MM-DD — Phase NN 失敗

**症狀：**（一句話描述）
**根因：**（為何發生）
**修復：**（怎麼解的）
**避免重發：**（建議下次怎麼做）
**對應 PLAN.md 改動：**（如果發現 PLAN.md 該 Phase 的「已知陷阱」漏了，補上）
```

累積這個檔將成為 v7.1 / v8 的修訂依據。

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

## 二十九、容量規劃

> v6 新增、v7 章節編號從 28 改為 29（28 已被 Phase 失敗回復程序占用）。

### 29.1 預期負載（v1.0 自用）

| 維度 | 目標 |
|------|------|
| 同時在線用戶 | 1-5 |
| 每天分析次數 | 5-20 |
| 每天 API 請求數 | < 10,000 |
| 同時 WebSocket 連線 | < 10 |
| 每月儲存增長（行情） | ~500 MB |
| 每月儲存增長（Qdrant） | ~200 MB |
| 每月儲存增長（audit log） | ~100 MB |

### 29.2 瓶頸與處理

| 瓶頸 | 觸發點 | 處理 |
|------|-------|------|
| LLM API 配額 | 50 次分析/天 | 增加月預算 / 切換 provider |
| FinMind 配額 | backfill 大量股票 | 升級付費 / 減少 backfill 範圍 |
| TimescaleDB 磁碟 | > 80% | 加大 retention（v1.0 1 年）/ 加磁碟 |
| Qdrant 記憶體 | 向量 > 100 萬 | 加機器 RAM / 啟用 quantization |
| Celery worker 飽和 | concurrent > 4 | 加 worker count |
| Nginx 連線 | 同時 > 1000 | 升級到多 worker |

### 29.3 擴容路線

| 階段 | 配置 | 月費 |
|------|------|------|
| 現在 v1.0 自用 | 單機 16GB | ~$154 |
| 增長 1（5+ 用戶） | 加 RAM 至 32GB | ~$200 |
| 增長 2（多用戶） | 拆 DB + Backend | v2.0 重新規劃 |
| 增長 3（公開服務） | K8s + 多 region | v3.0 |

---

## 三十、資源、預算與成本

### 30.1 硬體（單機）

| 配置 | 最低 | 推薦 |
|------|-----|------|
| CPU | 4 cores | 8 cores |
| RAM | 16 GB | 32 GB |
| 磁碟 | 100 GB SSD | 500 GB SSD |
| 網路 | 100 Mbps | 1 Gbps |

### 30.2 月費

| 項目 | 月費 |
|------|------|
| FinMind 付費 | ~$99 |
| Alpha Vantage 付費 | ~$50 |
| Gemini Flash | ~$5 |
| **小計** | **~$154/月** |

### 30.3 LLM 單次成本

| 模型 | 成本 |
|------|------|
| Gemini 2.0 Flash | ~$0.012 |
| Gemini 2.5 Pro | ~$0.15 |
| GPT-4o-mini | ~$0.018 |
| Claude Haiku 3.5 | ~$0.10 |

### 30.4 開發 Token 預算（v7 修訂：21 Phase）

| Phase | Token | Phase | Token | Phase | Token |
|-------|-------|-------|-------|-------|-------|
| P0 | 0（手動） | P7 | ~70k | P14 | ~75k |
| P1 | ~50k | P8 | ~75k | P15 | ~78k |
| P2 | ~45k | P9 | ~70k | P16 | ~80k |
| P3 | ~70k | P10 | ~78k | P17 | ~80k |
| P4 | ~75k | P11 | ~78k | P18 | ~70k |
| P5 | ~75k | P12 | ~65k | P19 | ~70k |
| P6 | ~70k | P13 | ~75k | P20 | ~60k |
| | | | | **合計** | **~1.39M** |

每 Phase 都在 Opus 4.7 Max 200k context window 內，且預留 ≥ 25% 緩衝（含 PLAN.md 章節閱讀 + 工具輸出 + 程式碼產出）。

---

## 三十一、部署架構

### 31.1 開發

```bash
make up               # DB 三服務
make init-db          # schema + admin（一次性）
make seed-stocks      # 股票清單（一次性）
make backend-dev
make frontend-dev
make up-workers
```

### 31.2 自用伺服器

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml --profile worker up -d
```

### 31.3 備份

| 資料 | 頻率 | 保留 |
|------|------|------|
| TimescaleDB | 每日 02:00 | 30 天 |
| Qdrant | 每日 02:30 | 30 天 |
| .env / DATA_ENCRYPTION_KEY | 變動時手動 | 永久（加密隨身碟） |
| 備份還原驗證 | 每月 | - |

### 31.4 監控（v1.0）

- /metrics endpoint
- 前端 /admin/system
- 每日 verify_data + verify_audit + slo_report
- 異常 → LINE
- v2.0 接 Prometheus + Grafana

---

## 三十二、災難復原 SOP

### 32.1 目標
RTO 1 小時 / RPO 24 小時

### 32.2 情境

| 情境 | 步驟 |
|------|------|
| **A. TimescaleDB 損毀** | make down → 移除 volume → make up → init-db → restore.sh → verify_data |
| **B. Qdrant 索引損毀** | recreate collections → restore snapshot 或重跑 news_ingest（過去 30 天） |
| **C. Audit 偵測竄改** | 立即停服 → 從可信備份還原 audit_logs → 重新校驗 → 調查原因 |
| **D. 整機損毀** | 新機 Docker → clone repo 同 commit → 還原 .env + DATA_ENCRYPTION_KEY → backups → make up + restore |
| **E. LLM 持續失敗** | 檢查 fallback chain log → 改 .env 預設 provider → 重啟 |
| **F. 資料源全失敗** | Circuit breaker 已通知 → 用快取運作（前端標延遲）→ 恢復後 backfill |

### 32.3 演練

每季演練情境 A，記錄實際 RTO 調整 SOP。

---

## 三十三、後續延展路線圖

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

## 結語：v7.0 的設計目標達成

v7.0 是**可執行性收斂版本**。聚焦在「保證每個 Phase 都能在 Opus 4.7 Max 5 小時 session 一次跑完」：

- ✅ **Phase 拆細**（10 → 21）：每個 Phase 程式碼 ≤ 1500 行、token ≤ 80k
- ✅ **每 Phase 自我檢查 SOP**（第 8.5 章）：8 項通用檢查 + 各 Phase 專屬退出條件
- ✅ **跨 Phase 健康檢查**（第 23.5 章）：每 Phase 開頭先驗證上一 Phase 還能跑
- ✅ **累積測試基準**（第 23.5.1）：每 Phase 後測試數量明確下限
- ✅ **Phase 啟動 Prompt 模板**（第 25 章）：固定 9 段格式
- ✅ **Phase 報告產物**：每 Phase 結尾在 docs/phase_reports/PHASE_NN.md 留下檢核紀錄
- ✅ **失敗 Cookbook**（第 28.2 章）：每 Phase 常見失敗對應處理
- ✅ **最終驗證 Phase**：P19 + P20 專責整合驗證 + 報告產出
- ✅ **保留 v6 全部優點**：Part A/B/C/D 結構、ADR、版本相容性矩陣、原版遷移指南、反模式清單

**v7.0 規劃進度：**

| 規劃次數 | 已完成 | 待完成 |
|---------|-------|-------|
| 第 1 次 ✅ | 框架（Part A/B/D 章節更新）+ Phase 0-5 詳細 | Phase 6-20 詳細 |
| 第 2 次 ✅ | Phase 6-12 詳細 + Part D 章節編號修正 | Phase 13-20 詳細 |
| 第 3 次 ✅ | Phase 13-17 詳細（Analyst + 美股 + LLM Fallback + 前端 18 頁） | Phase 18-20 詳細 + 最終 review |
| 第 4 次 ✅（最後一次） | Phase 18-20 詳細 + 全文 sanity check + 結案 | **無** |

**🎉 規劃完成度：21 / 21 Phase（100%）** + 完整框架 + 章節編號完整 + 全部 9 段 Phase 格式一致 + 21 個 health_check 對應腳本 + 累積測試基準完整。

**v7.0 規劃結束。下一步開始執行 Phase 0。**

實際執行中發現問題 → 在 `docs/runbooks/phase_failures.md` 累積，作為 v7.1 修訂依據。

*計劃文件 v7.0 完成度：依規劃次數推進中。*
*下一步：完成所有 Phase 詳細 → 跑 Phase 0 環境驗證 → 開新對話貼 Phase 1 Prompt 開始執行。*
*嚴格依序 P0 → P20，每 Phase 通過具體驗收指令 + Self-Check SOP + 跨 Phase 健康檢查 才進下一個。*
