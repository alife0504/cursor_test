# Phase 13 — 4 種台股 Analyst 完整化 + Bull/Bear/Manager + 結構化輸出

> 狀態：✅ 完成
> 分支：`phase/13-tw-analysts`
> 完成日期：2026-05-16
> PLAN.md 章節：第二十七章 ▌Phase 13（必讀第 4.4 / 8.5 / 10.5 / 14.4 / 14.9 / 18.2 / 20.3-20.4）

---

## 1. 範圍

Phase 13 把 P12 的「LangGraph 框架」升級為**端到端可跑的台股完整分析**：4 個 Analyst 全部接真實 LLM、加上 Bull/Bear 多輪辯論、ResearchManager 結構化決策、token usage 記錄到 DB。

### 1.1 完成的 10 個目標

1. ✅ **12 個 prompt 模板**集中放在 `app/agents/prompts/`（8 個 system + 4 個 user_tw）+ `prompts_loader.py`（importlib + `format_map` + SafeDict）
2. ✅ **7 個 Pydantic schema**（`schemas.py`）：MarketAnalysisResult / FundamentalAnalysisResult / NewsAnalysisResult / SentimentAnalysisResult / BullArgument / BearArgument / FinalSignal — 全部嚴格 validation + Decimal 自動序列化（取代已棄用的 `json_encoders`）
3. ✅ **`llm_helpers.py`**：`extract_json_block`（多 fence 容錯）+ `llm_call_with_schema`（自動 repair retry，最多 2 次）+ `record_llm_usage` / `record_llm_usage_sync`（async / sync 雙版）
4. ✅ **`indicators.py`**：RSI(14) / MACD(12,26,9) / KD(9) / BBANDS(20,2σ) / MA(20/60)，純 numpy + pandas，無 ta-lib 依賴；`compute_indicators(ohlcv)` 統一 entry
5. ✅ **4 個 Analyst 完整版**（覆寫 P12 stub）：每個都走 tools → 後端算指標/比率 → 渲染 prompt → LLM with schema → 寫 llm_usage
   - MarketAnalyst：60 日 OHLCV + indicators
   - FundamentalAnalyst：4 季財報 + 月營收 (TW) + ratio
   - NewsAnalyst：7 日新聞 + 30 日公告（無新聞時回中性 stub，不 raise）
   - SentimentAnalyst：30 日三大法人 + 融資融券 + 月營收（TW only, US 上呼叫 raise）
   - **向下相容**：若 `llm=None` → 回 `[stub]`（不破壞 P12 graph 測試）
6. ✅ **BullResearcher / BearResearcher**：吃所有 analyst 結論 + 對方上一輪論點，依輪次累積 `bull_arguments` / `bear_arguments` 與 `debate_history`
7. ✅ **ResearchManager**：綜合所有 analyst + debate → FinalSignal（action / confidence / target_price_low/high / stop_loss / time_horizon / position_size_pct / debate_winner / reasoning_zh）+ 渲染最終 Markdown 報告
8. ✅ **graph_builder 升級**：加入 bull/bear/manager 節點 + `add_conditional_edges` 控制多輪辯論；`llm=None` → 走 placeholder_manager 保留 P12 相容
9. ✅ **`run_analysis` Celery task 升級為真實版**：accept `analyst_types` / `debate_rounds` kwargs，跑完 graph 寫回 DB（signal / report_md / confidence / target_price / stop_loss / take_profit / total_tokens / total_cost_usd）；cost 從 `llm_usage` 表彙總
10. ✅ **P11 bug fix**：`ALLOWED_ANALYST_TYPES` 把 `social` → `sentiment`（與 SentimentAnalyst.name 對齊），讓 spec 範例 `["market","fundamental","news","sentiment"]` 通過驗證

### 1.2 P13 範圍外（後續 Phase）

| 項目 | 完成 Phase |
|------|-----------|
| 美股 Analyst 共用 class（複用 4 個 analyst） | P14 |
| LLM Fallback Chain（OpenAI / Anthropic） | P14 |
| WS streaming events（即時辯論過程推送） | P14 |
| LLM 月配額（$50/user） | P14 |
| Redis checkpointer | P14 |
| Qdrant similarity search 用於 NewsAnalyst | P14 加強 |

