@echo off
setlocal
title Install Taiwan-Quant-Lab V2
cd /d "%~dp0"
if not exist ".venv-v2\Scripts\python.exe" (
    if exist "%USERPROFILE%\.venv\Scripts\python.exe" (
        echo Found your existing Python 3 environment.
        "%USERPROFILE%\.venv\Scripts\python.exe" -m venv ".venv-v2"
    ) else (
        echo Using Python 3.12 launcher.
        py -3.12 -m venv ".venv-v2"
    )
)
if not exist ".venv-v2\Scripts\python.exe" (
    echo Cannot find Python 3.12 or create .venv-v2.
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
