# Legacy: 原版 TradingAgents (v0.2.4)

此目錄保留改造前的原版套件作為參考。

## 內容

- `tradingagents/` — 原版 Python 套件（agents/, graph/, llm_clients/, dataflows/）
- `cli/` — 原版 CLI 入口
- `tests/` — 原版測試
- `scripts/` — 原版工具腳本（注意：與新版 `scripts/` 同名但內容完全不同）
- `main.py`, `test.py` — 原版範例入口
- `pyproject.toml`, `requirements.txt`, `requirements.lock`, `uv.lock` — 原版套件定義
- `Dockerfile`, `docker-compose.yml` — 原版容器配置
- `setup.bat`, `setup.ps1`, `start.bat`, `start.ps1`, `add_to_path.bat` — 原版啟動腳本
- `assets/` — 原版圖檔（README 用）
- `.dockerignore`, `.env.enterprise.example` — 原版設定範例

## 用途說明

1. **Phase 13 LangGraph Agent 系統時參考結構**：
   - `tradingagents/agents/analysts/*.py` — Analyst prompt 結構參考（**v7 改繁中、加台股脈絡**）
   - `tradingagents/agents/researchers/*.py` — Bull/Bear 辯論結構參考
   - `tradingagents/agents/managers/research_manager.py` — 結構化輸出模式參考
   - `tradingagents/graph/setup.py` — LangGraph StateGraph 構造參考
   - `tradingagents/agents/utils/agent_states.py` — TypedDict 狀態設計參考

2. **不要做的事：**
   - ❌ 不要 `from legacy.tradingagents import ...`（架構已大改）
   - ❌ 不要直接 import 此處任何程式碼到新後端（`backend/app/`）
   - ❌ 不要修改此目錄內檔案（保留原版作對照）

## 完整原版回到方式

```bash
git checkout pre-tw-edition-backup
```

## 為什麼保留

- 保留 git history（user 要求）
- 原版 agent prompt 經驗有參考價值
- 萬一 v1.0 改造嚴重失敗，可作 fallback 還原點
