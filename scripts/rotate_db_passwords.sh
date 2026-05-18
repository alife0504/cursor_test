#!/usr/bin/env bash
# scripts/rotate_db_passwords.sh — Postgres ta_service_rw / ta_agent_ro 密碼輪替。
#
# 流程：
#   1. 產生新密碼
#   2. ALTER USER ... WITH PASSWORD '<new>'（用 ta_migration 帳號跑）
#   3. 更新 .env 對應欄位
#   4. 重啟 backend + workers
#
# Usage:
#   ./scripts/rotate_db_passwords.sh ta_service_rw
#   ./scripts/rotate_db_passwords.sh ta_agent_ro
#
# Notes:
#   - 需要 ta_migration 帳號連線（PGUSER/PGPASSWORD env or .env）
#   - 重啟期間（5-30s）會有 connection error；建議搭配連線重試

set -euo pipefail

USER_NAME="${1:-}"
if [ -z "$USER_NAME" ]; then
  echo "Usage: $0 <ta_service_rw|ta_agent_ro>"
  exit 1
fi

case "$USER_NAME" in
  ta_service_rw|ta_agent_ro) ;;
  *) echo "ERROR: 只支援 ta_service_rw / ta_agent_ro"; exit 1 ;;
esac

ENV_FILE="${ENV_FILE:-.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE 不存在"; exit 1; }

# 從 .env 讀 ta_migration 連線
MIG_PWD=$(grep -E '^TA_MIGRATION_PASSWORD=' "$ENV_FILE" | head -1 | cut -d= -f2-)
PG_HOST=$(grep -E '^POSTGRES_HOST=' "$ENV_FILE" | head -1 | cut -d= -f2-)
PG_PORT=$(grep -E '^POSTGRES_PORT=' "$ENV_FILE" | head -1 | cut -d= -f2-)
PG_DB=$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | head -1 | cut -d= -f2-)

if [ -z "$MIG_PWD" ] || [ -z "$PG_HOST" ] || [ -z "$PG_PORT" ] || [ -z "$PG_DB" ]; then
  echo "ERROR: .env 必須有 TA_MIGRATION_PASSWORD / POSTGRES_HOST / POSTGRES_PORT / POSTGRES_DB"
  exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)
BAK="${ENV_FILE}.bak.${TS}"
cp "$ENV_FILE" "$BAK"
echo "✓ 備份 .env → $BAK"

NEW_PWD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

# 更新 DB（用 psql via docker exec；若有本機 psql 也可）
echo "→ 用 ta_migration 跑 ALTER USER $USER_NAME ..."
PGPASSWORD="$MIG_PWD" psql \
  -h "$PG_HOST" -p "$PG_PORT" -U ta_migration -d "$PG_DB" \
  -v ON_ERROR_STOP=1 \
  -c "ALTER USER $USER_NAME WITH PASSWORD '$NEW_PWD'"

# 更新 .env
ENV_KEY=""
case "$USER_NAME" in
  ta_service_rw) ENV_KEY="TA_SERVICE_RW_PASSWORD" ;;
  ta_agent_ro)   ENV_KEY="TA_AGENT_RO_PASSWORD" ;;
esac

if grep -qE "^${ENV_KEY}=" "$ENV_FILE"; then
  awk -v k="$ENV_KEY" -v v="$NEW_PWD" '
    $0 ~ "^" k "=" { print k "=" v; next }
    { print }
  ' "$ENV_FILE" > "${ENV_FILE}.tmp"
  mv "${ENV_FILE}.tmp" "$ENV_FILE"
else
  echo "${ENV_KEY}=$NEW_PWD" >> "$ENV_FILE"
fi

echo "✓ DB 密碼已輪替 + .env 已更新。"
echo "  → 重啟 backend + workers（make backend-restart make workers-restart）"
echo "  → 若失敗：cp $BAK $ENV_FILE 還原"
