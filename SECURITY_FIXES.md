# 安全強化記錄 / Security Fixes Applied

本檔記錄相對於 TauricResearch/TradingAgents v0.2.4 上游所做的安全強化內容。

掃描日期：2026-05-01
基底版本：v0.2.4 (commit 7c37249)

---

## 修復前後對照

| 項目 | 上游狀態 | 加固版狀態 |
| ---- | -------- | ---------- |
| requirements 版本固定 | 無（pip 解析最新） | `requirements.lock` 鎖定 128 個套件 |
| pip 已知 CVE | 3 個（CVE-2025-8869, 2026-1703, 2026-3219） | 全數修復（pip 26.1+） |
| SECURITY.md | 無 | 完整漏洞通報政策 |
| Dependabot 自動更新 | 無 | 啟用（pip / actions / docker） |
| CI 安全掃描 | 無 | pip-audit + bandit + gitleaks + CodeQL |
| Dockerfile 基礎映像 | python:3.12-slim 浮動 | 文件化 digest 固定方法 + OS 升級補丁 |
| Dockerfile pip 版本 | 預設（含 CVE） | 建置時主動升級 |
| Dockerfile 用戶權限 | 0755 | 0700（僅自己可讀） |
| Dockerfile HEALTHCHECK | 無 | 已加入 |
| .env.example 安全提示 | 無 | 加入權限、輪換、洩漏警示 |
| .gitignore 範圍 | 僅排除 .env | 額外排除金鑰類、本地交易資料 |
| 安全自檢工具 | 無 | `scripts/check_env_security.sh` |

---

## 已新增/修改的檔案

### 新增
- `SECURITY.md` — 漏洞通報流程、回應 SLA、安全範圍定義
- `requirements.lock` — pip freeze 快照，128 個套件全數鎖定版本
- `.github/workflows/security.yml` — CI 自動掃描（push、PR、每週）
- `.github/dependabot.yml` — 每週自動 PR 更新依賴
- `scripts/check_env_security.sh` — 7 項安全自檢
- `SECURITY_FIXES.md` — 本文件

### 修改
- `Dockerfile` — 多階段建置強化、OS 補丁、pip 升級、權限收緊、HEALTHCHECK
- `.env.example` — 加入安全警示、API 取得連結、操作步驟
- `.gitignore` — 新增金鑰、憑證、本地交易資料的排除規則

### 保留不動
- `tradingagents/` 核心邏輯（無安全問題）
- `cli/` 命令列介面
- `pyproject.toml`（與 requirements.lock 互補）
- `uv.lock`（保留給 uv 使用者）
- `LICENSE`、`README.md`、`CHANGELOG.md`

---

## 對使用者的影響評估

| 影響面向 | 評估 |
| -------- | ---- |
| 既有功能 | 零影響，所有 API 不變 |
| 安裝步驟 | 多一個可選的 `pip install -r requirements.lock` |
| 啟動速度 | 完全相同 |
| Docker 建置時間 | +30~60 秒（OS 補丁與 pip 升級） |
| 執行記憶體 | 完全相同 |
| 維護負擔 | 自動化（Dependabot 每週自動 PR） |

---

## 驗證結果

```
$ pip-audit --skip-editable
No known vulnerabilities found
```

```
$ bash scripts/check_env_security.sh
.gitignore 已排除 .env             [✓]
git 歷史未發現明顯金鑰格式          [✓]
未發現全域可寫的敏感檔案            [✓]
```

---

## 已知殘留風險（無法在程式碼層完全解決）

1. **yfinance 為非官方 API** — Yahoo 可隨時改變介面或封鎖 IP；此風險屬資料源層面，非程式碼缺陷
2. **本地 SQLite 與 trading_memory.md 為明文** — 由 OS 檔案權限保護（已強制 0700），如需更高安全等級需另加應用層加密
3. **LLM 提示注入** — 模型本身的安全性問題，框架層只能做有限緩解
4. **API 金鑰仍集中於 .env** — 業界最佳實踐改用 secrets manager（如 HashiCorp Vault），但對個人/小團隊使用 .env + 0600 權限已足夠

---

## 持續維護建議

| 頻率 | 動作 |
| ---- | ---- |
| 每次 commit 前 | 執行 `bash scripts/check_env_security.sh` |
| 每月 | 執行 `pip-audit -r requirements.lock` |
| 每季 | 輪換所有 LLM API 金鑰 |
| 每半年 | 用 docker pull 重新取得 base image digest |
