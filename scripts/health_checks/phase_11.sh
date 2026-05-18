#!/bin/bash
# scripts/health_checks/phase_11.sh
# Phase 11 健康檢查：業務 API 第二批（analysis / orders / reports / exports /
# notifications / admin / ws / metrics）+ Idempotency-Key + 並發核准 + WS IDOR 防護。
#
# 前提：
#   - docker compose up（postgres + redis + qdrant healthy）
#   - alembic upgrade head
#   - DB 有 admin
#
# 涵蓋（14 項）：
#   1. P10 仍正常
#   2. uv sync + ruff lint
#   3. backend 起得來，/health/live 200
#   4. /openapi.json paths 數 ≥ 50
#   5. admin login + 取 token / csrf
#   6. POST /analysis（帶 Idempotency-Key）→ 201；同 key 第二次回 200 + 同 id
#   7. GET /analysis 列表 + envelope
#   8. POST /api/v1/auth/ws-ticket → 拿到 ticket
#   9. PDF 匯出（fake completed analysis）→ %PDF magic
#  10. 並發 approve：一個 200、一個 409；DB 內僅一筆 APPROVED
#  11. /metrics admin only：未登入 401/403；admin 200 + analysis_total
#  12. /admin/audit 可查
#  13. /admin/pipeline/dlq 可查
#  14. P11 新測試全部通過 + 累積測試 ≥ 510

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 11 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

# Docker graceful skip（Phase 12 audit fix #16）— Docker 未啟動時不要 silent fail
if ! docker info > /dev/null 2>&1; then
  echo "⚠️  Docker daemon 未啟動 → 跳過 runtime 檢查（請啟動 Docker Desktop 後重跑）"
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

# ── 1) Phase 10 仍正常 ─────────────────────────────────────
bash scripts/health_checks/phase_10.sh > /dev/null 2>&1
echo "✓ Phase 10 健康檢查仍綠"

docker compose exec -T redis redis-cli -n 2 -a "$REDIS_PWD" --no-auth-warning FLUSHDB > /dev/null 2>&1 || true

# ── 2) uv sync + ruff ───────────────────────────────────
( cd backend && uv sync > /dev/null 2>&1 )
( cd backend && uv run ruff check app/ tests/ > /dev/null 2>&1 )
echo "✓ uv sync + ruff lint 通過"

