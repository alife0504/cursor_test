#!/bin/bash
# scripts/restore.sh
#
# Phase 19 — 從 GPG-encrypted backup 還原到 prod。
#
# ⚠️ 警告：這會 DROP & RECREATE prod DB，再 pg_restore。請務必小心。
#
# 前置：
#   - .env.prod 已配置
#   - GPG 私鑰已 import（gpg --import path/to/backup_privkey.asc）
#   - docker-compose.prod.yml 服務跑著（timescaledb healthy）
#
# 用法：
#   bash scripts/restore.sh docker/backups/full_20260518_020000.tar.gz.gpg

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.prod"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

BACKUP_FILE="${1:?usage: bash scripts/restore.sh <full_*.tar.gz.gpg>}"

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

POSTGRES_DB="${POSTGRES_DB:-tradingagents_tw}"

echo "═══════════════════════════════════════"
echo "TradingAgents-TW Restore"
echo "  Backup: $BACKUP_FILE"
echo "  Target DB: $POSTGRES_DB"
echo "═══════════════════════════════════════"

# ──────────────────────────────────────────────────────
# 0. 雙重確認
# ──────────────────────────────────────────────────────
if [ -z "${RESTORE_AUTO_CONFIRM:-}" ]; then
    echo ""
    echo "⚠️  即將：DROP DATABASE $POSTGRES_DB → CREATE → 還原"
    echo "    所有現有資料會被覆蓋。"
    echo ""
    read -r -p "請輸入 yes 確認：" confirm
    if [ "$confirm" != "yes" ]; then
        echo "已取消"
        exit 1
    fi
fi

# ──────────────────────────────────────────────────────
# 1. GPG decrypt
# ──────────────────────────────────────────────────────
echo "[1/4] GPG decrypt..."
gpg --batch --yes --decrypt --output "$TMP_DIR/full.tar.gz" "$BACKUP_FILE"

# ──────────────────────────────────────────────────────
# 2. 解壓
# ──────────────────────────────────────────────────────
echo "[2/4] extract tar..."
tar xzf "$TMP_DIR/full.tar.gz" -C "$TMP_DIR/"

DB_DUMP=$(ls "$TMP_DIR"/db_*.dump 2>/dev/null | head -1)
QD_TAR=$(ls "$TMP_DIR"/qdrant_*.tar.gz 2>/dev/null | head -1)

if [ -z "$DB_DUMP" ]; then
    echo "❌ tarball 內找不到 db_*.dump" >&2
    exit 1
fi

# ──────────────────────────────────────────────────────
# 3. PG restore
# ──────────────────────────────────────────────────────
echo "[3/4] PG: DROP / CREATE / pg_restore..."

# 切回 postgres DB 才能 DROP 目標 DB
docker compose -f "$COMPOSE_FILE" exec -T timescaledb \
    psql -U postgres -d postgres -c \
    "DROP DATABASE IF EXISTS ${POSTGRES_DB} WITH (FORCE);"

docker compose -f "$COMPOSE_FILE" exec -T timescaledb \
    psql -U postgres -d postgres -c \
    "CREATE DATABASE ${POSTGRES_DB};"

# 還原前先建 extension（TimescaleDB / pgcrypto）
docker compose -f "$COMPOSE_FILE" exec -T timescaledb \
    psql -U postgres -d "${POSTGRES_DB}" -c \
    "CREATE EXTENSION IF NOT EXISTS timescaledb; CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# 用 pg_restore（容忍 extension 已存在 / 部分 owner 錯誤）
docker compose -f "$COMPOSE_FILE" exec -T timescaledb \
    pg_restore -U postgres -d "${POSTGRES_DB}" \
        --no-owner --no-privileges \
        --if-exists --clean \
    < "$DB_DUMP" || echo "    (pg_restore 有 warnings；通常無傷)"

# ──────────────────────────────────────────────────────
# 4. Qdrant 還原（若有）
# ──────────────────────────────────────────────────────
if [ -n "$QD_TAR" ] && [ -f "$QD_TAR" ]; then
    echo "[4/4] Qdrant restore..."

    # 停 qdrant container（避免寫入衝突）
    docker compose -f "$COMPOSE_FILE" stop qdrant > /dev/null

    QDRANT_VOL="tradingagents_qdrant_data_prod"
    # 清空舊資料 + 解壓還原
    docker run --rm \
        -v "${QDRANT_VOL}:/qdrant" \
        -v "${TMP_DIR}:/backup:ro" \
        alpine:3.20 \
        sh -c "rm -rf /qdrant/* /qdrant/.[!.]* 2>/dev/null; tar xzf /backup/$(basename "$QD_TAR") -C /qdrant"

    # 重啟 qdrant
    docker compose -f "$COMPOSE_FILE" start qdrant > /dev/null
    echo "    ✓ Qdrant 已還原並重啟"
else
    echo "[4/4] tarball 無 qdrant snapshot，跳過"
fi

echo ""
echo "✅ Restore complete"
echo "下一步建議："
echo "  1. uv run python data-pipeline/scripts/verify_data.py"
echo "  2. bash scripts/verify_audit_chain.py"
echo "  3. 用 admin 登入確認"
