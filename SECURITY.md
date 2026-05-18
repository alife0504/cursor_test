# 安全政策 / Security Policy

> **v1.0 狀態**：TradingAgents-TW Secure Edition — 自用單機部署版本（單一使用者 + localhost）。

本專案為 TauricResearch/TradingAgents 的繁體中文加固版，承襲 Apache 2.0 授權。

---

## 支援版本

僅對最新 main 分支提供安全修補。

| 版本 | 支援狀態 |
| ---- | ------- |
| latest (main) | ✅ |
| 其他 | ❌ |

---

## 通報安全漏洞

**請勿透過公開的 GitHub Issues 通報安全問題**，以免在修補前被惡意利用。

請透過以下任一管道私下通報：

1. **GitHub Private Vulnerability Reporting**（推薦）
   進入 Security 分頁 → Report a vulnerability
2. **加密 email**：請提供 PGP 公鑰後再傳送敏感細節

### 通報內容建議包含

- 漏洞類型（如：注入、權限繞過、敏感資訊洩漏）
- 觸發步驟與最小重現範例
- 影響範圍與嚴重程度評估
- 已知的緩解方式（若有）

### 回應時程承諾

| 時點 | 動作 |
| ---- | ---- |
| 24 小時內 | 確認收到通報 |
| 7 天內 | 完成初步評估與嚴重性分級 |
| 30 天內 | 高/嚴重漏洞發布修補 |
| 修補後 | 在 CHANGELOG 記錄並標註通報者（若同意） |

---

## 安全架構摘要（PLAN 第 19 章）

### 認證授權
- 密碼：12 字元 + 4 類字元、bcrypt cost=12、不可同最近 5 次（`password_history` 表）
- Lockout：5 次失敗 → 15 分鐘鎖
- JWT：HS256 (32-byte 以上 secret) + access 15 min + refresh 7 天 + dual-key rotation
- CSRF：refresh path X-CSRF-Token + SameSite=Strict
- WS 認證：Subprotocol + Ticket（一次性 60s）
- Session：per user 5 個上限
- 角色：ADMIN / ANALYST / VIEWER

### Secret 管理（P18）
- Dev `.env`、Prod Docker secrets
- JWT 雙 key 7 天並存（`scripts/rotate_secrets.sh`）
- DB 半年輪換（`scripts/rotate_db_passwords.sh`）
- Fernet `DATA_ENCRYPTION_KEY`（與 `SECRET_KEY` 分離）加密 LINE / Telegram token
- 加密 key 輪替（`scripts/rotate_encryption_key.sh`）
- log 自動遮蔽（`structlog` mask processor）

### Audit 不可竄改（P9 / P18）
- hash chain（prev_hash + entry_hash）
- 撤銷 UPDATE / DELETE 權限（`migrations/0013_baseline_revoke.py`）
- 每日校驗（`scripts/verify_audit_chain.py`）
- DB-level trigger 自動算 hash

### CSP（P18）
- Dev：寬鬆 + unsafe-eval（Next.js HMR / SWC dev mode 必要）
- Prod：nonce-based + strict-dynamic + frame-ancestors 'none'

### 容器安全（P19 才完整啟用）
- 非 root（uid 1000）
- Read-only fs + drop ALL capabilities（nginx 加 NET_BIND_SERVICE）
- Image 掃描：Trivy（`make trivy-scan`）

---

## 安全範圍

**屬於安全漏洞**：
- 遠端程式碼執行（RCE）
- 任意檔案讀寫
- 未授權存取使用者資料、API 金鑰、決策記錄
- LLM 提示注入導致信任邊界被突破
- 依賴套件中的高/嚴重 CVE
- Audit hash chain 完整性被繞過
- Fernet 加密 token 解密失敗仍寫入 DB

**不屬於安全漏洞**：
- 投資/交易決策的準確性問題（本框架僅供研究教學）
- LLM 模型本身的偏見或幻覺
- 第三方資料來源（yfinance / FinnHub / TWSE）的資料品質問題
- 因使用者自行修改設定造成的問題

---

## 安全最佳實踐（給使用者）

