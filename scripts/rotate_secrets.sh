#!/usr/bin/env bash
# scripts/rotate_secrets.sh — JWT SECRET_KEY 雙 key 輪替（PLAN 第 19.4 章）。
#
# 流程：
#   1. 第一階段（rotate）：
#      - 產生 SECRET_KEY_NEW
#      - .env：SECRET_KEY_PREVIOUS = 舊 SECRET_KEY
#              SECRET_KEY          = 新 KEY
#      - 重啟 backend / workers（用兩把 key decode 都通過 = 平滑切換）
#   2. 第二階段（--finalize，> 7 天後跑）：
#      - 移除 SECRET_KEY_PREVIOUS
#      - 重啟 → 只剩新 key
#
# Usage:
#   ./scripts/rotate_secrets.sh           # 觸發第一階段
#   ./scripts/rotate_secrets.sh --finalize  # 7 天後 finalize
#
# Notes:
#   - .env 一定要有備份（會 cp .env .env.bak.<ts>）
#   - rollback：cp .env.bak.<ts> .env

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
MODE="${1:-rotate}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE 不存在"
  exit 1
fi

# 自動備份
TS=$(date +%Y%m%d_%H%M%S)
BAK="${ENV_FILE}.bak.${TS}"
cp "$ENV_FILE" "$BAK"
echo "✓ 備份 .env → $BAK"

# 取舊 SECRET_KEY
OLD_KEY=$(grep -E '^SECRET_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2- || echo "")
if [ -z "$OLD_KEY" ]; then
  echo "ERROR: $ENV_FILE 沒有 SECRET_KEY 行"
  exit 1
fi

case "$MODE" in
  rotate)
    # 產生新 KEY（base64 編碼的 32 byte 隨機）
    NEW_KEY=$(python3 -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('='))")

    # 把 SECRET_KEY_PREVIOUS 設為舊 KEY；SECRET_KEY 設為新 KEY
    # 若已有 SECRET_KEY_PREVIOUS 行，先移除
    grep -v -E '^SECRET_KEY_PREVIOUS=' "$ENV_FILE" > "${ENV_FILE}.tmp"
    mv "${ENV_FILE}.tmp" "$ENV_FILE"

    # 替換 SECRET_KEY 行 + append SECRET_KEY_PREVIOUS
    if grep -qE '^SECRET_KEY=' "$ENV_FILE"; then
      # 用 awk 替換而非 sed -i（跨 shell 一致）
      awk -v new="$NEW_KEY" '
        /^SECRET_KEY=/ { print "SECRET_KEY=" new; next }
        { print }
      ' "$ENV_FILE" > "${ENV_FILE}.tmp"
      mv "${ENV_FILE}.tmp" "$ENV_FILE"
    else
      echo "SECRET_KEY=$NEW_KEY" >> "$ENV_FILE"
    fi
    echo "SECRET_KEY_PREVIOUS=$OLD_KEY" >> "$ENV_FILE"

    echo "✓ SECRET_KEY 輪替完成。"
    echo "  - 新 SECRET_KEY 已寫入"
    echo "  - 舊 KEY 暫存 SECRET_KEY_PREVIOUS（7 天後 ./scripts/rotate_secrets.sh --finalize）"
    echo "  下一步：重啟 backend + workers（make backend-restart）"
    ;;

  --finalize|finalize)
    # 移除 SECRET_KEY_PREVIOUS
    grep -v -E '^SECRET_KEY_PREVIOUS=' "$ENV_FILE" > "${ENV_FILE}.tmp"
    mv "${ENV_FILE}.tmp" "$ENV_FILE"
    echo "✓ SECRET_KEY_PREVIOUS 已移除（finalize）。"
    echo "  下一步：重啟 backend + workers"
    ;;

  *)
    echo "Usage: $0 [rotate|--finalize]"
    exit 1
    ;;
esac
