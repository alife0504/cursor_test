#!/bin/bash
# scripts/health_checks/phase_09.sh
# Phase 9 健康檢查：Security Middleware（Audit / RateLimit / CSRF / BodySize / Validators / verify_audit_chain）。
#
# 前提：
#   - docker compose up（postgres + redis + qdrant healthy）
#   - alembic upgrade head
#   - DB 有 admin
#
# 涵蓋（12 項）：
#   1. P8 仍正常（auth login 可跑通）
#   2. uv sync + ruff lint
#   3. backend 起得來，/health/live 200
#   4. SecurityHeadersMiddleware：CSP / X-Frame-Options 在
#   5. CSRFMiddleware：POST 沒 X-CSRF-Token → 403
#   6. RateLimitMiddleware：/auth/login 6 次 → 第 6 次 429 + Retry-After
#   7. BodySizeMiddleware：2 MB body → 413
#   8. AuditMiddleware：/auth/login 之後 audit_logs 含 http.post 紀錄
#   9. AuditRepository.verify_chain：CLI 跑通
#   10. validators：symbol / date_range 行為正確
#   11. P9 全部測試通過（unit + integration + security）
#   12. 累積測試 ≥ 192

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 09 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

# 讀 .env
ADMIN_EMAIL=$(grep ^ADMIN_EMAIL= .env | cut -d= -f2- | tr -d '"' | tr -d "'")
ADMIN_PWD=$(grep ^ADMIN_INITIAL_PASSWORD= .env | cut -d= -f2- | tr -d '"' | tr -d "'")
PG_PWD=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2- | tr -d '"' | tr -d "'")
REDIS_PWD=$(grep ^REDIS_PASSWORD= .env | cut -d= -f2- | tr -d '"' | tr -d "'")
PG_DB=$(grep ^POSTGRES_DB= .env | cut -d= -f2- | tr -d '"' | tr -d "'")
PG_DB=${PG_DB:-tradingagents_tw}

# 預先解鎖 admin + 清 rate-limit redis
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='$ADMIN_EMAIL'" \
  > /dev/null 2>&1 || true
docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true

# ── 1) P8 仍正常 ─────────────────────────────────────────
bash scripts/health_checks/phase_08.sh > /dev/null 2>&1
echo "✓ Phase 8 健康檢查仍綠"

# 清 rate limit 給 P9 自己用
docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true

# ── 2) uv sync + ruff ───────────────────────────────────
( cd backend && uv sync > /dev/null 2>&1 )
( cd backend && uv run ruff check app/ tests/ > /dev/null 2>&1 )
echo "✓ uv sync + ruff lint 通過"

# ── 3) 起 backend ─────────────────────────────────────
SERVER_PID=""
LOG_FILE=$(mktemp)
trap '[ -n "$SERVER_PID" ] && kill $SERVER_PID 2>/dev/null; rm -f "$LOG_FILE"' EXIT

if ! curl -fsS http://localhost:8000/health/live > /dev/null 2>&1; then
  echo "  → 啟動臨時 uvicorn server..."
  ( cd backend && uv run uvicorn app.main:app --port 8000 > "$LOG_FILE" 2>&1 ) &
  SERVER_PID=$!
  for i in 1 2 3 4 5 6 7 8 9 10; do
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

