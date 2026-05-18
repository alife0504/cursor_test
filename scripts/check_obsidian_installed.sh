#!/bin/bash
# scripts/check_obsidian_installed.sh
# 檢查使用者主機是否裝了 Obsidian。
#
# v1.0 不強制 Obsidian（只提供 vault 路徑建議 + 範例查詢）；
# 如果沒裝 → 顯示安裝指引（docs/runbooks/obsidian_setup.md），exit 0。
# 如果裝了 → exit 0；資訊性訊息。
#
# 跑：bash scripts/check_obsidian_installed.sh

set -u

OBSIDIAN_FOUND=0
OBSIDIAN_PATH=""

# ────────────────────────────────
# Windows（Git Bash / WSL 都會到這支腳本）
# bash 變數名不能含括號，故用 env 抓取 ProgramFiles(x86)
# ────────────────────────────────
PF_X86="$(env | grep -E '^ProgramFiles\(x86\)=' | head -1 | cut -d= -f2- || true)"

if [ -n "${LOCALAPPDATA:-}" ] || [ -n "${ProgramFiles:-}" ]; then
  for P in \
    "${LOCALAPPDATA:-}/Obsidian/Obsidian.exe" \
    "${ProgramFiles:-}/Obsidian/Obsidian.exe" \
    "${PF_X86}/Obsidian/Obsidian.exe" \
    "$HOME/AppData/Local/Obsidian/Obsidian.exe" \
    "$HOME/AppData/Local/Programs/obsidian/Obsidian.exe"
  do
    if [ -n "$P" ] && [ -f "$P" ]; then
      OBSIDIAN_FOUND=1
      OBSIDIAN_PATH="$P"
      break
    fi
  done
fi

# ────────────────────────────────
# macOS
# ────────────────────────────────
if [ "$OBSIDIAN_FOUND" = "0" ] && [ "$(uname)" = "Darwin" ]; then
  for P in \
    "/Applications/Obsidian.app" \
    "$HOME/Applications/Obsidian.app"
  do
    if [ -d "$P" ]; then
      OBSIDIAN_FOUND=1
      OBSIDIAN_PATH="$P"
      break
    fi
  done
fi

# ────────────────────────────────
# Linux
# ────────────────────────────────
if [ "$OBSIDIAN_FOUND" = "0" ] && [ "$(uname)" = "Linux" ]; then
  if command -v obsidian > /dev/null 2>&1; then
    OBSIDIAN_FOUND=1
    OBSIDIAN_PATH="$(command -v obsidian)"
  elif [ -f "/usr/bin/obsidian" ]; then
    OBSIDIAN_FOUND=1
    OBSIDIAN_PATH="/usr/bin/obsidian"
  elif compgen -G "$HOME/.local/share/applications/Obsidian-*.AppImage" > /dev/null 2>&1; then
    OBSIDIAN_FOUND=1
    OBSIDIAN_PATH="$(ls $HOME/.local/share/applications/Obsidian-*.AppImage | head -1)"
  fi
fi

# ────────────────────────────────
# 結果
# ────────────────────────────────
if [ "$OBSIDIAN_FOUND" = "1" ]; then
  echo "✅ Obsidian 已安裝：$OBSIDIAN_PATH"
  echo ""
  echo "下一步：依 docs/runbooks/obsidian_setup.md 建立 vault。"
  echo "  建議 vault 路徑：C:/Projects/TradingAgents/obsidian_vault"
  exit 0
else
  echo "⚠️  Obsidian 未安裝（不影響 v1.0 任何功能）。"
  echo ""
  echo "如要使用個人筆記整合："
  echo "  1. 下載：https://obsidian.md/download"
  echo "  2. 安裝後依 docs/runbooks/obsidian_setup.md 建 vault"
  echo ""
  echo "v1.0 不強制 Obsidian。v1.1 才會做自動匯出整合。"
  exit 0
fi
