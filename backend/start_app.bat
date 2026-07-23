@echo off
cd /d "%~dp0\.."

echo ==========================================================
echo    Fresher Job Application Platform (Official Adzuna API)
echo ==========================================================
echo.

set VENV_PYTHON=backend\.venv\Scripts\python.exe

if not exist %VENV_PYTHON% (
    set VENV_PYTHON=.venv\Scripts\python.exe
)

echo [INFO] Starting Backend Server on http://localhost:8000 ...
start "JobAssist Backend Server" cmd /k "%VENV_PYTHON% -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

echo [INFO] Backend server started in a dedicated window!
echo Open http://localhost:8000 in your browser.
echo.
