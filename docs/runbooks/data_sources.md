# 資料源 Runbook — 各 source 的限制 / 失敗處理 / 接線方法

> Phase 5 起逐步補完。本檔追蹤每個 TW / US source 的官方限制、實作策略、常見問題、與運維 SOP。

---

## 1. TW 資料源

### 1.1 FinMind（主源）

- **官網**：<https://finmindtrade.com/analysis/#/data/api>
- **配額**：免費版依官方公告（v7.0 P5 撰寫時保守設 0.5 req/s）；付費 ~$99/月 quota 較高
- **TOKEN**：`.env` 設 `FINMIND_TOKEN=...`；空也可呼叫 public dataset，但 quota 更小
- **支援 DataKind**：OHLCV / COMPANY_INFO / FINANCIAL / INSTITUTIONAL / MARGIN / MONTHLY_REVENUE
- **錯誤碼**：
  - 401 / msg=invalid token → `AuthError`（API key 換）
  - 402 / 429 / msg 含 "limit" → `RateLimitError`（fallback 自動切備源）
  - 其他 5xx → `ExternalServiceError`
- **dataset 對照**：
  | DataKind | dataset |
  |----------|---------|
  | OHLCV | TaiwanStockPrice |
  | COMPANY_INFO | TaiwanStockInfo |
  | FINANCIAL | TaiwanStockFinancialStatements |
  | INSTITUTIONAL | TaiwanStockInstitutionalInvestorsBuySell |
  | MARGIN | TaiwanStockMarginPurchaseShortSale |
  | MONTHLY_REVENUE | TaiwanStockMonthRevenue |

### 1.2 TWSE OpenAPI（OHLCV 備源 + 三大法人）

- **官網**：<https://openapi.twse.com.tw/>
- **歷史 OHLCV**：用 `https://www.twse.com.tw/exchangeReport/STOCK_DAY` （月為單位），格式 JSON
- **配額**：官方建議 ≤ 1 req/s；無 API key
- **支援 DataKind**：OHLCV / INSTITUTIONAL
- **日期格式**：民國「114/05/12」→ 解析 helper `_roc_to_date()`
- **限制**：
  - 多日歷史要 loop 月份 → 大量 backfill 用 FinMind，TWSE 只做兜底

### 1.3 TPEX（OTC OHLCV 備源）

- **官網**：<https://www.tpex.org.tw>
- **端點**：`/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?d=YYY/MM/DD&se=AL`
- **回應**：JSON `{aaData: [[symbol, name, close, ...], ...]}`
- **配額**：保守 0.5 req/s
- **支援 DataKind**：OHLCV（只用於 `market='TPEX'` 的股票）
- **特性**：單日全市場 → caller filter symbol；歷史需 loop 日期（成本高）

### 1.4 MOPS 公開資訊觀測站（財報 / 月營收 / 重大訊息備源）

- **官網**：<https://mops.twse.com.tw>
- **月營收**：`/nas/t21/sii/t21sc03_<roc_year>_<month>.html`（big5 編碼）
- **重大訊息**：`/mops/web/ajax_t05st02`（POST form，utf-8）
- **配額**：官方建議 ≤ 1 req/s；專案保守 0.5 req/s
- **支援 DataKind**：ANNOUNCEMENT / MONTHLY_REVENUE
- **HTML parsing**：BeautifulSoup + lxml；結構若變動，調整 `_parse_monthly_for_symbol` / `_parse_announcements` 兩函式
- **404 處理**：當月還沒到 → 404 → 跳過該月份，不視為錯誤（FinMind 主源也會無資料）

### 1.5 cnyes RSS（新聞主源）

- **官網**：<https://news.cnyes.com>
- **端點**：`/rss/cat/tw_stock`（公開 RSS，無 token）
- **解析**：`feedparser`
- **支援 DataKind**：NEWS
- **症狀**：偶爾 RSS 內容包含舊新聞 → news_repo 用 url dedupe
- **匹配策略**：P5 簡化用 symbol 字串 substring；P7 接 stock_list 後改成「symbol → 公司中文名」精準匹配

