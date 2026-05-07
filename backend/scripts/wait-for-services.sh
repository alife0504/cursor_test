#!/bin/sh
# wait-for-services.sh — 等待 timescaledb / redis / qdrant 全部 ready
# 依 PLAN.md 第 13.2 章設計。
#
# 用法：CMD ["./scripts/wait-for-services.sh", "uv", "run", "uvicorn", "app.main:app", ...]
# 在 P3 backend container 啟動時用，確保 DB / cache / vector 都 ready 才跑 uvicorn。
#
# 注意：用 sh（不是 bash），相容 alpine container；exec "$@" 才能正確 pid=1。

set -e

POSTGRES_HOST="${POSTGRES_HOST:-timescaledb}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
QDRANT_HOST="${QDRANT_HOST:-qdrant}"
QDRANT_PORT="${QDRANT_PORT:-6333}"

MAX_WAIT="${WAIT_FOR_SERVICES_TIMEOUT:-180}"
INTERVAL=2
elapsed=0

wait_for() {
  name="$1"; shift
  cmd="$*"
  echo "Waiting for $name..."
  while ! eval "$cmd" >/dev/null 2>&1; do
    if [ "$elapsed" -ge "$MAX_WAIT" ]; then
      echo "❌ Timeout waiting for $name (${MAX_WAIT}s)"
      exit 1
    fi
    sleep "$INTERVAL"
    elapsed=$((elapsed + INTERVAL))
  done
  echo "✓ $name ready"
}

# ── TimescaleDB ──
# pg_isready 是 alpine 的 postgresql-client 套件提供（backend image 需裝）
wait_for "TimescaleDB" "pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER"

# ── Redis ──
# redis-cli 同樣需 backend image 裝；用 PING 不需 password 也能驗（NOAUTH error 也代表 ready）
wait_for "Redis" "(echo PING | nc -w 2 $REDIS_HOST $REDIS_PORT) | grep -qE 'PONG|NOAUTH'"

# ── Qdrant ──
# /healthz 不需 API key
wait_for "Qdrant" "wget -qO- http://$QDRANT_HOST:$QDRANT_PORT/healthz"

echo ""
echo "✅ All services ready (took ${elapsed}s)"
echo ""
exec "$@"
