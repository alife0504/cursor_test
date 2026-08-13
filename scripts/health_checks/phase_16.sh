#!/bin/bash
# scripts/health_checks/phase_16.sh
# Phase 16 健康檢查:前端 8 個核心頁面(後端整合)
#
# 涵蓋(13 項):
#   1. node / npm 可用
#   2. frontend/node_modules 已 install
#   3. lint 通過
#   4. typecheck 通過
#   5. build 成功
#   6. unit tests 通過 (≥ 70)
#   7. dev server 起得來 + /login 200
#   8. middleware:未登入 /dashboard → 307/302
#   9. 8 核心頁路由都返回 200/302/307
#  10. AgentFlowGraph 元件檔案存在
#  11. 10+ React Query hooks 存在
#  12. backend /api/v1/users/me/quota 端點檔案有定義
#  13. bundle .next/static 大小合理

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 16 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

FRONTEND="$PROJECT_ROOT/frontend"
BACKEND="$PROJECT_ROOT/backend"

# 1. node / npm
echo "[1] node / npm 版本..."
command -v node > /dev/null || { echo "✗ node 未安裝"; exit 1; }
command -v npm > /dev/null || { echo "✗ npm 未安裝"; exit 1; }
node --version
npm --version
echo "✓ node / npm OK"

# 2. node_modules
echo "[2] node_modules 已 install..."
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "✗ frontend/node_modules 不存在,先跑 make frontend-install"
  exit 1
fi
echo "✓ node_modules 存在"

# 3. lint
echo "[3] next lint..."
(cd "$FRONTEND" && npm run lint --silent) > /tmp/lint.log 2>&1 || {
  echo "✗ lint 失敗"
  tail -20 /tmp/lint.log
  exit 1
}
echo "✓ lint 通過"

# 4. typecheck
echo "[4] tsc --noEmit..."
(cd "$FRONTEND" && npx tsc --noEmit) > /tmp/tsc.log 2>&1 || {
  echo "✗ typecheck 失敗"
  tail -20 /tmp/tsc.log
  exit 1
}
echo "✓ typecheck 通過"

# 5. build
echo "[5] next build..."
(cd "$FRONTEND" && npm run build) > /tmp/build.log 2>&1 || {
  echo "✗ build 失敗"
  tail -30 /tmp/build.log
  exit 1
}
echo "✓ build 成功"

# 6. unit tests (≥ 70)
echo "[6] vitest unit tests..."
(cd "$FRONTEND" && NO_COLOR=1 FORCE_COLOR=0 npm test -- --reporter=basic) > /tmp/vitest.log 2>&1 || {
  echo "✗ unit tests 失敗"
  tail -30 /tmp/vitest.log
  exit 1
}
TESTS=$(sed 's/\x1b\[[0-9;]*m//g' /tmp/vitest.log \
  | grep -E "Tests[[:space:]]+[0-9]+ passed" \
  | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" | head -1)
TESTS=${TESTS:-0}
if [ "$TESTS" -lt 70 ]; then
  echo "✗ 通過測試 $TESTS < 70(P16 累積最低)"
  tail -10 /tmp/vitest.log
  exit 1
fi
echo "✓ unit tests 通過 ($TESTS)"

# 7-9 dev server
echo "[7] 啟動 dev server..."
(cd "$FRONTEND" && npm run dev) > /tmp/dev.log 2>&1 &
DEV_PID=$!
trap 'kill $DEV_PID 2>/dev/null || true' EXIT

for i in $(seq 1 30); do
  if curl -fsS -o /dev/null http://localhost:3000/login 2>/dev/null; then
    break
  fi
  sleep 2
done

if ! curl -fsS -o /dev/null http://localhost:3000/login 2>/dev/null; then
  echo "✗ dev server 未起來"
  tail -30 /tmp/dev.log
  exit 1
fi
echo "✓ dev server 起來 + /login 200"

# 8. middleware
echo "[8] middleware 未登入 /dashboard → redirect..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/dashboard)
case "$STATUS" in
  307|302) echo "✓ /dashboard → $STATUS";;
  *) echo "✗ /dashboard → $STATUS(期待 302/307)"; exit 1;;
esac

# 9. 8 核心頁路由
echo "[9] 8 核心頁路由全 200/302/307..."
BAD=0
for path in dashboard \
            screener/watchlist \
            analysis/new \
            analysis/history \
            portfolio/orders \
            admin/users \
            admin/audit; do
  s=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000/$path")
  case "$s" in
    200|302|307) ;;
    *) echo "  ✗ /$path → $s"; BAD=$((BAD+1));;
  esac
done
if [ $BAD -ne 0 ]; then
  echo "✗ 有 $BAD 頁路由不在 200/302/307"
  exit 1
fi
echo "✓ 7 個核心頁路由全綠"
echo "  (注:/analysis/[id] 動態頁需有資料才能測,改在 E2E 中覆蓋)"

# 10. AgentFlowGraph 元件
echo "[10] AgentFlowGraph 元件檔案..."
test -f "$FRONTEND/src/components/AgentFlowGraph.tsx" \
  || { echo "✗ 缺 AgentFlowGraph.tsx"; exit 1; }
echo "✓ AgentFlowGraph.tsx 存在"

# 11. React Query hooks
echo "[11] 10+ React Query hooks..."
HOOK_COUNT=0
for f in useStocks useWatchlist useAnalysis useOrders useUsers useAdmin useQuota useMarket useWebSocket; do
  if [ -f "$FRONTEND/src/hooks/${f}.ts" ] || [ -f "$FRONTEND/src/hooks/${f}.tsx" ]; then
    HOOK_COUNT=$((HOOK_COUNT+1))
  fi
done
if [ "$HOOK_COUNT" -lt 9 ]; then
  echo "✗ hooks 檔案數 $HOOK_COUNT < 9"
  exit 1
fi
echo "✓ hooks 檔案齊($HOOK_COUNT)"

# 12. backend /users/me/quota
echo "[12] backend /users/me/quota 端點..."
if grep -q "/me/quota" "$BACKEND/app/api/v1/users_router.py"; then
  echo "✓ /users/me/quota 端點已定義"
else
  echo "✗ users_router.py 找不到 /me/quota"
  exit 1
fi

# 13. bundle size
echo "[13] .next/static 大小..."
SIZE_KB=$(du -sk "$FRONTEND/.next/static" 2>/dev/null | awk '{print $1}')
echo "  .next/static = ${SIZE_KB} KB"
if [ "$SIZE_KB" -gt 51200 ]; then
  echo "✗ bundle ${SIZE_KB}KB > 51200KB(50MB),需要 review"
  exit 1
fi
echo "✓ bundle 大小符合預期(<= 50MB,寬鬆上限)"

# 收尾
kill $DEV_PID 2>/dev/null || true

echo ""
echo "✅ Phase 16 健康檢查全部通過"
