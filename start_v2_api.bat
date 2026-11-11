@echo off
setlocal
title Taiwan-Quant-Lab V2 API
cd /d "%~dp0"
set "PYTHON="
if exist ".venv-v2\Scripts\python.exe" set "PYTHON=.venv-v2\Scripts\python.exe"
if not defined PYTHON if exist "C:\Users\SOON\.venv\Scripts\python.exe" set "PYTHON=C:\Users\SOON\.venv\Scripts\python.exe"
if not defined PYTHON (
    echo No virtual environment. Run install_v2.bat first.
    pause
    exit /b 1
)
"%PYTHON%" -c "import fastapi, uvicorn, duckdb, sklearn" 2>nul
if errorlevel 1 (
    echo Missing V2 packages. Run install_v2.bat first.
    pause
    exit /b 1
)
echo Starting PRIVATE localhost API on port 8000...
"%PYTHON%" -m quantlab.v2.server
echo.
echo API stopped.
pause