---

## 2. 共用機制

### 2.1 Circuit Breaker（PLAN 14.3）

- 全域 `app.core.circuit_breaker.CIRCUIT_BREAKERS: dict[str, CircuitBreaker]`
- 連續 5 次失敗 → OPEN 10 分鐘 → HALF_OPEN 試 1 次 → 成功 CLOSED / 失敗繼續 OPEN
- 觸發 OPEN 時 log `circuit_breaker.opened`（CRITICAL）— P18 接 LINE 通知

### 2.2 DataSourceFallback chain（PLAN 14.4）

```python
fb = DataSourceFallback([FinMindSource(s), TWSESource(s), TPEXSource(s)],
                        stale_cache_loader=redis_cache_get)
df = await fb.fetch_ohlcv("2330", start, end)
```

行為：
1. 依 priority 升序排（10 → 20 → 25 → 30）
2. 對每個 source：
   - `cb.state == OPEN` → 跳過，不浪費 quota
   - try fetch → 成功 `cb.record_success` 並 return
   - 失敗 → `cb.record_failure` + log warning，繼續下一個
3. 全部失敗 → 嘗試 `stale_cache_loader`；無快取 → raise `ExternalServiceError`

### 2.3 AsyncLimiter（rate limit）

> 注意陷阱：`AsyncLimiter(max_rate, time_period)` 在 max_rate < 1 時 leaky bucket capacity 會被 floor 為 0 → 永久 acquire 失敗（`Can't acquire more than the maximum capacity`）。
>
> `BaseDataSource.__init__` 在 rate < 1 時自動切成「1 次 / N 秒」（`AsyncLimiter(1, 1.0 / rate)`）。

---

## 3. 運維 SOP

### 3.1 加新 source

1. 新增檔案 `app/data_sources/<region>/<source_name>_source.py`
2. 繼承 `BaseDataSource`，設定 class-level：`name / priority / supported_regions / supported_kinds / rate_limit_per_sec / base_url`
3. Override `fetch_*` 對應支援的 DataKind
4. 用 `@register_data_source` 裝飾
5. 在 `app/data_sources/<region>/__init__.py` import 該檔（觸發 register）
6. 加 unit test（mock httpx + 各種錯誤情境）

### 3.2 切換主備源

修改 source class 的 `priority` 屬性即可。例如：
- FinMind 配額用盡 → 把 `FinMindSource.priority` 從 10 改成 30；TWSE 從 20 改成 10
- 不需要動 fallback 邏輯（自動 re-sort）

### 3.3 緊急停用某 source

```python
# 不要刪程式碼，直接讓 CB 強制 OPEN
cb = CIRCUIT_BREAKERS["finmind"]
for _ in range(cb.failure_threshold):
    await cb.record_failure()
# fallback 會自動跳過
```

或刪除 `@register_data_source` 裝飾（會被 re-import 時自動恢復，建議用 CB 法）。

### 3.4 監控

| 訊號 | 對應 log event |
|------|----------------|
| Source 失敗 | `fallback.source_failed` |
| 跳過 OPEN CB | `fallback.skipped_open_breaker` |
| 用備源回應 | `fallback.recovered_via_secondary` |
| 用 stale cache | `fallback.using_stale_cache` |
| CB 觸發 OPEN | `circuit_breaker.opened`（CRITICAL）|

P18 接 LINE / Grafana 推送 CRITICAL。

---

## 4. US 資料源（Phase 6 補完）

預留 stub：

| 來源 | 主／備 | DataKind | 預計實作 |
|------|--------|----------|---------|
| yfinance | 主 | OHLCV / FINANCIAL / NEWS | Phase 6 |
| Alpha Vantage | 備 | OHLCV / FINANCIAL | Phase 6 |
| Finnhub | 備 | FINANCIAL | Phase 6 |
| SEC EDGAR | 主 | ANNOUNCEMENT（10-K/10-Q/8-K） | Phase 6 |
