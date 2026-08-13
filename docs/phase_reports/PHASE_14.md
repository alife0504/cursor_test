# Phase 14 — 美股 Analyst + LLM Provider Fallback Chain + WS 串流 + 月配額

> 狀態：✅ 完成
> 分支：`phase/14-us-analyst-llm-fallback`
> 完成日期：2026-05-17
> PLAN.md 章節：第二十七章 ▌Phase 14（必讀第 8.5 / 10 / 14.4 / 16.2 / 18.2 / 19.3）

---

## 1. 範圍

Phase 14 把 P13 的「TW 完整版」升級為**真正的跨市場、生產級可靠**：美股端到端可跑、LLM 三家備援、WebSocket 即時推送辯論過程、月配額卡關控制成本。

### 1.1 完成的 8 個目標

1. ✅ **美股 3 種 Analyst**（market / fundamental / news；無 sentiment）— **共用 class 寫法**，在 prompt 模板層分台股/美股（依 PLAN 10.5 章 Analyst × 市場）。新增 3 個 us_template，欄位 schema 完全相容台股版，但加入「美股市場常識」段落讓 LLM 不要套用台股漲跌停假設。
2. ✅ **OpenAIProvider**（gpt-4o-mini，input $0.15/1M、output $0.60/1M）+ **AnthropicProvider**（claude-haiku-3-5-20241022，input $0.80/1M、output $4.00/1M）— 兩個都直接用 SDK（不繞 langchain wrapper），token usage 取自 `response.usage`，cost 自帶 pricing 表。
3. ✅ **LLMFallbackChain**（依 PLAN 14.4 章 fallback map：google↔openai↔anthropic）— 整合 CircuitBreaker（CB OPEN 直接跳過該 provider）、記錄 `last_used_provider`、`generate(system, user)` 對 `BaseLLMProvider` 介面相容，Analyst 注入無需改 code。
4. ✅ **`get_llm_chain(settings)`**：依 `.env` 設定哪些 provider 可用（有 API key 才註冊），primary 為 `settings.LLM_DEFAULT_PROVIDER`，找不到 fall back 到第一個可用 provider + warning。
5. ✅ **main.py lifespan readiness check**：開機對每個 provider 跑 `health_check()` 並 log；PYTEST_RUNNING 跳過 ping（避免 test 燒配額）。
6. ✅ **WebSocket 串流**（Redis db4 PUBSUB）— 6 種事件：`started` / `analyst_completed` / `debate_argument` / `synthesis_completed` / `completed` / `failed`。設計上 `graph_builder._stream_wrap` 把每個 node 包成「執行 + publish event」，**不污染 Analyst / Researcher / Manager 程式碼**（避免 4×7=28 個檔都要改）。
7. ✅ **`QuotaService`**（PLAN 19.3 L6, $50/user/月）— `check_user_can_analyze(user_id, session=)` 回 `(allowed, used, limit)`；每月 1 號 00:00 UTC reset；80% 預算自動 log warning。POST /analysis 在 Idempotency 之後加 quota check（replay 不再扣）。
8. ✅ **`signal_to_pending_order`**：BUY/SELL → 建 `PendingOrder(status=PENDING)` 等核准；HOLD → None。qty 計算用 `DEFAULT_NOTIONAL_USD ($10000) / target_price`（PLAN 已知陷阱：v1.0 暫無 portfolio balance）。`run_analysis` 完成後依 signal 自動建單，失敗只 log warning 不擋 analysis。

### 1.2 P14 範圍外

| 項目 | 完成 Phase |
|------|-----------|
| 前端 UI（dashboard / analysis 詳情頁 / WS 訂閱） | P15+ |
| LINE / Telegram 通知（pending_order 建立時推） | P18 |
| Portfolio balance 真實串接（取代 fixed notional） | P16 |
| Qdrant similarity search for NewsAnalyst | P14 加強（次 Phase 視需求） |
| OpenAI / Anthropic function calling | 次 Phase（目前 prompt-driven JSON） |

---

## 2. 新增 / 修改檔案

### 2.1 新增

