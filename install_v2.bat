@echo off
setlocal
title Install Taiwan-Quant-Lab V2
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher not found. Install Python 3.12 first.
    pause
    exit /b 1
)
if not exist ".venv-v2\Scripts\python.exe" py -3.12 -m venv ".venv-v2"
if errorlevel 1 (
    echo Failed to create environment.
    pause
    exit /b 1
)
".venv-v2\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv-v2\Scripts\python.exe" -m pip install -r requirements-v2.txt
if errorlevel 1 goto :failed
echo.
echo V2 installation completed. Start start_v2_api.bat.
pause
exit /b 0
:failed
echo INSTALL FAILED. See error messages above.
pause
exit /b 1
