@echo off
title VIBE 2.0
echo =========================================
echo   VIBE 2.0 시작...
echo   백엔드:   http://localhost:8010
echo   대시보드: http://localhost:3002
echo =========================================

cd /d "%~dp0"

start /B uvicorn app.main:app --port 8010 --host 0.0.0.0
echo [Backend]  started

cd dashboard
start /B npm run dev
echo [Dashboard] started

echo.
echo 종료하려면 이 창을 닫거나 Ctrl+C
pause >nul
taskkill /F /IM uvicorn.exe 2>nul
taskkill /F /IM node.exe 2>nul
echo 종료 완료.
