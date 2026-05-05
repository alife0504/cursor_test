#!/usr/bin/env bash
# ============================================================================
# TradingAgents 安全自我檢查腳本
# ============================================================================
# 用法: bash scripts/check_env_security.sh
# 功能: 檢查常見的安全設定錯誤，幫使用者在 push 前抓出問題
# ============================================================================

set -u
cd "$(dirname "$0")/.."

PASS=0
FAIL=0
WARN=0

ok()    { printf "  [\033[32m✓\033[0m] %s\n" "$1"; PASS=$((PASS+1)); }
fail()  { printf "  [\033[31m✗\033[0m] %s\n" "$1"; FAIL=$((FAIL+1)); }
warn()  { printf "  [\033[33m!\033[0m] %s\n" "$1"; WARN=$((WARN+1)); }
info()  { echo "  [i] $1"; }

echo
echo "============================================"
echo " TradingAgents 安全自我檢查"
echo "============================================"

# 1. .env 檔案是否存在且未被 git 追蹤
echo
echo "[1/7] 檢查 .env 檔案"
if [ -f .env ]; then
    ok ".env 存在"
    if git ls-files --error-unmatch .env > /dev/null 2>&1; then
        fail ".env 已被 git 追蹤！危險！立即執行: git rm --cached .env"
    else
        ok ".env 未被 git 追蹤"
    fi

    PERM=$(stat -c '%a' .env 2>/dev/null || stat -f '%A' .env 2>/dev/null)
    if [ "$PERM" = "600" ] || [ "$PERM" = "0600" ]; then
        ok ".env 權限為 600（僅自己可讀寫）"
    else
        warn ".env 權限為 $PERM，建議執行: chmod 600 .env"
    fi
else
    warn ".env 不存在，請執行: cp .env.example .env"
fi

# 2. .gitignore 是否包含 .env
echo
echo "[2/7] 檢查 .gitignore"
if grep -qE "^\.env$|^\.env\.\*$" .gitignore 2>/dev/null; then
    ok ".gitignore 已排除 .env"
else
    fail ".gitignore 未排除 .env"
fi

# 3. 檢查歷史 commit 中是否有真實的 API 金鑰
echo
echo "[3/7] 掃描 git 歷史中的疑似金鑰"
if git rev-parse --git-dir > /dev/null 2>&1; then
    LEAKS=$(git log -p --all 2>/dev/null | grep -E "(sk-[a-zA-Z0-9]{20,}|AIza[a-zA-Z0-9_\\-]{35})" | head -5)
    if [ -z "$LEAKS" ]; then
        ok "git 歷史未發現明顯金鑰格式"
    else
        fail "git 歷史可能含金鑰！建議用 git-filter-repo 清除並輪換金鑰"
    fi
else
    info "非 git 倉庫，跳過"
fi

# 4. 檢查 ~/.tradingagents 目錄權限
echo
echo "[4/7] 檢查本地資料目錄"
TADIR="${TRADINGAGENTS_CACHE_DIR:-$HOME/.tradingagents}"
if [ -d "$TADIR" ]; then
    PERM=$(stat -c '%a' "$TADIR" 2>/dev/null || stat -f '%A' "$TADIR" 2>/dev/null)
    if [ "$PERM" = "700" ]; then
        ok "$TADIR 權限為 700"
    else
        warn "$TADIR 權限為 $PERM，建議: chmod 700 $TADIR"
    fi
else
    info "$TADIR 不存在（首次使用屬正常）"
fi

# 5. 檢查 pip 版本
echo
echo "[5/7] 檢查 pip 版本"
if command -v pip > /dev/null 2>&1; then
    PIPV=$(pip --version | awk '{print $2}')
    PIPMAJ=$(echo "$PIPV" | cut -d. -f1)
    if [ "$PIPMAJ" -ge 25 ]; then
        ok "pip $PIPV（已修補已知 CVE）"
    else
        warn "pip $PIPV 過舊，請執行: pip install --upgrade pip"
    fi
else
    warn "找不到 pip"
fi

# 6. 是否安裝 pip-audit
echo
echo "[6/7] 檢查依賴漏洞"
if command -v pip-audit > /dev/null 2>&1; then
    if [ -f requirements.lock ]; then
        info "使用 requirements.lock 掃描..."
        pip-audit -r requirements.lock 2>&1 | tail -5 || true
    else
        info "使用已安裝的依賴掃描..."
        pip-audit --skip-editable 2>&1 | tail -5 || true
    fi
else
    warn "未安裝 pip-audit，建議: pip install pip-audit"
fi

# 7. 是否有可疑的權限 0777 檔案
echo
echo "[7/7] 檢查危險權限檔案"
DANG=$(find . -type f \( -name "*.py" -o -name "*.env*" \) -perm -o+w 2>/dev/null \
       -not -path "./venv/*" -not -path "./.git/*" -not -path "./node_modules/*" | head -5)
if [ -z "$DANG" ]; then
    ok "未發現全域可寫的敏感檔案"
else
    warn "發現全域可寫檔案："
    echo "$DANG" | sed 's/^/      /'
fi

echo
echo "============================================"
echo " 結果：通過 $PASS  警告 $WARN  失敗 $FAIL"
echo "============================================"

if [ $FAIL -gt 0 ]; then
    echo "  請優先處理 [✗] 標示的項目"
    exit 1
elif [ $WARN -gt 0 ]; then
    echo "  建議處理 [!] 標示的項目以提升安全等級"
    exit 0
else
    echo "  通過所有檢查"
    exit 0
fi
