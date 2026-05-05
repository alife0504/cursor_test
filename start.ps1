#Requires -Version 5.1
<#
.SYNOPSIS
    TradingAgents Daily Launcher (PowerShell)
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  TradingAgents - Starting..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "[ERROR] Virtual environment not found!" -ForegroundColor Red
    Write-Host "  Please run setup.ps1 or setup.bat first."
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path ".env")) {
    Write-Host "[ERROR] .env file not found!" -ForegroundColor Red
    Write-Host "  Please copy .env.example to .env and add your API key."
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if at least one API key is set
$envContent = Get-Content ".env" -Raw
$hasKey = $envContent -match "(OPENAI|ANTHROPIC|GOOGLE|DEEPSEEK|DASHSCOPE|XAI|ZHIPU|OPENROUTER)_API_KEY=.+"
if (-not $hasKey) {
    Write-Host "[WARNING] No API key found in .env!" -ForegroundColor Yellow
    Write-Host "  Add at least one key, e.g.: DEEPSEEK_API_KEY=sk-xxxxxxxx"
    $c = Read-Host "Continue anyway? (y/N)"
    if ($c -ne "y" -and $c -ne "Y") { exit 0 }
}

Write-Host "Activating virtual environment..." -ForegroundColor Gray
& .\venv\Scripts\Activate.ps1

Write-Host "Launching TradingAgents..." -ForegroundColor Green
Write-Host ""

tradingagents analyze

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Analysis complete. Reports saved to: reports\" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
