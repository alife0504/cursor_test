# autostart-stack.ps1
# 開機/登入時確保 TradingAgents 全棧容器都起來（冪等）。
# 由 Windows 排程任務「TradingAgents-Autostart」於登入時呼叫（見 scripts/register-autostart.ps1）。
#
# 設計：
# - Docker Desktop 已設定登入自啟（registry Run），容器又都 restart:unless-stopped，
#   正常情況開機後會自動回來；本腳本是「保險層」：即使曾 docker compose down、
#   或 profile 前端沒被既有容器帶起，也會用 up -d 補齊整套。
# - 等 Docker 引擎就緒才動作（開機初期 engine 尚未 ready）。
# - 冪等：已在跑的容器 up -d 不會重啟、無副作用。

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$log = Join-Path $logDir "autostart.log"

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Add-Content -Path $log -Value $line -Encoding utf8
    Write-Host $line
}

Write-Log "=== autostart 開始 ==="

# 1) 確保 Docker Desktop 進程在跑（登入自啟通常已帶起；沒有就補啟）
$dd = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
if (-not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
    if (Test-Path $dd) {
        Write-Log "Docker Desktop 未在跑 → 啟動"
        Start-Process $dd | Out-Null
    } else {
        Write-Log "找不到 Docker Desktop.exe（$dd）"
    }
}

# 2) 等 Docker 引擎就緒（最多 ~5 分鐘）
$ready = $false
for ($i = 1; $i -le 60; $i++) {
    try {
        docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 5
}
if (-not $ready) { Write-Log "Docker 引擎逾時未就緒，放棄本次（下次登入再試）"; exit 1 }
Write-Log "Docker 引擎就緒"

# 3) 啟動全棧（含 profile 前端）。冪等。
# 注意：docker compose 的進度訊息（Container X Running/Started）走 stderr；PS 5.1 在
# ErrorActionPreference=Stop 下會把 native stderr 當終止錯誤，故此段改 Continue，
# 以 $LASTEXITCODE 判成敗（compose 成功回 0，不論 stderr 有無進度行）。
Set-Location $root
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
docker compose --profile frontend --profile monitoring up -d 2>&1 | ForEach-Object { Write-Log "compose: $_" }
$code = $LASTEXITCODE
$ErrorActionPreference = $prevEAP
if ($code -eq 0) {
    Write-Log "=== compose up 完成 (exit 0) ==="
} else {
    # 冷開機時 backend 較慢變 healthy（等 DB/redis/qdrant + 啟動探針），compose 可能先報依賴
    # 失敗；但 restart:unless-stopped 會續拉起。等待後複檢最終狀態，全部在跑才視為成功，
    # 避免 autostart 誤報 0x1（先前每次登入都失敗一次的根因）。
    Write-Log "compose up 首次 exit=$code；等待 120s 讓 backend 變 healthy 後複檢…"
    Start-Sleep -Seconds 120
    $ErrorActionPreference = "Continue"
    docker compose --profile frontend --profile monitoring up -d 2>&1 | ForEach-Object { Write-Log "compose(retry): $_" }
    Start-Sleep -Seconds 30
    $expected = @("ta-timescaledb", "ta-redis", "ta-qdrant", "ta-backend",
        "ta-celery-worker", "ta-celery-beat", "ta-frontend")
    $running = @((docker ps --format "{{.Names}}") -split "`n" | ForEach-Object { $_.Trim() })
    $missing = @($expected | Where-Object { $running -notcontains $_ })
    $ErrorActionPreference = $prevEAP
    if ($missing.Count -eq 0) {
        Write-Log "=== 複檢:全部容器已在跑 (exit 0) ==="
    } else {
        Write-Log "複檢後仍缺:$($missing -join ', ') (exit 1)"
        exit 1
    }
}
