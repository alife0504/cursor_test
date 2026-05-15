#!/bin/bash
# scripts/health_checks/phase_10.sh
# Phase 10 健康檢查：業務 API 第一批（stocks / watchlist / market / screener / users）。
#
# 前提：
#   - docker compose up（postgres + redis + qdrant healthy）
#   - alembic upgrade head
#   - DB 有 admin
#
# 涵蓋（12 項）：
#   1. P9 仍正常（auth + audit + rate limit + CSRF）
#   2. uv sync + ruff lint
#   3. backend 起得來，/health/live 200
#   4. /openapi.json paths 數 ≥ 25
#   5. admin login + 取得 access token + CSRF cookie
#   6. GET /api/v1/stocks 200 + envelope（資料量可為 0）
#   7. GET /api/v1/market/overview 200 + market="TW"
#   8. GET /api/v1/screener?market=TW&sort=symbol 200
#   9. POST /api/v1/watchlist（先 seed 一支測試股 + 帶 CSRF）→ 201；列出含該 symbol
#  10. cursor pagination：先 seed 多支，limit=2，二次取資料不重複
#  11. RBAC：viewer 不能 POST /api/v1/users → 403
#  12. P10 所有測試通過 + 累積 ≥ 477（435 + 42 = 477，留 1~3 個 skip 容忍）

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 10 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

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

# 預先解鎖 admin + 清 rate-limit
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='$ADMIN_EMAIL'" \
  > /dev/null 2>&1 || true
docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true

# ── 1) Phase 9 仍正常 ─────────────────────────────────────
bash scripts/health_checks/phase_09.sh > /dev/null 2>&1
echo "✓ Phase 9 健康檢查仍綠"

docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true

# ── 2) uv sync + ruff ───────────────────────────────────
( cd backend && uv sync > /dev/null 2>&1 )
( cd backend && uv run ruff check app/ tests/ > /dev/null 2>&1 )
echo "✓ uv sync + ruff lint 通過"

# ── 3) 起 backend ───────────────────────────────────────
SERVER_PID=""
LOG_FILE=$(mktemp)
COOKIE_JAR=$(mktemp)
SEED_SYMBOLS_LIST="'90001','90002','90003','90004','90005'"
cleanup() {
  [ -n "$SERVER_PID" ] && kill $SERVER_PID 2>/dev/null || true
  rm -f "$LOG_FILE" "$COOKIE_JAR"
  docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
    psql -h localhost -U postgres "$PG_DB" \
    -c "DELETE FROM user_watchlist WHERE symbol IN ($SEED_SYMBOLS_LIST); DELETE FROM stock_list WHERE symbol IN ($SEED_SYMBOLS_LIST);" \
    > /dev/null 2>&1 || true
}
trap cleanup EXIT

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

