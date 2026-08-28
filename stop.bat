@echo off
title TLS SaaS - Stop All
echo.
echo  Stopping all TLS SaaS servers...
echo.
taskkill /FI "WINDOWTITLE eq TLS Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq TLS Frontend*" /F >nul 2>&1
taskkill /F /IM "uvicorn.exe" >nul 2>&1
taskkill /F /IM "node.exe" >nul 2>&1
echo  Done! All servers stopped.
echo.
pause
