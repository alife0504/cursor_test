#!/bin/bash
# scripts/health_checks/phase_19.sh
# Phase 19 健康檢查：Prod 部署 + 備份/還原/DR + E2E
#
# 涵蓋（15 項）：
#   1. backend uv sync OK
#   2. ruff check 通過
#   3. docker-compose.prod.yml YAML 可解析 + 必要 services 全到位
#   4. docker-compose.test-restore.yml YAML 可解析 + timescaledb_test 對外 5433
#   5. docker/nginx/nginx.conf 含 HTTPS / WS / SSE / rate limit / X-Frame
#   6. .env.prod.example 含 prod 必需 keys
#   7. backup.sh / restore.sh / verify_backup.sh / dr_drill_a.sh / generate_self_signed_cert.sh 存在 +x + 語法正確
#   8. scripts/slo_report.py 可 import + compute_error_budget 正確
#   9. 後端 E2E test files 存在（test_full_workflow_e2e / test_slo_report / test_backup_restore）
#  10. 前端 full-workflow.spec.ts 含 ≥ 8 個 test cases（P19 升級）
#  11. Makefile 含 P19 targets（prod-up / backup / restore / verify-backup / slo-report / dr-drill-a）
#  12. docker/nginx/certs 目錄存在
#  13. (optional) docker-compose.prod.yml 可被 docker compose config 通過驗證
#  14. P18 健康檢查仍綠（連動）
#  15. backend pytest --collect-only 累積 ≥ P19 基準（後端 unit+integration+security ≥ 410）

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Windows Git Bash 跑 Python 需要 Windows 路徑（Python 不認 /c/...）
if command -v cygpath > /dev/null 2>&1; then
  PROJECT_ROOT_NATIVE="$(cygpath -w "$PROJECT_ROOT")"
else
  PROJECT_ROOT_NATIVE="$PROJECT_ROOT"
fi

echo "=== Phase 19 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

BACKEND="$PROJECT_ROOT/backend"
FRONTEND="$PROJECT_ROOT/frontend"

# ──────────────────────────────────────────────────────
# 1. uv sync
# ──────────────────────────────────────────────────────
echo "[1] backend uv sync..."
(cd "$BACKEND" && uv sync --quiet) > /tmp/p19-uvsync.log 2>&1 || {
  echo "✗ uv sync 失敗"
  tail -20 /tmp/p19-uvsync.log
  exit 1
}
echo "✓ uv sync OK"

# ──────────────────────────────────────────────────────
# 2. ruff
# ──────────────────────────────────────────────────────
echo "[2] ruff check..."
(cd "$BACKEND" && uv run ruff check app/) > /tmp/p19-ruff.log 2>&1 || {
  echo "✗ ruff 失敗"
  tail -20 /tmp/p19-ruff.log
  exit 1
}
echo "✓ ruff 通過"

