@echo off
chcp 65001 >nul
title Step 2 - Init Database
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found. Install Python 3.12 first.
    echo.
    pause
    exit /b 1
)
python db_init.py
if errorlevel 1 (
    echo.
    echo ======================================================
    echo   [FAILED] See the message above.
    echo   Please screenshot the last 20 lines and send to group.
    echo ======================================================
    echo.
    pause
    exit /b 1
)
echo.
pause
exit /b 0