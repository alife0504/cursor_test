# TradingAgents-TW v1.0

> 多 Agent AI 投資分析平台 — **台股主、美股輔、繁中 UI、安全架構優先、自用 Secure Edition**
>
> 改造自 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) v0.2.4，原版已備份於 `legacy/`

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Node 20](https://img.shields.io/badge/node-20-green.svg)](https://nodejs.org/)
[![TimescaleDB 2.16](https://img.shields.io/badge/TimescaleDB-2.16-orange.svg)](https://www.timescale.com/)
[![FastAPI 0.115](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js 14.2](https://img.shields.io/badge/Next.js-14.2-black.svg)](https://nextjs.org/)
[![Status: Release Ready](https://img.shields.io/badge/Status-Release%20Ready-success)](docs/PROJECT_FINAL_REPORT.md)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## 🎯 v1.0 簡介

- **4 種 Analyst**（市場面 / 基本面 / 新聞面 / 籌碼面）+ Bull/Bear 多輪辯論 + Manager 綜合決策
- **跨市場**：台股 5 個資料源（FinMind/TWSE/TPEX/MOPS/cnyes）+ 美股 4 個資料源（yfinance/Alpha Vantage/Finnhub/SEC EDGAR）
- **18 頁繁中前端**：AgentFlowGraph 即時動畫、AI 流程視覺化、PDF/MD/XLSX 匯出
- **手動核准下單**（不直連券商，ADR-007）
- **完整 audit hash chain**（不可竄改 / 每日自動校驗）
- **LINE / Telegram 通知**、CB 熔斷、Fallback chain
- **716 自動化測試 + 57 前端 E2E**，bandit/Trivy/npm audit 全綠

---

## 🚀 快速啟動

**第一次使用**：依 [docs/connection-guide.md](docs/connection-guide.md) 走完 10 個步驟。

**Prod 啟動 SOP（最短版）**：

```bash
# 1. 複製 prod env + 填好 keys（詳見 docs/connection-guide.md 第 1 節）
cp .env.prod.example .env.prod
# (編輯 .env.prod)

# 2. 產 self-signed cert（自用 / 內網）
bash scripts/generate_self_signed_cert.sh

# 3. 啟動 8 服務（DB / Redis / Qdrant / backend / celery×2 / frontend / nginx）
make prod-up
sleep 60

# 4. 進 https://localhost 登入（admin 帳號於 .env.prod）

# 5. 第一個分析（依 user-guide 第 7 節）
```

詳見 [連線指南](docs/connection-guide.md) 與 [使用者指南](docs/user-guide.md)。

---

## 🏗 技術棧

| 層 | 技術 |
|----|------|
| **前端** | Next.js 14.2 + TypeScript + shadcn/ui + Tailwind + lightweight-charts + @xyflow/react + Zustand + React Query |
| **後端** | FastAPI 0.115 + LangGraph 0.2.x + Celery 5.4 + Pydantic v2 + SQLAlchemy 2.0 (async) |
| **DB** | TimescaleDB 2.16（行情 + 25 表 + audit hash chain）+ Qdrant 1.9（7 collections，新聞 RAG）+ Redis 7（cache / queue / pubsub / blacklist / ws ticket / rate limit / idempotency） |
| **LLM** | Gemini 2.0 Flash（預設、最便宜）+ GPT-4o-mini（fallback 第 2）+ Claude Haiku 3.5（fallback 第 3）+ CB 自動切換 |
| **資料源** | TW：FinMind / TWSE / TPEX / MOPS / cnyes RSS；US：yfinance / Alpha Vantage / Finnhub / SEC EDGAR |
| **部署** | Docker Compose（prod 8 services）+ nginx（HTTPS + WS / SSE）+ self-signed cert |
| **觀測性** | structlog JSON + trace_id 全鏈路 + Prometheus metrics + 每日 SLO 報表 |

---

## 📊 v1.0 完成度

整體計劃 21 個 Phase（P0-P20）100% 完成：

| 階段 | Phase | 主題 | 狀態 |
|------|-------|------|------|
| 準備 | P0 | 環境驗證 | ✅ |
| 基礎設施 | P1-P3 | 骨架、Docker、後端基礎 | ✅ |
| 資料層 | P4-P7 | Schema、TW、US、Celery | ✅ |
| 後端 API | P8-P11 | Auth、安全 middleware、業務 API（28+50 endpoints） | ✅ |
| AI Agent | P12-P14 | LangGraph、TW Analyst、US Analyst + LLM fallback | ✅ |
| 前端 | P15-P17 | 基礎、核心 8 頁、進階 15 頁 | ✅ |
| 強化 + 部署 | P18-P19 | OWASP、通知、prod compose、DR 演練 | ✅ |
| 驗證 + 結案 | P20 | 全面驗證 + 完整報告 + Release | ✅ |

詳見 [docs/phase_progress.md](docs/phase_progress.md) 與 [docs/PROJECT_FINAL_REPORT.md](docs/PROJECT_FINAL_REPORT.md)。

---

## 📋 文件目錄

### 入門
- **[連線指南](docs/connection-guide.md)** — 第一次使用必看（10 步驟）
- **[使用者指南](docs/user-guide.md)** — 18 頁操作 + 完整 FAQ
- [docs/setup.md](docs/setup.md) — 開發環境設定

### 規劃 / 設計
- **[PLAN.md](PLAN.md)** — 完整實施計劃 v7.0（21 Phase 詳細 prompt，10844 行）
- [docs/engineering-standards.md](docs/engineering-standards.md) — 工程規範
- [docs/contributing.md](docs/contributing.md) — 貢獻指南

### 結案 / 報告
- **[docs/PROJECT_FINAL_REPORT.md](docs/PROJECT_FINAL_REPORT.md)** — v1.0 結案報告（最重要！）
- [docs/phase_progress.md](docs/phase_progress.md) — Phase 執行進度
- [docs/phase_reports/PHASE_NN.md](docs/phase_reports/) — 21 份 Phase 完成報告

### 維運（runbooks）
- [services.md](docs/runbooks/services.md) / [migrations.md](docs/runbooks/migrations.md) / [auth.md](docs/runbooks/auth.md) / [security.md](docs/runbooks/security.md)
- [data_sources.md](docs/runbooks/data_sources.md) / [llm_providers.md](docs/runbooks/llm_providers.md) / [agents.md](docs/runbooks/agents.md)
- [api.md](docs/runbooks/api.md) / [exports.md](docs/runbooks/exports.md) / [frontend_pages.md](docs/runbooks/frontend_pages.md)
- [prod_deployment.md](docs/runbooks/prod_deployment.md) / [backup_restore.md](docs/runbooks/backup_restore.md) / [disaster_recovery.md](docs/runbooks/disaster_recovery.md)
- [secret_rotation.md](docs/runbooks/secret_rotation.md) / [pentest_checklist.md](docs/runbooks/pentest_checklist.md) / [obsidian_setup.md](docs/runbooks/obsidian_setup.md)

### 安全
- **[SECURITY.md](SECURITY.md)** — v1.0 安全政策 + 已接受風險
- [SECURITY_FIXES.md](SECURITY_FIXES.md) — 安全修補歷史
- [CHANGELOG.md](CHANGELOG.md) — 完整變更紀錄

---

## 🔒 安全亮點

- **DB 三帳號分離**：migration（DDL）/ service_rw（業務）/ agent_ro（Agent 只讀） — 防 prompt injection
- **JWT 雙 key rotation + Redis blacklist**（DB3）+ **CSRF double-submit cookie** + **WS Ticket**（不在 URL）
- **bcrypt cost=12** + **Lockout**（5 fail / 15min）+ 密碼策略（≥12/4 類/email check/最近 5 次）
- **6 層 Rate Limit**（L1 global / L2 login / L3 password reset / L4 idempotency / L5 ws / L6 admin）
- **Audit hash chain**（PG trigger 自動串鏈，每日 verify）+ 不可竄改
- **Fernet 加密**敏感欄位（LINE / Telegram token）
- **CSP nonce-based**（prod，per-request token_urlsafe 16 + strict-dynamic）
- **TLS 1.2/1.3 only** + nginx security headers
- **Container 非 root**（uid 1000）+ **cap_drop ALL** + **read-only fs**
- **OWASP Top 10 + Pen test checklist** 全綠
- **SSRF validate_safe_url**（file:// / 私有 IP / metadata service blocklist）

詳見 [SECURITY.md](SECURITY.md)。

---

## 🛣 後續路線圖

依 [PLAN.md 第 33 章](PLAN.md)：

### v1.1（1-2 個月）
calendar / compare / backtest 真實後端、Email 通知、自動匯出到 Obsidian、法說會 Whisper、美股 13F & insider、AI 對話介面

### v1.2（3-6 個月）
英文 UI、2FA TOTP、IP 白名單、自定義警報、LINE Bot 雙向、港股

### v2.0（6-12 個月）
多用戶多組織、即時分鐘 K、Prometheus + Grafana + OpenTelemetry、Kubernetes、真實券商 API（仍手動核准）、行動 App、A 股 / 日股、AI Trading Bot 自動策略

---

## 💰 v1.0 成本（自用單機）

- **LLM**：~$5-10/月（Gemini Flash 為主，每月 ~50 個分析）
- **資料源**：$0（FinMind 免費 token + Alpha Vantage 免費版 5 次/分鐘）
- **主機**：$0（自用伺服器；雲端 VM 約 $20-40/月）
- **合計**：**~$5-10/月**（遠低於原規劃 $154）

詳見 [docs/PROJECT_FINAL_REPORT.md](docs/PROJECT_FINAL_REPORT.md) 第 7 節。

---

## 🤝 關於原版

本專案改造自 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) v0.2.4。

原版套件碼已遷移至 `legacy/` 目錄保留作參考，**不會被 v1.0 直接 import**：

- `legacy/tradingagents/` — 原版 agents、graph、dataflows
- `legacy/cli/` — 原版 CLI
- `legacy/tests/` — 原版測試
- `legacy/README_original.md` — 原版完整 README

詳見 [legacy/README.md](legacy/README.md)。

---

## License

[Apache License 2.0](LICENSE) — 沿用原版。

## Acknowledgments

- [Tauric Research](https://github.com/TauricResearch)) — 原版 v0.2.4 基礎
- 本台股版本（TradingAgents-TW）由 [PLAN.md v7.0](PLAN.md) 規劃並依此實作完成

---

**v1.0.0 — Release Ready — 2026-05-18**