| 路徑 | 行數（概） | 說明 |
|------|-----------|------|
| `app/llm/openai_provider.py` | ~170 | OpenAIProvider（gpt-4o-mini），含 pricing 表 + CB |
| `app/llm/anthropic_provider.py` | ~170 | AnthropicProvider（claude-haiku-3-5-20241022），含 pricing 表 + CB |
| `app/llm/fallback_chain.py` | ~225 | LLMFallbackChain + `FALLBACK_CHAIN` 字典；`generate_with_chain` 回 (resp, used) |
| `app/agents/streaming.py` | ~140 | `publish_event` (async) + `publish_event_sync` (celery 用) + 6 個 EVENT_* 常數 |
| `app/agents/managers/orders_decision.py` | ~145 | `signal_to_pending_order` + `calculate_qty`；HOLD → None |
| `app/services/quota_service.py` | ~165 | QuotaService（session injection；月配額查 LLMUsage 累計 vs LLMMonthlyQuota.budget_usd） |
| `app/agents/prompts/market_analyst_user_us_template.txt` | ~30 | 美股技術面 prompt（含「美股市場常識」段落） |
| `app/agents/prompts/fundamental_analyst_user_us_template.txt` | ~30 | 美股基本面 prompt（無月營收，季度財報） |
| `app/agents/prompts/news_analyst_user_us_template.txt` | ~25 | 美股新聞 prompt（earnings / FOMC / 法人評級） |
| `tests/unit/test_openai_provider.py` | ~120 | 8 個測試（registry / pricing / health / generate mock） |
| `tests/unit/test_anthropic_provider.py` | ~120 | 8 個測試（同上） |
| `tests/unit/test_fallback_chain.py` | ~180 | 9 個測試（primary 成功 / fallback / CB OPEN 跳過 / 全 fail raise / chain 順序…） |
| `tests/unit/test_signal_to_order.py` | ~120 | 7 個測試（HOLD/BUY/SELL/qty 計算/invalid action raise/None signal） |
| `tests/integration/test_us_full_pipeline.py` | ~280 | 3 個測試（AAPL 完整跑、sentiment region check raise、pending_order BUY） |
| `tests/integration/test_cross_market_e2e.py` | ~265 | 2 個測試（2330 + AAPL 都跑通） |
| `tests/integration/test_quota_service.py` | ~155 | 5 個測試（under / at / default / record / 跨月隔離） |
| `tests/integration/test_llm_quota_blocks_analysis.py` | ~95 | 2 個測試（402 quota exceeded / 201 quota 通過） |
| `tests/integration/test_ws_streaming.py` | ~115 | 5 個測試（started / analyst_completed / completed / failed / publish_sync） |
| `scripts/health_checks/phase_14.sh` | ~210 | 13 項健康檢查 |
| `docs/phase_reports/PHASE_14.md` | （本檔） | Phase 14 報告 |

### 2.2 修改

| 路徑 | 變更 |
|------|------|
| `backend/pyproject.toml` | 新增 `openai>=1.50,<2.0`、`anthropic>=0.40,<1.0`、`langchain-openai>=0.2,<1.0`、`langchain-anthropic>=0.3,<1.0` |
| `app/llm/__init__.py` | 新增 `get_llm_chain(settings)`；side-effect import 三個 provider |
| `app/llm/gemini_provider.py` | 加 `self.cb = get_or_create_breaker("llm.google")` 配合 fallback chain |
| `app/main.py` | lifespan 新增 `app.state.llm_chain` + 對每個 provider ping `health_check()`（PYTEST_RUNNING 跳過） |
| `app/agents/llm_helpers.py` | docstring 註明 `llm` 參數可為 `BaseLLMProvider` 或 `LLMFallbackChain`（介面相容） |
| `app/agents/analysts/market_analyst.py` | `analyze()` 依 `state["region"]` 切 us/tw template；error 帶 region 標籤 |
| `app/agents/analysts/fundamental_analyst.py` | 同上；美股 monthly_revenue 顯示「美股無月度營收公告制度」 |
| `app/agents/analysts/news_analyst.py` | 同上 |
| `app/agents/graph_builder.py` | 新增 `_stream_wrap`；每個 node 包裝後 publish event；不動 Analyst / Researcher / Manager 程式碼 |
| `app/agents/managers/__init__.py` | 匯出 `signal_to_pending_order` + `calculate_qty` |
| `app/api/v1/analysis_router.py` | POST 加 quota check（session 注入 `QuotaService.check_user_can_analyze`）；放 idempotency 之後 |
| `app/workers/tasks/run_analysis.py` | 用 `get_llm_chain` 取代 single provider；開頭 publish started、結尾 publish completed/failed；完成後依 signal 建 pending_order |

