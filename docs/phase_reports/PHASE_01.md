# Phase 01 完成報告

> Phase：原版遷移 + 新骨架 + 工程規範文件 + Git 工作流程
> 起始：2026-05-04
> 完成：2026-05-04
> 對應計劃：PLAN.md 第二十七章 Phase 1

---

## 1. 做了什麼

### 1.1 原版遷移（任務 B）

把根目錄原版 v0.2.4 殘留檔遷至 `legacy/`：

- `.dockerignore` → `legacy/.dockerignore`
- `.env.enterprise.example` → `legacy/.env.enterprise.example`
- `uv.lock`（原版的）→ `legacy/uv.lock`
- 清理 build artefacts：`build/`、`tradingagents.egg-info/`
- `README.md` 備份至 `legacy/README_original.md`，根目錄 `README.md` 改寫為新版

注意：`tradingagents/`、`cli/`、`tests/`、`scripts/`（原版）等大目錄已在前次操作遷移完成，本 Phase 處理的是殘留小檔。

新建 `legacy/README.md` 說明用途與「不可 import」原則。

### 1.2 新目錄骨架（任務 C）

建立 41 個子目錄 + `.gitkeep`，涵蓋：

- `backend/app/{api,core,repos,services,domain,models,schemas,agents,data_sources,llm,workers,notifications,exports}/`
- `backend/migrations/`、`backend/scripts/`、`backend/tests/{unit,integration,security}/`
- `frontend/src/{app,components,lib,store,hooks,i18n}/`、`frontend/tests/{unit,e2e}/`
- `data-pipeline/{schemas,scripts}/`
- `docker/{timescaledb,nginx/certs,backups,playwright}/`
- `docs/runbooks/`

### 1.3 設定檔（任務 D-N）

| 檔案 | 大小 | 說明 |
|------|------|------|
| `.gitignore` | 1.3 KB | 涵蓋 .venv / node_modules / .env / docker/backups / IDE |
| `.vscode/settings.json` | 1.4 KB | 排除 legacy/，啟用 ruff format-on-save |
| `.env.example` | 4.2 KB | 列齊 v1.0 所有欄位 + 各 Phase 補值時程 |
| `.pre-commit-config.yaml` | 1.5 KB | ruff + detect-secrets + check-yaml/json/toml |
| `.secrets.baseline` | ~3 KB | detect-secrets baseline（0 個 false positive） |
| `.github/workflows/ci.yml` | 1.7 KB | lint + secret-scan + pre-commit jobs |
| `.github/workflows/security.yml` | 2.0 KB | bandit + gitleaks + CodeQL（升級自原版） |
| `Makefile` | 1.4 KB | help / lint / format / test / secrets-scan / precommit / clean |
| `backend/pyproject.toml` | 2.7 KB | FastAPI 0.115 + Pydantic v2 + SQLAlchemy 2.0 + structlog + httpx + uv |
| `backend/uv.lock` | ~700 KB | uv lock（79 packages） |
| `backend/Dockerfile` | 1.2 KB | python:3.11-slim + uv + uid 1000 |

### 1.4 文件（任務 O-S）

- `docs/engineering-standards.md`（5.4 KB）：完整輸出 PLAN.md 第十七章工程規範
- `docs/setup.md`（2.0 KB）：開發環境設定 + Phase 啟動指令清單
- `docs/contributing.md`（4.1 KB）：Git 工作流程、commit 格式、PR 流程、反模式
- `README.md`（覆寫）：新版總覽 + 技術棧徽章 + 進度表
- `CHANGELOG.md`：加 `[Unreleased]` v0.3.0 entry

### 1.5 測試雛形（任務 T）

5 個 unit test 檔（**collect 36 tests**）：

- `test_skeleton.py`：5 tests（驗證骨架目錄齊全 + legacy 隔離 + 文件齊全）
- `test_repo_imports.py`：16 tests（14 個套件 import + Python 3.11 + Pydantic v2）
- `test_config_loader.py`：5 tests（標 skip，P3 啟用）
- `test_logging_format.py`：5 tests（標 skip，P3 啟用）
- `test_envelope_shape.py`：5 tests（標 skip，P3 啟用）

