# Phase 12 — LangGraph 基礎 + Plugin + State trim + Tool 註冊

> 狀態：✅ 完成  
> 分支：`phase/12-langgraph-foundation`  
> 完成日期：2026-05-16  
> PLAN.md 章節：第二十七章 ▌Phase 12（必讀第 4.4 / 6.1 / 8.5 / 14.4 / 14.9 / 18.2 / 19 / 20.4）

---

## 1. 範圍

Phase 12 建立「LangGraph 與 Tool 框架」，**不**寫 Analyst 真實 prompt（P13）；
**不**接 Bull/Bear/Manager（P13）；**不**接美股 Analyst 與 LLM Fallback Chain（P14）。

### 1.1 完成的 10 個目標

1. ✅ `AgentState` TypedDict（含 `Annotated[list, add]` reducer + dict 累積 reducer）
2. ✅ `BaseAnalyst` Plugin + `ANALYST_REGISTRY` + `@register_analyst` 裝飾器
3. ✅ 4 種台股 Analyst stub：market / fundamental / news / sentiment
4. ✅ ToolRegistry（8 個 method：OHLCV / company_info / financial / news /
   announcements / institutional / margin / monthly_revenue）
5. ✅ Tools 全部走 `ta_agent_ro` 對應 sessionmaker（防 prompt injection）
6. ✅ State trim 邏輯（`trim_debate_history` + `estimate_state_size`）
7. ✅ `BaseLLMProvider` 抽象 + Gemini 實作 + `LLM_PROVIDER_REGISTRY`
8. ✅ `build_graph(symbol, market)` 函數骨架（含 region 過濾）
9. ✅ Celery `run_analysis` task 接 LangGraph（P12 跑 stub）
10. ✅ `POST /api/v1/analysis` 升級為實際推 celery task

### 1.2 P12 範圍外（後續 Phase）

| 項目 | 完成 Phase |
|------|-----------|
| 4 種 Analyst 真實 prompt | P13 |
| Bull/Bear/Manager Researcher | P13 |
| 結構化輸出 schema（signal/confidence/target_price/...） | P13 |
| 美股 Analyst 共用 class | P14 |
| LLM Fallback Chain（OpenAI/Anthropic） | P14 |
| WS streaming events | P14 |
| LLM 月配額 ($50/user) | P14 |
| Redis checkpointer（state persistence） | P14 |

---

## 2. 新增 / 修改檔案

### 2.1 新增

| 路徑 | 用途 |
|------|------|
| `backend/app/agents/__init__.py` | agents package 入口 |
| `backend/app/agents/state.py` | `AgentState` TypedDict + reducer |
| `backend/app/agents/base_analyst.py` | `BaseAnalyst` ABC + Registry |
| `backend/app/agents/analysts/__init__.py` | 4 個 Analyst side-effect import |
| `backend/app/agents/analysts/market_analyst.py` | 技術面（TW+US）stub |
| `backend/app/agents/analysts/fundamental_analyst.py` | 基本面（TW+US）stub |
| `backend/app/agents/analysts/news_analyst.py` | 新聞/公告面（TW+US）stub |
| `backend/app/agents/analysts/sentiment_analyst.py` | 籌碼面（TW only）stub |
| `backend/app/agents/tools/__init__.py` | ToolRegistry + 8 個 method |
| `backend/app/agents/state_trim.py` | trim_debate_history |
| `backend/app/agents/graph_builder.py` | build_graph + placeholder_manager |
| `backend/app/llm/__init__.py` | LLM package 入口 |
| `backend/app/llm/base_provider.py` | BaseLLMProvider + LLMResponse + TokenUsage + Registry |
| `backend/app/llm/gemini_provider.py` | GeminiProvider |
| `backend/app/workers/tasks/run_analysis.py` | Celery run_analysis task |
| `backend/tests/unit/test_state_trim.py` | state trim 測試（5 個）|
| `backend/tests/unit/test_graph_builder.py` | build_graph + manager 測試（7 個）|
| `backend/tests/unit/test_tool_registry.py` | ToolRegistry 測試（10 個）|
| `backend/tests/unit/test_gemini_provider.py` | Gemini Provider 測試（8 個）|
| `backend/tests/integration/test_analysis_pipeline_stub.py` | end-to-end stub（4 個）|
| `scripts/health_checks/phase_12.sh` | Phase 12 健康檢查（11 項）|
| `docs/phase_reports/PHASE_12.md` | 本檔案 |
| `docs/runbooks/agents.md` | Agents debug runbook |

