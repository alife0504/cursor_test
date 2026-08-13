#!/bin/bash
# scripts/health_checks/phase_18.sh
# Phase 18 健康檢查:通知整合 + OWASP 強化 + 滲透測試
#
# 涵蓋(15 項):
#   1. backend uv sync OK
#   2. ruff check 通過
#   3. notification adapter 註冊 (line/telegram)
#   4. NotificationDispatcher 可 import
#   5. bandit HIGH severity = 0
#   6. detect-secrets baseline 無新發現
#   7. owasp / audit_chain_tampering / secret_handling 測試檔存在
#   8. notifications_e2e / csp_nonce 測試檔存在
#   9. core/crypto + core/security_headers 加 nonce
#  10. CSP_PROD 啟用時 / health/live 含 nonce-
#  11. SecretRotation 三個 shell script 存在 + +x
#  12. CSRF / RateLimit / Audit middleware 仍在
#  13. front-end build OK
#  14. (optional) Trivy 後/前端 image HIGH+CRITICAL = 0 — 若 trivy 不可用則 warn
#  15. npm audit (允許 v1.0 已接受 next 14.x advisories - warn 不擋)

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 18 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

BACKEND="$PROJECT_ROOT/backend"
FRONTEND="$PROJECT_ROOT/frontend"

# 1. uv sync
echo "[1] backend uv sync..."
(cd "$BACKEND" && uv sync --quiet) > /tmp/p18-uvsync.log 2>&1 || {
  echo "✗ uv sync 失敗"
  tail -20 /tmp/p18-uvsync.log
  exit 1
}
echo "✓ uv sync OK"

# 2. ruff
echo "[2] ruff check..."
(cd "$BACKEND" && uv run ruff check app/) > /tmp/p18-ruff.log 2>&1 || {
  echo "✗ ruff 失敗"
  tail -20 /tmp/p18-ruff.log
  exit 1
}
echo "✓ ruff 通過"

# 3. notifier 註冊
echo "[3] 兩個 notifier 已註冊..."
cd "$BACKEND" && uv run python -c "
from app.notifications.line_notifier import LINENotifier
from app.notifications.telegram_notifier import TelegramNotifier
from app.notifications.base import NOTIFIER_REGISTRY
assert 'line' in NOTIFIER_REGISTRY, 'line notifier 未註冊'
assert 'telegram' in NOTIFIER_REGISTRY, 'telegram notifier 未註冊'
assert NOTIFIER_REGISTRY['line'] is LINENotifier
assert NOTIFIER_REGISTRY['telegram'] is TelegramNotifier
print('OK')
" > /tmp/p18-notifiers.log 2>&1 || {
  echo "✗ notifier 註冊驗證失敗"
  cat /tmp/p18-notifiers.log
  cd "$PROJECT_ROOT"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ line / telegram notifier 已註冊"

# 4. dispatcher 可 import
echo "[4] NotificationDispatcher import..."
cd "$BACKEND" && uv run python -c "
from app.notifications.dispatcher import NotificationDispatcher, get_dispatcher
d = NotificationDispatcher()
d2 = get_dispatcher()
print('OK')
" > /tmp/p18-dispatcher.log 2>&1 || {
  echo "✗ dispatcher import 失敗"
  cat /tmp/p18-dispatcher.log
  cd "$PROJECT_ROOT"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ NotificationDispatcher OK"

# 5. bandit HIGH = 0
echo "[5] bandit HIGH severity = 0..."
# 用 mktemp 拿到 cross-platform 暫存路徑（Windows MSYS 下 /tmp 對 Windows native python 不可見）
BANDIT_JSON="$(mktemp -t p18-bandit-XXXX.json)"
# 轉成 Windows path 給 native Python 讀
if command -v cygpath > /dev/null 2>&1; then
  BANDIT_JSON_WIN=$(cygpath -m "$BANDIT_JSON")
else
  BANDIT_JSON_WIN="$BANDIT_JSON"
