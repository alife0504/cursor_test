#!/bin/bash
# scripts/verify_backup.sh
#
# Phase 19 — 在隔離 DB（docker-compose.test-restore.yml）還原備份，
# 跑 verify_data.py 確認可還原成功，不影響 prod。
#
# 用法：
#   bash scripts/verify_backup.sh docker/backups/full_20260518_020000.tar.gz.gpg
#
# 排程建議：每月一次，crontab
#   0 4 1 * * cd /path/to/TradingAgents && bash scripts/verify_backup.sh $(ls -t docker/backups/full_*.tar.gz.gpg | head -1)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.prod"
TEST_COMPOSE="${PROJECT_ROOT}/docker-compose.test-restore.yml"
TMP_DIR="$(mktemp -d)"
trap 'cleanup' EXIT

cleanup() {
    rm -rf "$TMP_DIR"
    if [ "${KEEP_TEST_DB:-0}" != "1" ]; then
        echo "→ 清理 test DB（KEEP_TEST_DB=1 可保留）"
        docker compose -f "$TEST_COMPOSE" down -v > /dev/null 2>&1 || true
    fi
}

BACKUP_FILE="${1:?usage: bash scripts/verify_backup.sh <full_*.tar.gz.gpg>}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ 找不到備份檔：$BACKUP_FILE" >&2
    exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ 找不到 $ENV_FILE" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

TEST_DB="tradingagents_tw_test"
TEST_PORT="${TEST_RESTORE_PG_PORT:-5433}"

echo "═══════════════════════════════════════"
echo "TradingAgents-TW Backup Verify"
echo "  Backup: $BACKUP_FILE"
echo "  Test DB: $TEST_DB @ localhost:$TEST_PORT"
echo "═══════════════════════════════════════"

# ──────────────────────────────────────────────────────
# 1. 啟動隔離 DB
# ──────────────────────────────────────────────────────
echo "[1/5] 啟動 test DB..."
# 先確保乾淨
docker compose -f "$TEST_COMPOSE" down -v > /dev/null 2>&1 || true
docker compose -f "$TEST_COMPOSE" up -d timescaledb_test

# 等 healthy
ATTEMPT=0
until docker compose -f "$TEST_COMPOSE" ps --format json 2>/dev/null | grep -q '"Health":"healthy"'; do
    ATTEMPT=$((ATTEMPT + 1))
    if [ "$ATTEMPT" -gt 30 ]; then
        echo "❌ test DB 60 秒內未 healthy" >&2
        docker compose -f "$TEST_COMPOSE" logs timescaledb_test | tail -50
        exit 1
    fi
    sleep 2
done
echo "    ✓ test DB healthy"

# ──────────────────────────────────────────────────────
# 2. GPG decrypt + 解壓
# ──────────────────────────────────────────────────────
echo "[2/5] decrypt + extract..."
gpg --batch --yes --decrypt --output "$TMP_DIR/full.tar.gz" "$BACKUP_FILE"
tar xzf "$TMP_DIR/full.tar.gz" -C "$TMP_DIR/"

DB_DUMP=$(ls "$TMP_DIR"/db_*.dump 2>/dev/null | head -1)
if [ -z "$DB_DUMP" ]; then
    echo "❌ 找不到 db_*.dump" >&2
    exit 1
fi
echo "    ✓ dump: $(du -h "$DB_DUMP" | cut -f1)"

# ──────────────────────────────────────────────────────
# 3. pg_restore 到 test DB
# ──────────────────────────────────────────────────────
echo "[3/5] pg_restore..."
docker compose -f "$TEST_COMPOSE" exec -T timescaledb_test \
    psql -U postgres -d "$TEST_DB" -c \
    "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;
     CREATE EXTENSION IF NOT EXISTS timescaledb;
     CREATE EXTENSION IF NOT EXISTS pgcrypto;" > /dev/null

docker compose -f "$TEST_COMPOSE" exec -T timescaledb_test \
    pg_restore -U postgres -d "$TEST_DB" \
        --no-owner --no-privileges --if-exists --clean \
    < "$DB_DUMP" 2>&1 | grep -vE "^pg_restore: warning" | tail -20 || true

# ──────────────────────────────────────────────────────
# 4. 跑 verify_data.py（指向 test DB）
# ──────────────────────────────────────────────────────
echo "[4/5] verify_data.py..."

# 用 env override 對 test DB 跑驗證
cd "$PROJECT_ROOT"
POSTGRES_HOST=localhost \
POSTGRES_PORT="$TEST_PORT" \
POSTGRES_DB="$TEST_DB" \
POSTGRES_SUPERUSER_PASSWORD="${POSTGRES_SUPERUSER_PASSWORD}" \
    uv --project backend run python data-pipeline/scripts/verify_data.py \
    || { echo "❌ verify_data.py 失敗"; exit 1; }

# ──────────────────────────────────────────────────────
# 5. 摘要
# ──────────────────────────────────────────────────────
echo "[5/5] 摘要..."
ROW_COUNT=$(docker compose -f "$TEST_COMPOSE" exec -T timescaledb_test \
    psql -U postgres -d "$TEST_DB" -tAc \
    "SELECT
        (SELECT count(*) FROM users) || ' users, ' ||
        (SELECT count(*) FROM stock_list) || ' stocks, ' ||
        (SELECT count(*) FROM audit_logs) || ' audit_logs'" 2>/dev/null \
    || echo "(query failed)")
echo "    → $ROW_COUNT"

echo ""
echo "✅ Backup verified: $BACKUP_FILE"
