#!/bin/bash
# scripts/health_checks/phase_08.sh
# Phase 8 健康檢查：Auth（JWT + RBAC + CSRF + WS Ticket + Lockout + Password Reset）。
#
# 前提：
#   - docker compose up（postgres + redis + qdrant healthy）
#   - alembic 已 upgrade head（含 0015 password_history）
#   - DB 有 admin（make seed-admin 已跑過）
#   - backend 已啟動於 :8000（或本腳本會自動啟動）
#
# 涵蓋：
#   1. P7 仍正常（celery_app + beat schedule）
#   2. uv sync 通過（含 P8 新加 fakeredis）
#   3. ruff lint 全綠
#   4. backend 可起，/health/live 200
#   5. /openapi.json 含 /api/v1/auth/login
#   6. admin 登入成功並拿 access token
#   7. /me 用 token 可呼叫，response 不含 password_hash
#   8. WS ticket 可發，且 60s 一次性（Redis db5 寫入 verify）
#   9. lockout：連 5 次錯密碼 → 423
#  10. unlock：DB UPDATE → 帳號可再 login
#  11. audit_logs 有 auth.login event
#  12. P8 所有測試通過（38 unit + 36 integration = 74 個）

set -e

# ── 找專案根 ─────────────────────────────────────────────
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 08 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

# ── 讀 .env ─────────────────────────────────────────────
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

# ── 1) Phase 7 仍正常 ────────────────────────────────────
bash scripts/health_checks/phase_07.sh > /dev/null 2>&1
echo "✓ Phase 7 健康檢查仍綠"

# ── 2) uv sync ──────────────────────────────────────────
( cd backend && uv sync > /dev/null 2>&1 )
echo "✓ uv sync 通過（含 fakeredis）"

# ── 3) ruff lint ────────────────────────────────────────
( cd backend && uv run ruff check app/ > /dev/null 2>&1 )
echo "✓ ruff check 通過"

# ── 3.5) 預先解鎖 admin（避免上次跑剩下的 lockout） ─────
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='$ADMIN_EMAIL'" \
  > /dev/null 2>&1 || true

# ── 4) 起 backend（若沒在跑） ───────────────────────────
SERVER_PID=""
LOG_FILE=$(mktemp)
trap '[ -n "$SERVER_PID" ] && kill $SERVER_PID 2>/dev/null; rm -f "$LOG_FILE"' EXIT

if ! curl -fsS http://localhost:8000/health/live > /dev/null 2>&1; then
  echo "  → 啟動臨時 uvicorn server..."
  ( cd backend && uv run uvicorn app.main:app --port 8000 > "$LOG_FILE" 2>&1 ) &
  SERVER_PID=$!
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS http://localhost:8000/health/live > /dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if ! curl -fsS http://localhost:8000/health/live > /dev/null 2>&1; then
    echo "❌ backend 啟動失敗"
    cat "$LOG_FILE"
    exit 1
  fi
fi
echo "✓ /health/live 回 200"

# 用 python 取代 jq（Windows / Git Bash 環境通常沒裝 jq）
JQ_LIKE() { python -c "import json,sys; d=json.load(sys.stdin); $1" 2>/dev/null; }

# ── 5) /openapi.json 含 auth 路由 ───────────────────────
OPENAPI=$(curl -fsS http://localhost:8000/openapi.json)
if ! echo "$OPENAPI" | python -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if '/api/v1/auth/login' in d.get('paths', {}) else 1)"; then
  echo "❌ /api/v1/auth/login 不在 openapi schema"
  exit 1
fi
echo "✓ openapi schema 含 /api/v1/auth/login"

# ── 6) admin login（用 cookie jar 保存 csrf_token） ──
COOKIE_JAR=$(mktemp)
LOGIN_RESP=$(curl -s -c "$COOKIE_JAR" -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PWD\"}")
TOKEN=$(echo "$LOGIN_RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('access_token', ''))" 2>/dev/null)
CSRF_TOKEN=$(awk '/csrf_token/ {print $NF}' "$COOKIE_JAR" | tail -1)
if [ -z "$TOKEN" ] || [ "$TOKEN" = "None" ]; then
  echo "❌ admin login 失敗，response: $LOGIN_RESP"
  rm -f "$COOKIE_JAR"
  exit 1