### 2.2 修改

| 路徑 | 變更 |
|------|------|
| `backend/pyproject.toml` | 加 langgraph (<0.3) + langchain-core 0.3 + langchain-google-genai 2.x + tiktoken |
| `backend/app/core/database.py` | 新增 `ro_session()` async context manager（給 Agent/Tool 用）|
| `backend/app/api/v1/analysis_router.py` | POST 新增 `_enqueue_run_analysis()` 推 celery task |
| `backend/app/workers/celery_app.py` | `include` 新增 `app.workers.tasks.run_analysis` |
| `docs/phase_progress.md` | P12 標記完成 |

---

## 3. 設計重點

### 3.1 AgentState reducer

```python
class AgentState(TypedDict, total=False):
    # 累積欄位
    analyses: Annotated[dict[str, str], merge_dict]
    debate_history: Annotated[list[dict], add]
    bull_arguments: Annotated[list[str], add]
    bear_arguments: Annotated[list[str], add]
    # 終結欄位（最後 node 寫一次）
    signal: dict | None
    report_md: str | None
```

- 用 `Annotated[..., reducer]` 讓 LangGraph 自動處理多 node 寫入同欄位的合併。
- `merge_dict` 對 `analyses` 做淺合併（避免 overwrite）。
- `add`（`operator.add`）對 list 做 append。

### 3.2 Plugin Pattern（依 PLAN 18.2）

- `@register_analyst` 裝飾器自動把子類進 `ANALYST_REGISTRY`。
- `BaseAnalyst.can_handle(region)` 由 `graph_builder` 用來過濾。
- `LLM_PROVIDER_REGISTRY` 與 `@register_llm_provider` 同模式。

### 3.3 安全核心：Tool 用 ta_agent_ro

- `ToolRegistry(ro_sessionmaker)` 強制注入 ro_sessionmaker。
- ro session 對應 `ta_agent_ro` DB 帳號（PLAN 19.1），DB 層阻止任何 DML。
- `_assert_tw_only()` 對 TW-only tool（institutional/margin/monthly_revenue）做 region 檢查。
- 額外的範圍 validator：days_back / months_back 上下限，防 LLM 亂塞極大數字。

### 3.4 跨市場過濾

- `SentimentAnalyst.supported_regions = [MarketRegion.TW]`
- TW symbol → 4 個 Analyst 都跑；US symbol → market/fundamental/news 跑（無 sentiment）。
- region 來源優先：`detect_region(symbol)`（不一致時警告但不報錯）。

### 3.5 State trim 策略

- `MAX_DEBATE_HISTORY = 6`：超過則前面壓縮為一段 LLM summary。
- 沒提供 LLM（測試 / P12 stub） → 截斷 fallback，仍可正常運作。
- `trim_debate_history` 回**新 state**（不 mutate 原 state，遵守 LangGraph reducer 慣例）。

### 3.6 Cost 計算

- `BaseLLMProvider.pricing: dict[model_id, (input/1k, output/1k)]`
- `calc_cost(model, input_tokens, output_tokens) → Decimal`，quantize 到 6 位（與 DB `total_cost_usd` Numeric(12,6) 一致）。
- 未知 model → 回 0 + warning，不 raise（避免新模型發布時系統炸）。

### 3.7 run_analysis task 異步模式

