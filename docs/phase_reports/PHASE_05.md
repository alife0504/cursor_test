# Phase 05 完成報告 — TW 資料源 Adapter（FinMind/TWSE/TPEX/MOPS/cnyes）+ Repository

> Phase：v7.0 第 5 階段 — 讓專案具備「從 5 個台股資料來源抓資料 + 寫入 DB」的能力
> 起始：2026-05-12
> 完成：2026-05-12
> 對應計劃：PLAN.md 第二十七章 Phase 5（v7.0）
> Git tag：`phase-05-complete`

---

## 1. 做了什麼

### 1.1 BaseDataSource 抽象基類 + 註冊機制（PLAN 18.2 Plugin Pattern）

| 檔案 | 用途 |
|------|------|
| `backend/app/data_sources/base.py` | `BaseDataSource` 基類 + `DataKind`/`MarketRegion` enum + `@register_data_source` 裝飾器 + `DATA_SOURCE_REGISTRY` |
| `backend/app/data_sources/fallback.py` | `DataSourceFallback`：依 priority 排序 → 跳過 OPEN CB → 主源 fail → 備源 → 24h stale cache（callback 由 caller 提供） |

**核心設計**：

- 抽象方法 `fetch_ohlcv / fetch_company_info / fetch_financial / fetch_news / fetch_announcement / fetch_institutional / fetch_margin / fetch_monthly_revenue` 預設 raise `NotImplementedError` → subclass 只需 override 自己支援的 kind
- 每個 source 在 `__init__` 時自動 `get_or_create_breaker(name)` 註冊 CB（per source name）
- `rate_limit_per_sec` 自動轉成 `AsyncLimiter`：< 1 時切成「1 次 / N 秒」避免 leaky bucket capacity floor 為 0
- `priority`：越小越優先（主源 10、備源 20、補強 25/30）

### 1.2 5 個 TW Adapter

| 檔案 | source name | priority | 支援 DataKind | rate |
|------|-------------|---------|---------------|------|
| `tw/finmind_source.py` | `finmind` | 10（主源） | OHLCV / COMPANY_INFO / FINANCIAL / INSTITUTIONAL / MARGIN / MONTHLY_REVENUE | 0.5/s（每 2 秒 1 次） |
| `tw/twse_openapi_source.py` | `twse_openapi` | 20 | OHLCV / INSTITUTIONAL | 1.0/s |
| `tw/tpex_source.py` | `tpex` | 25 | OHLCV（OTC） | 0.5/s |
| `tw/mops_source.py` | `mops` | 30 | ANNOUNCEMENT / MONTHLY_REVENUE | 0.5/s |
| `tw/cnyes_rss_source.py` | `cnyes_rss` | 10（NEWS 主源） | NEWS | 1.0/s |

關鍵實作要點：

- **FinMind**：包裝 `TaiwanStockPrice / TaiwanStockInfo / TaiwanStockFinancialStatements / TaiwanStockMonthRevenue / TaiwanStockInstitutionalInvestorsBuySell / TaiwanStockMarginPurchaseShortSale` 六個 dataset。內建錯誤鑑別（401 → AuthError、402/429 → RateLimitError、5xx → ExternalServiceError）。OHLCV / 三大法人 / 月營收均有 `_normalize_*` helper 統一輸出欄位 + Decimal 精度
- **TWSE**：STOCK_DAY 月為單位 loop；民國日期解析；rate limit 1.0/s
- **TPEX**：daily_close_quotes 按日抓全市場 + filter symbol；解析 `aaData` 多欄位
- **MOPS**：HTML 表格 + BeautifulSoup parser；月營收（big5 編碼）+ 重大訊息（utf-8）；月份 404 自動跳過
- **cnyes RSS**：feedparser 解析；symbol filter 用 substring 匹配（P7 換成 stock_list 名稱對照）

### 1.3 FinancialStatement 新表 + alembic 0014

| 檔案 | 用途 |
|------|------|
| `app/models/financials.py` | `FinancialStatement` ORM model（PK = symbol/year/quarter/statement_type；payload JSONB） |
| `migrations/versions/0014_phase5_financial_statements.py` | 建表 + CHECK constraint（statement_type IN IS/BS/CF + quarter BETWEEN 0 AND 4） |