---

## 2. 新增 / 修改檔案

### 2.1 新增

| 路徑 | 行數（概） | 說明 |
|------|-----------|------|
| `backend/app/agents/prompts/__init__.py` | 12 | prompts package marker |
| `backend/app/agents/prompts/*.txt` (12 個) | ~250 | system / user 模板 |
| `backend/app/agents/prompts_loader.py` | 58 | `load_prompt` + `render_template` |
| `backend/app/agents/schemas.py` | 175 | 7 個 Pydantic schema |
| `backend/app/agents/llm_helpers.py` | 270 | `llm_call_with_schema` + `record_llm_usage` |
| `backend/app/agents/indicators.py` | 250 | RSI/MACD/KD/BBANDS/MA |
| `backend/app/agents/researchers/__init__.py` | 12 | exports |
| `backend/app/agents/researchers/bull_researcher.py` | 130 | BullResearcher |
| `backend/app/agents/researchers/bear_researcher.py` | 110 | BearResearcher |
| `backend/app/agents/managers/__init__.py` | 8 | exports |
| `backend/app/agents/managers/research_manager.py` | 175 | ResearchManager + render_report_md |
| `backend/tests/unit/test_indicators.py` | 200 | 13 個測試 |
| `backend/tests/unit/test_schemas.py` | 270 | 18 個測試 |
| `backend/tests/unit/test_llm_helpers.py` | 200 | 10 個測試 |
| `backend/tests/integration/test_market_analyst.py` | 200 | 5 個測試 |
| `backend/tests/integration/test_full_tw_pipeline.py` | 290 | 3 個測試 |
| `backend/tests/integration/test_real_llm_2330.py` | 70 | 1 個測試（@network @expensive） |
| `scripts/health_checks/phase_13.sh` | 290 | 12 項健康檢查 |
| `docs/phase_reports/PHASE_13.md` | 本檔 | Phase 報告 |

### 2.2 修改

| 路徑 | 變更 |
|------|------|
| `backend/app/agents/analysts/market_analyst.py` | stub → 真實版（OHLCV + indicators + LLM） |
| `backend/app/agents/analysts/fundamental_analyst.py` | stub → 真實版（financial + ratios + LLM） |
| `backend/app/agents/analysts/news_analyst.py` | stub → 真實版（news/announcement + LLM） |
| `backend/app/agents/analysts/sentiment_analyst.py` | stub → 真實版（institutional/margin/monthly_rev + LLM） |
| `backend/app/agents/graph_builder.py` | 加入 bull/bear/manager 節點 + conditional edge |
| `backend/app/workers/tasks/run_analysis.py` | stub → 真實 pipeline + DB 寫回 |
| `backend/app/core/database.py` | 新增 `rw_session` async context manager |
| `backend/app/schemas/analysis.py` | P11 bug fix：`social` → `sentiment` |
| `backend/app/api/v1/analysis_router.py` | 透過 task kwargs 傳遞 analyst_types / debate_rounds |
| `docs/phase_progress.md` | 標記 P13 完成 |

---

## 3. 驗證結果

### 3.1 phase_13.sh 12 項全綠

```
=== Phase 13 健康檢查 ===
✓ Phase 12 健康檢查仍綠
✓ uv sync + ruff lint 通過
✓ /health/live 200
✓ 4 個 Analyst 全部非 stub（含 tool call + llm_call_with_schema）
✓ 12 個 prompt + 7 個 schema 載入完整
✓ P13 unit + integration 測試全綠
✓ POST /analysis (含 sentiment) 推 task：analysis_id=...
✓ graph_builder 含 bull/bear/manager node
✓/⚠ 真 LLM 測試（取決於 .env 是否有 GOOGLE_API_KEY）
✓ llm_usage schema 完整（5 個關鍵欄位）
✓ 累積測試 604 ≥ 595
✓ run_analysis 接受 analyst_types/debate_rounds kwargs

✅ Phase 13 健康檢查全部通過
```

### 3.2 測試統計

- P12 累積：554 tests
- P13 新增：50 tests（13 indicators + 18 schemas + 10 llm_helpers + 5 market_analyst + 3 full_tw_pipeline + 1 real_llm）
- **P13 累積：604 tests**（600 passed + 1 skipped (docker 探活) + 3 deselected（@network/@expensive））

