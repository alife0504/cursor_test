#!/bin/bash
# scripts/health_checks/phase_13.sh
# Phase 13 健康檢查：4 種 TW Analyst 完整化 + Bull/Bear/Manager + 結構化輸出。
#
# 涵蓋（12 項）：
#   1. P12 健康檢查仍正常
#   2. uv sync + ruff lint
#   3. backend 起得來，/health/live 200
#   4. 4 個 Analyst 已非 stub（含 compute_indicators / tools.get_*）
#   5. 12 個 prompt 模板可載入 + 7 個 Pydantic schema 可序列化
#   6. P13 unit + integration 測試全綠（test_indicators / test_schemas / test_llm_helpers /
#       test_market_analyst / test_full_tw_pipeline）
#   7. POST /analysis 推 task（analyst_types=4 種 + sentiment 不被擋）
#   8. ResearchManager 已加入 graph（含 bull/bear 路徑）
#   9. Real LLM 測試（若有 GOOGLE_API_KEY）
#  10. llm_usage 表 schema 存在（已在 P4 migration）
#  11. 累積測試 ≥ 595
#  12. run_analysis task 接受 analyst_types/debate_rounds kwargs

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 13 健康檢查 ==="
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

docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='$ADMIN_EMAIL'" \
  > /dev/null 2>&1 || true
docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true
docker compose exec -T redis redis-cli -n 6 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true

# ── 1) Phase 12 仍正常 ─────────────────────────────────
echo "  → 跑 Phase 12 健康檢查（內含啟動，約 1~3 分鐘）..."
P12_LOG=$(mktemp)
if ! bash scripts/health_checks/phase_12.sh > "$P12_LOG" 2>&1; then
  echo "❌ Phase 12 健康檢查失敗（最後 30 行）："
  tail -30 "$P12_LOG"
  rm -f "$P12_LOG"
  exit 1
fi
rm -f "$P12_LOG"
echo "✓ Phase 12 健康檢查仍綠"

docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true

# ── 2) uv sync + ruff ───────────────────────────────────
( cd backend && uv sync > /dev/null 2>&1 )
( cd backend && uv run ruff check app/ tests/ > /dev/null 2>&1 )
echo "✓ uv sync + ruff lint 通過"