執行結果：**21 passed, 15 skipped, 0 failed**

### 1.6 健康檢查 + 報告（任務 U-W）

- `scripts/health_checks/phase_01.sh`：10 項檢查全綠（含 ruff、pytest collect、detect-secrets）
- `docs/phase_reports/PHASE_01.md`（本檔）
- `docs/phase_progress.md`：P1 標完成

---

## 2. 退出條件指令結果

| # | 指令 | 結果 |
|---|------|------|
| 1 | 原版完整遷移（4 個 test 子項） | ✓ |
| 2 | 新骨架完整（10 個目錄 test） | ✓ |
| 3 | `cd backend && uv sync --frozen` | ✓（79 packages）|
| 4 | `cd backend && uv run ruff check app/` | ✓ All checks passed |
| 5 | pytest collect ≥ 5 | ✓（36 tests collected）|
| 6 | detect-secrets baseline | ✓（0 false positive）|
| 7 | pre-commit run --all-files | 待 commit 後跑（會自動觸發） |
| 8 | .env.example 必要欄位 | ✓（11 個關鍵欄位）|
| 9 | 文件齊全 | ✓ |
| 10 | health_check phase_01.sh | ✓（10/10 項通過）|
| 11 | PHASE_01.md ≥ 20 行 | ✓（本檔）|
| 12 | CI 綠燈 | 待 push 後驗證 |

---

## 3. 已知遺漏

### 3.1 venv/ 未清

`venv/` (379 MB) 是上一輪 v0.2.4 殘留的 Python venv。**仍保留**，理由：

- 已在 `.gitignore` 排除（不會進 git）
- v7 改用 uv + `.venv/`，舊 venv 純粹是磁碟空間佔用
- **建議用戶在 P2 開始前手動 `rm -rf venv/`** 釋放空間

### 3.2 P0 補建項目

發現 P0 跑 v6 PowerShell 流程時漏建以下 v7.0 新增的 P0 產物，本 Phase 已補建：

- `docs/phase_progress.md`
- `docs/phase_reports/.gitkeep`
- `scripts/health_checks/.gitkeep`

已在 master 分支 commit (`54eafd9`) 後再切 phase/01 分支，避免產物分散。

### 3.3 ruff 設定加 RUF001/002/003 ignore

繁中專案大量使用全形標點，需在 ruff `[tool.ruff.lint] ignore` 加 `RUF001/002/003` 否則 docstring/comment 會 lint fail。已修正並寫入 pyproject.toml。

---

## 4. 給下一 Phase（Phase 2）的提醒

1. **先跑 `bash scripts/health_checks/phase_01.sh`** 確認 P1 結果還能跑
2. P2 主題：Docker 基礎服務（TimescaleDB / Redis / Qdrant）+ DB 帳號分離
3. P2 會在 `.env` / `.env.example` 補入 DB / Redis / Qdrant 密碼（隨機 32 字元）
4. P2 不寫業務程式（避免 Phase 過大）
5. 必讀章節：PLAN.md 第 6.1, 8.5, 12, 13, 19.1, 19.4, 19.5 章
6. **P2 啟動前可先 `rm -rf venv/`** 清舊 Python venv 釋放 379 MB
7. P2 完成後 `.env` 應有：`POSTGRES_SUPERUSER_PASSWORD`、`TA_MIGRATION_PASSWORD`、`TA_SERVICE_RW_PASSWORD`、`TA_AGENT_RO_PASSWORD`、`REDIS_PASSWORD`、`QDRANT_API_KEY`

---

## 5. 跑了多久

- 開始：2026-05-04（Phase 1 對話開始）
- 完成：2026-05-04（同日）
- Claude session：1
- 估計實際時數：~3 hr（含 P0 補建）

---

## 6. Git 操作摘要

```
master:
  54eafd9  chore(phase-0): 補建 phase 進度追蹤檔與健康檢查目錄

phase/01-migration-and-skeleton:
  39829f8  chore(phase-1): 將原版 v0.2.4 殘留檔遷至 legacy/ 並補 README
  (本 Phase 結尾再做大 commit + tag)
```
