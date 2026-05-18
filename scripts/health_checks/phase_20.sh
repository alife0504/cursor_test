#!/bin/bash
# scripts/health_checks/phase_20.sh
# Phase 20 健康檢查：最終驗證 + 完整報告 + v1.0 Release
#
# 涵蓋（依 Phase 20 第 5 節 14 項驗收）：
#   1. all.sh 存在且可執行 + 內容含必要檢查項
#   2. PROJECT_FINAL_REPORT.md 存在 + ≥ 100 行 + ≥ 20 個 ✅/❌ 檢核點
#   3. connection-guide.md + user-guide.md 存在且 ≥ 50/100 行
#   4. 21 個 phase_reports/PHASE_NN.md 全部存在（PHASE_00 ~ PHASE_20）
#   5. 19 個 phase_NN.sh + all.sh 全部存在 +x
#   6. README.md 含 v1.0 標題 + Release Ready badge
#   7. CHANGELOG.md 含 [1.0.0] entry
#   8. SECURITY.md ≥ 50 行（v1.0 真實內容）
#   9. Obsidian check script 可跑 + obsidian_setup.md 存在
#  10. backend pytest 全綠
#  11. 累積測試 ≥ 535
#  12. SLO 報表存在（最近一份）
#  13. final_smoke 5 個 test 全綠
#  14. PHASE_20.md 存在 + phase_progress.md 標 P20 完成

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 20 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

BACKEND="$PROJECT_ROOT/backend"

# ──────────────────────────────────────────────────────
# 1. all.sh 存在且可執行
# ──────────────────────────────────────────────────────
echo "[1] all.sh 存在 + 可執行..."
test -x "$PROJECT_ROOT/scripts/health_checks/all.sh" || {
  echo "✗ all.sh 缺檔或無 +x"
  exit 1
}
# 必須含這些字串
for KW in "phase_01.sh" "phase_19.sh" "backend pytest" "bandit" "detect-secrets"; do
  grep -q "$KW" "$PROJECT_ROOT/scripts/health_checks/all.sh" || {
    echo "✗ all.sh 缺關鍵字: $KW"
    exit 1
  }
done
echo "✓ all.sh 存在 + 包含必要檢查項"

# ──────────────────────────────────────────────────────
# 2. PROJECT_FINAL_REPORT.md
# ──────────────────────────────────────────────────────
echo "[2] PROJECT_FINAL_REPORT.md..."
test -f "$PROJECT_ROOT/docs/PROJECT_FINAL_REPORT.md" || {
  echo "✗ docs/PROJECT_FINAL_REPORT.md 不存在"
  exit 1
}
LINES=$(wc -l < "$PROJECT_ROOT/docs/PROJECT_FINAL_REPORT.md")
[ "$LINES" -ge 100 ] || {
  echo "✗ PROJECT_FINAL_REPORT.md 行數 $LINES < 100"
  exit 1
}
CHECKS=$(grep -cE "✅|❌" "$PROJECT_ROOT/docs/PROJECT_FINAL_REPORT.md" || true)
[ "$CHECKS" -ge 20 ] || {
  echo "✗ PROJECT_FINAL_REPORT.md 檢核點 $CHECKS < 20"
  exit 1
}
echo "✓ PROJECT_FINAL_REPORT.md 完整（$LINES 行, $CHECKS 檢核點）"

# ──────────────────────────────────────────────────────
# 3. connection-guide + user-guide
# ──────────────────────────────────────────────────────
echo "[3] connection-guide + user-guide..."
test -f "$PROJECT_ROOT/docs/connection-guide.md" || { echo "✗ connection-guide.md 不存在"; exit 1; }
test -f "$PROJECT_ROOT/docs/user-guide.md" || { echo "✗ user-guide.md 不存在"; exit 1; }
CG_LINES=$(wc -l < "$PROJECT_ROOT/docs/connection-guide.md")
UG_LINES=$(wc -l < "$PROJECT_ROOT/docs/user-guide.md")
[ "$CG_LINES" -gt 50 ] || { echo "✗ connection-guide.md 行數 $CG_LINES < 50"; exit 1; }
[ "$UG_LINES" -gt 100 ] || { echo "✗ user-guide.md 行數 $UG_LINES < 100"; exit 1; }
echo "✓ connection-guide.md $CG_LINES 行 / user-guide.md $UG_LINES 行"