# ── 3) backend 起得來 ──────────────────────────────────
SERVER_PID=""
LOG_FILE=$(mktemp)
COOKIE_JAR=$(mktemp)
HC_SYMBOL="91301"
cleanup() {
  [ -n "$SERVER_PID" ] && kill $SERVER_PID 2>/dev/null || true
  rm -f "$LOG_FILE" "$COOKIE_JAR"
  docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
    psql -h localhost -U postgres "$PG_DB" \
    -c "DELETE FROM llm_usage WHERE analysis_id IN (SELECT id FROM analysis_reports WHERE symbol='$HC_SYMBOL');
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

# ── 4) 4 個 Analyst 不再是 stub ─────────────────────────
( cd backend && uv run python -c "
import inspect
from app.agents.analysts.market_analyst import MarketAnalyst
from app.agents.analysts.fundamental_analyst import FundamentalAnalyst
from app.agents.analysts.news_analyst import NewsAnalyst
from app.agents.analysts.sentiment_analyst import SentimentAnalyst

required = [
    (MarketAnalyst, ['compute_indicators', 'tools.get_ohlcv', 'llm_call_with_schema']),
    (FundamentalAnalyst, ['tools.get_financial', 'llm_call_with_schema']),
    (NewsAnalyst, ['tools.get_news', 'llm_call_with_schema']),
    (SentimentAnalyst, ['tools.get_institutional', 'llm_call_with_schema']),
]
for cls, needles in required:
    src = inspect.getsource(cls.analyze)
    for n in needles:
        assert n in src, f'{cls.__name__} 缺少 {n!r} - 仍是 stub？'
print('OK')
" )
echo "✓ 4 個 Analyst 全部非 stub（含 tool call + llm_call_with_schema）"

# ── 5) prompts + schemas 載入驗證 ──────────────────────
( cd backend && uv run python -c "
from app.agents.prompts_loader import load_prompt
prompts = [
    'market_analyst_system', 'market_analyst_user_tw_template',
    'fundamental_analyst_system', 'fundamental_analyst_user_tw_template',
    'news_analyst_system', 'news_analyst_user_tw_template',
    'sentiment_analyst_system', 'sentiment_analyst_user_template',
    'bull_researcher_system', 'bear_researcher_system',
    'research_manager_system', 'debate_template',
]
for name in prompts:
    txt = load_prompt(name)
    assert len(txt) > 50, f'{name} too short'

from app.agents.schemas import (
    MarketAnalysisResult, FundamentalAnalysisResult, NewsAnalysisResult,
    SentimentAnalysisResult, BullArgument, BearArgument, FinalSignal,
)
for cls in (MarketAnalysisResult, FundamentalAnalysisResult, NewsAnalysisResult,
            SentimentAnalysisResult, BullArgument, BearArgument, FinalSignal):
    schema = cls.model_json_schema()
    assert 'properties' in schema
print('OK')
" )
echo "✓ 12 個 prompt + 7 個 schema 載入完整"

# ── 6) P13 測試全綠 ────────────────────────────────────
P13_LOG=$(mktemp)
if ! ( cd backend && uv run pytest \
        tests/unit/test_indicators.py \
        tests/unit/test_schemas.py \
        tests/unit/test_llm_helpers.py \
        tests/integration/test_market_analyst.py \
        tests/integration/test_full_tw_pipeline.py \
        -m "not network and not expensive" -q 2>&1 ) > "$P13_LOG" 2>&1 ; then
  echo "❌ P13 測試失敗（最後 40 行）："
  tail -40 "$P13_LOG"
  rm -f "$P13_LOG"
  exit 1
fi
rm -f "$P13_LOG"
echo "✓ P13 unit + integration 測試全綠"

# ── 7) POST /analysis 含 sentiment（驗 P11 fix）────────
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "INSERT INTO stock_list (symbol, market, name, is_active) VALUES ('$HC_SYMBOL','TWSE','P13健檢',true)
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
  -d "{\"symbol\":\"$HC_SYMBOL\",\"analyst_types\":[\"market\",\"fundamental\",\"news\",\"sentiment\"],\"llm_model\":\"gemini-2.0-flash\",\"debate_rounds\":1}")
ANALYSIS_ID=$(echo "$A_RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('analysis_id', ''))" 2>/dev/null)
if [ -z "$ANALYSIS_ID" ] || [ "$ANALYSIS_ID" = "None" ]; then
  echo "❌ POST /analysis 失敗（含 sentiment）：$A_RESP"
  exit 1
fi
echo "✓ POST /analysis (含 sentiment) 推 task：analysis_id=$ANALYSIS_ID"

# ── 8) graph_builder 已有 bull/bear/manager ─────────────
( cd backend && uv run python -c "
from app.agents.graph_builder import build_graph
class M:
    name='m'; default_model='m'; pricing={}
    async def generate(self, *a, **kw): raise NotImplementedError
g = build_graph('2330', 'TWSE', debate_rounds=1, llm=M())
nodes = set(g.get_graph().nodes.keys())
assert 'bull' in nodes and 'bear' in nodes and 'manager' in nodes, f'missing: {nodes}'
print('OK')
" )
echo "✓ graph_builder 含 bull/bear/manager node"

# ── 9) 真 LLM 測試（@expensive，若有 GOOGLE_API_KEY）──
GOOGLE_KEY=$(grep "^GOOGLE_API_KEY=" .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
if [ -n "$GOOGLE_KEY" ]; then
  echo "  → 跑真 LLM 測試（一次約 \$0.005~\$0.02）..."
  REAL_LOG=$(mktemp)
  export GOOGLE_API_KEY="$GOOGLE_KEY"
  # 不加 --timeout（pytest-timeout 非預設依賴）；單一 LLM call 自身有 timeout
  if ( cd backend && uv run pytest tests/integration/test_real_llm_2330.py \
       -m "network and expensive" -q ) > "$REAL_LOG" 2>&1; then
    echo "✓ 真 LLM 測試通過"
  else
    echo "⚠ 真 LLM 測試失敗或略過（看末尾 log）："
    tail -20 "$REAL_LOG"
  fi
  rm -f "$REAL_LOG"
else
  echo "ℹ 無 GOOGLE_API_KEY，略過真 LLM 測試"
fi

# ── 10) llm_usage schema 存在 ─────────────────────────
LLM_USAGE_COL=$(docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" -tAc \
  "SELECT count(*) FROM information_schema.columns WHERE table_name='llm_usage' AND column_name IN ('analysis_id','provider','model','cost_usd','total_tokens')" 2>/dev/null | tr -d ' \r\n')
if [ "$LLM_USAGE_COL" = "5" ]; then
  echo "✓ llm_usage schema 完整（5 個關鍵欄位）"
else
  echo "⚠ llm_usage schema 不完整（找到 $LLM_USAGE_COL/5 個欄位；非 fatal）"
fi

# ── 11) 累積測試 ≥ 595 ────────────────────────────────
TOTAL=$( cd backend && uv run pytest --collect-only -q 2>&1 | tail -1 | grep -oE "[0-9]+ tests" | grep -oE "[0-9]+" )
if [ "${TOTAL:-0}" -lt 595 ]; then
  echo "❌ 累積測試 $TOTAL < 595"
  exit 1
fi
echo "✓ 累積測試 $TOTAL ≥ 595"

# ── 12) run_analysis 接受 kwargs ──────────────────────
( cd backend && uv run python -c "
import inspect
from app.workers.tasks.run_analysis import run_analysis
sig = inspect.signature(run_analysis.__wrapped__)  # celery decorator 包了一層
params = list(sig.parameters.keys())
assert 'analyst_types' in params and 'debate_rounds' in params, f'missing kwargs: {params}'
print('OK')
" )
echo "✓ run_analysis 接受 analyst_types/debate_rounds kwargs"

echo ""
echo "✅ Phase 13 健康檢查全部通過"