新增表設計：

```
financial_statements
  PK (symbol, fiscal_year, fiscal_quarter, statement_type)
  常用欄位：revenue / gross_profit / operating_income / net_income / eps
            total_assets / total_liabilities / total_equity
            operating_cashflow / investing_cashflow / financing_cashflow
  payload JSONB（保留 source 完整 response）
  announced_at / source / ingested_at
```

### 1.4 Repository pattern

| 檔案 | 主要方法 |
|------|---------|
| `app/repos/base.py` | `BaseRepository(session)` + `ReadOnlyRepository`（型別語意；P10 上線時用 type-check 限制） |
| `app/repos/stock_repo.py` | `list_active / get_by_symbol / search_by_name / upsert_many` |
| `app/repos/ohlcv_repo.py` | `get_range / latest_date / gaps(weekday_only) / upsert_many` — 全部用 `INSERT ... ON CONFLICT DO UPDATE` |
| `app/repos/news_repo.py` | `list_by_symbol / upsert_many_by_url`（URL 為自然 dedupe key） |
| `app/repos/financials_repo.py` | `list_statements / upsert_statements / list_monthly_revenue / upsert_monthly_revenue` |

關鍵：

- Repo 不主動 commit；caller 控制 transaction（unit-of-work）；提供 `commit=True` 參數方便 single-step 場景
- 寫入前清理：空字串 / None / NaN 不會炸 PG Numeric type
- Decimal 全程用 `_ensure_decimal()` 保留精度（pandas → str → Decimal）

### 1.5 DataPipelineService

`app/services/data_pipeline_service.py`：

- `sync_ohlcv(symbol, market, start, end)`
- `sync_news_for_symbol(symbol, since)`
- `sync_monthly_revenue(symbol, year)`
- `sync_financial(symbol, year, quarter)`

每個方法 = 從 `sources_by_kind` 找到對應 source list → 包成 `DataSourceFallback` → fetch → repo.upsert_many(commit=True)。

---

## 2. 測試覆蓋

### 2.1 新增 9 個 test 檔（共 ~67 個測試）

| 檔案 | 數量 | 涵蓋 |
|------|------|------|
| `tests/unit/test_finmind_source.py` | 10 | 正規化、API endpoint、401/402/5xx 錯誤、CB 累積、三大法人 pivot |
| `tests/unit/test_twse_source.py` | 7 | 民國日期、`_to_int`/`_to_decimal`、STOCK_DAY 單月、空回應、429、5xx |
| `tests/unit/test_tpex_source.py` | 5 | helper、symbol filter、空、429、5xx |
| `tests/unit/test_mops_source.py` | 9 | helper、HTML parsing（月營收 + 重大訊息）、since filter、12 月 loop、404 跳過、5xx |
| `tests/unit/test_cnyes_rss_source.py` | 4 | RSS parsing、symbol filter、since filter、HTTP error |
| `tests/unit/test_data_source_fallback.py` | 8 | 健康→主、fail→secondary、OPEN CB skip、cache fallback、無 cache 拋錯、record success、priority 排序、kind 無 source |
| `tests/unit/test_repositories.py` | 19 | 4 repo CRUD + decimal precision + gaps_excludes_weekends + dedupe + ensure_decimal |
| `tests/integration/test_data_pipeline_service.py` | 5 | sync_ohlcv 寫 DB、fallback、idempotent ON CONFLICT、news dedupe、monthly_revenue 寫 DB |
| `tests/integration/test_real_finmind.py` | 1 | @pytest.mark.network — 無 FINMIND_TOKEN 自動 skip |

### 2.2 測試結果

```
$ uv run pytest -m "not network" -q
181 passed, 1 skipped, 1 deselected in 32.43s
```

整體 collected = 183（含 1 個 network 標 skip）。

---

## 3. PLAN 對應