- 不用 `asyncio.run()` 而是 `asyncio.new_event_loop() + run_until_complete`，避免在 celery worker 中重建 loop 的 RuntimeWarning。
- 每個 task 新建一份 async ro engine（不共用，避免跨 event loop 衝突）。
- 失敗 → 寫 `status='failed' + error_msg`；orphan cleanup 兜底（PLAN 15.4）。
- `max_retries=0`：LangGraph 多半是邏輯 / quota 錯誤，retry 浪費 LLM cost。

---

## 4. 測試覆蓋

| 檔案 | 測試數 | 重點 |
|------|--------|------|
| `tests/unit/test_state_trim.py` | 5 | size 估算、無 LLM fallback、LLM 摘要、不 mutate 原 state |
| `tests/unit/test_graph_builder.py` | 7 | 4 註冊、TW 含 sentiment / US 不含、analyst_types 過濾、stub graph 跑通 |
| `tests/unit/test_tool_registry.py` | 10 | 8 tool mock session、TW-only 阻擋 US、validator 範圍、langchain wrap |
| `tests/unit/test_gemini_provider.py` | 8 | registry 註冊、cost 計算、health_check、未知 model fallback |
| `tests/integration/test_analysis_pipeline_stub.py` | 4 | end-to-end stub TW/US、signal/started_at、空 analyst_types |

**累積：** 518 + 34 = **552 tests**（達標 ≥ 535）

---

## 5. 完成驗收

依 Phase 12 prompt【5. 完成驗收】11 個指令：

| # | 驗收項目 | 結果 |
|---|---------|------|
| 1 | uv sync + ruff lint | ✓ |
| 2 | 啟動 backend + worker | ✓ |
| 3 | 啟動 celery worker | ✓ |
| 4 | 4 種 analyst 註冊 | ✓ |
| 5 | TW graph 含 sentiment | ✓ |
| 6 | US graph 不含 sentiment | ✓ |
| 7 | ro session 阻止 INSERT | ✓ |
| 8 | POST /analysis 推 celery task | ✓ |
| 9 | 30 秒後 status=completed/running | ✓ |
| 10 | 全部新測試通過 | ✓ |
| 11 | health_check phase_12 通過 | ✓ |

---

## 6. 已知限制與 P13/P14 接續

- ⚠ Analyst 都是 stub（回 `[stub]` 開頭文字）；P13 接 LLM。
- ⚠ Manager 是 placeholder（report_md 為固定模板 + signal=HOLD/confidence=50）；P13 改結構化輸出。
- ⚠ 無 checkpointer（state 重啟即失）；P14 加 Redis checkpointer。
- ⚠ token usage 用 tiktoken `gpt-4` encoder 粗估（誤差 ~10%，PLAN 14.9 已知陷阱）。
- ⚠ Pricing 表抓取於 2026-05；Gemini 改價需更新 `gemini_provider.py:pricing`。
- ⚠ 月配額（$50/user）尚未強制（P14 才加 rate-limit L6）。

### 6.1 P13 預計事項

- 替換 4 個 Analyst stub 為真實 prompt（拉資料 → LLM 解讀 → 結構化輸出）。
- 新增 Bull/Bear Researcher（debate loop）+ Manager Researcher（結構化整合）。
- graph 從 sequential 改 parallel Analyst + 然後 debate loop。

### 6.2 P14 預計事項

- 美股 Analyst 共用 class（market/fundamental/news 沿用；sentiment 留 v1.1）。
- LLM Fallback Chain（PLAN 14.4）：google → openai → anthropic。
- WS streaming events（Redis pubsub → frontend）。
- 月配額（rate-limit L6）+ daily LLM cost metric。

---

## 7. Smoke Test 記錄

✓ `ipython` 中 `build_graph("2330", "TWSE").get_graph().draw_mermaid()` 看 graph 結構  
✓ stub Analyst 跑一次 analysis：celery worker log 顯示 `run_analysis.start` → `run_analysis.done`  
✓ `debate_history` 累積 10 筆 → `trim_debate_history` 後變 7 筆（1 summary + 6 recent）  
✓ ro session 嘗試 INSERT → permission denied / read-only transaction，不會炸服務  

---

## 8. Git tag

```bash
git tag phase-12-complete
```
