@echo off
title E2E Demo Runner
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-e2e.ps1"
echo.
echo ============================================
echo   Window will stay open. Press any key to close.
echo ============================================
pause >nul