| PLAN 章節 | 落實 |
|-----------|------|
| 7. 限制（FinMind 配額不足）| 主用 FinMind + TWSE/TPEX 備援 + AsyncLimiter 0.5/s 保守 |
| 8.5（Phase SOP）| 健康檢查腳本、commit message 規範 |
| 10.4（資料來源對照）| OHLCV 主 FinMind / 備 TWSE+TPEX；財報主 FinMind / 備 MOPS；新聞主 cnyes RSS；公告 MOPS；籌碼 FinMind+TWSE |
| 14.2（重試）| 透過 `app.core.http_client.request_with_retry`（既有） |
| 14.3（Circuit Breaker）| 每 source 一個 `CircuitBreaker`（lazy 註冊），CB OPEN 時 fallback 跳過該 source |
| 14.4（fallback）| `DataSourceFallback` 三層：主源 → 備源 → 24h cache（caller 提供 callback） |
| 17.5（快取）| stale_cache_loader 介面已留；P10 接 Redis 24h cache |
| 18.1（後端分層）| API → Service → Domain → Repository → Infrastructure（source 屬 Infrastructure） |
| 18.2（Plugin Pattern）| `@register_data_source` 裝飾器 + `DATA_SOURCE_REGISTRY` |
| 20.1（資料來源限制）| 各 source 文件內列出官方 rate limit |
| 20.2（完整資料表）| 新增 `financial_statements` + 0014 migration |

---

## 4. 已知陷阱與避坑

| 陷阱 | 解法 |
|------|------|
| `AsyncLimiter(0.5, 1.0)` capacity 被 floor 為 0 → 永久 acquire 失敗 | base.py：< 1 時改用 `AsyncLimiter(1, 1.0/rate)` 表示「1 次 / N 秒」 |
| FinMind 配額 600/day → 跑大量會撞限 | 主用 + 備援 TWSE/TPEX + Redis 24h cache（P10 加） |
| MOPS HTML 結構偶爾改 → BeautifulSoup parser 失敗 | parser 拋 ExternalServiceError 並交給 fallback；單元測試 mock HTML 確保結構穩定 |
| Decimal 透過 pandas 變 float | normalize_ohlcv / `_to_decimal_or_none` 全程用 `Decimal(str(v))` |
| httpx 4xx 不會自動 raise | 各 source 主動檢查 status_code 並包成 AppError 子類 |
| Circuit Breaker per-thread 共用 | 全域 `CIRCUIT_BREAKERS` dict by name + 內含 `asyncio.Lock`（PLAN 14.3） |
| 12 月份 loop MOPS（rate 0.5/s）→ 測試跑超慢 | 測試 fixture 統一 `src.limiter = None` |

---

## 5. 完成驗收（Section 5）

健康檢查腳本：`scripts/health_checks/phase_05.sh`

```bash
$ bash scripts/health_checks/phase_05.sh
=== Phase 05 健康檢查 ===
✓ alembic head = 0014
✓ financial_statements 表存在
✓ 5 個 TW source 全部註冊成功
✓ 5 個 CircuitBreaker 全部註冊
✓ ruff check app/ 通過
✓ P5 unit tests 全綠
✓ P5 integration tests 全綠
✓ P4 退化測試通過
✅ Phase 05 健康檢查全部通過
```

---

## 6. 對 Phase 6+ 的影響

- Phase 6（美股資料源）：直接複製 `tw/` 結構 → `us/yfinance_source.py` / `us/alpha_vantage_source.py` / `us/finnhub_source.py` / `us/sec_edgar_source.py`，公用 `BaseDataSource` 與 `DataSourceFallback`
- Phase 7（Celery 任務 + backfill）：Celery task 直接呼叫 `DataPipelineService.sync_*`，task signature 包 retry / DLQ / 軟硬 timeout
- Phase 10（API router）：`StockRepository.search_by_name` 接前端 `/api/v1/stocks/search`；`OHLCVRepository.get_range` 接 `/api/v1/stocks/{symbol}/ohlcv`
- Phase 12（LangGraph Tool）：Agent 用 `ReadOnlyRepository` + `ta_agent_ro` 帳號讀資料（注入點已留）
