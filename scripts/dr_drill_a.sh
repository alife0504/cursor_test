#!/bin/bash
# scripts/dr_drill_a.sh
#
# Phase 19 — DR 演練情境 A：TimescaleDB 損毀。
#
# 流程（依 PLAN 第 32.2 章）：
#   1. backup → 取得最新 .gpg
#   2. 「損毀」：stop timescaledb + 砍 volume
#   3. 重建：up timescaledb（會跑 init.sh）
#   4. restore：把備份還原回去（含 RESTORE_AUTO_CONFIRM）
#   5. verify_data.py + verify_audit_chain.py
#   6. 紀錄 RTO 到 docs/dr_drills/YYYY-MM-DD.md
#
# ⚠️ 警告：這會清空 prod DB volume！只在演練窗口執行。
#
# 用法：
#   bash scripts/dr_drill_a.sh
#   DR_DRILL_AUTO_CONFIRM=1 bash scripts/dr_drill_a.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_ROOT}/docker/backups}"
DRILL_DIR="${PROJECT_ROOT}/docs/dr_drills"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
START_TS=$(date +%s)

mkdir -p "$DRILL_DIR"
DRILL_REPORT="$DRILL_DIR/scenario_a_${TIMESTAMP}.md"

echo "═══════════════════════════════════════"
echo "DR 演練 — 情境 A：DB 損毀"
echo "  時間：$(date -Iseconds)"
echo "  報告：$DRILL_REPORT"
echo "═══════════════════════════════════════"

# ──────────────────────────────────────────────────────
# 0. 確認
# ──────────────────────────────────────────────────────
if [ -z "${DR_DRILL_AUTO_CONFIRM:-}" ]; then
    echo ""
    echo "⚠️  此演練會：DROP DATABASE → 砍 volume → 重建 → 還原"
    echo "    生產資料會丟失，僅還原備份內容。"
    echo ""
    read -r -p "確認進入演練？(yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "已取消"
        exit 1
    fi
fi

# ──────────────────────────────────────────────────────
# 1. Backup
# ──────────────────────────────────────────────────────
echo "[1/6] 跑 backup..."
STEP1_START=$(date +%s)
bash "${PROJECT_ROOT}/scripts/backup.sh"
STEP1_DUR=$(($(date +%s) - STEP1_START))

LATEST_BACKUP="$(ls -t "$BACKUP_DIR"/full_*.tar.gz.gpg 2>/dev/null | head -1)"
if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ backup.sh 沒產生檔案" >&2
    exit 1
fi
echo "    最新備份：$LATEST_BACKUP"

# ──────────────────────────────────────────────────────
# 2. 「損毀」
# ──────────────────────────────────────────────────────
echo "[2/6] 模擬 DB 損毀..."
STEP2_START=$(date +%s)

# 先停 backend / celery 避免抓住連線
docker compose -f "$COMPOSE_FILE" stop backend celery_worker celery_beat > /dev/null 2>&1 || true
docker compose -f "$COMPOSE_FILE" stop timescaledb
docker volume rm tradingagents_timescaledb_data_prod
STEP2_DUR=$(($(date +%s) - STEP2_START))
echo "    ✓ volume 已砍"

# ──────────────────────────────────────────────────────
# 3. 重建
# ──────────────────────────────────────────────────────
echo "[3/6] 重建 timescaledb（會跑 init.sh）..."
STEP3_START=$(date +%s)
docker compose -f "$COMPOSE_FILE" up -d timescaledb

# 等 healthy
ATTEMPT=0
until docker compose -f "$COMPOSE_FILE" ps timescaledb --format json 2>/dev/null | grep -q '"Health":"healthy"'; do
    ATTEMPT=$((ATTEMPT + 1))
    if [ "$ATTEMPT" -gt 60 ]; then
        echo "❌ timescaledb 2 分鐘內未 healthy" >&2
        exit 1
    fi
    sleep 2
done
STEP3_DUR=$(($(date +%s) - STEP3_START))
echo "    ✓ healthy（耗時 ${STEP3_DUR}s）"

# ──────────────────────────────────────────────────────
# 4. Restore
# ──────────────────────────────────────────────────────
echo "[4/6] 還原最新備份..."
STEP4_START=$(date +%s)
RESTORE_AUTO_CONFIRM=1 bash "${PROJECT_ROOT}/scripts/restore.sh" "$LATEST_BACKUP"
STEP4_DUR=$(($(date +%s) - STEP4_START))

# ──────────────────────────────────────────────────────
# 5. Verify + 重啟 backend
# ──────────────────────────────────────────────────────
echo "[5/6] 重啟 backend + verify..."
STEP5_START=$(date +%s)
docker compose -f "$COMPOSE_FILE" up -d backend celery_worker celery_beat > /dev/null

sleep 15

# verify_data（容錯：可能 backup 內沒料）
cd "$PROJECT_ROOT"
uv --project backend run python data-pipeline/scripts/verify_data.py \
    || echo "    (verify_data.py 部分失敗，繼續)"

uv --project backend run python scripts/verify_audit_chain.py \
    || echo "    (verify_audit_chain.py 失敗，請調查)"

STEP5_DUR=$(($(date +%s) - STEP5_START))

# ──────────────────────────────────────────────────────
# 6. 報告
# ──────────────────────────────────────────────────────
TOTAL_DUR=$(($(date +%s) - START_TS))
RTO_MIN=$((TOTAL_DUR / 60))

cat > "$DRILL_REPORT" <<EOF
# DR 演練報告 — 情境 A（DB 損毀）

- 演練時間：$(date -Iseconds)
- 演練人員：$(whoami)
- 還原備份：\`$LATEST_BACKUP\`

## 各步驟耗時

| 步驟 | 耗時（秒） |
|------|----------:|
| 1. backup | ${STEP1_DUR} |
| 2. 模擬損毀（stop + 砍 volume） | ${STEP2_DUR} |
| 3. 重建 timescaledb（init.sh） | ${STEP3_DUR} |
| 4. restore | ${STEP4_DUR} |
| 5. backend 重啟 + verify | ${STEP5_DUR} |
| **總計** | **${TOTAL_DUR}** |

## RTO

實際 RTO：${RTO_MIN} 分鐘
SLO 目標：60 分鐘
結果：$([ "$RTO_MIN" -le 60 ] && echo "✅ 達標" || echo "❌ 未達標，需檢討")

## 後續行動

- 確認 \`docs/runbooks/disaster_recovery.md\` 內容與實際流程一致
- 如有耗時瓶頸，調整或文件化
EOF

echo ""
echo "═══════════════════════════════════════"
echo "✅ DR 演練 A 完成"
echo "   總耗時 ${RTO_MIN} 分鐘（RTO 目標 60 分）"
echo "   報告：$DRILL_REPORT"
echo "═══════════════════════════════════════"
