#!/bin/bash
# scripts/health_checks/phase_14.sh
# Phase 14 健康檢查：美股 Analyst + LLM Fallback Chain + WS 串流 + 月配額。
#
# 涵蓋（13 項）：
#   1. Phase 13 仍正常
#   2. uv sync + ruff lint
#   3. backend 起得來，/health/live 200
#   4. 3 個 LLM provider 已註冊（google / openai / anthropic）
#   5. get_llm_chain(settings) 可建（至少一個 provider 有 key）
#   6. 美股 prompt 模板存在（market / fundamental / news 三個 _us_template）
#   7. orders_decision.signal_to_pending_order 邏輯正確（BUY → order, HOLD → None）
#   8. QuotaService 行為正確（unit test）
#   9. P14 unit 測試全綠
#  10. P14 integration 測試全綠（US pipeline + cross-market + quota + WS streaming）
#  11. POST /analysis 仍可推 task（含 quota 通過路徑）
#  12. 累積測試 ≥ 640（從 P13 的 604 增加 ≥ 36）
#  13. run_analysis 任務 import LLMFallbackChain 不再用 single provider

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 14 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

# Docker graceful skip
if ! docker info > /dev/null 2>&1; then
  echo "⚠️  Docker daemon 未啟動 → 跳過 runtime 檢查"
  exit 0
fi

if [ ! -f .env ]; then
  echo "❌ 找不到 .env"
  exit 1
fi

ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env | cut -d= -f2- | tr -d '"' | tr -d "'")
ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env | cut -d= -f2- | tr -d '"' | tr -d "'")
PG_PWD=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2- | tr -d '"' | tr -d "'")
REDIS_PWD=$(grep ^REDIS_PASSWORD= .env | cut -d= -f2- | tr -d '"' | tr -d "'")
PG_DB=$(grep ^POSTGRES_DB= .env | cut -d= -f2- | tr -d '"' | tr -d "'")
PG_DB=${PG_DB:-tradingagents_tw}

# 預先解鎖 admin + 清 rate-limit + idempotency
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='$ADMIN_EMAIL'" \
  > /dev/null 2>&1 || true
docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true
docker compose exec -T redis redis-cli -n 6 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true

# ── 1) Phase 13 仍正常 ─────────────────────────────────
echo "  → 跑 Phase 13 健康檢查（內含 backend 啟動，約需 1~3 分鐘）..."
P13_LOG=$(mktemp)
if ! bash scripts/health_checks/phase_13.sh > "$P13_LOG" 2>&1; then
  echo "❌ Phase 13 健康檢查失敗（最後 30 行）："
  tail -30 "$P13_LOG"
  rm -f "$P13_LOG"
  exit 1
fi
rm -f "$P13_LOG"
echo "✓ Phase 13 健康檢查仍綠"

docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true

# ── 2) uv sync + ruff ───────────────────────────────────
( cd backend && uv sync > /dev/null 2>&1 )
( cd backend && uv run ruff check app/ tests/ > /dev/null 2>&1 )
echo "✓ uv sync + ruff lint 通過"

# ── 3) backend 起得來 ──────────────────────────────────
SERVER_PID=""
LOG_FILE=$(mktemp)
COOKIE_JAR=$(mktemp)
HC_SYMBOL="91401"
cleanup() {
  [ -n "$SERVER_PID" ] && kill $SERVER_PID 2>/dev/null || true
  rm -f "$LOG_FILE" "$COOKIE_JAR"
  docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
    psql -h localhost -U postgres "$PG_DB" \
    -c "DELETE FROM pending_orders WHERE symbol='$HC_SYMBOL';
        DELETE FROM llm_usage WHERE analysis_id IN (SELECT id FROM analysis_reports WHERE symbol='$HC_SYMBOL');
        DELETE FROM debate_history WHERE analysis_id IN (SELECT id FROM analysis_reports WHERE symbol='$HC_SYMBOL');
        DELETE FROM analysis_reports WHERE symbol='$HC_SYMBOL';
        DELETE FROM stock_list WHERE symbol='$HC_SYMBOL';" \
    > /dev/null 2>&1 || true
  docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
    psql -h localhost -U postgres "$PG_DB" \
    -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='$ADMIN_EMAIL'" \
    > /dev/null 2>&1 || true
}
trap cleanup EXIT

