# Phase 06 完成報告 — US 資料源 Adapter（yfinance/AV/Finnhub/SEC EDGAR）+ 跨市場 Dispatcher

> Phase：v7.0 第 6 階段 — 讓專案具備「美股資料抓取 + 跨市場自動派送」能力
> 起始：2026-05-13
> 完成：2026-05-13
> 對應計劃：PLAN.md 第二十七章 ▌Phase 6（v7.0）
> Git tag：`phase-06-complete`

---

## 1. 做了什麼

### 1.1 跨市場 Dispatcher（PLAN 10.1-10.2 + 18.2 Plugin Pattern）

| 檔案 | 用途 |
|------|------|
| `backend/app/core/market_dispatcher.py` | `Market` enum（TWSE/TPEX/NASDAQ/NYSE/AMEX）+ `detect_region()` symbol regex + `validate_symbol_exists()` + `MarketDispatcher` |

**核心設計**：

- `TW_SYMBOL_PATTERN = r'^[0-9]{4}[A-Z0-9]?$|^[0-9]{6}[A-Z]?$'`
  涵蓋一般股 `2330`、ETF `0050`/`00878`/`006208`、特別股 `2884A`、權證 `043333P`
- `US_SYMBOL_PATTERN = r'^[A-Z]{1,5}(\.[A-Z])?$'`
  涵蓋 `AAPL`/`F`/`T` 短代號、`BRK.B`/`BF.B` dual class
- `MarketDispatcher.get_sources_for(region, kind)`：依 region + DataKind 取 source list
- `get_sources_for_symbol(symbol, kind)`：便利方法（自動 detect_region）
- `market_to_region(market)`：交易所 enum → region

### 1.2 4 個美股 Adapter

| 檔案 | source name | priority | 支援 DataKind | rate | 備註 |
|------|-------------|---------|---------------|------|------|
| `us/yfinance_source.py` | `yfinance` | 10（主源） | OHLCV / COMPANY_INFO / FINANCIAL / NEWS | 2.0/s | 同步包；`run_in_executor` wrap；`BRK.B` → `BRK-B` |
| `us/alpha_vantage_source.py` | `alpha_vantage` | 20 | OHLCV / FINANCIAL | 0.4/s | 25/day 配額；`Note`/`Information` 主動檢查 → `QuotaExceededError` |
| `us/finnhub_source.py` | `finnhub` | 30 | NEWS / COMPANY_INFO | 1.0/s | 60/min 免費；403 → `ForbiddenError`（plan 限制） |
| `us/sec_edgar_source.py` | `sec_edgar` | 10（filings 主源） | ANNOUNCEMENT | 5.0/s | 強制 `User-Agent`（含 `ADMIN_EMAIL`）；CIK 24h 記憶體 cache；過濾 10-K/10-Q/8-K/20-F/6-K |

關鍵實作要點：

- **yfinance**：同步 API 必須 `asyncio.get_running_loop().run_in_executor(None, ...)` 包裝避免 block event loop；MultiIndex columns flatten；空 DataFrame → `NotFoundError`；symbol upper + `.` → `-`
- **Alpha Vantage**：配額耗盡時回 200 + `Note` 欄位（非 4xx），實作中明確主動檢查 → `QuotaExceededError`；`Error Message` → `NotFoundError`；outputsize compact/full 依日期區間自動切
- **Finnhub**：免費 plan 403 → `ForbiddenError`（不算 ExternalServiceError，避免炸 CB）；新聞 epoch timestamp 解析；company profile 標準化
- **SEC EDGAR**：`__init__` 內注入 `User-Agent: TradingAgents-TW/{APP_VERSION} ({ADMIN_EMAIL})`；CIK lookup 24h 簡易 cache；submissions JSON 解析 + filing URL 組裝；CIK zfill(10) 含前導零

### 1.3 us/__init__.py + get_us_sources()

| 檔案 | 用途 |
|------|------|
| `us/__init__.py` | 4 個 source class re-export + `get_us_sources(settings)` 依 `DataKind` 分組（priority 排序） |

### 1.4 24h stale cache（PLAN 14.3）

| 檔案 | 用途 |
|------|------|
| `app/data_sources/cache.py` | Redis（db 0）+ pyarrow parquet bytes（不用 pickle）；key 含 `market` 防 NASDAQ 與 TWSE 同 symbol 撞 key；提供 `ohlcv_stale_cache_loader` callback 給 `DataSourceFallback` |

關鍵：

