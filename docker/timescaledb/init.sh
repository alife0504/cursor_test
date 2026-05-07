#!/bin/bash
# TradingAgents-TW TimescaleDB 初始化 entrypoint
# Phase 2 設計：postgres docker-entrypoint.sh 會在 init phase 跑此 script。
# 此 script 用 envsubst 把 init.sql.template 中的 ${VAR} 替換成實際值，
# 再 piped 給 psql 執行。
#
# 為什麼不直接用 psql -v：
#   psql -v VAR=val 在 SQL 中要寫 :'VAR'，與一般 ${VAR} 寫法不同，
#   且對 multiline 與多服務變數展開不友善。envsubst 預處理是更乾淨方式。

set -euo pipefail

TEMPLATE="/docker-entrypoint-initdb.d/init.sql.template"
GENERATED="/tmp/init.sql"

if [ ! -f "$TEMPLATE" ]; then
  echo "❌ Template not found: $TEMPLATE" >&2
  exit 1
fi

# 必要環境變數（沒設就直接失敗，避免空密碼帳號）
: "${TA_MIGRATION_PASSWORD:?TA_MIGRATION_PASSWORD 必須設定}"
: "${TA_SERVICE_RW_PASSWORD:?TA_SERVICE_RW_PASSWORD 必須設定}"
: "${TA_AGENT_RO_PASSWORD:?TA_AGENT_RO_PASSWORD 必須設定}"

echo "[init.sh] envsubst 替換 template → $GENERATED"
# 限制只替換我們要的變數，避免意外展開 SQL 中的 $$、$1 等
envsubst '${TA_MIGRATION_PASSWORD} ${TA_SERVICE_RW_PASSWORD} ${TA_AGENT_RO_PASSWORD}' \
  < "$TEMPLATE" > "$GENERATED"

echo "[init.sh] 跑 psql..."
# postgres docker-entrypoint 已啟動 server 並設好 PGUSER=postgres / PGDATABASE=$POSTGRES_DB
# 直接 psql 連 superuser
psql -v ON_ERROR_STOP=1 \
  --username "${POSTGRES_USER:-postgres}" \
  --dbname "${POSTGRES_DB:-tradingagents_tw}" \
  --file "$GENERATED"

echo "[init.sh] 清理臨時檔"
rm -f "$GENERATED"

echo "[init.sh] ✅ TimescaleDB 初始化完成"
