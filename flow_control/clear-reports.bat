@echo off
title Clear Reports
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0clear-reports.ps1"
echo.
echo ============================================
echo   Window will stay open. Press any key to close.
echo ============================================
pause >nul
