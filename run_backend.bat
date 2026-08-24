@echo off
title Revenue Gov Platform - Backend (Port 8000)
cd /d "%~dp0backend"
echo ===================================================
echo   Revenue Gov Platform - Backend Server (Port 8000)
echo ===================================================
echo LLM Provider : OpenRouter (openrouter/auto)
echo OCR Engine   : Deterministic Multilingual Tesseract
echo.
"C:\Python314\python.exe" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
