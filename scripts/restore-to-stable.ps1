# restore-to-stable.ps1
# 一鍵把 TradingAgents 還原到已知良好的穩定點（程式碼 + 系統 image）。
# 資料還原「預設不做」（具破壞性）——只有加 -RestoreData 才會用 pg_dump 備份還原 DB。
#
# 用法（PowerShell）：
#   ./scripts/restore-to-stable.ps1                 # 還原程式碼 + image + 重新部署（最常用）
#   ./scripts/restore-to-stable.ps1 -RestoreData    # 連資料庫也還原（僅在資料被改壞時）
#   ./scripts/restore-to-stable.ps1 -Tag stable-2026-08-13   # 指定還原點
#
# 你的大修變更不會遺失：切換前會自動 git stash（git stash list 看得到、git stash pop 救得回），
# 你的大修分支也原封不動。

param(
    [string]$Tag = "stable-2026-08-13",
    [switch]$RestoreData
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "=== 還原到 $Tag ===" -ForegroundColor Cyan

# 0) 檢查 tag 存在
git rev-parse --verify "$Tag^{commit}" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "找不到 tag $Tag（git tag 可列出）" -ForegroundColor Red; exit 1 }

# 1) 程式碼：先自動保存未提交的大修 WIP，再切到穩定 tag
if (git status --porcelain) {
    git stash push -u -m "restore-to-stable 前自動保存的大修WIP" | Out-Null
    Write-Host "[1/4] 已把未提交的大修變更 stash（git stash pop 可救回）" -ForegroundColor Yellow
} else {
    Write-Host "[1/4] 工作樹乾淨，無需 stash" -ForegroundColor Green
}
git checkout $Tag 2>&1 | Out-Host
Write-Host "      程式碼已回到 $Tag" -ForegroundColor Green

# 2) 系統 image：把穩定快照重新指到 :dev（不需重建，秒回）
docker tag "tradingagents-backend:$Tag" tradingagents-backend:dev
docker tag "tradingagents-frontend:$Tag" tradingagents-frontend:dev
Write-Host "[2/4] image 已還原為 $Tag 快照" -ForegroundColor Green

# 3) 用還原後的 image 重新部署
$prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
docker compose --profile frontend up -d 2>&1 | Out-Host
$ErrorActionPreference = $prevEAP
Write-Host "[3/4] 已用穩定 image 重新部署" -ForegroundColor Green

# 4) 資料（僅 -RestoreData）：TimescaleDB 正確還原程序（pre/post_restore + --clean）
if ($RestoreData) {
    $dump = Join-Path $root "backups\tradingagents_tw-$Tag.dump"
    if (-not (Test-Path $dump)) { Write-Host "[4/4] 找不到備份 $dump，略過資料還原" -ForegroundColor Red; exit 1 }
    Write-Host "[4/4] 還原資料庫（破壞性；將覆蓋現有資料）..." -ForegroundColor Yellow
    $ans = Read-Host "  確定要覆蓋現有 DB 嗎？輸入 YES 繼續"
    if ($ans -ne "YES") { Write-Host "  已取消資料還原" -ForegroundColor Yellow; exit 0 }
    $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    docker compose stop backend celery_worker celery_beat 2>&1 | Out-Host
    docker cp $dump ta-timescaledb:/tmp/restore.dump
    docker exec ta-timescaledb sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -U postgres -d tradingagents_tw -c "SELECT timescaledb_pre_restore();"'
    docker exec ta-timescaledb sh -c 'PGPASSWORD=$POSTGRES_PASSWORD pg_restore -U postgres -d tradingagents_tw --clean --if-exists --no-owner /tmp/restore.dump'
    docker exec ta-timescaledb sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -U postgres -d tradingagents_tw -c "SELECT timescaledb_post_restore();"'
    docker exec ta-timescaledb rm -f /tmp/restore.dump
    docker compose --profile frontend up -d 2>&1 | Out-Host
    $ErrorActionPreference = $prevEAP
    Write-Host "      資料庫已還原" -ForegroundColor Green
} else {
    Write-Host "[4/4] 資料庫未動（如需還原資料請加 -RestoreData）" -ForegroundColor DarkGray
}

Write-Host "=== 還原完成。等容器 healthy 後即為穩定狀態 ===" -ForegroundColor Cyan
Write-Host "（要回到你的大修：git checkout <你的大修分支>；git stash pop 取回剛才保存的 WIP）" -ForegroundColor DarkGray
