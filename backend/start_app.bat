@echo off
cd /d "%~dp0.."

echo ==========================================================
echo    Fresher Job Application Platform (Official Adzuna API)
echo ==========================================================
echo.

set VENV_DIR=backend\.venv

if not exist %VENV_DIR% (
    set VENV_DIR=.venv
)

if not exist %VENV_DIR% (
    echo [ERROR] Virtual environment directory '%VENV_DIR%' not found.
    pause
    exit /b 1
)

echo [INFO] Activating virtual environment from %VENV_DIR%...
call %VENV_DIR%\Scripts\activate

echo [INFO] Starting Job Application Assistance Platform on http://localhost:8000 ...
echo.
echo Open http://localhost:8000 in your browser.
echo Press Ctrl+C to stop the server.
echo.

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
