@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   TradingAgents - Setup Installer
echo ============================================================
echo.

echo [1/6] Checking Python version...
python --version > nul 2>&1
if errorlevel 1 (
    py --version > nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found!
        echo Download from: https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during install.
        pause
        exit /b 1
    )
    set PYTHON=py
) else (
    set PYTHON=python
)
for /f "tokens=2" %%v in ('!PYTHON! --version 2^>^&1') do set PYVER=%%v
echo     Python !PYVER! found.

echo.
echo [2/6] Creating virtual environment...
if exist venv (
    echo     venv already exists, skipping.
) else (
    !PYTHON! -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo     Virtual environment created.
)

echo.
echo [3/6] Upgrading pip...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
echo     pip upgraded.

echo.
echo [4/6] Installing dependencies (3-5 min)...
echo     Step 4a: Install all third-party packages from requirements.lock...
pip install -r requirements.lock -q
if errorlevel 1 (
    echo [WARN] requirements.lock install had issues, falling back to pyproject.toml...
    pip install . -q
) else (
    echo     Step 4b: Install tradingagents itself (no extra deps)...
    pip install --no-deps . -q
)
if errorlevel 1 (
    echo [ERROR] Installation failed. Check your internet connection.
    pause
    exit /b 1
)
echo     All packages installed.

echo.
echo [5/6] Setting up .env file...
if exist .env (
    echo     .env already exists, keeping current settings.
) else (
    if exist .env.example (
        copy .env.example .env > nul
        echo     Created .env from .env.example
        echo     *** Open .env with Notepad and add your API key ***
    )
)

echo.
echo [6/6] Verifying installation...
python -c "from tradingagents.graph.trading_graph import TradingAgentsGraph; print('    Core module OK')"
if errorlevel 1 (
    echo [ERROR] Verification failed.
    pause
    exit /b 1
)
where tradingagents > nul 2>&1
if not errorlevel 1 (
    echo     tradingagents command: OK
)

echo.
echo ============================================================
echo   Setup complete!
echo.
echo   Next steps:
echo   1. Open .env with Notepad, add your LLM API key:
echo      e.g.  DEEPSEEK_API_KEY=sk-xxxxxxxx
echo      Get one free: https://platform.deepseek.com/api_keys
echo.
echo   2. Run start.bat to launch TradingAgents
echo ============================================================
echo.
pause
