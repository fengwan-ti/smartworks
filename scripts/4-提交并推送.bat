@echo off
chcp 65001 >nul
title Commit and Push
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found.
    echo.
    pause
    exit /b 1
)
python git_sync.py
echo.
pause
exit /b 0