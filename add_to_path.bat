@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   Add tradingagents to PATH
echo   (so you can type it in any CMD window)
echo ============================================================
echo.

set PROJ_DIR=%~dp0
set SCRIPTS_DIR=%PROJ_DIR%venv\Scripts

if not exist "%SCRIPTS_DIR%\tradingagents.exe" (
    echo [ERROR] tradingagents.exe not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

echo Will add to PATH:
echo %SCRIPTS_DIR%
echo.

for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set CURRENT_PATH=%%b

echo !CURRENT_PATH! | findstr /i /c:"%SCRIPTS_DIR%" > nul
if not errorlevel 1 (
    echo Already in PATH. No change needed.
    goto :done
)

if defined CURRENT_PATH (
    set NEW_PATH=!CURRENT_PATH!;%SCRIPTS_DIR%
) else (
    set NEW_PATH=%SCRIPTS_DIR%
)

reg add "HKCU\Environment" /v Path /t REG_EXPAND_SZ /d "!NEW_PATH!" /f > nul
if errorlevel 1 (
    echo [ERROR] Cannot modify PATH. Try running as Administrator.
    pause
    exit /b 1
)

echo PATH updated successfully!

:done
echo.
echo ============================================================
echo   How to use (after opening a NEW CMD window):
echo.
echo   cd /d "%PROJ_DIR%"
echo   venv\Scripts\activate
echo   tradingagents analyze
echo.
echo   OR simply double-click start.bat
echo ============================================================
echo.
pause
