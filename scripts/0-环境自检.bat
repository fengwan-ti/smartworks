@echo off
chcp 65001 >nul
title Step 0 - Environment Check
cd /d "%~dp0"
echo.
echo ======================================================
echo   SmartWorks : Step 0 Environment Check
echo ======================================================
echo.
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo         Install Python 3.12 and check:
    echo         "Add python.exe to PATH"
    echo.
    pause
    exit /b 1
)
python env_check.py
echo.
pause
exit /b 0