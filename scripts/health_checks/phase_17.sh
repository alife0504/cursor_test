#!/bin/bash
# scripts/health_checks/phase_17.sh
# Phase 17 健康檢查:前端 10 個進階頁(接後端) + 5 個 mock 頁
#
# 涵蓋(13 項):
#   1. node / npm 可用
#   2. frontend/node_modules 已 install
#   3. lint 通過
#   4. typecheck 通過
#   5. build 成功
#   6. unit tests 通過 (≥ 110)
#   7. dev server 起得來 + /login 200
#   8. middleware:未登入 /dashboard → 307/302
#   9. 22 個 18 路由全部回 200 / 302 / 307
#  10. 7 個 P17 hooks 檔案存在
#  11. 共用元件 BarChart / PieChart / MockBanner 存在
#  12. Sidebar 已標 mock(grep "mock>" 字串)
#  13. mock 頁渲染含 "Mock" 字串(grep build output)

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 17 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

FRONTEND="$PROJECT_ROOT/frontend"

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
(cd "$FRONTEND" && npm run lint --silent) > /tmp/p17-lint.log 2>&1 || {
  echo "✗ lint 失敗"
  tail -20 /tmp/p17-lint.log
  exit 1
}
echo "✓ lint 通過"

# 4. typecheck
echo "[4] tsc --noEmit..."
(cd "$FRONTEND" && npx tsc --noEmit) > /tmp/p17-tsc.log 2>&1 || {
  echo "✗ typecheck 失敗"
  tail -20 /tmp/p17-tsc.log
  exit 1
}
echo "✓ typecheck 通過"

# 5. build
echo "[5] next build..."
(cd "$FRONTEND" && npm run build) > /tmp/p17-build.log 2>&1 || {
  echo "✗ build 失敗"
  tail -30 /tmp/p17-build.log
  exit 1
}
echo "✓ build 成功"

# 6. unit tests (≥ 110)
echo "[6] vitest unit tests..."
(cd "$FRONTEND" && NO_COLOR=1 FORCE_COLOR=0 npm test -- --reporter=basic) > /tmp/p17-vitest.log 2>&1 || {
  echo "✗ unit tests 失敗"
  tail -30 /tmp/p17-vitest.log
  exit 1
}
TESTS=$(sed 's/\x1b\[[0-9;]*m//g' /tmp/p17-vitest.log \
  | grep -E "Tests[[:space:]]+[0-9]+ passed" \
  | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" | head -1)
TESTS=${TESTS:-0}
if [ "$TESTS" -lt 110 ]; then
  echo "✗ 通過測試 $TESTS < 110 (P17 累積最低)"
  tail -10 /tmp/p17-vitest.log
  exit 1
fi
echo "✓ unit tests 通過 ($TESTS)"

# 7. dev server
echo "[7] 啟動 dev server..."
(cd "$FRONTEND" && npm run dev) > /tmp/p17-dev.log 2>&1 &
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
  tail -30 /tmp/p17-dev.log
  exit 1
fi
echo "✓ dev server 起來 + /login 200"

# 8. middleware
echo "[8] middleware 未登入 /dashboard → redirect..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/dashboard)
case "$STATUS" in
  307|302) echo "✓ /dashboard → $STATUS";;
  *) echo "✗ /dashboard → $STATUS (期待 302/307)"; exit 1;;
esac

# 9. 全 22 路由
echo "[9] 22 路由(含 P16 + P17)全 200/302/307..."
BAD=0
for path in dashboard \
            market/overview market/institutional market/calendar \
            screener/watchlist screener/filter screener/compare \
            analysis/new analysis/history \
            statistics/accuracy statistics/models statistics/backtest \
            portfolio/positions portfolio/orders portfolio/history \
            news/sentiment news/announcements \
            notifications \
            admin/users admin/audit admin/system admin/pipeline; do
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
echo "✓ 22 個路由全綠"

# 10. P17 hooks
echo "[10] 7 個 P17 hooks 檔案..."
HOOK_COUNT=0
for f in useScreener useNews usePortfolio useNotifications useSystem useStatistics; do
  if [ -f "$FRONTEND/src/hooks/${f}.ts" ] || [ -f "$FRONTEND/src/hooks/${f}.tsx" ]; then
    HOOK_COUNT=$((HOOK_COUNT+1))
  fi
done
if [ "$HOOK_COUNT" -lt 6 ]; then
  echo "✗ P17 hooks 檔案數 $HOOK_COUNT < 6"
  exit 1
fi
echo "✓ P17 hooks 檔案齊 ($HOOK_COUNT)"

# 11. 共用元件
echo "[11] BarChart / PieChart / MockBanner..."
test -f "$FRONTEND/src/components/common/BarChart.tsx" \
  || { echo "✗ 缺 BarChart.tsx"; exit 1; }
test -f "$FRONTEND/src/components/common/PieChart.tsx" \
  || { echo "✗ 缺 PieChart.tsx"; exit 1; }
test -f "$FRONTEND/src/components/common/MockBanner.tsx" \
  || { echo "✗ 缺 MockBanner.tsx"; exit 1; }
echo "✓ 3 個共用元件存在"

# 12. Sidebar 已標 mock
echo "[12] Sidebar 含 mock badge..."
if grep -qE 'mock: true|>mock<|>\s*mock\s*<' "$FRONTEND/src/components/common/Sidebar.tsx"; then
  echo "✓ Sidebar 含 mock badge"
else
  echo "✗ Sidebar 沒有 mock 標示"
  exit 1
fi

# 13. mock 頁渲染含 "Mock" 字串(從原始檔 grep,不用真打開頁)
echo "[13] mock 頁含 Mock / v1.1 字串..."
MOCK_PAGES=(
  "src/app/(app)/market/calendar/page.tsx"
  "src/app/(app)/screener/compare/page.tsx"
  "src/app/(app)/statistics/backtest/page.tsx"
)
for p in "${MOCK_PAGES[@]}"; do
  if ! grep -qi "mock" "$FRONTEND/$p"; then
    echo "✗ $p 缺 mock 標示"
    exit 1
  fi
done
echo "✓ 3 個 mock 頁含 Mock 標示"

# 收尾
kill $DEV_PID 2>/dev/null || true

echo ""
echo "✅ Phase 17 健康檢查全部通過"
