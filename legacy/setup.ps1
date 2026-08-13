#Requires -Version 5.1
<#
.SYNOPSIS
    TradingAgents Setup Script (PowerShell)
.NOTES
    Run: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
    Then: .\setup.ps1
#>

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  TradingAgents - Setup Installer (PowerShell)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$policy = Get-ExecutionPolicy -Scope CurrentUser
if ($policy -eq "Restricted") {
    Write-Host "[Fix] Setting execution policy..." -ForegroundColor Yellow
    Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
}

# Step 1: Find Python 3.10+
Write-Host "[1/6] Checking Python..." -ForegroundColor White
$pythonCmd = $null
foreach ($cmd in @("python", "py", "python3")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                $pythonCmd = $cmd
                Write-Host "  Found: $ver ($cmd)" -ForegroundColor Green
                break
            }
        }
    } catch {}
}
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python 3.10+ not found!" -ForegroundColor Red
    Write-Host "  Download: https://www.python.org/downloads/"
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 2: Create venv
Write-Host ""
Write-Host "[2/6] Setting up virtual environment..." -ForegroundColor White
if (Test-Path "venv") {
    Write-Host "  venv already exists, skipping." -ForegroundColor Yellow
} else {
    & $pythonCmd -m venv venv
    Write-Host "  Virtual environment created." -ForegroundColor Green
}

# Step 3: Upgrade pip
Write-Host ""
Write-Host "[3/6] Upgrading pip..." -ForegroundColor White
& .\venv\Scripts\python.exe -m pip install --upgrade pip -q
Write-Host "  pip upgraded." -ForegroundColor Green

# Step 4: Install packages (two-step to avoid local path issue)
Write-Host ""
Write-Host "[4/6] Installing packages (3-5 min)..." -ForegroundColor White
Write-Host "  Step 4a: Install third-party packages from requirements.lock..."
try {
    & .\venv\Scripts\pip.exe install -r requirements.lock -q
    Write-Host "  Step 4b: Install tradingagents itself..."
    & .\venv\Scripts\pip.exe install --no-deps . -q
    Write-Host "  All packages installed." -ForegroundColor Green
} catch {
    Write-Host "  Falling back to pyproject.toml install..."
    & .\venv\Scripts\pip.exe install . -q
    Write-Host "  Installed from pyproject.toml." -ForegroundColor Green
}

# Step 5: Create .env
Write-Host ""
Write-Host "[5/6] Setting up .env..." -ForegroundColor White
if (Test-Path ".env") {
    Write-Host "  .env already exists, keeping current settings." -ForegroundColor Yellow
} else {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "  Created .env from .env.example" -ForegroundColor Green
        Write-Host "  *** Open .env with Notepad and add your API key ***" -ForegroundColor Yellow
    }
}

# Step 6: Verify
Write-Host ""
Write-Host "[6/6] Verifying installation..." -ForegroundColor White
$result = & .\venv\Scripts\python.exe -c "from tradingagents.graph.trading_graph import TradingAgentsGraph; print('OK')" 2>&1
if ($result -eq "OK") {
    Write-Host "  Core module loaded successfully." -ForegroundColor Green
} else {
    Write-Host "[ERROR] Verification failed: $result" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:"
Write-Host "  1. Open .env with Notepad, add your LLM API key:"
Write-Host "     DEEPSEEK_API_KEY=sk-xxxxxxxx"
Write-Host "     Get key free: https://platform.deepseek.com/api_keys"
Write-Host ""
Write-Host "  2. Launch: double-click start.bat  OR  run .\start.ps1"
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"