# ── 4) /openapi.json paths 數 ≥ 25 ──────────────────────
PATH_COUNT=$(curl -fsS http://localhost:8000/openapi.json | python -c "import json,sys; print(len(json.load(sys.stdin).get('paths', {})))")
if [ "$PATH_COUNT" -lt 25 ]; then
  echo "❌ openapi.json paths 數 $PATH_COUNT < 25"
  exit 1
fi
echo "✓ openapi.json 有 $PATH_COUNT 個 path"

# ── 5) admin login ──────────────────────────────────────
LOGIN_RESP=$(curl -s -c "$COOKIE_JAR" -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}")
TOKEN=$(echo "$LOGIN_RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('access_token', ''))" 2>/dev/null)
CSRF_TOKEN=$(awk '/csrf_token/ {print $NF}' "$COOKIE_JAR" | tail -1)
if [ -z "$TOKEN" ] || [ "$TOKEN" = "None" ]; then
  echo "❌ admin login 失敗，response: $LOGIN_RESP"
  exit 1
fi
echo "✓ admin login 成功，CSRF token 已取得"

# ── 6) GET /api/v1/stocks 200 ────────────────────────────
STOCKS_BODY=$(curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stocks?market=TW&limit=10")
echo "$STOCKS_BODY" | python -c "import json,sys; d=json.load(sys.stdin); assert 'data' in d and 'pagination' in d, d"
echo "✓ GET /api/v1/stocks 200 + envelope（data + pagination）"

# ── 7) GET /api/v1/market/overview 200 ──────────────────
OVERVIEW_BODY=$(curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/market/overview?market=TW")
OVERVIEW_MARKET=$(echo "$OVERVIEW_BODY" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('market'))")
if [ "$OVERVIEW_MARKET" != "TW" ]; then
  echo "❌ /market/overview 回的 market 不是 TW（實際 $OVERVIEW_MARKET）"
  exit 1
fi
echo "✓ GET /api/v1/market/overview market=TW"

# ── 8) GET /api/v1/screener 200 ─────────────────────────
SCREENER_BODY=$(curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/screener?market=TW&sort=symbol&limit=10")
echo "$SCREENER_BODY" | python -c "import json,sys; d=json.load(sys.stdin); assert 'data' in d and 'pagination' in d, d"
echo "✓ GET /api/v1/screener 200 + envelope"

# ── 9) POST /watchlist + 列出 ───────────────────────────
# 預先 seed 一支符合 TW pattern 的測試股
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "DELETE FROM user_watchlist WHERE symbol IN ($SEED_SYMBOLS_LIST); DELETE FROM stock_list WHERE symbol IN ($SEED_SYMBOLS_LIST);
      INSERT INTO stock_list (symbol, market, name, is_active) VALUES
        ('90001','TWSE','測試A',true), ('90002','TWSE','測試B',true),
        ('90003','TWSE','測試C',true), ('90004','TWSE','測試D',true),
        ('90005','TWSE','測試E',true);" \
  > /dev/null 2>&1

WL_RESP=$(curl -s -b "$COOKIE_JAR" -X POST http://localhost:8000/api/v1/watchlist \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"90001","market":"TWSE","notes":"phase10 health-check"}')
WL_SYM=$(echo "$WL_RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('symbol'))" 2>/dev/null)
if [ "$WL_SYM" != "90001" ]; then
  echo "❌ POST /watchlist 失敗：$WL_RESP"
  exit 1
fi
echo "✓ POST /api/v1/watchlist 加入 90001"

WL_LIST=$(curl -fsS -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/watchlist)
if ! echo "$WL_LIST" | python -c "import json,sys; assert any(r['symbol']=='90001' for r in json.load(sys.stdin).get('data', [])), 'no 90001'"; then
  echo "❌ GET /watchlist 不含 90001：$WL_LIST"
  exit 1
fi
echo "✓ GET /api/v1/watchlist 含 90001"

# ── 10) cursor pagination — limit=2 取兩頁不重複 ────────
P1=$(curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stocks?market=TW&q=9000&limit=2")
CURSOR=$(printf '%s' "$P1" | python -c "import json,sys; d=json.load(sys.stdin); c=d.get('pagination', {}).get('next_cursor'); print(c if c else '')")
if [ -z "$CURSOR" ]; then
  echo "❌ stocks page1 沒帶 next_cursor"
  exit 1
fi
P2=$(curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stocks?market=TW&q=9000&limit=2&cursor=$CURSOR")
DUP=$(P1_JSON="$P1" P2_JSON="$P2" python -c "
import json, os
p1 = set(r['symbol'] for r in json.loads(os.environ['P1_JSON'])['data'])
p2 = set(r['symbol'] for r in json.loads(os.environ['P2_JSON'])['data'])
print(len(p1 & p2))
")
if [ "$DUP" != "0" ]; then
  echo "❌ cursor 第二頁與第一頁有重複（$DUP 筆）"
  exit 1
fi
echo "✓ cursor pagination 兩頁不重複"

# ── 11) RBAC：先建 viewer，再用 viewer token POST /users → 403 ──
VIEWER_EMAIL="p10-viewer-$(date +%s)@test.example.com"
# 用 admin 建 viewer
VIEWER_BODY=$(curl -s -b "$COOKIE_JAR" -X POST http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$VIEWER_EMAIL\",\"password\":\"TestPwd2026!Ab\",\"role\":\"VIEWER\",\"must_change_password\":false}")
VIEWER_ID=$(echo "$VIEWER_BODY" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('id', ''))" 2>/dev/null)
if [ -z "$VIEWER_ID" ] || [ "$VIEWER_ID" = "None" ]; then
  echo "❌ admin 建 viewer 失敗：$VIEWER_BODY"
  exit 1
fi
# viewer login（換新 cookie jar）
VIEWER_JAR=$(mktemp)
VLOGIN=$(curl -s -c "$VIEWER_JAR" -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$VIEWER_EMAIL\",\"password\":\"TestPwd2026!Ab\"}")
VTOKEN=$(echo "$VLOGIN" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('access_token', ''))")
VCSRF=$(awk '/csrf_token/ {print $NF}' "$VIEWER_JAR" | tail -1)
# viewer 嘗試 POST /users → 403
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -b "$VIEWER_JAR" -X POST http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $VTOKEN" \
  -H "X-CSRF-Token: $VCSRF" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"should-fail@test.example.com\",\"password\":\"TestPwd2026!Ab\",\"role\":\"VIEWER\"}")
rm -f "$VIEWER_JAR"
if [ "$STATUS" != "403" ]; then
  echo "❌ viewer POST /users 期望 403，實際 $STATUS"
  exit 1
fi
echo "✓ RBAC：viewer POST /users → 403"

# cleanup viewer
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "DELETE FROM user_sessions WHERE user_id='$VIEWER_ID'; DELETE FROM users WHERE id='$VIEWER_ID';" \
  > /dev/null 2>&1 || true

# 清 health-check 自己的 seed（避免測試前撞排序前幾筆）
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "DELETE FROM user_watchlist WHERE symbol IN ($SEED_SYMBOLS_LIST); DELETE FROM stock_list WHERE symbol IN ($SEED_SYMBOLS_LIST);" \
  > /dev/null 2>&1 || true

# ── 12) P10 全部測試通過 + 累積測試 ≥ 477 ───────────────
P10_TEST_LOG=$(mktemp)
if ! ( cd backend && uv run pytest tests/unit/test_cursor.py \
  tests/integration/test_stocks_router.py tests/integration/test_watchlist_router.py \
  tests/integration/test_market_router.py tests/integration/test_screener_router.py \
  tests/integration/test_users_router.py -q 2>&1 ) > "$P10_TEST_LOG" 2>&1 ; then
  echo "❌ P10 測試失敗（最後 30 行）："
  tail -30 "$P10_TEST_LOG"
  rm -f "$P10_TEST_LOG"
  exit 1
fi
rm -f "$P10_TEST_LOG"
echo "✓ P10 unit + integration 測試全綠"

TOTAL=$( cd backend && uv run pytest --collect-only -q 2>&1 | tail -1 | grep -oE "[0-9]+ tests" | grep -oE "[0-9]+" )
if [ "${TOTAL:-0}" -lt 477 ]; then
  echo "❌ 累積測試 $TOTAL < 477"
  exit 1
fi
echo "✓ 累積測試 $TOTAL ≥ 477"

# 清 watchlist seed
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "DELETE FROM user_watchlist WHERE symbol IN ($SEED_SYMBOLS_LIST); DELETE FROM stock_list WHERE symbol IN ($SEED_SYMBOLS_LIST);" \
  > /dev/null 2>&1 || true

# 解鎖 admin
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='$ADMIN_EMAIL'" \
  > /dev/null 2>&1 || true

echo ""
echo "✅ Phase 10 健康檢查全部通過"
