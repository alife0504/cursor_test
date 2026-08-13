#!/bin/bash
# scripts/health_checks/phase_06.sh
# Phase 6 健康檢查：4 個美股 Adapter + 跨市場 Dispatcher + Symbol regex + Cache。
#
# 涵蓋：
#   1. P5 仍正常（5 個 TW source 註冊）
#   2. 4 個 US source 註冊（yfinance / alpha_vantage / finnhub / sec_edgar）
#   3. detect_region 對所有 PLAN 10.2 樣態行為正確
#   4. ruff lint 通過
#   5. P6 unit test 全綠（不含 network）
#   6. P6 integration (mock) 全綠
#   7. P5 退化檢查（fallback / pipeline 仍綠）

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 06 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

# 1. P5 仍正常 — 5 個 TW source 註冊
cd backend
uv run python -c "
import app.data_sources.tw
from app.data_sources.base import DATA_SOURCE_REGISTRY
expected = {'finmind', 'twse_openapi', 'tpex', 'mops', 'cnyes_rss'}
got = set(DATA_SOURCE_REGISTRY.keys()) & expected
assert got == expected, f'missing TW source: {expected - got}'
print('OK')
" >/dev/null 2>&1 || { echo "❌ P5 退化：5 個 TW source 未全部註冊"; exit 1; }
echo "✓ 5 個 TW source 註冊（P5 仍正常）"
cd "$PROJECT_ROOT"

# 2. 4 個 US source 註冊
cd backend
uv run python -c "
import app.data_sources.us
from app.data_sources.base import DATA_SOURCE_REGISTRY
expected = {'yfinance', 'alpha_vantage', 'finnhub', 'sec_edgar'}
got = set(DATA_SOURCE_REGISTRY.keys()) & expected
assert got == expected, f'missing US source: {expected - got}'
print('OK', got)
" >/dev/null 2>&1 || { echo "❌ 4 個 US source 未全部註冊"; exit 1; }
echo "✓ 4 個 US source 全部註冊"
cd "$PROJECT_ROOT"

# 3. detect_region 對 PLAN 10.2 樣態行為正確
cd backend
uv run python -c "
from app.core.market_dispatcher import detect_region, MarketRegion
cases = [
    # TW
    ('2330','TW'),('2317','TW'),('1101','TW'),
    ('0050','TW'),('00878','TW'),('006208','TW'),  # ETF
    ('2884A','TW'),                                  # 特別股
    # US
    ('AAPL','US'),('MSFT','US'),('TSLA','US'),('F','US'),('T','US'),
    ('BRK.B','US'),('BF.B','US'),                    # dual class
]
for sym, exp in cases:
    got = detect_region(sym).value
    assert got == exp, f'{sym}: got={got} expected={exp}'
print('OK')
" >/dev/null 2>&1 || { echo "❌ detect_region 行為錯誤"; exit 1; }
echo "✓ detect_region 對 PLAN 10.2 樣態全部判對"
cd "$PROJECT_ROOT"

# 4. ruff 通過
cd backend
uv run ruff check app/ >/dev/null 2>&1 || { echo "❌ ruff check 失敗"; exit 1; }
cd "$PROJECT_ROOT"
echo "✓ ruff check app/ 通過"

# 5. P6 unit tests 全綠
cd backend
uv run pytest \
  tests/unit/test_yfinance_source.py \
  tests/unit/test_alpha_vantage_source.py \
  tests/unit/test_finnhub_source.py \
  tests/unit/test_sec_edgar_source.py \
  tests/unit/test_market_dispatcher.py \
  tests/unit/test_cache.py \
  -m "not network" -q --no-header 2>&1 | tail -1 | grep -qE "[0-9]+ passed" || {
  echo "❌ P6 unit tests 未全綠"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ P6 unit tests 全綠"

# 6. P6 integration tests (mock，不含 network) 全綠
cd backend
uv run pytest tests/integration/test_dispatcher_end_to_end.py \
  -m "not network" -q --no-header 2>&1 | tail -1 | grep -qE "[0-9]+ passed" || {
  echo "❌ P6 integration tests (mock) 未全綠"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ P6 integration tests (mock) 全綠"

# 7. P5 退化檢查 — 5 個 TW source 測試 + fallback + repo + pipeline 仍綠
cd backend
uv run pytest \
  tests/unit/test_finmind_source.py \
  tests/unit/test_twse_source.py \
  tests/unit/test_tpex_source.py \
  tests/unit/test_mops_source.py \
  tests/unit/test_cnyes_rss_source.py \
  tests/unit/test_data_source_fallback.py \
  tests/unit/test_repositories.py \
  tests/integration/test_data_pipeline_service.py \
  -m "not network" -q --no-header 2>&1 | tail -1 | grep -qE "[0-9]+ passed" || {
  echo "❌ P5 退化測試未全綠"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ P5 退化測試通過"

echo ""
echo "✅ Phase 06 健康檢查全部通過"
