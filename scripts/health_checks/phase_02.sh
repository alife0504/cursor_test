#!/bin/bash
# scripts/health_checks/phase_02.sh
# Phase 2 健康檢查：驗證 Docker 三服務 + DB 帳號分離 + Qdrant API key
# 後續 Phase 開頭跑此 script 確保 P2 結果還能跑

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 02 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

# 0. .env 必要欄位
test -f .env || { echo "❌ .env 不存在"; exit 1; }
for var in POSTGRES_SUPERUSER_PASSWORD TA_MIGRATION_PASSWORD TA_SERVICE_RW_PASSWORD \
           TA_AGENT_RO_PASSWORD REDIS_PASSWORD QDRANT_API_KEY; do
  val=$(grep "^${var}=" .env | cut -d= -f2)
  test -n "$val" || { echo "❌ .env 缺 ${var}（或為空）"; exit 1; }
done
echo "✓ .env 必要密碼欄位齊全"

# 1. docker compose 設定檔
test -f docker-compose.yml      || { echo "❌ docker-compose.yml 缺"; exit 1; }
test -f docker-compose.prod.yml || { echo "❌ docker-compose.prod.yml 缺"; exit 1; }
test -x docker/timescaledb/init.sh        || { echo "❌ init.sh 不可執行"; exit 1; }
test -f docker/timescaledb/init.sql.template || { echo "❌ init.sql.template 缺"; exit 1; }
test -x backend/scripts/wait-for-services.sh || { echo "❌ wait-for-services.sh 不可執行"; exit 1; }
echo "✓ docker compose 設定檔齊全"

# 2. docker daemon 在跑（沒跑就跳過後續 runtime 檢查）
if ! docker info >/dev/null 2>&1; then
  echo "⚠️  Docker daemon 未啟動 → 跳過 runtime 檢查（請啟動 Docker Desktop 後重跑）"
  exit 0
fi

# 3. 三服務在跑
RUNNING=$(docker compose ps --status running --format json 2>/dev/null | grep -c "Service" || echo "0")
if [ "$RUNNING" -lt 3 ]; then
  echo "⚠️  Docker 三服務未全跑（make up 後重跑）"
  exit 0
fi
echo "✓ 三服務 running"

# 4. timescaledb healthcheck
docker compose exec -T timescaledb pg_isready -U postgres >/dev/null 2>&1 || \
  { echo "❌ timescaledb 未 ready"; exit 1; }
echo "✓ timescaledb 可連"

# 5. timescaledb 三帳號可連
PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
PG_DB="${POSTGRES_DB:-tradingagents_tw}"

for user in ta_migration ta_service_rw ta_agent_ro; do
  var_name=$(echo "${user}_PASSWORD" | tr 'a-z' 'A-Z')
  pwd=$(grep "^${var_name}=" .env | cut -d= -f2)
  PGPASSWORD="$pwd" docker compose exec -T -e PGPASSWORD="$pwd" timescaledb \
    psql -h localhost -U "$user" -d "$PG_DB" -c "SELECT 1" >/dev/null 2>&1 || \
    { echo "❌ ${user} 連線失敗"; exit 1; }
done
echo "✓ ta_migration / ta_service_rw / ta_agent_ro 三帳號皆可連"

# 6. ta_service_rw 不能 DDL
RW_PWD=$(grep "^TA_SERVICE_RW_PASSWORD=" .env | cut -d= -f2)
out=$(docker compose exec -T -e PGPASSWORD="$RW_PWD" timescaledb \
  psql -h localhost -U ta_service_rw -d "$PG_DB" \
  -c "CREATE TABLE _hc_should_fail (x INT)" 2>&1 || true)
echo "$out" | grep -qi "permission denied\|must be owner" || \
  { echo "❌ ta_service_rw 不該能建表，但成功了"; exit 1; }
echo "✓ ta_service_rw 無 DDL 權限（符合預期）"

# 7. ta_agent_ro 不能 INSERT/CREATE
RO_PWD=$(grep "^TA_AGENT_RO_PASSWORD=" .env | cut -d= -f2)
out=$(docker compose exec -T -e PGPASSWORD="$RO_PWD" timescaledb \
  psql -h localhost -U ta_agent_ro -d "$PG_DB" \
  -c "CREATE TABLE _hc_ro_fail (x INT)" 2>&1 || true)
echo "$out" | grep -qi "permission denied\|must be owner" || \
  { echo "❌ ta_agent_ro 不該能建表，但成功了"; exit 1; }
echo "✓ ta_agent_ro 無 DDL 權限（符合預期）"

# 8. timescaledb extension 已啟
SU_PWD=$(grep "^POSTGRES_SUPERUSER_PASSWORD=" .env | cut -d= -f2)
ext=$(docker compose exec -T -e PGPASSWORD="$SU_PWD" timescaledb \
  psql -h localhost -U postgres -d "$PG_DB" \
  -tAc "SELECT extname FROM pg_extension WHERE extname='timescaledb'" 2>/dev/null)
test "$ext" = "timescaledb" || { echo "❌ timescaledb extension 未啟用"; exit 1; }
echo "✓ timescaledb extension 已啟用"

# 9. redis 可 ping
REDIS_PWD=$(grep "^REDIS_PASSWORD=" .env | cut -d= -f2)
docker compose exec -T redis redis-cli -a "$REDIS_PWD" ping 2>/dev/null | grep -q PONG || \
  { echo "❌ redis ping 失敗"; exit 1; }
echo "✓ redis ping OK"

# 10. qdrant healthz
curl -sf http://localhost:6333/healthz >/dev/null 2>&1 || \
  { echo "❌ qdrant /healthz 失敗"; exit 1; }
echo "✓ qdrant /healthz OK"

# 11. qdrant 需要 API key 才能列 collections
QK=$(grep "^QDRANT_API_KEY=" .env | cut -d= -f2)
status_no_key=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:6333/collections)
echo "$status_no_key" | grep -qE "^(401|403)$" || \
  { echo "❌ qdrant 沒帶 api-key 應 401/403，實際 $status_no_key"; exit 1; }

status_with_key=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "api-key: $QK" http://localhost:6333/collections)
test "$status_with_key" = "200" || \
  { echo "❌ qdrant 帶 api-key 應 200，實際 $status_with_key"; exit 1; }
echo "✓ qdrant API key 驗證生效"

cd "$PROJECT_ROOT"
echo ""
echo "✅ Phase 02 健康檢查全部通過"
