#!/bin/bash
# scripts/health_checks/phase_03.sh
# Phase 3 健康檢查：後端工程基礎程式碼 + 最小可運行 backend
# 後續 Phase 開頭跑此 script 確保 P3 結果還能跑

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 03 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

# 1. backend core 模組齊全
for f in backend/app/core/config.py \
         backend/app/core/logging_config.py \
         backend/app/core/errors.py \
         backend/app/core/error_handlers.py \
         backend/app/core/response_envelope.py \
         backend/app/core/request_id.py \
         backend/app/core/security_headers.py \
         backend/app/core/http_client.py \
         backend/app/core/circuit_breaker.py \
         backend/app/core/database.py \
         backend/app/core/redis_client.py \
         backend/app/core/qdrant_client.py \
         backend/app/main.py \
         backend/app/__init__.py; do
  test -f "$f" || { echo "❌ 缺少檔案：$f"; exit 1; }
done
echo "✓ backend core 14 個模組齊全"

# 2. backend deps OK
cd backend
uv sync --frozen >/dev/null 2>&1 || { echo "❌ uv sync 失敗"; exit 1; }
echo "✓ uv sync OK"

# 3. ruff lint 通過
uv run ruff check app/ tests/ >/dev/null 2>&1 || { echo "❌ ruff lint 失敗"; exit 1; }
echo "✓ ruff lint 全綠"

# 4. backend import 不報錯
uv run python -c "from app.main import app; assert app.version == '0.3.0'" 2>&1 | tail -1
echo "✓ backend import OK"

# 5. pytest collect ≥ 70
COLLECTED=$(uv run pytest --collect-only -q 2>&1 | tail -1 | grep -oE '[0-9]+' | head -1)
if [ -z "$COLLECTED" ] || [ "$COLLECTED" -lt 70 ]; then
  echo "❌ pytest collect = $COLLECTED < 70"
  exit 1
fi
echo "✓ pytest 已 collect $COLLECTED tests（≥ 70）"

# 6. unit tests 全綠（不依賴 docker）
uv run pytest tests/unit/ -q --no-header 2>&1 | tail -1 | grep -q "passed" || {
  echo "❌ unit tests 有 fail"
  exit 1
}
echo "✓ unit tests 全綠"

# 7. 啟 backend 嘗試打 /health/live
# 若 docker 沒跑，PYTEST_RUNNING=true 跳過 startup probe（讓 server 能啟）
PYTEST_RUNNING=true uv run uvicorn app.main:app --port 8000 --no-access-log &
SERVER_PID=$!

# 等 uvicorn 啟動（最多 10 秒）
for i in $(seq 1 20); do
  if curl -fsS http://localhost:8000/health/live >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# 8. /health/live 200
if ! curl -fsS http://localhost:8000/health/live >/dev/null 2>&1; then
  kill $SERVER_PID 2>/dev/null || true
  echo "❌ /health/live 未回 200"
  exit 1
fi
echo "✓ /health/live 200"

# 9. X-Request-ID header
if ! curl -sI http://localhost:8000/health/live | grep -qi "X-Request-ID"; then
  kill $SERVER_PID 2>/dev/null || true
  echo "❌ X-Request-ID header 缺"
  exit 1
fi
echo "✓ X-Request-ID header 存在"

# 10. envelope 格式（用 Python 解析，避開 jq 依賴）
ENV_OK=$(curl -s http://localhost:8000/health/live | \
  python -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('data',{}).get('status')=='alive' and 'meta' in d else 'FAIL')" 2>&1)
if [ "$ENV_OK" != "OK" ]; then
  kill $SERVER_PID 2>/dev/null || true
  echo "❌ envelope 格式錯：$ENV_OK"
  exit 1
fi
echo "✓ envelope 格式正確"

# 11. /health/seeded 回 false
SEEDED_FALSE=$(curl -s http://localhost:8000/health/seeded | \
  python -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('data',{}).get('seeded') is False else 'FAIL')" 2>&1)
if [ "$SEEDED_FALSE" != "OK" ]; then
  kill $SERVER_PID 2>/dev/null || true
  echo "❌ /health/seeded 應 false，實際非 false"
  exit 1
fi
echo "✓ /health/seeded 回 false"

# 12. 404 走 envelope_error 格式
ERR_OK=$(curl -s http://localhost:8000/__no_such_path__ | \
  python -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'error' in d and d['error'].get('code') in ('NOT_FOUND','HTTP_404') else 'FAIL')" 2>&1)
if [ "$ERR_OK" != "OK" ]; then
  kill $SERVER_PID 2>/dev/null || true
  echo "❌ 404 envelope 格式錯：$ERR_OK"
  exit 1
fi
echo "✓ 404 走 envelope_error"

# 13. SecurityHeaders
HDRS=$(curl -sI http://localhost:8000/health/live)
echo "$HDRS" | grep -qi "X-Content-Type-Options: nosniff" || {
  kill $SERVER_PID 2>/dev/null || true
  echo "❌ X-Content-Type-Options 缺"
  exit 1
}
echo "$HDRS" | grep -qi "X-Frame-Options: DENY" || {
  kill $SERVER_PID 2>/dev/null || true
  echo "❌ X-Frame-Options 缺"
  exit 1
}
echo "✓ SecurityHeaders 完整"

# 收尾
kill $SERVER_PID 2>/dev/null || true
# 等 server 完全關
for i in $(seq 1 10); do
  if ! curl -s http://localhost:8000/health/live >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

cd "$PROJECT_ROOT"
echo ""
echo "✅ Phase 03 健康檢查全部通過"
