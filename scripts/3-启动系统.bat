@echo off
chcp 65001 >nul
title Step 3 - Start System
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found. Install Python 3.12 first.
    echo.
    pause
    exit /b 1
)
python start_system.py
echo.
pause
exit /b 0