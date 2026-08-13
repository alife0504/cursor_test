#!/bin/sh
# TradingAgents-TW TimescaleDB 初始化 entrypoint
# Phase 2 設計：postgres docker-entrypoint.sh 會在 init phase 跑此 script。
# 此 script 用 sed 把 init.sql.template 中的特定變數替換成實際值，
# 再 piped 給 psql 執行。
#
# 為什麼用 sed 而非 envsubst：
#   timescale/timescaledb 是 alpine-based image，預設無 gettext 套件（envsubst）。
#   裝 gettext 會增加 image 大小，sed 用 stdlib 完全可達同目的。
#
# 為什麼不直接 psql -v：
#   psql -v VAR=val 在 SQL 中要寫 :'VAR'，對 multiline 與多服務變數展開不友善。

set -eu

TEMPLATE="/docker-entrypoint-initdb.d/init.sql.template"
GENERATED="/tmp/init.sql"

if [ ! -f "$TEMPLATE" ]; then
  echo "[init.sh] ❌ Template not found: $TEMPLATE" >&2
  exit 1
fi

# 必要環境變數（沒設就直接失敗，避免空密碼帳號）
: "${TA_MIGRATION_PASSWORD:?TA_MIGRATION_PASSWORD 必須設定}"
: "${TA_SERVICE_RW_PASSWORD:?TA_SERVICE_RW_PASSWORD 必須設定}"
: "${TA_AGENT_RO_PASSWORD:?TA_AGENT_RO_PASSWORD 必須設定}"

echo "[init.sh] sed 替換 template → $GENERATED"
# 只替換我們明確列出的變數，避免意外展開 SQL 中的其他 $$、$1 等。
# 注意：密碼可能含 / 字元，所以用 # 當 sed 分隔符。
sed \
  -e "s#\${TA_MIGRATION_PASSWORD}#${TA_MIGRATION_PASSWORD}#g" \
  -e "s#\${TA_SERVICE_RW_PASSWORD}#${TA_SERVICE_RW_PASSWORD}#g" \
  -e "s#\${TA_AGENT_RO_PASSWORD}#${TA_AGENT_RO_PASSWORD}#g" \
  "$TEMPLATE" > "$GENERATED"

# 安全檢查：替換後不該還有 ${...} 殘留（除非是 SQL 中的 dollar-quoted string）
if grep -qE '\$\{[A-Z_]+\}' "$GENERATED"; then
  echo "[init.sh] ❌ 仍有未替換的 \${VAR} 變數：" >&2
  grep -nE '\$\{[A-Z_]+\}' "$GENERATED" >&2
  exit 1
fi

echo "[init.sh] 跑 psql..."
# postgres docker-entrypoint 已啟動 server 並設好 PGUSER=postgres / PGDATABASE=$POSTGRES_DB
psql -v ON_ERROR_STOP=1 \
  --username "${POSTGRES_USER:-postgres}" \
  --dbname "${POSTGRES_DB:-tradingagents_tw}" \
  --file "$GENERATED"

echo "[init.sh] 清理臨時檔"
rm -f "$GENERATED"

echo "[init.sh] ✅ TimescaleDB 初始化完成"