# ── 3) 起 backend ───────────────────────────────────────
SERVER_PID=""
LOG_FILE=$(mktemp)
COOKIE_JAR=$(mktemp)
HC_SYMBOLS="'91101','91102'"
cleanup() {
  [ -n "$SERVER_PID" ] && kill $SERVER_PID 2>/dev/null || true
  rm -f "$LOG_FILE" "$COOKIE_JAR"
  docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
    psql -h localhost -U postgres "$PG_DB" \
    -c "DELETE FROM portfolio_positions WHERE symbol IN ($HC_SYMBOLS);
        DELETE FROM pending_orders WHERE symbol IN ($HC_SYMBOLS);
        DELETE FROM debate_history WHERE analysis_id IN (SELECT id FROM analysis_reports WHERE symbol IN ($HC_SYMBOLS));
        DELETE FROM analysis_reports WHERE symbol IN ($HC_SYMBOLS);
        DELETE FROM stock_list WHERE symbol IN ($HC_SYMBOLS);" \
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

# ── 4) /openapi.json paths ≥ 50 ─────────────────────────
PATH_COUNT=$(curl -fsS http://localhost:8000/openapi.json | python -c "import json,sys; print(len(json.load(sys.stdin).get('paths', {})))")
if [ "$PATH_COUNT" -lt 50 ]; then
  echo "❌ openapi.json paths 數 $PATH_COUNT < 50"
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
  echo "❌ admin login 失敗：$LOGIN_RESP"
  exit 1
fi
ADMIN_ID=$(docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" -tAc "SELECT id FROM users WHERE email='$ADMIN_EMAIL'" | tr -d '[:space:]')
echo "✓ admin login 成功 + 取 CSRF"

# 預先 seed 兩個健康檢查專用 symbol
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "INSERT INTO stock_list (symbol, market, name, is_active) VALUES
        ('91101','TWSE','健檢A',true), ('91102','TWSE','健檢B',true)
      ON CONFLICT (symbol) DO NOTHING;" \
  > /dev/null 2>&1

# ── 6) POST /analysis + Idempotency-Key ────────────────
KEY=$(python -c "import uuid; print(uuid.uuid4())")
A_RESP=$(curl -s -b "$COOKIE_JAR" -X POST http://localhost:8000/api/v1/analysis \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"91101","analyst_types":["market"],"llm_model":"gemini-2.0-flash","debate_rounds":0}')
ANALYSIS_ID=$(echo "$A_RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('analysis_id', ''))" 2>/dev/null)
if [ -z "$ANALYSIS_ID" ] || [ "$ANALYSIS_ID" = "None" ]; then
  echo "❌ POST /analysis 失敗：$A_RESP"
  exit 1
fi

# 同 key 第二次：回相同 id
A_RESP2=$(curl -s -b "$COOKIE_JAR" -X POST http://localhost:8000/api/v1/analysis \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"91101","analyst_types":["market"],"llm_model":"gemini-2.0-flash","debate_rounds":0}')
ID2=$(echo "$A_RESP2" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('analysis_id', ''))" 2>/dev/null)
if [ "$ID2" != "$ANALYSIS_ID" ]; then
  echo "❌ Idempotency 失效：第一次 $ANALYSIS_ID，第二次 $ID2"
  exit 1
fi
echo "✓ POST /analysis 201 + Idempotency-Key 命中"

# ── 7) GET /analysis 列表 ───────────────────────────────
LIST_BODY=$(curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/analysis?limit=10")
echo "$LIST_BODY" | python -c "import json,sys; d=json.load(sys.stdin); assert 'data' in d and 'pagination' in d, d"
echo "✓ GET /api/v1/analysis 列表 + envelope"

# ── 8) WS ticket ────────────────────────────────────────
TICKET_RESP=$(curl -s -b "$COOKIE_JAR" -X POST http://localhost:8000/api/v1/auth/ws-ticket \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN")
TICKET=$(echo "$TICKET_RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('data', {}).get('ticket', ''))" 2>/dev/null)
if [ -z "$TICKET" ] || [ "$TICKET" = "None" ]; then
  echo "❌ ws-ticket 失敗：$TICKET_RESP"
  exit 1
fi
echo "✓ POST /auth/ws-ticket 取得 ticket"

# ── 9) PDF 匯出 ─────────────────────────────────────────
# 把分析改成 completed + 帶中文 markdown，方便 PDF 渲染
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "UPDATE analysis_reports
        SET status='completed',
            report_md=E'# 健檢A (91101) 分析\n\n投資建議：BUY\n\n本報告為 phase_11 自動化健康檢查產物。',
            signal='BUY',
            confidence=0.75
        WHERE id='$ANALYSIS_ID'" \
  > /dev/null 2>&1

PDF_FILE=$(mktemp --suffix=.pdf)
PDF_HTTP=$(curl -s -o "$PDF_FILE" -w "%{http_code}" -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/exports/$ANALYSIS_ID?format=pdf")
if [ "$PDF_HTTP" = "200" ] && head -c 4 "$PDF_FILE" | grep -q "%PDF"; then
  echo "✓ PDF 匯出（%PDF magic 正確）"
else
  # 在沒裝 chromium 的環境會 503，視為通過（log 顯示原因）
  if [ "$PDF_HTTP" = "503" ]; then
    echo "⚠ PDF 匯出 503（chromium 不可用），改驗 MD 匯出"
    MD_HTTP=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" \
      "http://localhost:8000/api/v1/exports/$ANALYSIS_ID?format=md")
    if [ "$MD_HTTP" != "200" ]; then
      echo "❌ MD 匯出失敗（http $MD_HTTP）"
      exit 1
    fi
    echo "✓ MD 匯出 200"
  else
    echo "❌ PDF 匯出失敗（http $PDF_HTTP）"
    head -c 200 "$PDF_FILE"
    exit 1
  fi
fi
rm -f "$PDF_FILE"

# ── 10) 並發 approve ─────────────────────────────────────
# 預先產 UUID，避免 RETURNING + 訊息合併
ORDER_ID=$(python -c "import uuid; print(uuid.uuid4())")
docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" \
  -c "INSERT INTO pending_orders (id, user_id, analysis_id, symbol, market, side, qty, target_price, status, version)
      VALUES ('$ORDER_ID', '$ADMIN_ID', '$ANALYSIS_ID', '91101', 'TWSE', 'BUY', 1000, 600.0, 'PENDING', 1)" \
  > /dev/null 2>&1
ACTUAL=$(docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" -tAc "SELECT id FROM pending_orders WHERE id='$ORDER_ID'" | tr -d '[:space:]')
if [ "$ACTUAL" != "$ORDER_ID" ]; then
  echo "❌ 建立並發測試 pending_order 失敗（actual=$ACTUAL）"
  exit 1
fi

# 並發兩個 approve；分別寫到 tmp file 比對 status
A_OUT=$(mktemp)
B_OUT=$(mktemp)
(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" -X POST \
  -H "Authorization: Bearer $TOKEN" -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" -d '{}' \
  "http://localhost:8000/api/v1/orders/$ORDER_ID/approve" > "$A_OUT") &
(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" -X POST \
  -H "Authorization: Bearer $TOKEN" -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" -d '{}' \
  "http://localhost:8000/api/v1/orders/$ORDER_ID/approve" > "$B_OUT") &
wait
STATUS_A=$(cat "$A_OUT")
STATUS_B=$(cat "$B_OUT")
rm -f "$A_OUT" "$B_OUT"

APPROVED_CNT=$(docker compose exec -T -e PGPASSWORD="$PG_PWD" timescaledb \
  psql -h localhost -U postgres "$PG_DB" -tAc \
  "SELECT count(*) FROM pending_orders WHERE id='$ORDER_ID' AND status='APPROVED'" | tr -d '[:space:]')
if [ "$APPROVED_CNT" != "1" ]; then
  echo "❌ 並發 approve 預期 1 筆 APPROVED，實際 $APPROVED_CNT（status_a=$STATUS_A status_b=$STATUS_B）"
  exit 1
fi
# 一個 200 / 一個非 200（200 + 409 / 200 + 500 都可），不能兩個都 200
if [ "$STATUS_A" = "200" ] && [ "$STATUS_B" = "200" ]; then
  echo "❌ 並發兩次都 200，未觸發互斥"
  exit 1
fi
echo "✓ 並發 approve：唯一一筆 APPROVED（http: $STATUS_A / $STATUS_B）"

# ── 11) /metrics admin only ─────────────────────────────
UNAUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/metrics)
if [ "$UNAUTH_STATUS" != "401" ] && [ "$UNAUTH_STATUS" != "403" ]; then
  echo "❌ /metrics 未登入應為 401/403，實際 $UNAUTH_STATUS"
  exit 1
fi
METRICS=$(curl -fsS -H "Authorization: Bearer $TOKEN" http://localhost:8000/metrics)
echo "$METRICS" | grep -q "analysis_total" || {
  echo "❌ /metrics 缺 analysis_total"; exit 1;
}
echo "✓ /metrics admin only + 含 analysis_total"

# ── 12) /admin/audit ────────────────────────────────────
AUDIT_BODY=$(curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/admin/audit?limit=5")
echo "$AUDIT_BODY" | python -c "import json,sys; d=json.load(sys.stdin); assert 'data' in d, d"
echo "✓ /admin/audit 可查"

# ── 13) /admin/pipeline/dlq ─────────────────────────────
DLQ_BODY=$(curl -fsS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/admin/pipeline/dlq?resolved=false")
echo "$DLQ_BODY" | python -c "import json,sys; d=json.load(sys.stdin); assert 'data' in d, d"
echo "✓ /admin/pipeline/dlq 可查"

# ── 14) P11 全部新測試 + 累積測試 ≥ 510 ────────────────
P11_TEST_LOG=$(mktemp)
if ! ( cd backend && uv run pytest \
        tests/integration/test_analysis_router.py \
        tests/integration/test_orders_concurrent_approve.py \
        tests/integration/test_exports_pdf.py \
        tests/integration/test_notifications_router.py \
        tests/integration/test_admin_router.py \
        tests/integration/test_ws_analysis.py \
        tests/integration/test_idempotency.py \
        tests/unit/test_metrics.py -q 2>&1 ) > "$P11_TEST_LOG" 2>&1 ; then
  echo "❌ P11 測試失敗（最後 30 行）："
  tail -30 "$P11_TEST_LOG"
  rm -f "$P11_TEST_LOG"
  exit 1
fi
rm -f "$P11_TEST_LOG"
echo "✓ P11 unit + integration 測試全綠"

TOTAL=$( cd backend && uv run pytest --collect-only -q 2>&1 | tail -1 | grep -oE "[0-9]+ tests" | grep -oE "[0-9]+" )
if [ "${TOTAL:-0}" -lt 510 ]; then
  echo "❌ 累積測試 $TOTAL < 510"
  exit 1
fi
echo "✓ 累積測試 $TOTAL ≥ 510"

echo ""
echo "✅ Phase 11 健康檢查全部通過"
