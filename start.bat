@echo off
chcp 65001 > nul
setlocal

echo.
echo ============================================================
echo   TradingAgents - Starting...
echo ============================================================
echo.

if not exist venv\Scripts\activate.bat (
    echo [ERROR] Virtual environment not found!
    echo Please run setup.bat first.
    pause
    exit /b 1
)

if not exist .env (
    echo [ERROR] .env file not found!
    echo Please copy .env.example to .env and add your API key.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo [OK] Virtual environment activated
echo [OK] Starting analysis...
echo.

tradingagents analyze

echo.
echo ============================================================
echo   Done. Reports saved to: reports\
echo ============================================================
echo.
pause
