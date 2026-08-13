# run-host-supervised.ps1
# 在「本機」以自動重啟方式跑 backend(uvicorn) + frontend(next dev)。
# 用途：想保留前端 HMR、又不想崩潰/休眠後服務停掉不回來。
#
# ⚠️ 真正要「持續運行、開機自啟、關終端機也不停」請改用：  make stack-up
#    （全棧容器化，Docker 自動重啟；本腳本只在這兩個視窗開著時有效。）
#
# 用法（PowerShell）：  ./scripts/run-host-supervised.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Windows 把 6379/6333 列為保留 port，redis/qdrant 改發佈高位 port（內網仍 6379/6333）
$env:REDIS_PORT = "16379"
$env:QDRANT_PORT = "16333"
$env:QDRANT_GRPC_PORT = "16334"

Write-Host "[1/3] 確保 Docker 基礎服務 up（DB / Redis / Qdrant / celery worker+beat）..." -ForegroundColor Cyan
docker compose up -d timescaledb redis qdrant celery_worker celery_beat

# backend 監督迴圈（不用 --reload：reload 在壞檔存檔時會直接掛掉不回來）
$backendCmd = @"
`$env:REDIS_PORT='16379'; `$env:QDRANT_PORT='16333'; `$env:QDRANT_GRPC_PORT='16334'
Set-Location '$root\backend'
while (`$true) {
  Write-Host '[backend] 啟動 uvicorn 0.0.0.0:8000 ...' -ForegroundColor Green
  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
  Write-Host '[backend] 已退出，3 秒後自動重啟 ...' -ForegroundColor Yellow
  Start-Sleep -Seconds 3
}
"@

# frontend 監督迴圈（next dev 保留 HMR）
$frontendCmd = @"
Set-Location '$root\frontend'
while (`$true) {
  Write-Host '[frontend] 啟動 next dev :3000 ...' -ForegroundColor Green
  npm run dev
  Write-Host '[frontend] 已退出，3 秒後自動重啟 ...' -ForegroundColor Yellow
  Start-Sleep -Seconds 3
}
"@

Write-Host "[2/3] 開啟 backend 監督視窗（崩潰自動重啟）..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

Write-Host "[3/3] 開啟 frontend 監督視窗（崩潰自動重啟）..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Write-Host ""
Write-Host "✅ 已啟動。前端 http://localhost:3000   後端 http://localhost:8000" -ForegroundColor Green
Write-Host "   關閉那兩個視窗即停止。要常駐/開機自啟，請用：make stack-up" -ForegroundColor DarkGray