1. **API 金鑰管理**
   - 切勿將 `.env` 提交至 git
   - 為每個 LLM 服務建立範圍受限的金鑰
   - 每 6 個月輪換金鑰（`scripts/rotate_*.sh`）
   - 使用本專案提供的 `scripts/check_env_security.sh` 自我檢查

2. **本地檔案保護**
   - `~/.tradingagents/` 目錄含分析決策歷史，請確保檔案權限為 0700
   - 多人共用主機請使用獨立帳號

3. **依賴更新**
   - Backend：`uv pip list --outdated`；每月跑 `uv run pip-audit`
   - Frontend：`npm audit --audit-level=high`；每月檢視
   - Image：`make trivy-scan`（PLAN 第 19.5 章）
   - 留意 GitHub Dependabot 通知

4. **網路安全**
   - LLM API 呼叫請走 HTTPS（預設行為）
   - 若使用代理，請確認其可信
   - 後端 API 不應對公網開放；v1.0 設計為 localhost-only

---

## v1.0 已接受風險（Accepted Risks）

依 PLAN 第七章「接受的限制」，下列風險為 v1.0 自用版可接受項目：

### A. Next.js 14.2.35 殘留 advisories（v1.1 計劃升級）

| Advisory | 嚴重度 | v1.0 風險評估 |
| --- | --- | --- |
| [GHSA-c4j6-fc7j-m34r](https://github.com/advisories/GHSA-c4j6-fc7j-m34r) SSRF via WebSocket upgrade | HIGH | 不啟用 WebSocket upgrade 路徑；自用 localhost |
| [GHSA-wfc6-r584-vfw7](https://github.com/advisories/GHSA-wfc6-r584-vfw7) Cache poisoning in RSC | HIGH | 無 CDN；單機 |
| [GHSA-36qx-fr4f-26g5](https://github.com/advisories/GHSA-36qx-fr4f-26g5) Pages Router i18n bypass | HIGH | 用 App Router，不用 i18n + Pages Router |
| postcss `<8.5.10` XSS via stringify | MEDIUM | build-time only，不在 runtime |

**升級計劃**：v1.1 升 Next.js → 15 或 16（須重新驗收 18 個前端頁面）。

### B. cookie 不綁 IP（v1.1 加 IP binding）

PLAN「已知陷阱」第 9 點：cookie 複製到另一瀏覽器仍能用 refresh。
- v1.0：自用 localhost、單機，攻擊面極小
- v1.1：refresh cookie 加 IP binding（PLAN ADR 待寫）

### C. 通知 dedupe 為 in-process

`quota_service._quota_notify` 用 in-process dict 做 24h dedupe；多 worker 場景每個 worker 各自 dedupe。
- v1.0 自用版實際只有 1 個 backend + 1 個 celery worker，影響極小
- v1.1 改 redis SETNX 共享 dedupe

### D. LINE Notify 已於 2025/04 棄用

但既有 token 仍可運作一段時間；v1.1 將改用 LINE Messaging API（adapter 已 plugin 化，加一個 class 即可）。

---

## 安全工具與檢查清單

| 工具 | 目的 | 頻率 | 指令 |
| --- | --- | --- | --- |
| bandit | Python static analysis | 每 PR | `make bandit` |
| detect-secrets | 偵測 secret 進 git | 每 commit（pre-commit）| `detect-secrets scan --baseline .secrets.baseline` |
| Trivy | 容器 image CVE 掃描 | 每月 | `make trivy-scan` |
| npm audit | 前端依賴 CVE | 每月 | `cd frontend && npm audit --audit-level=high` |
| pip-audit | Python 依賴 CVE | 每月 | `cd backend && uv run pip-audit` |
| verify_audit_chain | hash chain 完整性 | 每日（cron） | `python scripts/verify_audit_chain.py` |
| rotate_secrets | JWT 雙 key 輪替 | 半年 | `./scripts/rotate_secrets.sh && (+7d) ./scripts/rotate_secrets.sh --finalize` |
| rotate_db_passwords | DB 帳號密碼輪替 | 半年 | `./scripts/rotate_db_passwords.sh ta_service_rw` |
| rotate_encryption_key | Fernet 輪替 | 每年 | `./scripts/rotate_encryption_key.sh` |
| Pen test checklist | 手動測試 | 每 release | `docs/runbooks/pentest_checklist.md` |
