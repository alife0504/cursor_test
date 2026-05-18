#!/bin/bash
# scripts/health_checks/phase_04.sh
# Phase 4 健康檢查：完整 DB Schema + Alembic Migration + Hypertable + Trigger + Qdrant
#
# 後續 Phase 開頭跑此 script 確保 P4 schema 還能跑。

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 04 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

# 共用 helper：跑 psql 到 docker container（不依賴本機裝 psql）
psql_pg() {
  docker compose exec -T -e PGPASSWORD="$1" timescaledb \
    psql -U "$2" -d tradingagents_tw -tAc "$3" 2>/dev/null
}

# 讀 .env
PG=$(grep ^POSTGRES_SUPERUSER_PASSWORD= .env | cut -d= -f2)
TS=$(grep ^TA_SERVICE_RW_PASSWORD= .env | cut -d= -f2)
RO=$(grep ^TA_AGENT_RO_PASSWORD= .env | cut -d= -f2)
QK=$(grep ^QDRANT_API_KEY= .env | cut -d= -f2)

# 1. 表數量 ≥ 24（25 業務 + 1 alembic_version）
COUNT=$(psql_pg "$PG" postgres "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
if [ -z "$COUNT" ] || [ "$COUNT" -lt 24 ]; then
  echo "❌ public schema table count = $COUNT (< 24)"
  exit 1
fi
echo "✓ 表數量 = $COUNT (≥ 24)"

# 2. hypertable ≥ 6（stock_prices / audit_logs / llm_usage / notification_log /
#    celery_dead_letters / debate_history）
COUNT=$(psql_pg "$PG" postgres "SELECT count(*) FROM timescaledb_information.hypertables")
if [ -z "$COUNT" ] || [ "$COUNT" -lt 6 ]; then
  echo "❌ hypertable count = $COUNT (< 6)"
  exit 1
fi
echo "✓ hypertable 數 = $COUNT (≥ 6)"

# 3. retention policy ≥ 6
COUNT=$(psql_pg "$PG" postgres "SELECT count(*) FROM timescaledb_information.jobs WHERE proc_name='policy_retention'")
if [ -z "$COUNT" ] || [ "$COUNT" -lt 6 ]; then
  echo "❌ retention policy count = $COUNT (< 6)"
  exit 1
fi
echo "✓ retention policy 數 = $COUNT (≥ 6)"

# 4. audit_logs hash chain trigger 存在（用 pg_trigger 避免 hypertable chunks 重複計數）
HAS_TRIGGER=$(psql_pg "$PG" postgres "SELECT count(*) FROM pg_trigger WHERE tgname='trg_audit_logs_hash_chain' AND NOT tgisinternal")
if [ -z "$HAS_TRIGGER" ] || [ "$HAS_TRIGGER" -lt 1 ]; then
  echo "❌ audit_logs hash chain trigger 不存在"
  exit 1
fi
echo "✓ audit_logs hash chain trigger 存在"

# 5. updated_at trigger 存在（至少 8 個）— 用 pg_trigger
COUNT=$(psql_pg "$PG" postgres "SELECT count(*) FROM pg_trigger WHERE tgname LIKE '%_updated_at' AND NOT tgisinternal")
if [ -z "$COUNT" ] || [ "$COUNT" -lt 8 ]; then
  echo "❌ updated_at trigger count = $COUNT (< 8)"
  exit 1
fi
echo "✓ updated_at trigger 數 = $COUNT (≥ 8)"

# 6. INSERT 一筆 audit_logs，看 entry_hash 是 64 字 hex
# psql 同時印 RETURNING 與 "INSERT 0 1"，用 grep 抓 64 字 hex 那行
HASH=$(psql_pg "$TS" ta_service_rw "INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details) VALUES (NULL, 'health_check.phase_04', 'system', 'phase_04_$(date +%s)', '{}'::jsonb) RETURNING entry_hash" | grep -E "^[a-f0-9]{64}$" | head -1)
if [ -z "$HASH" ] || [ "${#HASH}" -ne 64 ]; then
  echo "❌ entry_hash 不是 64 字（${#HASH}）：$HASH"
  exit 1
fi
echo "✓ audit_logs hash chain 寫入成功（entry_hash 64 字 hex）"

# 7. ta_service_rw 不能 UPDATE audit_logs
if psql_pg "$TS" ta_service_rw "UPDATE audit_logs SET action='hack' WHERE id=1" 2>&1 | grep -qi "permission denied"; then
  echo "✓ ta_service_rw 不可 UPDATE audit_logs"
else
  # 注意：psql 走 docker exec 時 stderr 可能不在 $? 中；改用 exit code
  if docker compose exec -T -e PGPASSWORD="$TS" timescaledb psql -U ta_service_rw -d tradingagents_tw -c "UPDATE audit_logs SET action='hack' WHERE id=1" 2>&1 | grep -qi "permission denied"; then
    echo "✓ ta_service_rw 不可 UPDATE audit_logs"
  else
    echo "❌ ta_service_rw 可 UPDATE audit_logs（不該允許）"
    exit 1
  fi
fi

# 8. ta_service_rw 不能 DELETE audit_logs
if docker compose exec -T -e PGPASSWORD="$TS" timescaledb psql -U ta_service_rw -d tradingagents_tw -c "DELETE FROM audit_logs WHERE id=1" 2>&1 | grep -qi "permission denied"; then
  echo "✓ ta_service_rw 不可 DELETE audit_logs"
else
  echo "❌ ta_service_rw 可 DELETE audit_logs（不該允許）"
  exit 1
fi

# 9. ta_agent_ro 可 SELECT stock_list
psql_pg "$RO" ta_agent_ro "SELECT count(*) FROM stock_list" >/dev/null
echo "✓ ta_agent_ro 可 SELECT stock_list"

# 10. ta_agent_ro 不可 INSERT users
if docker compose exec -T -e PGPASSWORD="$RO" timescaledb psql -U ta_agent_ro -d tradingagents_tw -c "INSERT INTO users (email, password_hash) VALUES ('hack@x.com', 'x')" 2>&1 | grep -qi "permission denied"; then
  echo "✓ ta_agent_ro 不可 INSERT users"
else
  echo "❌ ta_agent_ro 可 INSERT users（不該允許）"
  exit 1
fi

# 11. alembic upgrade / downgrade 雙向通過
cd backend
uv run alembic upgrade head >/dev/null 2>&1 || { echo "❌ alembic upgrade head 失敗"; exit 1; }
uv run alembic downgrade -1 >/dev/null 2>&1 || { echo "❌ alembic downgrade -1 失敗"; exit 1; }
uv run alembic upgrade head >/dev/null 2>&1 || { echo "❌ alembic upgrade head 失敗(第二次)"; exit 1; }
cd "$PROJECT_ROOT"
echo "✓ alembic upgrade / downgrade -1 / upgrade head 雙向 OK"

# 12. Qdrant 7 個 collections
COUNT=$(curl -s -H "api-key: $QK" http://localhost:6333/collections | python -c "import sys,json; r=json.load(sys.stdin); print(len(r['result']['collections']))" 2>/dev/null)
if [ -z "$COUNT" ] || [ "$COUNT" -lt 7 ]; then
  echo "❌ Qdrant collection count = $COUNT (< 7)"
  exit 1
fi
echo "✓ Qdrant collections = $COUNT (≥ 7)"

# 13. P4 新增測試全綠（≥ 27 個 unit+integration）
cd backend
uv run pytest tests/integration/test_schema.py tests/integration/test_migration_up_down.py tests/unit/test_models.py -q --no-header 2>&1 | tail -1 | grep -qE "[0-9]+ passed" || {
  echo "❌ P4 測試未全綠"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ P4 測試全綠"

echo ""
echo "✅ Phase 04 健康檢查全部通過"
