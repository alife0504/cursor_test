#!/bin/bash
# scripts/health_checks/phase_05.sh
# Phase 5 健康檢查：TW 資料源 Adapter (FinMind/TWSE/TPEX/MOPS/cnyes) + Repository + DataPipelineService
#
# 涵蓋：
#   1. P4 schema + alembic 0014 (financial_statements 表)
#   2. 5 個 TW source 註冊成功
#   3. 5 個 TW source 對應的 CircuitBreaker 註冊
#   4. unit test 全綠（不含 network）
#   5. integration test (data_pipeline_service mock) 全綠

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 05 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

psql_pg() {
  docker compose exec -T -e PGPASSWORD="$1" timescaledb \
    psql -U "$2" -d tradingagents_tw -tAc "$3" 2>/dev/null
}

PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)

# 1. 確保 alembic head 是 0014
HEAD=$(cd backend && uv run alembic current 2>&1 | grep -oE "[0-9]{4}" | tail -1)
cd "$PROJECT_ROOT"
if [ "$HEAD" != "0014" ]; then
  echo "❌ alembic head = $HEAD（預期 0014）"
  exit 1
fi
echo "✓ alembic head = 0014"

# 2. financial_statements 表存在
COUNT=$(psql_pg "$PG" postgres "SELECT count(*) FROM information_schema.tables WHERE table_name='financial_statements'")
if [ -z "$COUNT" ] || [ "$COUNT" -lt 1 ]; then
  echo "❌ financial_statements 表不存在"
  exit 1
fi
echo "✓ financial_statements 表存在"

# 3. 5 個 TW source 註冊成功
cd backend
uv run python -c "
from app.data_sources.base import DATA_SOURCE_REGISTRY
import app.data_sources.tw  # trigger registration
expected = {'finmind', 'twse_openapi', 'tpex', 'mops', 'cnyes_rss'}
got = set(DATA_SOURCE_REGISTRY.keys()) & expected
assert got == expected, f'missing: {expected - got}'
print('OK')
" >/dev/null 2>&1 || { echo "❌ 5 個 TW source 註冊失敗"; exit 1; }
echo "✓ 5 個 TW source 全部註冊成功"
cd "$PROJECT_ROOT"

# 4. 5 個 source 對應 CircuitBreaker 註冊
cd backend
uv run python -c "
from app.core.circuit_breaker import CIRCUIT_BREAKERS
from app.core.config import settings
from app.data_sources.tw import get_tw_sources
get_tw_sources(settings)  # 觸發 init → CB 註冊
expected = {'finmind', 'twse_openapi', 'tpex', 'mops', 'cnyes_rss'}
got = set(CIRCUIT_BREAKERS.keys()) & expected
assert got == expected, f'CB missing: {expected - got}'
print('OK')
" >/dev/null 2>&1 || { echo "❌ Circuit Breaker 註冊失敗"; exit 1; }
echo "✓ 5 個 CircuitBreaker 全部註冊"
cd "$PROJECT_ROOT"

# 5. ruff 通過
cd backend
uv run ruff check app/ >/dev/null 2>&1 || { echo "❌ ruff check 失敗"; exit 1; }
cd "$PROJECT_ROOT"
echo "✓ ruff check app/ 通過"

# 6. P5 unit test 全綠（不含 network）
cd backend
uv run pytest \
  tests/unit/test_finmind_source.py \
  tests/unit/test_twse_source.py \
  tests/unit/test_tpex_source.py \
  tests/unit/test_mops_source.py \
  tests/unit/test_cnyes_rss_source.py \
  tests/unit/test_data_source_fallback.py \
  tests/unit/test_repositories.py \
  -m "not network" -q --no-header 2>&1 | tail -1 | grep -qE "[0-9]+ passed" || {
  echo "❌ P5 unit test 未全綠"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ P5 unit tests 全綠"

# 7. P5 integration test (mock) 全綠
cd backend
uv run pytest tests/integration/test_data_pipeline_service.py -m "not network" -q --no-header 2>&1 | tail -1 | grep -qE "[0-9]+ passed" || {
  echo "❌ P5 integration test (mock) 未全綠"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ P5 integration tests 全綠"

# 8. P4 退化檢查（仍跑得過）
cd backend
uv run pytest tests/integration/test_schema.py tests/unit/test_models.py tests/unit/test_skeleton.py -q --no-header 2>&1 | tail -1 | grep -qE "[0-9]+ passed" || {
  echo "❌ P4 schema/model 測試退化"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ P4 退化測試通過"

echo ""
echo "✅ Phase 05 健康檢查全部通過"