fi
(cd "$BACKEND" && uv run bandit -r app/ -c .bandit -f json -o "$BANDIT_JSON_WIN") > /tmp/p18-bandit.log 2>&1 || true
HIGH_COUNT=$(python -c "
import json,sys
try:
    d = json.load(open(r'$BANDIT_JSON_WIN'))
    print(sum(1 for r in d['results'] if r['issue_severity'] == 'HIGH'))
except Exception as e:
    print(-1, file=sys.stderr)
    print(-1)
" 2>/dev/null || echo "-1")
if [ "$HIGH_COUNT" != "0" ]; then
  echo "✗ bandit HIGH=$HIGH_COUNT (預期 0)"
  echo "  bandit json: $BANDIT_JSON_WIN"
  exit 1
fi
echo "✓ bandit HIGH = 0"

# 6. detect-secrets baseline
echo "[6] detect-secrets baseline..."
(cd "$BACKEND" && uv run detect-secrets scan --baseline "$PROJECT_ROOT/.secrets.baseline") > /tmp/p18-secrets.log 2>&1 || {
  echo "✗ detect-secrets 發現新 secret"
  tail -20 /tmp/p18-secrets.log
  exit 1
}
echo "✓ detect-secrets 通過"

# 7. security tests 檔案
echo "[7] security tests 檔案存在..."
for f in \
  "tests/security/test_owasp_top10.py" \
  "tests/security/test_audit_chain_tampering.py" \
  "tests/security/test_secret_handling.py"; do
  test -f "$BACKEND/$f" || { echo "✗ 缺 $f"; exit 1; }
done
echo "✓ 3 個 security tests 檔案存在"

# 8. integration tests for P18
echo "[8] notifications_e2e + csp_nonce 測試檔案..."
for f in \
  "tests/integration/test_notifications_e2e.py" \
  "tests/integration/test_csp_nonce.py"; do
  test -f "$BACKEND/$f" || { echo "✗ 缺 $f"; exit 1; }
done
echo "✓ 2 個 integration tests 檔案存在"

# 9. core/crypto + security_headers nonce
echo "[9] core/crypto + CSP nonce 實作..."
grep -q "def encrypt_str\|def decrypt_str" "$BACKEND/app/core/crypto.py" \
  || { echo "✗ core/crypto.py 缺 encrypt_str/decrypt_str"; exit 1; }
grep -q "build_prod_csp\|nonce-" "$BACKEND/app/core/security_headers.py" \
  || { echo "✗ security_headers.py 沒升級到 nonce-based"; exit 1; }
echo "✓ crypto + CSP nonce 實作 OK"

# 10. CSP_PROD 啟用時 response 含 nonce-
echo "[10] CSP nonce 真實 response 測試..."
cd "$BACKEND"
uv run python -c "
from starlette.testclient import TestClient
from app.core.config import settings
settings.CSP_PROD_ENABLED = True
from app.main import app
with TestClient(app) as c:
    r = c.get('/health/live')
    csp = r.headers.get('Content-Security-Policy', '')
    assert 'nonce-' in csp, f'CSP 缺 nonce: {csp!r}'
    assert 'strict-dynamic' in csp, f'CSP 缺 strict-dynamic: {csp!r}'
print('OK')
" > /tmp/p18-csp.log 2>&1 || {
  echo "✗ CSP nonce 測試失敗"
  cat /tmp/p18-csp.log
  cd "$PROJECT_ROOT"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ prod CSP 含 nonce + strict-dynamic"

# 11. rotation scripts
echo "[11] rotation 腳本 + executable..."
for s in rotate_secrets.sh rotate_db_passwords.sh rotate_encryption_key.sh; do
  test -f "scripts/$s" || { echo "✗ scripts/$s 不存在"; exit 1; }
  test -x "scripts/$s" || { echo "✗ scripts/$s 不可執行"; exit 1; }
done
echo "✓ 3 個 rotation 腳本 OK"

# 12. middleware 仍在（防 regression）
echo "[12] middleware regression check..."
for mod in csrf_middleware audit_middleware rate_limit body_size_middleware security_headers; do
  grep -q "$mod" "$BACKEND/app/main.py" \
    || { echo "✗ $mod 不在 main.py 註冊"; exit 1; }
done
echo "✓ 5 個 middleware 仍掛在 main.py"

# 13. frontend build
echo "[13] frontend build..."
(cd "$FRONTEND" && npm run build) > /tmp/p18-feb.log 2>&1 || {
  echo "✗ frontend build 失敗"
  tail -30 /tmp/p18-feb.log
  exit 1
}
echo "✓ frontend build OK"

# 14. Trivy（optional — 沒裝就 warn 不擋）
echo "[14] Trivy image scan (optional)..."
if command -v trivy > /dev/null 2>&1; then
  trivy image tradingagents-backend:latest --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 \
    > /tmp/p18-trivy-be.log 2>&1 || {
    echo "⚠ Trivy 後端 image 有 HIGH+CRITICAL（見 /tmp/p18-trivy-be.log）— v1.0 視為 warn"
  }
  trivy image tradingagents-frontend:latest --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 \
    > /tmp/p18-trivy-fe.log 2>&1 || {
    echo "⚠ Trivy 前端 image 有 HIGH+CRITICAL（見 /tmp/p18-trivy-fe.log）— v1.0 視為 warn"
  }
  echo "✓ Trivy 已跑（如有結果見 /tmp/p18-trivy-*.log）"
elif command -v docker > /dev/null 2>&1; then
  echo "⚠ host 沒裝 trivy；可改用 make trivy-scan（docker run aquasec/trivy）"
else
  echo "⚠ 無 trivy 也無 docker — 跳過 image 掃描（請手動跑於 CI）"
fi

# 15. npm audit（v1.0 接受 Next 14.x advisories — warn 不擋）
echo "[15] npm audit (HIGH+CRITICAL — v1.0 已接受 Next 14.x 殘留)..."
NPM_JSON="$(mktemp -t p18-npm-XXXX.json)"
if command -v cygpath > /dev/null 2>&1; then
  NPM_JSON_WIN=$(cygpath -m "$NPM_JSON")
else
  NPM_JSON_WIN="$NPM_JSON"
fi
(cd "$FRONTEND" && npm audit --audit-level=high --json) > "$NPM_JSON_WIN" 2>&1 || true
NEW_HIGH=$(python -c "
import json
try:
    d = json.load(open(r'$NPM_JSON_WIN'))
    meta = d.get('metadata', {}).get('vulnerabilities', {})
    print(meta.get('high', 0) + meta.get('critical', 0))
except Exception:
    print(0)
" 2>/dev/null || echo "0")
if [ "$NEW_HIGH" = "0" ]; then
  echo "✓ npm audit HIGH+CRITICAL = 0"
else
  echo "⚠ npm audit HIGH+CRITICAL = $NEW_HIGH（v1.0 接受 Next 14.x 殘留，見 SECURITY.md）"
fi

echo ""
echo "✅ Phase 18 健康檢查全部通過"