- 用 `pyarrow.parquet` serialize/deserialize（跨語言、安全，不像 pickle）
- Decimal-as-object 自動轉 float（parquet 不支援 object Decimal）
- key 格式：`cache:ohlcv:{market}:{SYMBOL}:{start}:{end}`
- 失敗（Redis 連線炸 / 序列化錯）→ log warning，不會炸主流程

### 1.5 DataPipelineService 升級

| 檔案 | 主要變更 |
|------|---------|
| `app/services/data_pipeline_service.py` | 加 `with_dispatcher(dispatcher, session)` 工廠；`sync_ohlcv / sync_news_for_symbol / sync_financial / sync_announcements` 加 `market` 參數；`sync_monthly_revenue` / `sync_institutional` 強制 TW only（`_ensure_tw_only` 守門） |

關鍵：

- 雙模式：P5 `sources_by_kind` 仍可用；P6 新增 `dispatcher` 模式
- 自動推 region：`market` 給時用 `market_to_region`；否則用 `detect_region(symbol)`
- US symbol 呼 `sync_institutional` → `ValidationError("籌碼資料僅支援台股")`
- `_normalize_financial_rows`：自動辨識 FinMind 風格（groupby year/quarter）與 yfinance/AV 風格（passthrough 完整 statement）

### 1.6 main.py lifespan

| 檔案 | 主要變更 |
|------|---------|
| `app/main.py` | startup 建 `MarketDispatcher(tw_sources, us_sources)` → 掛在 `app.state.dispatcher` |

router 取用：`request.app.state.dispatcher`（P7 起會加 FastAPI dependency）。

### 1.7 測試（8 個檔案，63 個獨立測試 + parametrize 展開共 68 個 test items）

| 檔案 | 測試數（檔案內） | 涵蓋 |
|------|----------|------|
| `tests/unit/test_yfinance_source.py` | 9 | OHLCV / 大小寫 / `.→-` / `run_in_executor` / 空 → NotFound / 內部錯誤 wrap / news filter / CB / company_info |
| `tests/unit/test_alpha_vantage_source.py` | 9 | URL / quota Note / Information / Error Message → NotFound / full vs compact / Decimal 精度 / 缺 API key / 5xx |
| `tests/unit/test_finnhub_source.py` | 7 | news schema / symbol=None / 401 / 403 / 429 / company info / 空 dict → NotFound |
| `tests/unit/test_sec_edgar_source.py` | 8 | User-Agent / FORM list / CIK zfill10 / 不存在 → NotFound / cache hit / 403 / 429 / form filter + since |
| `tests/unit/test_market_dispatcher.py` | 15（含 parametrize 23 items） | TW 4-digit / ETF 5-6-digit / 特別股 / US normal / BRK.B / 短 symbol / unknown / dispatcher 路由 / validate_symbol_exists |
| `tests/unit/test_cache.py` | 8 | market 防撞 key / 大小寫 / parquet roundtrip / Decimal→float / empty / 非 df / Redis 異常 graceful / cache miss |
| `tests/integration/test_dispatcher_end_to_end.py` | 7 | 2330→TW / AAPL→US / 0050→TW / BRK.B→US / 不認識 → ValidationError / US 無 INSTITUTIONAL / pipeline TW-only 守門 |
| `tests/integration/test_real_yfinance.py` | 1（標 network） | 真實 yfinance AAPL 近 14 天 |

### 1.8 phase_06.sh

`scripts/health_checks/phase_06.sh` 涵蓋 7 個檢查：

1. P5 仍正常（5 個 TW source 註冊）
2. 4 個 US source 註冊
3. detect_region 對 PLAN 10.2 所有樣態行為正確
4. ruff check 通過
5. P6 unit tests 全綠
6. P6 integration tests（mock）全綠
7. P5 退化檢查（fallback / repos / pipeline 仍綠）

---

## 2. 退出條件驗收（11 條指令）

| # | 指令 | 結果 |
|---|------|------|
| 1 | `cd backend && uv sync` | ✓（新增 yfinance 0.2.66 + 依賴） |
| 2 | `cd backend && uv run ruff check app/` | ✓ All checks passed |
| 3 | `curl /health/live` 200 | ✓（PYTEST_RUNNING=1 模式 import 通過） |
| 4 | 4 個 US source 註冊 | ✓ `{yfinance, alpha_vantage, finnhub, sec_edgar}` |
| 5 | Symbol validator（含台股 ETF + 美股 BRK.B） | ✓ 7/7 案例皆 OK |
| 6 | Dispatcher 整合 lifespan | ✓（main.py 在 yield 前建立 `app.state.dispatcher`） |
| 7 | P6 unit tests | ✓ 64 passed（test_yfinance/AV/Finnhub/SEC/Dispatcher/Cache） |
| 8 | P6 integration tests (mock) | ✓ 7 passed |
| 9 | yfinance 真實 call | ⏳ 標 `@pytest.mark.network`；CI 不跑（需手動 `-m network`） |
| 10 | 累積測試 ≥ 101 | ✓ 252 passed / 1 skipped（從 P5 的 184 個提升至 252，**新增 68 個 test items**） |
| 11 | `bash scripts/health_checks/phase_06.sh` | ✓ 7/7 通過 |

