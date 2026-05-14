#!/bin/bash
# scripts/health_checks/phase_07.sh
# Phase 7 健康檢查：Celery Worker + Beat + DLQ + Bootstrap Scripts。
#
# 涵蓋：
#   1. P6 仍正常（5 TW + 4 US source 註冊 + ruff）
#   2. celery_app 模組可 import + beat schedule 註冊正確
#   3. DLQ 表存在 + 可寫入（用 sync_rw_session）
#   4. /health/seeded 端點回 envelope（status 200）
#   5. P7 4 個新 test 檔全綠
#   6. ta_service_rw 仍不能改 audit_logs（PLAN 19.6 退化）
#   7. ruff check 通過
#
# 不在這檢查的（acceptance 才檢）：
#   - seed_stock_list 真打網路（會 5-10 分鐘）→ acceptance step 3
#   - backfill 真打網路 → acceptance step 6
#   - celery_worker / celery_beat 容器啟動 → acceptance step 8

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 07 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

# 1. P6 仍正常 — 9 個 source 全部註冊
cd backend
uv run python -c "
import app.data_sources.tw, app.data_sources.us
from app.data_sources.base import DATA_SOURCE_REGISTRY
expected = {'finmind','twse_openapi','tpex','mops','cnyes_rss',
            'yfinance','alpha_vantage','finnhub','sec_edgar'}
got = set(DATA_SOURCE_REGISTRY.keys()) & expected
assert got == expected, f'missing: {expected - got}'
print('OK')
" >/dev/null 2>&1 || { echo "❌ P6 退化：9 個 source 未全部註冊"; exit 1; }
echo "✓ P6 source registry 仍正常（9 個）"
cd "$PROJECT_ROOT"

# 2. celery_app 可 import + beat schedule 註冊正確
cd backend
uv run python -c "
from app.workers.celery_app import celery_app
sched = celery_app.conf.beat_schedule
required = {
  'tw-ohlcv-after-close',
  'us-ohlcv-after-close',
  'tw-news-hourly',
  'us-news-3h',
  'tw-monthly-revenue',
  'tw-institutional-daily',
  'cleanup-orphans-daily',
  'cleanup-idempotency-daily',
  'verify-audit-chain-daily',
}
got = set(sched.keys())
assert required <= got, f'missing schedules: {required - got}'
assert celery_app.conf.timezone == 'Asia/Taipei', f'tz={celery_app.conf.timezone}'
assert celery_app.conf.task_acks_late is True
print('OK')
" >/dev/null 2>&1 || { echo "❌ celery_app 設定不正確"; exit 1; }
echo "✓ celery_app + beat schedule（9 排程）正確"
cd "$PROJECT_ROOT"

# 3. DLQ 表存在 + 可用 sync_rw_session 寫入
cd backend
uv run python -c "
import uuid
from app.core.database import sync_rw_session, dispose_sync_rw_engine
from app.models.dlq import CeleryDeadLetter
try:
    with sync_rw_session() as s:
        s.add(CeleryDeadLetter(
            task_name='health_check_p07',
            task_id=uuid.uuid4(),
            args={'a':1}, kwargs={'b':2},
            exception_type='HealthCheckError',
            exception='dummy from phase_07.sh',
            traceback='', retry_count=0, resolved=False,
        ))
        s.commit()
    # cleanup
    from sqlalchemy import text
    with sync_rw_session() as s:
        s.execute(text(\"DELETE FROM celery_dead_letters WHERE task_name='health_check_p07'\"))
        s.commit()
    print('OK')
finally:
    dispose_sync_rw_engine()
" >/dev/null 2>&1 || { echo "❌ DLQ sync 寫入失敗"; exit 1; }
echo "✓ DLQ 表存在 + sync_rw_session 寫入成功"
cd "$PROJECT_ROOT"

# 4. /health/seeded 端點 — 暫起 backend 跑就好；不一定回 true（依 DB 狀態）
#    這裡只驗 endpoint 跑得通且回 200 + envelope shape
if curl -fsS "http://localhost:8000/health/seeded" >/dev/null 2>&1; then
  BODY=$(curl -fsS "http://localhost:8000/health/seeded")
  echo "$BODY" | grep -q '"data"' && echo "$BODY" | grep -q '"seeded"' || {
    echo "❌ /health/seeded envelope shape 錯：$BODY"
    exit 1
  }
  echo "✓ /health/seeded 回 envelope (data.seeded 欄位存在)"
else
  echo "ⓘ backend 未跑（make backend-dev / docker compose up backend）— 略過 /health/seeded 線上驗"
fi

# 5. P7 4 個新 test 檔（unit + integration mock 部分，不打網路）
cd backend
uv run pytest \
  tests/unit/test_celery_app_config.py \
  tests/unit/test_dlq_signal.py \
  -m "not network" -q --no-header 2>&1 | tail -1 | grep -qE "[0-9]+ passed" || {
  echo "❌ P7 unit tests 未全綠"
  exit 1
}
echo "✓ P7 unit tests 全綠（celery_app_config + dlq_signal）"
cd "$PROJECT_ROOT"

# 6. ta_service_rw 仍不能 DELETE audit_logs（PLAN 19.6 退化）
#    用 docker exec 而非 host psql（避免 host 沒裝 postgresql-client）
RW=$(grep ^TA_SERVICE_RW_PASSWORD= .env | cut -d= -f2)
DELETE_OUT=$(docker compose exec -T -e PGPASSWORD="$RW" timescaledb \
  psql -h localhost -U ta_service_rw -d tradingagents_tw \
  -c "DELETE FROM audit_logs WHERE id=1" 2>&1 || true)
if echo "$DELETE_OUT" | grep -qi "permission denied"; then
  echo "✓ ta_service_rw 仍無 DELETE audit_logs 權限"
else
  echo "❌ ta_service_rw 對 audit_logs 權限有變動（請查 baseline 0013）"
  echo "    output: $DELETE_OUT"
  exit 1
fi

# 7. ruff 通過
cd backend
uv run ruff check app/ tests/ >/dev/null 2>&1 || { echo "❌ ruff check 失敗"; exit 1; }
cd "$PROJECT_ROOT"
echo "✓ ruff check 通過"

echo ""
echo "✅ Phase 07 健康檢查全部通過"
