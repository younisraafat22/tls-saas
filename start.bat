@echo off
title TLS SaaS Launcher
color 0A
echo.
echo  ============================================
echo    TLS Appointment Checker SaaS - Launcher
echo  ============================================
echo.
echo  Starting Backend (FastAPI) and Frontend (Next.js)...
echo.

:: Start Backend in a new window
start "TLS Backend - FastAPI (port 8000)" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate && echo. && echo  [Backend] Starting on http://localhost:8000 && echo. && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: Wait a moment for backend to initialize
timeout /t 3 /nobreak >nul

:: Start Frontend in a new window
start "TLS Frontend - Next.js (port 3000)" cmd /k "cd /d %~dp0frontend && echo. && echo  [Frontend] Starting on http://localhost:3000 && echo. && npx next dev -p 3000"

:: Wait for frontend to start
timeout /t 5 /nobreak >nul

:: Open the browser
start http://localhost:3000

echo.
echo  Both servers are starting!
echo.
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:3000
echo.
echo  Two new windows opened - keep them running.
echo  Close them to stop the servers.
echo.
pause
