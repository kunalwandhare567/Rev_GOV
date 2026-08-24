@echo off
title Revenue Gov Platform - Frontend (Port 5173)
cd /d "%~dp0frontend"
echo ===================================================
echo   Revenue Gov Platform - Frontend Dev Server
echo ===================================================
echo.
call npm run dev
pause