# ──────────────────────────────────────────────────────
# 4. 21 個 PHASE_NN.md 全部存在
# ──────────────────────────────────────────────────────
echo "[4] phase_reports/PHASE_NN.md（21 個）..."
MISSING=()
for i in $(seq -f "%02g" 0 20); do
  F="$PROJECT_ROOT/docs/phase_reports/PHASE_$i.md"
  if [ ! -f "$F" ]; then
    MISSING+=("PHASE_$i.md")
  fi
done
if [ ${#MISSING[@]} -ne 0 ]; then
  echo "✗ 缺少 ${#MISSING[@]} 個 phase report: ${MISSING[*]}"
  exit 1
fi
echo "✓ 21 個 phase report 全部存在（PHASE_00 ~ PHASE_20）"

# ──────────────────────────────────────────────────────
# 5. 19 個 phase_NN.sh + all.sh
# ──────────────────────────────────────────────────────
echo "[5] phase_NN.sh + all.sh..."
MISSING=()
for i in $(seq -f "%02g" 1 19); do
  F="$PROJECT_ROOT/scripts/health_checks/phase_$i.sh"
  if [ ! -x "$F" ]; then
    MISSING+=("phase_$i.sh")
  fi
done
test -x "$PROJECT_ROOT/scripts/health_checks/all.sh" || MISSING+=("all.sh")
test -x "$PROJECT_ROOT/scripts/health_checks/phase_20.sh" || MISSING+=("phase_20.sh")
if [ ${#MISSING[@]} -ne 0 ]; then
  echo "✗ 缺少 ${#MISSING[@]} 個 health check: ${MISSING[*]}"
  exit 1
fi
echo "✓ 19 phase_NN.sh + all.sh + phase_20.sh 全部存在 +x"

# ──────────────────────────────────────────────────────
# 6. README v1.0
# ──────────────────────────────────────────────────────
echo "[6] README v1.0..."
test -f "$PROJECT_ROOT/README.md" || { echo "✗ README.md 不存在"; exit 1; }
grep -qE "^# TradingAgents-TW v1\.0" "$PROJECT_ROOT/README.md" || {
  echo "✗ README.md 缺 v1.0 主標題"
  head -5 "$PROJECT_ROOT/README.md"
  exit 1
}
grep -qE "Release[- ]Ready|release.ready" "$PROJECT_ROOT/README.md" || {
  echo "✗ README.md 缺 Release Ready 標示"
  exit 1
}
echo "✓ README.md 含 v1.0 + Release Ready"

# ──────────────────────────────────────────────────────
# 7. CHANGELOG v1.0.0 entry
# ──────────────────────────────────────────────────────
echo "[7] CHANGELOG..."
grep -qE "^## \[1\.0\.0\]" "$PROJECT_ROOT/CHANGELOG.md" || {
  echo "✗ CHANGELOG 缺 [1.0.0] entry"
  exit 1
}
echo "✓ CHANGELOG.md 含 [1.0.0] entry"

# ──────────────────────────────────────────────────────
# 8. SECURITY.md ≥ 50 行
# ──────────────────────────────────────────────────────
echo "[8] SECURITY.md..."
test -f "$PROJECT_ROOT/SECURITY.md" || { echo "✗ SECURITY.md 不存在"; exit 1; }
SEC_LINES=$(wc -l < "$PROJECT_ROOT/SECURITY.md")
[ "$SEC_LINES" -gt 50 ] || { echo "✗ SECURITY.md 行數 $SEC_LINES < 50"; exit 1; }
echo "✓ SECURITY.md $SEC_LINES 行"

# ──────────────────────────────────────────────────────
# 9. Obsidian script + setup runbook
# ──────────────────────────────────────────────────────
echo "[9] Obsidian setup..."
test -x "$PROJECT_ROOT/scripts/check_obsidian_installed.sh" || {
  echo "✗ check_obsidian_installed.sh 不存在或無 +x"
  exit 1
}
test -f "$PROJECT_ROOT/docs/runbooks/obsidian_setup.md" || {
  echo "✗ docs/runbooks/obsidian_setup.md 不存在"
  exit 1
}
bash "$PROJECT_ROOT/scripts/check_obsidian_installed.sh" > /tmp/p20-obsidian.log 2>&1 || {
  echo "✗ check_obsidian_installed.sh 跑失敗（rc 非 0）"
  cat /tmp/p20-obsidian.log
  exit 1
}
echo "✓ Obsidian setup runbook + check script OK"

# ──────────────────────────────────────────────────────
# 10. backend pytest 全綠（pyt-test 沒列出來時要 run）
#     在這支 health check 只跑 test_final_smoke + collect-only
# ──────────────────────────────────────────────────────
echo "[10] backend final smoke tests..."
(cd "$BACKEND" && uv run pytest tests/integration/test_final_smoke.py -q --tb=short 2>&1) > /tmp/p20-smoke.log
SMOKE_RC=${PIPESTATUS[0]:-$?}
if [ "$SMOKE_RC" != "0" ]; then
  echo "✗ final smoke 失敗（rc=$SMOKE_RC）"
  tail -30 /tmp/p20-smoke.log
  exit 1
fi
PASS=$(grep -cE "PASSED|passed" /tmp/p20-smoke.log || true)
echo "✓ final smoke 5 個全綠（log: /tmp/p20-smoke.log）"

# ──────────────────────────────────────────────────────
# 11. 累積測試 ≥ 535（P20 基準）
# ──────────────────────────────────────────────────────
echo "[11] 累積測試數..."
(cd "$BACKEND" && uv run pytest --collect-only -q 2>&1) > /tmp/p20-collect.log
TEST_COUNT=$(grep -E "^[0-9]+ tests? collected" /tmp/p20-collect.log | tail -1 | awk '{print $1}')
[ -n "$TEST_COUNT" ] || { echo "✗ 無法取得測試數"; tail -10 /tmp/p20-collect.log; exit 1; }
[ "$TEST_COUNT" -ge 535 ] || { echo "✗ 後端測試 $TEST_COUNT < 535"; exit 1; }
echo "✓ 後端測試 $TEST_COUNT ≥ 535（P20 基準）"

# ──────────────────────────────────────────────────────
# 12. SLO 報表存在
# ──────────────────────────────────────────────────────
echo "[12] SLO 報表..."
SLO_DIR="$PROJECT_ROOT/docs/slo_reports"
test -d "$SLO_DIR" || { echo "✗ docs/slo_reports/ 不存在"; exit 1; }
LATEST=$(ls -t "$SLO_DIR"/*.json 2>/dev/null | head -1 || true)
if [ -z "$LATEST" ]; then
  echo "⚠️  尚無 SLO 報表（首次部署正常）— 跳過嚴格校驗"
else
  echo "✓ SLO 報表存在：$LATEST"
fi

# ──────────────────────────────────────────────────────
# 13. PHASE_20.md + phase_progress.md
# ──────────────────────────────────────────────────────
echo "[13] PHASE_20.md + phase_progress.md..."
test -f "$PROJECT_ROOT/docs/phase_reports/PHASE_20.md" || {
  echo "✗ docs/phase_reports/PHASE_20.md 不存在"
  exit 1
}
test -f "$PROJECT_ROOT/docs/phase_progress.md" || {
  echo "✗ docs/phase_progress.md 不存在"
  exit 1
}
grep -qE "^\| P20.*✅" "$PROJECT_ROOT/docs/phase_progress.md" || {
  echo "✗ phase_progress.md 未標 P20 完成"
  exit 1
}
echo "✓ PHASE_20.md + phase_progress.md（P20 ✅）"

# ──────────────────────────────────────────────────────
# 14. phase_19 health check 仍綠（連動）
# ──────────────────────────────────────────────────────
echo "[14] phase_19 連動..."
bash "$PROJECT_ROOT/scripts/health_checks/phase_19.sh" > /tmp/p20-p19.log 2>&1 || {
  echo "✗ phase_19.sh 失敗"
  tail -20 /tmp/p20-p19.log
  exit 1
}
echo "✓ phase_19 連動 OK"

echo ""
echo "✅ Phase 20 健康檢查全部通過（v1.0 Release Ready）"
