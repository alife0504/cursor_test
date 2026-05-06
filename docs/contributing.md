# 貢獻指南（Contributing）

> v1.0 為自用版，本文件規範「自我貢獻」流程。
> 後續若擴展為多人開發，可衍生為標準 OSS contributing guide。

---

## 1. 前置條件

開始貢獻前請確認：

1. 已讀 `PLAN.md`（至少 Part A 全部章節）
2. 已讀 `docs/engineering-standards.md`
3. 已跑過 Phase 0 + Phase 1 環境設定
4. 已切到對應 phase branch（`phase/<NN>-<簡稱>`）

---

## 2. Git 工作流程

### 2.1 Branch 命名

| 類型 | 格式 | 範例 |
|------|------|------|
| Phase 開發 | `phase/<NN>-<簡稱>` | `phase/02-docker-services` |
| Feature | `feat/<簡稱>` | `feat/watchlist-search` |
| Bugfix | `fix/<簡稱>` | `fix/jwt-rotation-bug` |
| 文件 | `docs/<簡稱>` | `docs/runbook-celery` |
| Hotfix | `hotfix/<簡稱>` | `hotfix/csrf-bypass` |

### 2.2 Commit message 格式（Conventional Commits）

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

- **type**：`feat` / `fix` / `chore` / `docs` / `test` / `refactor` / `perf` / `security`
- **scope**：`phase-<NN>` / `auth` / `api` / `frontend` / `db` / 等
- **subject**：祈使句（中文也可）、≤ 72 字、結尾不加句號

範例：
```
feat(phase-3): 加入 structlog JSON logging + trace_id middleware
fix(auth): 修正 JWT decode previous_key fallback 邏輯
chore(phase-1): 將原版 v0.2.4 殘留檔遷至 legacy/
test(api): 增加 watchlist 並發新增測試
docs(runbooks): 加入 celery DLQ 處理流程
```

### 2.3 Pre-commit hooks（**必跑**）

切到 backend 目錄 + 安裝一次（已在 P1 任務 G2 裝好）：

```bash
cd backend
uv run pre-commit install
```

之後每次 `git commit` 會自動跑：
- ruff check + format（會自動修檔）
- detect-secrets
- trailing-whitespace, end-of-file-fixer
- check-yaml, check-json, check-merge-conflict
- check-added-large-files (max 2MB)
- detect-private-key

**陷阱：** pre-commit 會自動修檔，修完後 git diff 會出現新變動。
**處理：** 重新 `git add` 修過的檔，再 `git commit`。

### 2.4 PR / Merge 流程（v1.0 自用版）

由於是個人專案，採「Self-merge」流程：

1. Phase 結束後跑完整退出條件（所有指令 exit code 0）
2. 跑 `bash scripts/health_checks/phase_<NN>.sh` 通過
3. 跑 8 項 Self-Check SOP 全綠
4. 寫 `docs/phase_reports/PHASE_<NN>.md`
5. 更新 `docs/phase_progress.md`
6. `git tag phase-<NN>-complete`
7. `git push origin phase/<NN>-<簡稱> --tags`
8. 在 GitHub 開 PR（即使 self-merge 也走 PR，方便回溯）
9. 等 CI 綠燈
10. **squash-merge** 到 main（commit history 乾淨）
11. `git checkout main && git pull && git branch -d phase/<NN>-<簡稱>`

---

## 3. 工程禁忌（依 PLAN.md 第八章「反模式清單」）

### 3.1 程式碼

| ❌ 不要 | ✅ 要 |
|--------|-------|
| `print()` 除錯 | `structlog.get_logger().info(...)` |
| `time.sleep()` in async | `asyncio.sleep()` |
| `requests.get()` in async | `httpx.AsyncClient` |
| `datetime.utcnow()` (Python 3.12+ deprecated) | `datetime.now(timezone.utc)` |
| `float` 算金額 | `Decimal` |
| `except Exception: pass` | 具體例外 + log |
| Agent tool 用 `ta_service_rw` | 必須 `ta_agent_ro`（read-only） |

### 3.2 安全

| ❌ 不要 | ✅ 要 |
|--------|-------|
| commit `.env` / API key | `.gitignore` + `detect-secrets` |
| JWT in URL query | Authorization header |
| WS auth 用 query token | Subprotocol + Ticket |
| 密碼明文比對 | `bcrypt` cost=12 |
| 5xx 吐 stack trace | trace_id 給 client，stack 進 log |

### 3.3 流程

| ❌ 不要 | ✅ 要 |
|--------|-------|
| 在 `main` 直接 commit | 切 `phase/` 或 `feat/` 分支 |
| Phase 沒驗收完進下一 Phase | 走完退出條件 + Self-Check + health_check |
| 跳過 pre-commit | 修好再 commit |
| 跳 Phase（先 P5 再回 P3） | 嚴格依序 P0 → P20 |
| 一個對話跑多 Phase | 每 Phase 開新 Claude 對話 |

---

## 4. 寫測試

### 4.1 命名

```python
# 檔名：test_<module>.py
# 函式：test_<function_or_behavior>

def test_user_login_success(): ...
def test_user_login_locked_after_5_failures(): ...
```

### 4.2 標記

```python
import pytest

@pytest.mark.unit          # 預設，無外部依賴
def test_pure_function(): ...

@pytest.mark.integration   # 需 docker compose up
def test_db_query(): ...

@pytest.mark.security      # OWASP 等
def test_sql_injection_blocked(): ...

@pytest.mark.network       # 真實打外部 API
def test_finmind_real_call(): ...

@pytest.mark.expensive     # 真實 LLM call（會花錢）
def test_real_2330_analysis(): ...
```

### 4.3 跑測試

```bash
# 預設只跑 unit + integration（CI 等同此設定）
make test

# 加 network
cd backend && uv run pytest -m "network"

# 加 expensive
cd backend && uv run pytest -m "expensive"

# 全部
cd backend && uv run pytest -m ""
```

---

## 5. 寫文件

- README、CLAUDE.md、commit message：**繁體中文**
- 程式碼註解、docstring：**繁體中文**（複雜技術細節可英文）
- 程式變數名、函式名：**英文**
- API endpoint 描述（Swagger）：**繁體中文**

---

## 6. 加新依賴（Python）

```bash
cd backend
uv add <package>           # 加到 [project.dependencies]
uv add --dev <package>     # 加到 [dependency-groups.dev]
git add pyproject.toml uv.lock
```

**禁止用 `pip install`**（會污染環境，且 uv.lock 不會同步）。

---

## 7. 加新依賴（前端）

```bash
cd frontend
npm install <package>           # 加到 dependencies
npm install --save-dev <package>  # 加到 devDependencies
git add package.json package-lock.json
```

**禁止用 `npm install -g`**（CI 環境沒有）。

---

## 8. 進階：Phase 跑到一半 context 用完

依 PLAN.md 第 8.5.6 章「context 接近上限緊急處理 SOP」：

1. WIP commit + push（`git commit -m "WIP: phase NN partial"`）
2. 在當前對話最後產出「接續 Prompt」
3. 結束當前對話
4. 開新對話貼接續 Prompt 繼續

**絕對不要硬撐到 context 滿**，Claude 會開始遺忘前面的決策、產出前後不一致的程式碼。
