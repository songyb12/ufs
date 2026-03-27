@echo off
:: ============================================================================
:: Session Manager Watchdog
:: ============================================================================
:: 서버가 죽으면 자동 재시작. taskkill //F //IM python.exe 등으로 전체 Python이
:: 죽어도 5초 내에 session-manager만 다시 살아남.
::
:: 사용법:
::   watchdog.bat              — 콘솔 모드 (로그 직접 출력)
::   watchdog.bat --headless   — 백그라운드 모드 (로그 파일에만 기록)
::
:: 종료: Ctrl+C 또는 이 창을 닫으면 watchdog도 종료됨
::       (서버는 별도 프로세스이므로 계속 실행됨)
:: ============================================================================

title Session Manager Watchdog
cd /d "%~dp0"

set VENV=.venv\Scripts\activate.bat
set LOG_FILE=data\logs\watchdog.log
set RESTART_DELAY=5
set MAX_RAPID_RESTARTS=5
set RAPID_WINDOW=60

:: venv 확인
if not exist %VENV% (
    echo [watchdog] ERROR: venv not found. Run start.bat first.
    pause
    exit /b 1
)

call %VENV%

:: 로그 디렉토리 보장
if not exist data\logs mkdir data\logs

:: headless 모드 확인
set HEADLESS=0
if "%~1"=="--headless" set HEADLESS=1

:: rapid restart 카운터
set RESTART_COUNT=0

:loop
    :: 서버 시작 전 타임스탬프 (초 단위 근사)
    for /f "tokens=1-3 delims=:." %%a in ("%time: =0%") do (
        set /a START_TIME=%%a*3600+%%b*60+%%c
    )

    echo [%date% %time%] [watchdog] Starting session-manager (attempt %RESTART_COUNT%)...

    if %HEADLESS%==1 (
        echo [%date% %time%] [watchdog] Starting session-manager >> %LOG_FILE%
        python -m app.main >> %LOG_FILE% 2>&1
    ) else (
        python -m app.main
    )

    :: 서버 종료됨 — exit code 확인
    set EXIT_CODE=%ERRORLEVEL%
    echo [%date% %time%] [watchdog] Server exited with code %EXIT_CODE%

    if %HEADLESS%==1 (
        echo [%date% %time%] [watchdog] Server exited with code %EXIT_CODE% >> %LOG_FILE%
    )

    :: 정상 종료 (exit code 0) 시 watchdog도 종료
    if %EXIT_CODE%==0 (
        echo [watchdog] Clean shutdown detected. Watchdog exiting.
        if %HEADLESS%==1 echo [%date% %time%] [watchdog] Clean shutdown. >> %LOG_FILE%
        exit /b 0
    )

    :: rapid restart 감지 — 짧은 시간 내 반복 크래시 방지
    for /f "tokens=1-3 delims=:." %%a in ("%time: =0%") do (
        set /a END_TIME=%%a*3600+%%b*60+%%c
    )
    set /a ELAPSED=%END_TIME%-%START_TIME%
    if %ELAPSED% lss 0 set /a ELAPSED=%ELAPSED%+86400

    if %ELAPSED% lss %RAPID_WINDOW% (
        set /a RESTART_COUNT+=1
    ) else (
        set RESTART_COUNT=0
    )

    if %RESTART_COUNT% geq %MAX_RAPID_RESTARTS% (
        echo [watchdog] ERROR: %MAX_RAPID_RESTARTS% rapid restarts in %RAPID_WINDOW%s. Giving up.
        if %HEADLESS%==1 echo [%date% %time%] [watchdog] Too many rapid restarts. Stopped. >> %LOG_FILE%
        pause
        exit /b 1
    )

    echo [watchdog] Restarting in %RESTART_DELAY% seconds...
    timeout /t %RESTART_DELAY% /nobreak >nul

goto loop
