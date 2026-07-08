@echo off
echo ==========================================================
echo       LinkedIn Scraper & Emailer Startup Script
echo ==========================================================
echo.

set VENV_DIR=.venv

if not exist %VENV_DIR% (
    echo [ERROR] Virtual environment directory '%VENV_DIR%' not found.
    echo Please make sure you are running this from the scraper root directory
    echo and that the virtual environment exists.
    pause
    exit /b 1
)

echo [INFO] Activating virtual environment...
call %VENV_DIR%\Scripts\activate

echo [INFO] Installing any missing requirements...
pip install -r requirements.txt

echo [INFO] Starting Flask application on http://127.0.0.1:8000 ...
echo.
echo Press Ctrl+C to stop the server.
echo.

python app.py

pause