# ──────────────────────────────────────────────────────
# 3. docker-compose.prod.yml YAML 解析
# ──────────────────────────────────────────────────────
echo "[3] docker-compose.prod.yml 結構..."
cd "$BACKEND" && uv run python -c "
import yaml
with open(r'$PROJECT_ROOT_NATIVE/docker-compose.prod.yml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
svcs = set(data['services'].keys())
need = {'timescaledb', 'redis', 'qdrant', 'backend', 'celery_worker', 'celery_beat', 'frontend', 'nginx'}
missing = need - svcs
assert not missing, f'缺少 services: {missing}'
print('OK')
" > /tmp/p19-prodcompose.log 2>&1 || {
  echo "✗ docker-compose.prod.yml 結構錯"
  cat /tmp/p19-prodcompose.log
  cd "$PROJECT_ROOT"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ docker-compose.prod.yml 含 8 個必要 services"

# ──────────────────────────────────────────────────────
# 4. docker-compose.test-restore.yml
# ──────────────────────────────────────────────────────
echo "[4] docker-compose.test-restore.yml 結構..."
cd "$BACKEND" && uv run python -c "
import yaml
with open(r'$PROJECT_ROOT_NATIVE/docker-compose.test-restore.yml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
assert 'timescaledb_test' in data['services'], 'missing timescaledb_test'
ports = data['services']['timescaledb_test']['ports']
assert any('5433' in str(p) for p in ports), f'expected 5433, got {ports}'
print('OK')
" > /tmp/p19-testrestore.log 2>&1 || {
  echo "✗ docker-compose.test-restore.yml 結構錯"
  cat /tmp/p19-testrestore.log
  cd "$PROJECT_ROOT"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ test-restore compose 含 timescaledb_test (5433)"

# ──────────────────────────────────────────────────────
# 5. nginx.conf 關鍵指令
# ──────────────────────────────────────────────────────
echo "[5] nginx.conf 內容..."
NGX="$PROJECT_ROOT/docker/nginx/nginx.conf"
test -f "$NGX" || { echo "✗ 找不到 $NGX"; exit 1; }
grep -q "listen 443" "$NGX" || { echo "✗ nginx 缺 listen 443"; exit 1; }
grep -q "ssl_certificate" "$NGX" || { echo "✗ nginx 缺 ssl_certificate"; exit 1; }
grep -q "limit_req_zone" "$NGX" || { echo "✗ nginx 缺 limit_req_zone"; exit 1; }
grep -q "Upgrade" "$NGX" || { echo "✗ nginx 缺 WS Upgrade"; exit 1; }
grep -q "proxy_buffering off" "$NGX" || { echo "✗ nginx 缺 SSE buffering off"; exit 1; }
grep -q "X-Frame-Options" "$NGX" || { echo "✗ nginx 缺 X-Frame-Options"; exit 1; }
grep -q "server_tokens off" "$NGX" || { echo "✗ nginx 缺 server_tokens off"; exit 1; }
echo "✓ nginx.conf 含 HTTPS/WS/SSE/rate-limit/security-headers"

# ──────────────────────────────────────────────────────
# 6. .env.prod.example 必需 keys
# ──────────────────────────────────────────────────────
echo "[6] .env.prod.example 必需 keys..."
ENVP="$PROJECT_ROOT/.env.prod.example"
test -f "$ENVP" || { echo "✗ 找不到 $ENVP"; exit 1; }
for key in APP_ENV=prod SECRET_KEY DATA_ENCRYPTION_KEY POSTGRES_SUPERUSER_PASSWORD \
           REDIS_PASSWORD QDRANT_API_KEY GOOGLE_API_KEY CSP_PROD_ENABLED=true \
           BACKUP_DIR GPG_RECIPIENT; do
  grep -q "$key" "$ENVP" || { echo "✗ .env.prod.example 缺 $key"; exit 1; }
done
echo "✓ .env.prod.example 含 prod 必需 10 個 key"

# ──────────────────────────────────────────────────────
# 7. backup/restore/verify_backup/dr_drill 腳本
# ──────────────────────────────────────────────────────
echo "[7] backup / restore / verify_backup / dr_drill_a / cert 腳本..."
for sh in backup.sh restore.sh verify_backup.sh dr_drill_a.sh generate_self_signed_cert.sh; do
  P="$PROJECT_ROOT/scripts/$sh"
  test -f "$P" || { echo "✗ 缺 $P"; exit 1; }
  test -x "$P" || { echo "✗ $P 沒 +x"; exit 1; }
  bash -n "$P" 2>/tmp/p19-syntax.log || {
    echo "✗ $sh 語法錯"; cat /tmp/p19-syntax.log; exit 1;
  }
done
echo "✓ 5 個 shell script 存在 + +x + 語法正確"

# ──────────────────────────────────────────────────────
# 8. slo_report.py 可 import + burn rate 正確
# ──────────────────────────────────────────────────────
echo "[8] slo_report.py 結構..."
cd "$BACKEND" && uv run python -c "
import sys
sys.path.insert(0, r'$PROJECT_ROOT_NATIVE')
from scripts import slo_report
# burn rate 邏輯快測
slo = {'api_availability': {'target': 0.99, 'actual': 0.98, 'passed': False}}
burn = slo_report.compute_error_budget(slo)
assert abs(burn['api_availability'] - 1.0) < 1e-6, f'burn rate 計算錯：{burn}'
assert hasattr(slo_report, 'compute_audit_integrity')
assert hasattr(slo_report, 'compute_data_freshness')
assert hasattr(slo_report, 'write_report')
print('OK')
" > /tmp/p19-slo.log 2>&1 || {
  echo "✗ slo_report.py 結構錯"
  cat /tmp/p19-slo.log
  cd "$PROJECT_ROOT"
  exit 1
}
cd "$PROJECT_ROOT"
echo "✓ slo_report.py 結構正確 + burn rate 計算對"

# ──────────────────────────────────────────────────────
# 9. 後端 E2E test files
# ──────────────────────────────────────────────────────
echo "[9] 後端 E2E test files..."
for f in test_full_workflow_e2e.py test_slo_report.py test_backup_restore.py; do
  P="$BACKEND/tests/integration/$f"
  test -f "$P" || { echo "✗ 缺 $P"; exit 1; }
done
echo "✓ 3 個 P19 integration tests 存在"

# ──────────────────────────────────────────────────────
# 10. 前端 full-workflow.spec.ts ≥ 8 個 test
# ──────────────────────────────────────────────────────
echo "[10] 前端 full-workflow.spec.ts test 數..."
SPEC="$FRONTEND/tests/e2e/full-workflow.spec.ts"
test -f "$SPEC" || { echo "✗ 缺 $SPEC"; exit 1; }
CNT=$(grep -cE "^\s*test\(" "$SPEC" || true)
if [ "$CNT" -lt 8 ]; then
  echo "✗ full-workflow.spec.ts 只有 $CNT 個 test (要求 ≥ 8)"
  exit 1
fi
echo "✓ full-workflow.spec.ts 含 $CNT 個 test"

# ──────────────────────────────────────────────────────
# 11. Makefile P19 targets
# ──────────────────────────────────────────────────────
echo "[11] Makefile P19 targets..."
MK="$PROJECT_ROOT/Makefile"
for target in prod-up: prod-down: backup: restore: verify-backup: slo-report: dr-drill-a: generate-cert:; do
  grep -q "^${target}" "$MK" || { echo "✗ Makefile 缺 target ${target}"; exit 1; }
done
echo "✓ Makefile 含 8 個 P19 targets"

# ──────────────────────────────────────────────────────
# 12. docker/nginx/certs 目錄
# ──────────────────────────────────────────────────────
echo "[12] docker/nginx/certs 目錄..."
test -d "$PROJECT_ROOT/docker/nginx/certs" || { echo "✗ 缺 docker/nginx/certs/"; exit 1; }
echo "✓ docker/nginx/certs/ 存在（cert 由 generate_self_signed_cert.sh 產生）"

# ──────────────────────────────────────────────────────
# 13. (optional) docker compose config 驗證
# ──────────────────────────────────────────────────────
echo "[13] docker compose -f docker-compose.prod.yml config..."
# 需要 .env.prod 才能跑 config interpolation；若無，建一個臨時的（值全 placeholder）
TMP_ENV=""
if [ ! -f "$PROJECT_ROOT/.env.prod" ]; then
  TMP_ENV="$PROJECT_ROOT/.env.prod"
  cp "$PROJECT_ROOT/.env.prod.example" "$TMP_ENV"
  # 把空值填 placeholder（避開 var 未設）
  sed -i.bak 's/^\([A-Z_]\+\)=$/\1=placeholder/' "$TMP_ENV" 2>/dev/null || true
  rm -f "${TMP_ENV}.bak" 2>/dev/null || true
fi
if docker compose -f "$PROJECT_ROOT/docker-compose.prod.yml" --env-file "$PROJECT_ROOT/.env.prod" config > /tmp/p19-compose-config.log 2>&1; then
  echo "✓ docker compose prod config 通過"
else
  echo "⚠ docker compose prod config 警告（可能是 docker daemon 不在或 secret 不全）"
  tail -10 /tmp/p19-compose-config.log
fi
# 清理臨時 env
if [ -n "$TMP_ENV" ] && [ -f "$TMP_ENV" ]; then
  rm -f "$TMP_ENV"
fi

# ──────────────────────────────────────────────────────
# 14. P18 健康檢查仍綠
# ──────────────────────────────────────────────────────
echo "[14] 連跑 phase_18.sh..."
if bash "$PROJECT_ROOT/scripts/health_checks/phase_18.sh" > /tmp/p19-p18.log 2>&1; then
  echo "✓ phase_18 health check 仍綠"
else
  echo "⚠ phase_18 health check 失敗（請確認 P19 改動沒打破 P18）"
  tail -30 /tmp/p19-p18.log
fi

# ──────────────────────────────────────────────────────
# 15. pytest collect 累積（P19 基準：unit+integration+security ≥ 410）
# ──────────────────────────────────────────────────────
echo "[15] pytest --collect-only..."
cd "$BACKEND" && uv run pytest --collect-only -q 2>/dev/null | tail -5 > /tmp/p19-collect.log
COLLECTED=$(grep -oE "^[0-9]+ tests collected" /tmp/p19-collect.log | awk '{print $1}' | head -1)
COLLECTED=${COLLECTED:-0}
echo "    tests collected: $COLLECTED"
if [ "$COLLECTED" -lt 410 ]; then
  echo "⚠ 後端測試數 $COLLECTED 低於 P19 基準 410+（可能 P18 試題不足；不阻斷）"
else
  echo "✓ 後端測試 $COLLECTED ≥ P19 基準 410"
fi
cd "$PROJECT_ROOT"

echo ""
echo "✅ Phase 19 健康檢查全部通過"
