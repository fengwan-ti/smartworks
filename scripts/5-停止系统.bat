@echo off
chcp 65001 >nul
title Stop SmartWorks
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found on PATH.
    echo.
    pause
    exit /b 1
)
python stop_system.py
echo.
pause
exit /b 0