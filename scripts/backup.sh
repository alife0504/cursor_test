#!/bin/bash
# scripts/backup.sh
#
# Phase 19 — 完整備份（PG + Qdrant）→ tar → GPG 加密 → 30 天保留。
#
# 前置：
#   - docker compose -f docker-compose.prod.yml up -d 已跑（timescaledb / qdrant healthy）
#   - .env.prod 含 GPG_RECIPIENT（GPG public key 的 user-id 或 fingerprint）
#   - gpg --import 已 import 過該 public key
#
# 用法：
#   bash scripts/backup.sh
#
# 輸出：
#   docker/backups/full_YYYYMMDD_HHMMSS.tar.gz.gpg
#
# 排程建議：crontab 每天 02:00
#   0 2 * * * cd /path/to/TradingAgents && bash scripts/backup.sh >> docker/backups/backup.log 2>&1

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.prod"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_ROOT}/docker/backups}"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# ──────────────────────────────────────────────────────
# 0. 前置檢查
# ──────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ 找不到 $ENV_FILE，請先 cp .env.prod.example .env.prod" >&2
    exit 1
fi

# 用 set -a + source 讀進來（接受 shell-safe 的值）
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

GPG_RECIPIENT="${GPG_RECIPIENT:-}"
if [ -z "$GPG_RECIPIENT" ]; then
    echo "❌ .env.prod 沒設 GPG_RECIPIENT（GPG public key user-id）" >&2
    exit 1
fi

# 確認 GPG key 已 import
if ! gpg --list-keys "$GPG_RECIPIENT" > /dev/null 2>&1; then
    echo "❌ GPG public key 未 import：$GPG_RECIPIENT" >&2
    echo "   執行：gpg --import path/to/backup_pubkey.asc" >&2
    exit 1
fi

# 確認 prod 服務在跑
if ! docker compose -f "$COMPOSE_FILE" ps --services --filter "status=running" 2>/dev/null | grep -q timescaledb; then
    echo "❌ docker-compose.prod.yml 的 timescaledb 未運行" >&2
    exit 1
fi

POSTGRES_DB="${POSTGRES_DB:-tradingagents_tw}"

echo "═══════════════════════════════════════"
echo "TradingAgents-TW Backup — $TIMESTAMP"
echo "═══════════════════════════════════════"

# ──────────────────────────────────────────────────────
# 1. PostgreSQL dump (custom format with compression)
# ──────────────────────────────────────────────────────
echo "[1/4] pg_dump..."
docker compose -f "$COMPOSE_FILE" exec -T timescaledb \
    pg_dump -U postgres -F custom -Z 9 -d "$POSTGRES_DB" \
    > "$TMP_DIR/db_${TIMESTAMP}.dump"

PG_SIZE=$(du -h "$TMP_DIR/db_${TIMESTAMP}.dump" | cut -f1)
echo "    ✓ DB dump: $PG_SIZE"

# ──────────────────────────────────────────────────────
# 2. Qdrant snapshot（先 trigger snapshot，再 tar storage）
# ──────────────────────────────────────────────────────
echo "[2/4] Qdrant snapshot..."

# 透過 docker network 內部呼叫 qdrant API（不依賴 host 對外）
COLLECTIONS=$(docker compose -f "$COMPOSE_FILE" exec -T qdrant \
    sh -c "wget -qO- --header='api-key: ${QDRANT_API_KEY}' http://localhost:6333/collections" 2>/dev/null \
    | python3 -c "import sys,json; r=json.load(sys.stdin); print(' '.join(c['name'] for c in r.get('result',{}).get('collections',[])))" \
    2>/dev/null || echo "")

if [ -n "$COLLECTIONS" ]; then
    for collection in $COLLECTIONS; do
        echo "    - snapshot: $collection"
        docker compose -f "$COMPOSE_FILE" exec -T qdrant \
            sh -c "wget -qO- --post-data='' --header='api-key: ${QDRANT_API_KEY}' http://localhost:6333/collections/${collection}/snapshots" \
            > /dev/null 2>&1 || echo "      (snapshot trigger 失敗，繼續)"
    done
else
    echo "    (尚無 collection，跳過 snapshot trigger)"
fi

# tar Qdrant data volume
QDRANT_VOL="tradingagents_qdrant_data_prod"
docker run --rm \
    -v "${QDRANT_VOL}:/qdrant:ro" \
    -v "${TMP_DIR}:/backup" \
    alpine:3.20 \
    tar czf "/backup/qdrant_${TIMESTAMP}.tar.gz" -C /qdrant . 2>/dev/null

QD_SIZE=$(du -h "$TMP_DIR/qdrant_${TIMESTAMP}.tar.gz" | cut -f1)
echo "    ✓ Qdrant tarball: $QD_SIZE"

# ──────────────────────────────────────────────────────
# 3. 打包 + GPG 加密
# ──────────────────────────────────────────────────────
echo "[3/4] tar + GPG encrypt..."

FULL_TAR="$TMP_DIR/full_${TIMESTAMP}.tar.gz"
tar czf "$FULL_TAR" -C "$TMP_DIR" "db_${TIMESTAMP}.dump" "qdrant_${TIMESTAMP}.tar.gz"

OUT="$BACKUP_DIR/full_${TIMESTAMP}.tar.gz.gpg"
gpg --batch --yes --trust-model always \
    --encrypt --recipient "$GPG_RECIPIENT" \
    --output "$OUT" \
    "$FULL_TAR"

OUT_SIZE=$(du -h "$OUT" | cut -f1)
echo "    ✓ encrypted: $OUT ($OUT_SIZE)"

# ──────────────────────────────────────────────────────
# 4. Retention（預設 30 天）
# ──────────────────────────────────────────────────────
RET="${BACKUP_RETENTION_DAYS:-30}"
echo "[4/4] Retention: $RET 天..."
DELETED=$(find "$BACKUP_DIR" -name "full_*.tar.gz.gpg" -mtime "+$RET" -print -delete 2>/dev/null | wc -l)
echo "    刪除 $DELETED 個過期備份"

echo ""
echo "✅ Backup complete: $OUT"
echo "   保留 ${RET} 天；目前共 $(ls "$BACKUP_DIR"/full_*.tar.gz.gpg 2>/dev/null | wc -l) 個備份"