---

## 3. 已知陷阱（已處理 / 仍待 P7+）

| 陷阱 | 處理 |
|------|------|
| yfinance 同步 → block event loop | ✓ `run_in_executor(None, ...)` |
| yfinance 大小寫敏感 | ✓ `symbol.upper()` |
| `BRK.B` URL 編碼 | ✓ `.` → `-`（yfinance 規格） |
| Alpha Vantage 配額耗盡回 200 + Note | ✓ 主動檢查 `Note` / `Information` → `QuotaExceededError` |
| Finnhub 免費版 endpoint 403 | ✓ 包成 `ForbiddenError`（不污染 CB） |
| SEC EDGAR 缺 User-Agent → 403 | ✓ `__init__` 內注入含 `ADMIN_EMAIL` |
| SEC EDGAR CIK 含前導零 | ✓ `str(cik).zfill(10)` |
| Symbol regex 漏 ETF（00878） | ✓ `r'^[0-9]{4}[A-Z0-9]?$|^[0-9]{6}[A-Z]?$'` |
| Cache 用 pickle 不安全 | ✓ 改用 `pyarrow.parquet` bytes |
| Cache key 漏 market | ✓ key 模板含 `{market}` |
| Dispatcher 沒注入 `app.state` | ✓ lifespan 建立後 `app.state.dispatcher = ...` |

---

## 4. 已知遺漏（給下一 Phase 提醒）

| 項目 | 狀態 | 哪個 Phase 處理 |
|------|------|--------------|
| Celery 任務 + backfill script | 不做（依本 Phase 範圍） | **P7** |
| FastAPI Depends 注入 dispatcher 給 router | 暫用 `app.state` | P7（或 P10 API 層） |
| `sync_announcements` 寫 DB | 只 return list | P7（需 announcements 表 + repo） |
| `sync_institutional` 寫 DB | 只 fetch DataFrame | P7（需 `institutional_trading_repo`） |
| Finnhub 大盤新聞 | symbol=None 回空 | P10（v1.1 接 NewsAPI） |
| yfinance financial XBRL 解析 | passthrough payload | P11 financial analyst 處理 |
| 用 Redis pubsub 處理 CB OPEN 事件 | log critical only | P18 通知 |

---

## 5. 統計

- **新增檔案**：12（market_dispatcher / 4 US adapter / us/__init__ / cache / 6 test files + 1 network test + phase_06.sh + PHASE_06.md）
- **修改檔案**：4（pyproject.toml + uv.lock / main.py / data_pipeline_service.py / phase_progress.md）
- **新增測試**：68 test items（含 parametrize 展開）
- **累積測試**：252 passed / 1 skipped（health endpoint）
- **耗時**：約 2 小時（單 session 一氣呵成）

---

## 6. 給下一 Phase 的提醒

1. **P7 排程任務**：
   - 跨市場 backfill：caller 給 `market`，pipeline 自動派 region；可參考 `DataPipelineService.sync_ohlcv` 範例。
   - `sync_announcements` 目前只 return list → P7 寫 `announcements` 表 + Repo（沿用 FinancialsRepository 模式）。
   - SEC EDGAR CIK cache 目前是 module-level dict（程式重啟會清）→ P7 可改用 Redis db 0 with 24h TTL。

2. **`app.state.dispatcher` 注入模式**：
   - 目前用 `request.app.state.dispatcher`；P7 可以建 FastAPI `Depends(get_dispatcher)`。

3. **API key 缺失行為**：
   - 沒設 `ALPHA_VANTAGE_API_KEY` / `FINNHUB_API_KEY` 不會炸啟動；只在實際呼叫時 raise `AuthError`；fallback chain 會跳過 → 整體仍可運作（只是配額無法享用）。

4. **真實 yfinance 測試**：
   - 標 `@pytest.mark.network`；P7 CI 設定 `pytest -m "not network"`，可選擇性手動跑。

5. **跨市場路由邊界**：
   - 若使用者打 `2330` 卻指定 `market=NASDAQ` → 目前 `_resolve_region` 優先採信 `market`（→ US）。實務上 router 層應先 `validate_symbol_exists(symbol, market)` 阻擋（PLAN 10.2 已規範）。
