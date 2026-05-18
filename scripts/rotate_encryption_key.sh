#!/usr/bin/env bash
# scripts/rotate_encryption_key.sh — Fernet DATA_ENCRYPTION_KEY 輪替（PLAN 第 19.4 章）。
#
# 流程：
#   1. 產生新 DATA_ENCRYPTION_KEY
#   2. 跑 Python 腳本：
#      - 用舊 key 解密 notification_settings.line_token_encrypted / telegram_bot_token_encrypted
#      - 用新 key 重新加密
#      - 全部成功 → 用一次 transaction 寫回 DB
#      - 任一失敗 → rollback，.env 不變
#   3. 更新 .env
#   4. 重啟 backend + workers
#
# rollback：cp .env.bak.<ts> .env
#
# Usage:
#   ./scripts/rotate_encryption_key.sh

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE 不存在"; exit 1; }

OLD_KEY=$(grep -E '^DATA_ENCRYPTION_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2-)
[ -n "$OLD_KEY" ] || { echo "ERROR: .env 缺 DATA_ENCRYPTION_KEY"; exit 1; }

TS=$(date +%Y%m%d_%H%M%S)
BAK="${ENV_FILE}.bak.${TS}"
cp "$ENV_FILE" "$BAK"
echo "✓ 備份 .env → $BAK"

NEW_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

cd backend
# 用 uv 跑 Python 腳本，確保使用相同的 cryptography 版本
uv run python - <<PYEOF
"""rotate_encryption_key — 解密用舊 key、加密用新 key，atomic 寫回。"""
import os, sys
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet, InvalidToken
import base64

OLD_KEY = "${OLD_KEY}"
NEW_KEY = "${NEW_KEY}"

def _derive_fernet(secret: str) -> Fernet:
    s = secret.strip()
    pad = (4 - len(s) % 4) % 4
    raw = base64.urlsafe_b64decode((s + ('=' * pad)).encode('ascii'))
    if len(raw) < 32:
        raise SystemExit("DATA_ENCRYPTION_KEY 解碼後須 ≥ 32 bytes")
    return Fernet(base64.urlsafe_b64encode(raw[:32]))

old_f = _derive_fernet(OLD_KEY)
new_f = _derive_fernet(NEW_KEY)

# 連 DB（用 ta_migration 帳號改加密欄位 — service_rw 也行，但要小心 trigger）
from app.core.config import settings
# 從 settings 拿 sync DSN
import urllib.parse
pwd = urllib.parse.quote_plus(settings.TA_SERVICE_RW_PASSWORD.get_secret_value())
dsn = f"postgresql+psycopg2://ta_service_rw:{pwd}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
engine = create_engine(dsn, future=True)

UPDATES = []  # (table, pk_id, field, new_value)
with Session(engine) as s:
    rows = list(s.execute(
        "SELECT id, line_token_encrypted, telegram_bot_token_encrypted "
        "FROM notification_settings"
    ).all())
    for r in rows:
        rid, line_enc, tg_enc = r
        try:
            if line_enc:
                plain = old_f.decrypt(line_enc.encode()).decode('utf-8')
                UPDATES.append(("line_token_encrypted", rid, new_f.encrypt(plain.encode()).decode('ascii')))
            if tg_enc:
                plain = old_f.decrypt(tg_enc.encode()).decode('utf-8')
                UPDATES.append(("telegram_bot_token_encrypted", rid, new_f.encrypt(plain.encode()).decode('ascii')))
        except InvalidToken as e:
            raise SystemExit(f"解密失敗 user_id={rid} field=?: {e}") from e

print(f"→ 準備寫回 {len(UPDATES)} 個加密欄位...")
with Session(engine) as s:
    for field, rid, val in UPDATES:
        s.execute(
            f"UPDATE notification_settings SET {field} = :v WHERE id = :id",
            {"v": val, "id": rid},
        )
    s.commit()
print("✓ rotate_encryption_key 完成（DB 已更新）。")
PYEOF

cd ..

# 更新 .env
awk -v new="$NEW_KEY" '
  /^DATA_ENCRYPTION_KEY=/ { print "DATA_ENCRYPTION_KEY=" new; next }
  { print }
' "$ENV_FILE" > "${ENV_FILE}.tmp"
mv "${ENV_FILE}.tmp" "$ENV_FILE"

echo "✓ .env 已更新新 DATA_ENCRYPTION_KEY"
echo "  → 重啟 backend + workers（必須）"
echo "  → 如有問題：cp $BAK $ENV_FILE && 用舊 key 重啟"
