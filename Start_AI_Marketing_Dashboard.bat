@echo off
title AI Digital Marketing Command Center - Corporate Cars Melbourne
echo ========================================================
echo   Launching AI Digital Marketing Command Center (CCM)
echo   FastAPI Backend + 16 Specialized AI Marketing Agents
echo ========================================================
echo.

cd /d "c:\Users\Administrator\Desktop\AI-Digital-Marketing"

echo [1/2] Checking & Starting Backend Server on http://127.0.0.1:8000...
start "" "corporate-cars-social-agent\.venv\Scripts\python.exe" -m uvicorn dashboard.api:app --host 127.0.0.1 --port 8000 --reload

echo [2/2] Opening Dashboard in Google Chrome...
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8000"

echo.
echo ========================================================
echo   Command Center is now LIVE at http://127.0.0.1:8000
echo   You can minimize this window.
echo ========================================================