### 3.3 P12 路徑回歸測試

跑 `test_graph_builder.py` (7 個) + `test_analysis_pipeline_stub.py` (4 個) + `test_state_trim.py` (5 個) + `test_tool_registry.py` (10 個) + `test_gemini_provider.py` (8 個) = **34 個 P12 測試全部仍綠**（無回歸）。

---

## 4. 重大設計決策

### 4.1 為何用「文字 JSON + repair retry」而非 Provider-side structured output？

LangChain v0.3 在 Gemini 上的 `with_structured_output` 偶有抖動（特別是 nested model + Decimal）。我們改用「明確要求 ```json``` block + Pydantic validate + 失敗時帶錯誤訊息 repair retry」，較穩定且跨 provider 一致。

### 4.2 為何 Analyst 在 `llm=None` 時回 stub？

P12 graph 測試（`test_stub_graph_invocation_completes` 等）假設 graph 可以無 LLM 跑完。為了不破壞既有測試與框架可測性，4 個 analyst 在 `self.llm is None` 時 graceful 回 stub。

### 4.3 為何 `analyst_types` / `debate_rounds` 透過 celery task kwargs 傳遞，而非寫入 `analysis_reports` 表？

DB 模型未存這兩欄位，audit_logs.details 讀取脆弱（schema 變動風險）；改用 task kwargs：
- API 收 request → 直接 enqueue 帶 kwargs
- celery worker 拿到 kwargs 後直接傳給 build_graph
- 無 migration 風險，調整 default 也容易

### 4.4 為何不算 PE / PB（只算 ROE / 毛利率）？

PE / PB 需要 spot price，FundamentalAnalyst 設計上不抓 OHLCV（避免越權）。Spot price 由 LLM 從 user prompt 內提供（若 prompt 沒給就回 null）。

### 4.5 Decimal 序列化策略

Pydantic v2 的 `model_dump(mode="json")` 預設會把 Decimal 序列化為 str（無需 `json_encoders`，後者已 deprecate 將於 v3 移除）。`FinalSignal.target_price_low` 等 `Decimal | None` 欄位在 LLM 回 `"null"` / `"N/A"` 等字串時用 `field_validator` coerce 成 None。

---

## 5. 已知限制

1. **真 LLM call 一次 ~$0.005~$0.02**（4 analyst + 1 round bull/bear + manager = 7 次 LLM call）
2. **Qdrant similarity search 尚未整合到 NewsAnalyst**（PLAN 20.3-20.4）。目前 NewsAnalyst 僅查 SQL metadata；qdrant 在 P14 加強。
3. **無 streaming events**：state 與 debate 過程在 graph 跑完前不會推到前端（P14 加 WS pubsub）。
4. **無 cost 上限**：跑完才計算總 cost；P14 加月配額 $50/user 並在跑前評估。
5. **PE / PB 缺 spot price**：fundamental 不抓 OHLCV，需 LLM 從 prompt 引用或在 P14 提供 spot_price field。
6. **Pydantic v2 PydanticDeprecatedSince20 警告**：來自 langchain 內部，與本專案無關。

---

## 6. P14 啟動提醒

1. **介面已凍結**：BaseAnalyst / BaseLLMProvider / FinalSignal schema / ToolRegistry / graph_builder signature 不會在 P14 中途改動。
2. **新加美股 Analyst**：可複用既有 4 個 class（market/fundamental/news 已 `supported_regions=[TW,US]`，只需 prompt 補 US 版）。
3. **LLM Fallback Chain**：直接在 `llm_call_with_schema` 外面套一層 try/except → 依 `LLM_FALLBACK_CHAIN`（PLAN 14.4）轉 provider 即可。
4. **WS streaming**：每個 analyst 結束時呼叫 `_publish_event` 推到 `analysis:{id}` channel；前端 WS 連這個 channel 接 SSE-style events。
5. **月配額**：跑前查 `llm_monthly_quota.used_usd` ≥ budget → raise；跑後 update used_usd。
6. **避免 prompt 直接拼 user 資料**：所有 user content 都要走 escape（PLAN 19）。