---

## 3. 設計決策

### 3.1 為什麼 LLMFallbackChain 不繼承 BaseLLMProvider？

- BaseLLMProvider 是 ABC，繼承會引入 `settings` 必填參數的不必要 coupling。
- chain 「quack like provider」更彈性：`name` / `default_model` 是 property（動態反映 last_used_provider），`generate(system, user)` 簽名相容即可。
- 結果：Analyst 注入 chain 完全無需改 code（直接傳 `llm=chain` 給 `build_graph`）。

### 3.2 為什麼 OpenAI / Anthropic 用直接 SDK 而非 langchain？

- 不同 provider 的 token usage / cost 計算邏輯不同；用 langchain 統一介面反而要再從 `usage_metadata` 解，多一層抽象。
- 直接 SDK：cost 直接從 `response.usage` 取，pricing 表自己維護，更精準。
- langchain-openai / langchain-anthropic 依然裝著，預留給 P15+ 真正需要 tool calling 時用。

### 3.3 為什麼 streaming wrapper 放 graph_builder 而非每個 Analyst？

- 不污染 Analyst / Researcher / Manager 共 7 個檔（避免每處都 if try except publish）。
- `_stream_wrap` 一次性處理，新增節點時自動有 streaming。
- publish 失敗（Redis 不可用）也不會擋分析流程 — fire-and-forget。

### 3.4 為什麼 quota check 在 idempotency 之後？

- Idempotent replay 不該重複扣配額（原請求已 cache response）。
- replay 時直接回 200 + cached body，跳過 quota check。

### 3.5 為什麼 QuotaService 加 session injection？

- production 走 `ro_session()` 自己開連線。
- pytest-asyncio 跨 event loop 時 module-level sessionmaker pool stale → "Event loop is closed"。
- session injection 讓 router 把已開的 session 傳入；test 也用獨立 session_maker fixture，徹底解耦。

### 3.6 為什麼 `signal_to_pending_order` qty 用 fixed notional？

- v1.0 沒有真實 portfolio balance；不該為了完成 P14 而提前建 Position 系統（P16 工作）。
- DEFAULT_NOTIONAL_USD = $10000 是合理的「示範值」；admin 在核准時可手動調整 qty。
- 文件清楚標示 v1.0 限制（PLAN 已知陷阱）。

---

## 4. PLAN.md 對齊

| PLAN 章節 | 對齊狀態 |
|----------|----------|
| 10.5 Analyst × 市場（Sentiment TW only） | ✅ MarketAnalyst / FundamentalAnalyst / NewsAnalyst supports both，SentimentAnalyst TW only；US 上呼叫 sentiment.analyze raise ValidationError |
| 14.3 Circuit Breaker（連續 5 次 → OPEN 10 分） | ✅ fallback_chain 整合既有 `app.core.circuit_breaker`；每個 provider 自帶 `self.cb` |
| 14.4 LLM Fallback Chain 映射表 | ✅ FALLBACK_CHAIN dict 完全照抄 |
| 14.6 Graceful Shutdown | ✅ streaming publish 失敗 fire-and-forget 不擋 |
| 16.2 metrics | ✅ used_provider / cost 寫 LLMUsage hypertable（既有 P12 機制） |
| 18.2 Plugin Pattern | ✅ provider 用 `@register_llm_provider`，與 P12 BaseLLMProvider / GeminiProvider 同模式 |
| 19.3 Rate Limit L6 月配額（$50/user） | ✅ QuotaService 預設讀 `settings.LLM_MONTHLY_BUDGET_USD_DEFAULT`；per-user override 走 `llm_monthly_quota.budget_usd` |

---

## 5. 測試覆蓋

### 5.1 新增測試（9 個檔，共 49 測試）