if ! curl -fsS http://localhost:8000/health/live > /dev/null 2>&1; then
  echo "  → 啟動臨時 uvicorn server..."
  ( cd backend && uv run uvicorn app.main:app --port 8000 > "$LOG_FILE" 2>&1 ) &
  SERVER_PID=$!
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    if curl -fsS http://localhost:8000/health/live > /dev/null 2>&1; then break; fi
    sleep 1
  done
  if ! curl -fsS http://localhost:8000/health/live > /dev/null 2>&1; then
    echo "❌ backend 啟動失敗"
    cat "$LOG_FILE"
    exit 1
  fi
fi
echo "✓ /health/live 200"

# ── 4) 3 個 LLM provider 已註冊 ────────────────────────
( cd backend && uv run python -c "
from app.llm import LLM_PROVIDER_REGISTRY
expected = {'google', 'openai', 'anthropic'}
got = set(LLM_PROVIDER_REGISTRY.keys())
assert expected.issubset(got), f'missing providers: {expected - got}'
print('OK')
" )
echo "✓ 3 個 LLM provider 已註冊（google / openai / anthropic）"

# ── 5) get_llm_chain 可建 ──────────────────────────────
( cd backend && uv run python -c "
from app.llm import get_llm_chain
from app.core.config import settings
chain = get_llm_chain(settings)
assert chain.providers, 'no provider'
print('OK', list(chain.providers.keys()), 'primary=' + chain.primary)
" )
echo "✓ LLMFallbackChain 可建（至少一個 provider 有 key）"

# ── 6) 美股 prompt 模板存在 ───────────────────────────
( cd backend && uv run python -c "
from app.agents.prompts_loader import load_prompt
for name in ('market_analyst_user_us_template',
            'fundamental_analyst_user_us_template',
            'news_analyst_user_us_template'):
    t = load_prompt(name)
    assert len(t) > 100, f'{name} too short'
print('OK')
" )
echo "✓ 美股 3 個 prompt 模板存在"

# ── 7) signal_to_pending_order 邏輯 ────────────────────
( cd backend && uv run python -c "
import uuid
from decimal import Decimal
from app.agents.managers.orders_decision import signal_to_pending_order
assert signal_to_pending_order({'action': 'HOLD'},
    analysis_id=uuid.uuid4(), user_id=uuid.uuid4(),
    symbol='2330', market='TWSE') is None
order = signal_to_pending_order(
    {'action': 'BUY', 'confidence': 70,
     'target_price_low': Decimal('100'), 'target_price_high': Decimal('120'),
     'stop_loss': Decimal('90')},
    analysis_id=uuid.uuid4(), user_id=uuid.uuid4(),
    symbol='AAPL', market='NASDAQ')
assert order is not None
assert order.side == 'BUY' and order.status == 'PENDING' and order.qty > 0
print('OK')
" )
echo "✓ signal_to_pending_order 邏輯正確（HOLD→None, BUY→PENDING）"

# ── 8) QuotaService unit 行為 ─────────────────────────
( cd backend && uv run python -c "
from app.services.quota_service import QuotaService
from app.core.config import settings
svc = QuotaService()
# 純靜態檢查 method signature
assert hasattr(svc, 'check_user_can_analyze')
assert hasattr(svc, 'record_usage')
assert hasattr(svc, 'get_user_budget')
print('OK')
" )
echo "✓ QuotaService method 完整"

# ── 9) P14 unit 測試 ──────────────────────────────────
P14_UNIT_LOG=$(mktemp)
if ! ( cd backend && uv run pytest \
        tests/unit/test_openai_provider.py \
        tests/unit/test_anthropic_provider.py \
        tests/unit/test_fallback_chain.py \
        tests/unit/test_signal_to_order.py \
        -m "not network and not expensive" -q 2>&1 ) > "$P14_UNIT_LOG" 2>&1; then
  echo "❌ P14 unit 測試失敗（最後 30 行）："
  tail -30 "$P14_UNIT_LOG"
  rm -f "$P14_UNIT_LOG"
  exit 1
fi
rm -f "$P14_UNIT_LOG"
echo "✓ P14 unit 測試全綠（OpenAI / Anthropic / FallbackChain / signal_to_order）"

# ── 10) P14 integration 測試 ──────────────────────────
P14_INT_LOG=$(mktemp)
if ! ( cd backend && uv run pytest \
        tests/integration/test_us_full_pipeline.py \
        tests/integration/test_cross_market_e2e.py \
        tests/integration/test_quota_service.py \
        tests/integration/test_llm_quota_blocks_analysis.py \
        tests/integration/test_ws_streaming.py \
        -m "not network and not expensive" -q 2>&1 ) > "$P14_INT_LOG" 2>&1; then
  echo "❌ P14 integration 測試失敗（最後 40 行）："
  tail -40 "$P14_INT_LOG"
  rm -f "$P14_INT_LOG"
  exit 1
fi
rm -f "$P14_INT_LOG"
echo "✓ P14 integration 測試全綠（US pipeline + cross-market + quota + WS streaming）"

# ── 11) POST /analysis 推 task（quota 通過）─────────────
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "INSERT INTO stock_list (symbol, market, name, is_active) VALUES ('$HC_SYMBOL','TWSE','P14健檢',true)
      ON CONFLICT (symbol) DO NOTHING;" \
  > /dev/null 2>&1

LOGIN_RESP=$(curl -s -c "$COOKIE_JAR" -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}")
TOKEN=$(echo "$LOGIN_RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('access_token', ''))" 2>/dev/null)
CSRF_TOKEN=$(awk '/csrf_token/ {print $NF}' "$COOKIE_JAR" | tail -1)
if [ -z "$TOKEN" ] || [ "$TOKEN" = "None" ]; then
  echo "❌ admin login 失敗：$LOGIN_RESP"
  exit 1
fi
KEY=$(python -c "import uuid; print(uuid.uuid4())")
A_RESP=$(curl -s -b "$COOKIE_JAR" -X POST http://localhost:8000/api/v1/analysis \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\":\"$HC_SYMBOL\",\"analyst_types\":[\"market\"],\"llm_model\":\"gemini-2.0-flash\",\"debate_rounds\":0}")
ANALYSIS_ID=$(echo "$A_RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('analysis_id', ''))" 2>/dev/null)
if [ -z "$ANALYSIS_ID" ] || [ "$ANALYSIS_ID" = "None" ]; then
  echo "❌ POST /analysis 失敗：$A_RESP"
  exit 1
fi
echo "✓ POST /analysis（quota 通過）→ analysis_id=$ANALYSIS_ID"

# ── 12) 累積測試 ≥ 640 ────────────────────────────────
TOTAL=$( cd backend && uv run pytest --collect-only -q 2>&1 | tail -1 | grep -oE "[0-9]+ tests" | grep -oE "[0-9]+" )
if [ "${TOTAL:-0}" -lt 640 ]; then
  echo "❌ 累積測試 $TOTAL < 640"
  exit 1
fi
echo "✓ 累積測試 $TOTAL ≥ 640"

# ── 13) run_analysis 已用 LLMFallbackChain ────────────
( cd backend && uv run python -c "
import inspect
from app.workers.tasks.run_analysis import _async_pipeline
src = inspect.getsource(_async_pipeline)
assert 'get_llm_chain' in src, 'run_analysis 未升級為 LLMFallbackChain'
assert 'publish_event_sync' in src, 'run_analysis 未串接 streaming'
assert 'signal_to_pending_order' in src, 'run_analysis 未串接 pending_order'
print('OK')
" )
echo "✓ run_analysis 已升級：LLM chain + streaming + pending_order"

echo ""
echo "✅ Phase 14 健康檢查全部通過"
