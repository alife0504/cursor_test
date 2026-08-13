# LLM Providers Runbook

> 適用 v7.0 Phase 14 起：Google Gemini / OpenAI / Anthropic + Fallback Chain。

---

## 1. 三個 Provider 概覽

| Provider | name | default_model | pricing（per 1M tokens） | 預設 health_check |
|----------|------|---------------|------------------------|-------------------|
| Google Gemini | `google` | `gemini-2.0-flash` | input $0.10 / output $0.40 | 檢查 API key + langchain 可 import（不打 API） |
| OpenAI | `openai` | `gpt-4o-mini` | input $0.15 / output $0.60 | `models.list(timeout=5)` |
| Anthropic | `anthropic` | `claude-haiku-3-5-20241022` | input $0.80 / output $4.00 | 發 1-token message（無 GET 端點可 ping） |

> Pricing 表寫死在各 provider 檔案的 `pricing` ClassVar；新 model name 上線時直接加 entry（key 為實際傳 API 的 model string）。

## 2. .env 設定

```bash
# 至少要設一個（lifespan 啟動會 raise）
GOOGLE_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# 預設 primary provider；fallback chain 啟動會用此
LLM_DEFAULT_PROVIDER=google
LLM_DEFAULT_MODEL=gemini-2.0-flash
OPENAI_DEFAULT_MODEL=gpt-4o-mini
ANTHROPIC_DEFAULT_MODEL=claude-haiku-3-5-20241022

# 月配額（每用戶；可被 llm_monthly_quota.budget_usd 覆寫）
LLM_MONTHLY_BUDGET_USD_DEFAULT=50.00
```

## 3. Fallback Chain 規則

依 PLAN.md 第 14.4 章：

```python
FALLBACK_CHAIN = {
    "google":    ["openai", "anthropic"],
    "openai":    ["google", "anthropic"],
    "anthropic": ["google", "openai"],
}
```

- primary 失敗 → 依序試 fallback 中的第一個未跳過的 provider。
- CB OPEN 的 provider 直接跳過（不浪費 timeout）。
- 該 provider 未配置 API key（不在 `chain.providers` dict）→ 跳過。
- 全部 fail / 全部跳過 → raise `ExternalServiceError(name="llm_fallback_chain")`。

## 4. 監控與排錯

### 4.1 觀察日誌

每次 LLM call 會 emit：

```
llm_fallback.success provider=openai primary=google used_fallback=True input_tokens=400 output_tokens=200
```

若 primary 切走，`used_fallback=True` 是黃旗 — 連續多次需排查 primary。

### 4.2 CircuitBreaker 狀態

```bash
# 查當前 OPEN 的 CB（在 Python REPL）
from app.core.circuit_breaker import CIRCUIT_BREAKERS
for name, cb in CIRCUIT_BREAKERS.items():
    if str(cb.state) != "CLOSED":
        print(name, cb)
```

預期應為 `llm.google` / `llm.openai` / `llm.anthropic`（其他是 data source CB）。

### 4.3 月配額查詢

```sql
-- 當月 used vs limit
SELECT
  u.email,
  COALESCE(q.budget_usd, 50.00) AS limit_usd,
  SUM(usage.cost_usd) AS used_usd
FROM users u
LEFT JOIN llm_monthly_quota q
  ON q.user_id = u.id AND q.year = EXTRACT(year FROM NOW())
  AND q.month = EXTRACT(month FROM NOW())
LEFT JOIN llm_usage usage
  ON usage.user_id = u.id
  AND usage.created_at >= DATE_TRUNC('month', NOW())
GROUP BY u.email, q.budget_usd
ORDER BY used_usd DESC NULLS LAST;
```

### 4.4 強制 fallback 切換（測試用）

```bash
# 把 GOOGLE_API_KEY 改成錯的 → primary 失敗 → 切 openai
export GOOGLE_API_KEY=invalid
uv run uvicorn app.main:app --port 8000

# 跑分析觀察 log 中 used_provider
```

### 4.5 全部 LLM 全失敗

- 啟動會直接 raise（lifespan 阻擋）。
- 跑分析時：`ExternalServiceError(name="llm_fallback_chain")` → 在 task 內 mark analysis status=failed → publish `failed` event。

## 5. 加新 model

1. 在對應 provider 的 `pricing` ClassVar 加 entry：
   ```python
   pricing: ClassVar[dict[str, tuple[Decimal, Decimal]]] = {
       "gemini-2.5-flash": (Decimal("0.0001"), Decimal("0.0004")),  # 新加
       ...
   }
   ```
2. 若 default model 要換 → 改 `default_model` ClassVar（或 .env 的 `OPENAI_DEFAULT_MODEL` 等）。
3. `pricing` 表沒對應 model name → `calc_cost` 回 `Decimal("0")` + warning（不擋呼叫）。

## 6. 加新 provider（plugin pattern）

依 PLAN.md 第 18.2 章：

1. 建 `app/llm/new_provider.py`：
   ```python
   @register_llm_provider
   class NewProvider(BaseLLMProvider):
       name: ClassVar[str] = "new"
       default_model: ClassVar[str] = "..."
       pricing: ClassVar[dict] = {...}

       def __init__(self, settings):
           super().__init__(settings)
           self.cb = get_or_create_breaker("llm.new")
           # client setup

       async def generate(self, system, user, **kw) -> LLMResponse: ...
       async def health_check(self) -> bool: ...
   ```
2. 在 `app/llm/__init__.py` 補 import + `get_llm_chain` 內 `if settings.NEW_API_KEY: providers["new"] = NewProvider(settings)`。
3. 在 `fallback_chain.FALLBACK_CHAIN` 加入該 provider 的 fallback order。
4. 在 `Settings` 加 `NEW_API_KEY: SecretStr | None = None` + `NEW_DEFAULT_MODEL`。

## 7. WS Streaming 事件

| event | data 範例 | 何時 |
|-------|-----------|------|
| `started` | `{symbol, market, analyst_types, debate_rounds, started_at}` | task 開始 |
| `analyst_completed` | `{node: "market", result_length: 1200, preview: "..."}` | 每個 analyst 跑完 |
| `debate_argument` | `{node: "bull", role: "bull", round: 1, preview: "..."}` | 每輪 bull/bear |
| `synthesis_completed` | `{node: "manager", action: "BUY", confidence: 75, report_length: 3500}` | manager 寫完報告 |
| `completed` | `{action, confidence, report_excerpt, used_provider, duration_s, tokens, pending_order_id}` | task 成功 |
| `failed` | `{error: "..."}` | task 失敗 |

channel: `analysis:{analysis_id}`（Redis db4 PUBSUB）。

### 7.1 訂閱範例（CLI）

```bash
docker compose exec -T redis redis-cli -n 4 -a "$REDIS_PWD" --no-auth-warning PSUBSCRIBE 'analysis:*'
```

### 7.2 client 失連自負責 reconnect

- 已發出的 message 不重送（pubsub 設計）。
- WS endpoint 在 `ws_router` 訂閱該 channel，把每筆 message forward 給前端。