# ── 4) Security headers ──────────────────────────────────
HEADERS=$(curl -sI http://localhost:8000/health/live)
echo "$HEADERS" | grep -qi "content-security-policy"
echo "$HEADERS" | grep -qi "x-content-type-options: nosniff"
echo "$HEADERS" | grep -qi "x-frame-options: DENY"
echo "$HEADERS" | grep -qi "referrer-policy"
echo "✓ SecurityHeaders 完整（CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy）"

# ── 5) CSRFMiddleware：登入後對 /logout POST 不帶 CSRF → 403 ──
docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true

LOGIN_RESP=$(curl -s -c /tmp/p9_cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}")
TOKEN=$(echo "$LOGIN_RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('access_token', ''))")
if [ -z "$TOKEN" ] || [ "$TOKEN" = "None" ]; then
  echo "❌ login 失敗: $LOGIN_RESP"
  exit 1
fi

# /logout POST 不帶 X-CSRF-Token → 403
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer $TOKEN")
test "$STATUS" = "403"
echo "✓ CSRF 中介層：POST 缺 X-CSRF-Token → 403"

# ── 6) RateLimit：/auth/login 6 次 → 第 6 次 429 ──
docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"rate-$i@test.example.com\",\"password\":\"Wrong12345!Ab\"}" > /dev/null
done
RL_RESP_HEADERS=$(curl -s -D - -o /dev/null -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"rate-x@test.example.com\",\"password\":\"Wrong12345!Ab\"}")
echo "$RL_RESP_HEADERS" | head -1 | grep -q "429"
echo "$RL_RESP_HEADERS" | grep -qi "retry-after"
echo "✓ RateLimit：L2 5/min 觸發 429 + Retry-After"

# ── 7) BodySize → 413（先清 rate-limit 避免被 429 攔截） ──
docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true
python -c "import sys; sys.stdout.buffer.write(b'a' * (2*1024*1024))" > /tmp/p9_huge.bin
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/p9_huge.bin)
test "$STATUS" = "413"
rm -f /tmp/p9_huge.bin
echo "✓ BodySize：2MB body → 413"

# ── 8) AuditMiddleware 寫 audit ──
docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}" > /dev/null
# audit_logs 應有 http.post + /api/v1/auth/login 紀錄
COUNT=$(docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -tAc "SELECT count(*) FROM audit_logs WHERE action='http.post' AND entity_id='/api/v1/auth/login'" 2>/dev/null | tr -d '[:space:]\r')
test "${COUNT:-0}" -gt 0
echo "✓ AuditMiddleware：/auth/login 寫入 http.post audit log（$COUNT 筆）"

# ── 9) verify_audit_chain CLI（只驗最近 60 秒，避免歷史測試殘留的破壞） ──
SINCE=$(python -c "from datetime import datetime, timezone, timedelta; print((datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat())")
( cd backend && uv run python "$PROJECT_ROOT/scripts/verify_audit_chain.py" --since "$SINCE" )
echo "✓ verify_audit_chain CLI 通過（since=最近 60 秒）"

# ── 10) validators 行為 ──
( cd backend && uv run python -c "
from app.core.validators import validate_symbol, validate_date_range
from datetime import date
from app.core.errors import ValidationError

assert validate_symbol('2330') == '2330'
assert validate_symbol('AAPL') == 'AAPL'
try:
    validate_symbol('NOT_A_SYMBOL!!!')
    raise AssertionError('expected ValidationError')
except ValidationError:
    pass

validate_date_range(date(2024,1,1), date(2024,12,31))
try:
    validate_date_range(date(2024,12,31), date(2024,1,1))
    raise AssertionError('expected ValidationError')
except ValidationError:
    pass
print('validators OK')
" )
echo "✓ validators 行為符合預期"

# ── 11) P9 全部測試 ──
( cd backend && uv run pytest tests/unit/test_validators.py tests/unit/test_rate_limit.py \
  tests/integration/test_audit_middleware.py tests/integration/test_csrf_middleware.py \
  tests/integration/test_rate_limit_endpoints.py tests/security/ -q > /dev/null 2>&1 )
echo "✓ P9 unit + integration + security tests 全綠"

# ── 12) 累積測試 ──
TOTAL=$( cd backend && uv run pytest --collect-only -q 2>&1 | tail -1 | grep -oE "[0-9]+ tests" | grep -oE "[0-9]+" )
test "${TOTAL:-0}" -ge 192
echo "✓ 累積測試 ${TOTAL} ≥ 192"

# 解鎖 admin（lockout 可能在 test 觸發）
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='$ADMIN_EMAIL'" \
  > /dev/null 2>&1 || true

echo ""
echo "✅ Phase 09 健康檢查全部通過"
