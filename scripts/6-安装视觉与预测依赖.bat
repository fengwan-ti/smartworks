@echo off
chcp 65001 >nul
title Install numpy / opencv / statsmodels
cd /d "%~dp0.."

set "PY=%CD%\.venv\Scripts\python.exe"
set PYTHONUNBUFFERED=1
set PIP_DISABLE_PIP_VERSION_CHECK=1

echo ============================================================
echo   Install numpy + opencv-python-headless + statsmodels
echo ============================================================
echo.
echo   Python: %PY%
if not exist "%PY%" (
    echo.
    echo [ERROR] venv python not found. Run 1-install-deps.bat first.
    pause
    exit /b 1
)
"%PY%" -c "import sys; print('   Version: ' + sys.version.split()[0])"
echo.
echo   Network note:
echo     pypi.org needs ~1.4 s per request on this machine, which makes pip
echo     look frozen. So we use the Tsinghua mirror first (~0.2 s).
echo     Total download is about 120 MB. The window may sit idle for a
echo     few minutes while it downloads. That is normal - do not close it.
echo.
pause
echo.

set "MIRROR=-i https://pypi.tuna.tsinghua.edu.cn/simple"

for %%P in (numpy opencv-python-headless statsmodels) do (
    echo ------------------------------------------------------------
    echo   Installing %%P  ...
    echo ------------------------------------------------------------
    "%PY%" -m pip install %MIRROR% --timeout 30 --retries 2 %%P
    if errorlevel 1 (
        echo.
        echo   [mirror failed] retrying %%P with default index ...
        "%PY%" -m pip install --timeout 60 --retries 2 %%P
    )
    if errorlevel 1 (
        echo.
        echo   [FAILED] %%P could not be installed.
        echo   Turn on your phone hotspot, then run this script again.
        echo.
        pause
        exit /b 1
    )
    echo   %%P done.
    echo.
)

echo ============================================================
echo   Verify
echo ============================================================
"%PY%" -c "import numpy; print('   numpy       OK ' + numpy.__version__)"
"%PY%" -c "import cv2; print('   opencv      OK ' + cv2.__version__)"
"%PY%" -c "import statsmodels; print('   statsmodels OK ' + statsmodels.__version__)"
"%PY%" -c "import scipy; print('   scipy       OK ' + scipy.__version__)"
echo.
echo   All OK means you are done.
echo   Next: double click 5-stop-system.bat, then 3-start-system.bat
echo.
pause