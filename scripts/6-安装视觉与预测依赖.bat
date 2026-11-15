@echo off
chcp 65001 >nul
title Install numpy / opencv / statsmodels
cd /d "%~dp0.."

set "PY=%CD%\.venv\Scripts\python.exe"

echo ============================================================
echo   Install numpy + opencv-python-headless + statsmodels
echo ============================================================
echo.
echo   Python: %PY%
echo.

if not exist "%PY%" (
    echo [ERROR] venv python not found:
    echo         %PY%
    echo.
    echo   Run 1-install-deps.bat first, or check the .venv folder.
    echo.
    pause
    exit /b 1
)

"%PY%" -c "import sys; print('  Python version:', sys.version.split()[0])"
echo.

echo --- Step 1/2: try default index ----------------------------
"%PY%" -m pip install --disable-pip-version-check numpy opencv-python-headless statsmodels
if not errorlevel 1 goto verify

echo.
echo --- Step 2/2: default index failed, try Tsinghua mirror ----
"%PY%" -m pip install --disable-pip-version-check -i https://pypi.tuna.tsinghua.edu.cn/simple numpy opencv-python-headless statsmodels
if errorlevel 1 (
    echo.
    echo [FAILED] Both attempts failed. Check network / hotspot, then rerun.
    echo.
    pause
    exit /b 1
)

:verify
echo.
echo ============================================================
echo   Verify
echo ============================================================
"%PY%" -c "import numpy; print('  numpy        OK', numpy.__version__)"
"%PY%" -c "import cv2; print('  opencv       OK', cv2.__version__)"
"%PY%" -c "import statsmodels; print('  statsmodels  OK', statsmodels.__version__)"
echo.
echo   If all three lines say OK, you are done.
echo   Next: run 5-stop-system.bat, then 3-start-system.bat
echo.
pause