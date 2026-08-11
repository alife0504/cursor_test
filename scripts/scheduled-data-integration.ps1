# scheduled-data-integration.ps1
# 一次性排程：2026/8/12 03:00 由排程任務「TradingAgents-DataIntegration-20260812」呼叫。
# 無人值守啟動 headless Claude，全方位分析 finmind(含 twnews) + twofc(tw-hawk) 裡
# 「可用但未用」的資料並接進本專案；來源資料庫一律唯讀，測試綠燈才部署。
#
# 護欄寫在 scripts/scheduled-prompt-20260812.md（任務提示）與下方 --append-system-prompt。

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$runLog = Join-Path $logDir "scheduled-integration-run.log"

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Add-Content -Path $runLog -Value $line -Encoding utf8
    Write-Host $line
}

Write-Log "=== scheduled data-integration 開始 ==="

# 1) 確保全棧 up（沿用 autostart 腳本，冪等）
$autostart = Join-Path $PSScriptRoot "autostart-stack.ps1"
if (Test-Path $autostart) {
    Write-Log "先確保 docker 全棧 up..."
    & $autostart | Out-Null
}

# 2) 定位 claude CLI 與任務提示
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) { Write-Log "找不到 claude CLI，放棄"; exit 1 }
$promptFile = Join-Path $PSScriptRoot "scheduled-prompt-20260812.md"
if (-not (Test-Path $promptFile)) { Write-Log "找不到任務提示 $promptFile"; exit 1 }
$prompt = Get-Content -Raw -Encoding UTF8 $promptFile

# 3) 護欄 system prompt（強化，避免任何情況下寫外部庫 / push / 動原廠 agent）
$guard = "這是 2026/8/12 的無人值守自動化執行。硬性規則不可違反：(1) 所有外部資料庫(finmind PostgreSQL、C:/Projects/tw-hawk/data/twofc.duckdb、tw-hawk 檔案)一律唯讀，只下 SELECT / read_only 連線，絕不寫入/改結構/刪改任何資料；(2) 只在分支 auto/data-integration-20260812 工作，不動 main 與既有功能分支的既有邏輯；(3) 測試(pytest/tsc/ruff)全綠才可 docker 部署，任何失敗就不部署、保留分支給人工審查；(4) 不要 git push；(5) 不重寫分析師/agent 的決策原廠邏輯，只可連接新資料源並餵給既有分析師；(6) PIT 安全，只用當下已公開資料。全程寫報告到 logs/scheduled-integration-20260812.md。"

$outLog = Join-Path $logDir "scheduled-integration-20260812.stdout.log"
Write-Log "啟動 headless Claude（輸出 → $outLog）..."
Set-Location $root

# 以 stdin 餵長提示。權限策略（安全重點）：
# - 用 --permission-mode acceptEdits（自動接受檔案編輯，headless 不卡）而非
#   --dangerously-skip-permissions；關鍵差異：acceptEdits 仍「強制執行」使用者
#   settings.json 的 deny 規則（Edit/Write(**/*.duckdb)、tw-hawk、finmind-platform），
#   而 skip-permissions 會整個繞過 → 來源資料庫/檔案的唯讀保護才真的被「強制」而非只被「叮嚀」。
# - --allowedTools 預先放行 headless 需要的工具，避免卡在權限詢問（deny 仍優先、擋不住的只有 Bash shell 寫入，
#   但任務無理由這麼做且提示明令禁止；duckdb 又以 read_only=True 連線，DB 層物理唯讀）。
# - --add-dir 給 finmind / tw-hawk 唯讀分析所需的目錄「讀取」存取（Edit/Write 仍被 deny 擋）。
$allowed = @("Bash", "Read", "Grep", "Glob", "Edit", "Write", "Task", "WebFetch", "WebSearch", "TodoWrite")
$prompt | & $claude -p `
    --permission-mode acceptEdits `
    --allowedTools $allowed `
    --add-dir "C:\Projects\finmind-platform" `
    --add-dir "C:\Projects\tw-hawk" `
    --append-system-prompt $guard 2>&1 | Tee-Object -FilePath $outLog

$code = $LASTEXITCODE
Write-Log "=== Claude 執行結束 exit=$code ==="
exit $code
