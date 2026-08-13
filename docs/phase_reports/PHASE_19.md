# Phase 19 — 整合測試 + E2E + Prod 部署 + 災難復原演練

完成日期：2026-05-18
分支：`phase/19-prod-deploy-dr`

## 1. 目標

讓系統「可在 prod 環境跑起來」+「災難復原可演練成功」：

1. Playwright 完整 E2E 流程（≥ 10 個 test，原本 5 個 → 升級 10）
2. `docker-compose.prod.yml` 完整化（nginx + TLS + resource limits + read-only + cap_drop）
3. `backup.sh` / `restore.sh` / `verify_backup.sh`（含 GPG 加密 + 30 天保留）
4. DR 演練情境 A（DB 損毀還原）腳本與 RTO 紀錄機制
5. SLO 報表 `slo_report.py` 完整化（依第 16.4 章 5 個指標 + 錯誤預算）
6. Prod 啟動 SOP 文件化（`docs/runbooks/prod_deployment.md`）
7. 後端 E2E 測試 7 個 + SLO 8 個 + backup/restore 11 個 = 26 個新 test
8. prod backend port 不對外（只 nginx）

## 2. 完成項目

### 2.1 程式檔（新增）

- `docker-compose.prod.yml`（完整化：DB 三服務 + backend + celery_worker + celery_beat + frontend + **nginx**）
- `docker-compose.test-restore.yml`（隔離還原驗證，timescaledb_test on port 5433）
- `docker/nginx/nginx.conf`（HTTPS / WS Upgrade / SSE buffering off / rate limit / security headers / JSON log format）
- `scripts/generate_self_signed_cert.sh`（含 SAN：CN/DNS/IP，cert 剩 < 30 天才重產）
- `scripts/backup.sh`（PG custom dump -Z 9 + Qdrant snapshot + tar + GPG encrypt + 30 天保留）
- `scripts/restore.sh`（GPG decrypt + DROP/CREATE DB + pg_restore + Qdrant volume 解壓）
- `scripts/verify_backup.sh`（用 docker-compose.test-restore.yml 啟隔離 DB 還原 + 跑 verify_data.py）
- `scripts/dr_drill_a.sh`（演練情境 A：backup → 砍 volume → 重建 → restore → 量 RTO → 寫報告）
- `scripts/slo_report.py`（5 個 SLI + 錯誤預算消耗率 + 任一 breach 廣播 system.alert）
- 後端測試（共 26 個）：
  - `tests/integration/test_full_workflow_e2e.py`（7 個 E2E）
  - `tests/integration/test_slo_report.py`（8 個 SLO unit/integration）
  - `tests/integration/test_backup_restore.py`（11 個 script + compose 驗證）
- `scripts/health_checks/phase_19.sh`（15 項檢查）

### 2.2 程式檔（修改）

- `.env.prod.example`（從 `.env.example` 衍生：APP_ENV=prod + CSP_PROD_ENABLED=true + BACKUP_DIR + GPG_RECIPIENT 等）
- `Makefile`（加 P19 8 個 target：`prod-up` / `prod-down` / `prod-logs` / `prod-ps` / `prod-restart` / `backup` / `restore` / `verify-backup` / `slo-report` / `dr-drill-a` / `generate-cert`）
- `frontend/tests/e2e/full-workflow.spec.ts`（5 → 10 test scenarios，加 theme / history / PDF download / offline / admin users）

### 2.3 文件檔（新增）

- `docs/phase_reports/PHASE_19.md`（本檔）
- `docs/runbooks/prod_deployment.md`（prod 啟動 SOP）
- `docs/runbooks/disaster_recovery.md`（DR 6 種情境 + 演練流程）
- `docs/runbooks/backup_restore.md`（backup/restore/verify 操作手冊）
- `docs/dr_drills/`（DR 演練報告存放目錄；`scripts/dr_drill_a.sh` 自動寫入）
- `docs/slo_reports/`（SLO 每日報表存放目錄；`scripts/slo_report.py` 自動寫入）

## 3. 設計決策

### 3.1 Backend / Celery 強化（PLAN § 12.1 + 19）

```yaml
backend:
  expose: ["8000"]           # 不對外
  read_only: true            # 整個檔案系統唯讀
  tmpfs: [/tmp:size=128M]    # 只開放 /tmp 寫入
  cap_drop: [ALL]            # 移除所有 capability
  user: "1000:1000"          # 非 root
  deploy.resources.limits: { memory: 4G, cpus: "4.0" }
```

DLQ fallback file 改寫 `/tmp/celery_dlq_fallback.jsonl`，Celery beat schedule 改寫 `/tmp/celerybeat-schedule`，避開 read-only fs。

### 3.2 nginx 設定亮點

- `proxy_buffering off` 給 SSE / WS（`/api/v1/analyses/*/stream` + `/api/v1/ws/`）
- WS upgrade 用 `^~` location 優先 + `proxy_read_timeout 86400s`
- rate limit zone：`api` 10 r/s + burst 20、`ws` 5 r/s + burst 10
- 安全 headers：X-Frame DENY / X-Content nosniff / Referrer-Policy strict-origin-when-cross-origin
- **HSTS 預設關閉**（self-signed cert 開啟會鎖死瀏覽器，docs 註記 prod 真實憑證後再打開）
- JSON access log（方便 SLO 與 trace_id 追蹤）

### 3.3 verify_backup.sh 隔離策略

