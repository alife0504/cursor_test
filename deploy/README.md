# 監控堆疊（Prometheus + Grafana）

即時運維指標的歷史走勢視覺化。後端 `/metrics` 一直有 Prometheus 格式輸出（`app/core/metrics.py`），本堆疊補上「抓取 + 儀表板」那層。

## 啟動

```bash
docker compose --profile monitoring up -d prometheus grafana
```

- **Grafana**：http://localhost:3001 （匿名可看；管理登入預設 `admin` / `admin`，或設 `GRAFANA_ADMIN_PASSWORD`）
  - 首頁儀表板：**TradingAgents 監控總覽**（`/d/tradingagents-main`）
- **Prometheus**：http://localhost:9090 （Status → Targets 應見 `tradingagents-backend` = UP）

## 認證（重要）

`/metrics` 用**靜態 token** 認證（JWT 會過期不適合 scrape）。需在 `.env` 設：

```
METRICS_TOKEN=<隨機字串>
```

- 已在本機 `.env` 產生（`python -c "import secrets;print(secrets.token_hex(32))"`）。
- Prometheus 容器啟動時，用 entrypoint 把 `prometheus.tmpl.yml` 的 `__METRICS_TOKEN__`
  換成此值（範本不含機密、可入 git；真值只在 gitignored 的 `.env`）。
- 未設 `METRICS_TOKEN` → `/metrics` 回 401（停用），Prometheus target 會 DOWN。

## 資料正確性（跨程序）

分析跑在 celery 程序、HTTP 在 backend 程序，in-memory counter 無法跨程序。
故業務指標（今日分析/成本/tokens、佇列、DB 大小、DLQ）由 `/metrics` **被抓取時
即時查 DB/redis/pool** 設定（pull 模型），保證與真實狀態一致。
HTTP 延遲/吞吐/錯誤率則由 backend（單一 uvicorn worker）的 middleware histogram 累積。

## 儀表板面板

HTTP 黃金訊號（請求速率 / p50·p95 延遲 / 5xx 錯誤率）＋ 業務即時值
（今日分析依 status、進行中、LLM 成本、tokens、Celery 佇列、DB 大小、DLQ、DB 連線）。
只放「保證有真實資料」的面板，不放空殼。