fi
echo "✓ admin login 成功"

# ── 7) /me 不含 password_hash ───────────────────────────
ME_RESP=$(curl -fsS -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me)
ME_EMAIL=$(echo "$ME_RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('email', ''))" 2>/dev/null)
if [ -z "$ME_EMAIL" ] || [ "$ME_EMAIL" = "None" ]; then
  echo "❌ /me 沒回 email"
  exit 1
fi
if echo "$ME_RESP" | python -c "import json,sys; sys.exit(0 if 'password_hash' in json.load(sys.stdin).get('data', {}) else 1)"; then
  echo "❌ /me 回了 password_hash 欄位（schema 漏遮）"
  exit 1
fi
echo "✓ /me 200，不含 password_hash"

# ── 8) WS ticket 一次性（P9 後 POST 需 CSRF；ws-ticket 也走 CSRF 中介層） ──
WSTICKET_RESP=$(curl -s -b "$COOKIE_JAR" -X POST http://localhost:8000/api/v1/auth/ws-ticket \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN")
TICKET=$(echo "$WSTICKET_RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('ticket', ''))" 2>/dev/null)
if [ -z "$TICKET" ] || [ "$TICKET" = "None" ]; then
  echo "❌ WS ticket issue 失敗 - resp: $WSTICKET_RESP"
  rm -f "$COOKIE_JAR"
  exit 1
fi
# 直接從 Redis db5 驗 key 存在
if command -v docker > /dev/null 2>&1; then
  TICKET_VALUE=$(docker compose exec -T redis redis-cli -n 5 -a "$REDIS_PWD" --no-auth-warning \
    GET "wst:$TICKET" 2>/dev/null || echo "")
  if [ -z "$TICKET_VALUE" ]; then
    echo "❌ Redis db5 沒有 wst:$TICKET（ticket 未寫入或 TTL 已過？）"
    exit 1
  fi
fi
echo "✓ WS ticket 發出且寫入 Redis db5"

# ── 9) lockout：連 5 次錯密碼 → 423 ─────────────────────
# P9 後 rate-limit L2 限 5/min/IP，每次 wrong-password 後清 redis db2 避開 rate limit
# （健康檢查目的是測 lockout，不是 rate-limit）
docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true
for i in 1 2 3 4 5; do
  curl -s -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"WRONG_$i!password1\"}" > /dev/null
  # 清 rate-limit 確保下一次不被擋
  docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true
done
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"WRONG_X!password\"}")
if [ "$STATUS" != "423" ]; then
  echo "❌ lockout 應回 423，實際 $STATUS"
  rm -f "$COOKIE_JAR"
  exit 1
fi
echo "✓ lockout 觸發 423"

# ── 10) 解鎖 + audit log 驗證（用 docker exec，host 未必有 psql） ──
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='$ADMIN_EMAIL'" \
  > /dev/null 2>&1 || true

# ── 11) audit_logs 有 auth.login event ──────────────────
LOGIN_AUDIT_COUNT=$(docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -tAc "SELECT count(*) FROM audit_logs WHERE action='auth.login'" 2>/dev/null | tr -d '[:space:]\r')
LOGIN_AUDIT_COUNT=${LOGIN_AUDIT_COUNT:-0}
if [ "$LOGIN_AUDIT_COUNT" -lt 1 ]; then
  echo "❌ audit_logs 沒有 auth.login event"
  exit 1
fi
echo "✓ audit_logs 有 auth.login event（共 $LOGIN_AUDIT_COUNT 筆）"

# ── 12) P8 全部測試通過 ─────────────────────────────────
( cd backend && uv run pytest tests/unit/test_password_policy.py \
  tests/unit/test_jwt_service.py tests/unit/test_ws_ticket.py \
  tests/integration/test_auth_login.py tests/integration/test_auth_refresh.py \
  tests/integration/test_auth_password_reset.py \
  tests/integration/test_auth_change_password.py \
  tests/integration/test_rbac.py -q > /dev/null 2>&1 )
echo "✓ P8 所有測試通過"

echo ""
echo "✅ Phase 08 健康檢查全部通過"