| 測試檔 | 數量 | 範圍 |
|--------|-----|------|
| `tests/unit/test_openai_provider.py` | 8 | registry / pricing(gpt-4o-mini & gpt-4o) / unknown model / health_check no key / generate no key raises / mock generate parses |
| `tests/unit/test_anthropic_provider.py` | 8 | 同上（claude-haiku-3-5 & sonnet-4 pricing） |
| `tests/unit/test_fallback_chain.py` | 9 | chain map / primary 成功 / fallback / CB OPEN skip / 全 fail / cb reset / used_provider name / 不存在 provider skip / generate 相容介面 |
| `tests/unit/test_signal_to_order.py` | 7 | HOLD→None / BUY / SELL / qty 計算 / invalid action raise / status=PENDING / empty signal |
| `tests/integration/test_us_full_pipeline.py` | 3 | AAPL 完整跑 / sentiment region check raise / BUY signal 建 NASDAQ order |
| `tests/integration/test_cross_market_e2e.py` | 2 | 2330 完整跑 / AAPL 完整跑（mock LLM） |
| `tests/integration/test_quota_service.py` | 5 | under limit / at limit blocked / default limit / record_usage 寫 DB / 跨月隔離 |
| `tests/integration/test_llm_quota_blocks_analysis.py` | 2 | quota exceeded → 402 / quota 通過 → 201 |
| `tests/integration/test_ws_streaming.py` | 5 | started / analyst_completed / completed signal / failed / publish_event_sync |
| **小計** | **49** | |

### 5.2 累積測試

| Phase | 累積 |
|-------|------|
| P12 | 552 |
| P13 | 604 |
| **P14** | **653**（+49） |

---

## 6. 完成驗收（phase_14.sh 13 項）

```bash
bash scripts/health_checks/phase_14.sh
```

驗收項：

1. ✅ Phase 13 仍正常
2. ✅ uv sync + ruff lint
3. ✅ backend 起得來，/health/live 200
4. ✅ 3 個 LLM provider 已註冊
5. ✅ `get_llm_chain(settings)` 可建
6. ✅ 美股 3 個 prompt 模板存在
7. ✅ `signal_to_pending_order` 邏輯正確（HOLD→None / BUY→PENDING）
8. ✅ QuotaService method 完整
9. ✅ P14 unit 測試全綠（OpenAI / Anthropic / FallbackChain / signal_to_order）
10. ✅ P14 integration 測試全綠（US pipeline + cross-market + quota + WS streaming）
11. ✅ POST /analysis（quota 通過路徑）
12. ✅ 累積測試 653 ≥ 640
13. ✅ `run_analysis` 已升級（LLM chain + streaming + pending_order）

---

## 7. 已知限制

1. **portfolio balance 未串接**：qty 用 fixed $10000 notional，P16 portfolio 系統上線後改真實計算。
2. **單元測試環境 LLM 沒打真 API**：用 monkeypatch 替換 SDK client；真實 API 整合留給 `test_real_llm_2330.py`（@expensive mark）。
3. **WS 訂閱端尚未升級**：本 Phase 只 publish events 到 Redis pubsub；前端 WS 端真實 subscribe 由 P15 frontend 串接（ws_router 已有 subscribe 邏輯但未對齊新 event schema）。
4. **OpenAI / Anthropic function calling 暫不接**：當前 Analyst 用「prompt-driven JSON output」確保跨 provider 一致；P15+ 若需 tool calling 再分 provider 串。
5. **race condition on quota check**：兩個 request 同時通過 check 是已知陷阱（PLAN 14）；接受小幅超標，不嚴格鎖。

---

## 8. 後續 Phase 對接

- **P15 前端**：訂閱 `analysis:{id}` channel，渲染辯論過程；POST /analysis 顯示 used_provider；402 quota exceeded 顯示提示。
- **P16 Portfolio**：取代 `DEFAULT_NOTIONAL_USD` 為真實 user balance；signal_to_pending_order 用 `position_size_pct * balance / target_price`。
- **P18 通知**：pending_order 自動建立後推 LINE / Telegram（重大訊號 BUY/SELL）。

---

**Phase 14 完成，準備進入 P15 前端開發。**