不污染 prod DB，用獨立 `docker-compose.test-restore.yml`：
- 容器 `ta-timescaledb-test-restore`，對外 5433（避開 prod 5432）
- DB 名 `tradingagents_tw_test`
- volume `tradingagents_timescaledb_data_test`（與 prod volume 完全隔離）
- 重複利用 prod 的 `init.sh` + `init.sql.template`（schema 對齊）
- `down -v` 預設每次清乾淨；`KEEP_TEST_DB=1` 可保留供除錯

### 3.4 SLO 報表（PLAN § 9.2 + 16.4）

5 個 SLI：

| 指標 | 目標 | 量測 |
|------|------|------|
| API 可用性 | ≥ 99% | `audit_logs` `action='http.request'` + `(details->>'status')::int >= 500` |
| 分析完成率 | ≥ 95% | `analysis_reports.status = 'completed'` / total |
| 分析延遲 P95 | ≤ 300s | PG `percentile_cont(0.95) WITHIN GROUP (ORDER BY completed_at - started_at)` |
| 資料新鮮度 | ≤ 60min | `max(stock_prices.ingested_at)`；**週末跳過**（資料源不更新） |
| Audit 完整性 | 100% | `AuditRepository.verify_chain(since)` |

**錯誤預算消耗率**：

- rate 類：`(target - actual) / (1 - target)`
- latency / freshness 類：`(actual - target) / target`
- > 1.0 表示 24h 預算超用

任一 breach → 發 `system.alert` WARN 事件（透過 NotificationDispatcher 廣播）。

### 3.5 DR 演練情境 A 流程

```
backup → stop backend/celery → stop timescaledb → docker volume rm
       → up timescaledb (跑 init.sh) → wait healthy
       → restore (RESTORE_AUTO_CONFIRM=1)
       → 重啟 backend → verify_data + verify_audit_chain
       → 寫 docs/dr_drills/scenario_a_YYYYMMDD.md（含各步驟耗時 + RTO 對比）
```

RTO 目標 60 分鐘；docs 自動算實際耗時並標示 ✅/❌。

## 4. 完成驗收（健康檢查 15 項）

```bash
bash scripts/health_checks/phase_19.sh
```

通過項目：
1. ✓ backend uv sync
2. ✓ ruff check 通過
3. ✓ docker-compose.prod.yml 含 8 個必要 services
4. ✓ test-restore compose 含 timescaledb_test (5433)
5. ✓ nginx.conf 含 HTTPS/WS/SSE/rate-limit/security-headers
6. ✓ .env.prod.example 含 prod 必需 10 個 key
7. ✓ 5 個 shell script 存在 + +x + 語法正確
8. ✓ slo_report.py 結構正確 + burn rate 計算對
9. ✓ 3 個 P19 integration tests 存在
10. ✓ full-workflow.spec.ts 含 10 個 test
11. ✓ Makefile 含 8 個 P19 targets
12. ✓ docker/nginx/certs/ 存在
13. ✓ docker compose prod config 通過
14. ✓ phase_18 health check 仍綠
15. ✓ 後端測試 714 ≥ P19 基準 410

## 5. 測試結果

- **後端**：
  - 累積 `pytest --collect-only` = **714 tests**（P18 結尾 688 + P19 新增 26 = 714）
  - P19 新測試（26）：
    - `test_full_workflow_e2e.py` × 7（全綠）
    - `test_slo_report.py` × 8（全綠）
    - `test_backup_restore.py` × 11（全綠）
- **前端 E2E**：`full-workflow.spec.ts` 10 個 scenarios

## 6. 已知限制

| 項目 | 限制 | 備註 |
|------|------|------|
| HSTS | 預設關閉 | self-signed cert 環境關掉防鎖死；上 prod 真實憑證後在 nginx.conf 取消註解 |
| Let's Encrypt 自動化 | 未實作 | v1.0 僅提供 self-signed；docs 寫 certbot 手動指引 |
| GPG key 自動 import | 未實作 | 部署者需先 `gpg --import backup_pubkey.asc`；docs 說明 |
| DR 演練情境 B/C/D/E/F | 未腳本化 | v1.0 僅 A（DB 損毀）；其他依 PLAN § 32.2 表手動 |
| `verify_backup.sh` 對 Qdrant | 僅 PG 驗 | Qdrant 還原驗證需單獨 trigger snapshot |
| Playwright PDF 匯出 E2E | 容忍 fallback | CI 環境 chromium dep 可能缺；test 允許 200/500/503 |

## 7. 操作快速參考

```bash
# Prod 啟動
make generate-cert                                    # 產 self-signed cert
cp .env.prod.example .env.prod && vim .env.prod      # 填值
make prod-up                                          # docker compose up -d
make init-db && make seed-stocks                      # 首次

# 備份
make backup                                           # 跑備份
ls -lt docker/backups/full_*.tar.gz.gpg | head        # 看最新

# 驗證
make verify-backup FILE=docker/backups/full_xxx.tar.gz.gpg

# 還原
make restore FILE=docker/backups/full_xxx.tar.gz.gpg

# DR 演練（會清資料！）
make dr-drill-a

# SLO 報表
make slo-report
ls docs/slo_reports/                                  # YYYY-MM-DD.json

# 健康檢查
bash scripts/health_checks/phase_19.sh
```

## 8. 後續行動（P20）

- `scripts/health_checks/all.sh` — 跑遍 phase_01.sh ~ phase_19.sh
- `PROJECT_FINAL_REPORT.md` — 累積測試數 / 涵蓋率 / 已知 risk / v1.1 roadmap
- 真實 prod 環境演練 DR 情境 A 至少一次
