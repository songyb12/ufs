@echo off
:: ============================================================================
:: Session Manager — 배포 스크립트
:: ============================================================================
:: 사용법:
::   deploy.bat          — 최신 master pull 후 재시작
::   deploy.bat v1.2.0   — 특정 태그 체크아웃 후 재시작
::
:: 실행 위치: 미니PC의 session-manager 디렉토리
:: ============================================================================

title Session Manager Deploy
cd /d "%~dp0"

set TARGET=%~1
if "%TARGET%"=="" set TARGET=master

echo.
echo [deploy] Target: %TARGET%
echo [deploy] Working dir: %cd%
echo.

:: ── 1. 현재 실행 중인 서버 종료 ─────────────────────────────────────────────
echo [deploy] Stopping server on port 8006...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8006 "') do (
    echo [deploy] Killing PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
:: watchdog 프로세스도 종료 (제목으로 찾기)
taskkill /F /FI "WINDOWTITLE eq Session Manager Watchdog" >nul 2>&1
timeout /t 2 /nobreak >nul

:: ── 2. git pull ──────────────────────────────────────────────────────────────
echo [deploy] Fetching from origin...
git fetch origin
if %ERRORLEVEL% neq 0 (
    echo [deploy] ERROR: git fetch failed. Check network / git config.
    pause
    exit /b 1
)

if "%~1"=="" (
    echo [deploy] Pulling master...
    git checkout master
    git pull origin master
) else (
    echo [deploy] Checking out tag %TARGET%...
    git checkout %TARGET%
)

if %ERRORLEVEL% neq 0 (
    echo [deploy] ERROR: git checkout/pull failed.
    pause
    exit /b 1
)

:: 현재 커밋 표시
for /f %%a in ('git rev-parse --short HEAD') do set COMMIT=%%a
for /f "delims=" %%a in ('git log -1 --format^="%s"') do set MSG=%%a
echo [deploy] Now at: %COMMIT% — %MSG%
echo.

:: ── 3. 의존성 업데이트 (requirements.txt 변경 시만) ──────────────────────────
echo [deploy] Checking requirements...
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [deploy] Creating venv...
    python -m venv .venv
    call .venv\Scripts\activate.bat
)
pip install -r requirements.txt -q --no-deps >nul 2>&1
pip install -r requirements.txt -q >nul 2>&1

:: ── 4. 서버 재시작 ───────────────────────────────────────────────────────────
echo [deploy] Starting watchdog...
start "Session Manager Watchdog" cmd /k watchdog.bat

echo.
echo [deploy] Done. Server starting on port 8006.
echo [deploy] Close this window or press any key to exit.
pause >nul
