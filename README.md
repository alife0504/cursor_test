# TradingAgents-TW Secure Edition v0.3.0

> 多 Agent AI 投資分析平台 — **台股主、美股輔、繁中 UI、安全架構優先**
>
> 改造自 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) v0.2.4，原版已備份於 `legacy/`

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Node 20](https://img.shields.io/badge/node-20-green.svg)](https://nodejs.org/)
[![TimescaleDB 2.16](https://img.shields.io/badge/TimescaleDB-2.16-orange.svg)](https://www.timescale.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js 14.2](https://img.shields.io/badge/Next.js-14.2-black.svg)](https://nextjs.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## 願景

打造**正式產品等級**、**台股主、美股輔**的多 Agent AI 投資分析平台：

- 4 種 Analyst（技術面 / 基本面 / 新聞面 / 籌碼面）跨市場辯論
- 18 頁繁中 UI、AI 流程動態視覺化
- 手動核准下單（不直連券商）
- Audit 不可竄改 hash chain、JWT + CSRF + WS Ticket 多層認證
- LINE / Telegram 通知、PDF / MD / XLSX 匯出

---

## 技術棧

| 層 | 技術 |
|----|------|
| **前端** | Next.js 14.2 + TypeScript + shadcn/ui + Tailwind + lightweight-charts + @xyflow/react |
| **後端** | FastAPI 0.115 + LangGraph 0.2.50 + Celery 5.4 + Pydantic v2 + SQLAlchemy 2.0 |
| **DB** | TimescaleDB 2.16（行情 + 審計）+ Qdrant 1.9（新聞 RAG）+ Redis 7（快取/Queue） |
| **LLM** | Gemini 2.0 Flash（預設）+ OpenAI / Anthropic（fallback chain） |
| **資料源** | FinMind / TWSE / TPEX / MOPS / cnyes（台股）+ yfinance / Alpha Vantage / Finnhub / SEC EDGAR（美股） |
| **部署** | Docker Compose + nginx + Let's Encrypt（自架 / 自用） |

---

## 快速啟動

詳見 [docs/setup.md](docs/setup.md)。

```bash
# 1. 環境驗證（PowerShell on Windows）
docker --version && uv --version && node --version

# 2. 切到 phase 開發分支（依當前進度）
git checkout phase/01-migration-and-skeleton

# 3. backend 依賴
cd backend && uv sync && uv run pre-commit install && cd ..

# 4. 後續 Phase 完成後（依 docs/phase_progress.md 進度）：
make up                # P2 完成後
make init-db           # P4 完成後
make seed-stocks       # P7 完成後
make backend-dev       # P3 完成後
make frontend-dev      # P15 完成後
```

> ⚠️ **Phase 1 起所有 Bash 指令請在 Git Bash / WSL 中執行**（PowerShell 不支援部分語法）。

---

## 目前進度

詳見 [docs/phase_progress.md](docs/phase_progress.md)。

整體計劃分 21 個 Phase（P0-P20），詳見 [PLAN.md](PLAN.md)：

| 階段 | Phase | 主題 | 狀態 |
|------|-------|------|------|
| 準備 | P0 | 環境驗證 | ✅ |
| 基礎設施 | P1-P3 | 骨架、Docker、後端基礎 | 🚧 P1 進行中 |
| 資料層 | P4-P7 | Schema、TW、US、Celery | ⏳ |
| 後端 API | P8-P11 | Auth、安全、業務 API | ⏳ |
| AI Agent | P12-P14 | LangGraph、Analyst、串流 | ⏳ |
| 前端 | P15-P17 | 基礎、核心頁、進階頁 | ⏳ |
| 強化 + 部署 | P18-P19 | 安全、通知、測試、部署 | ⏳ |
| 驗證 + 結案 | P20 | 全面驗證 + 報告 | ⏳ |

預估投入：**30-40 天 calendar time**（每天 5 小時 = 1 個 Phase）

預估月運行成本：**~$154 USD**（FinMind $99 + Alpha Vantage $50 + Gemini $5）

---

## 文件目錄

| 文件 | 用途 |
|------|------|
| [PLAN.md](PLAN.md) | 完整實施計劃（v7.0，21 個 Phase 詳細 prompt） |
| [docs/setup.md](docs/setup.md) | 開發環境設定 |
| [docs/engineering-standards.md](docs/engineering-standards.md) | 工程規範（logging、error、API、測試、Git） |
| [docs/contributing.md](docs/contributing.md) | 貢獻指南（commit 格式、PR 流程） |
| [docs/phase_progress.md](docs/phase_progress.md) | Phase 執行進度追蹤 |
| [docs/phase_reports/](docs/phase_reports/) | 每 Phase 完成報告 |
| [docs/runbooks/](docs/runbooks/) | 運維手冊（後續 Phase 補） |
| [legacy/README.md](legacy/README.md) | 原版 v0.2.4 用途說明 |
| [SECURITY.md](SECURITY.md) | 安全政策 |
| [LICENSE](LICENSE) | Apache 2.0 |

---

## 關於原版

本專案改造自 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) v0.2.4。

原版套件碼已遷移至 `legacy/` 目錄保留作參考，**不會被新版直接 import**：

- `legacy/tradingagents/` — 原版 agents、graph、dataflows
- `legacy/cli/` — 原版 CLI
- `legacy/tests/` — 原版測試
- `legacy/README_original.md` — 原版完整 README

詳見 [legacy/README.md](legacy/README.md)。

緊急回到原版狀態：

```bash
git checkout pre-tw-edition-backup
```

---

## License

[Apache License 2.0](LICENSE) — 沿用原版。

## Acknowledgments

感謝 [Tauric Research](https://github.com/TauricResearch) 提供 v0.2.4 原版基礎。
本台股版本（TradingAgents-TW）由 v7.0 PLAN 規劃下實作。
