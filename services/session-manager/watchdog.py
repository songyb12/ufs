"""
watchdog.py — Session Manager 자동 재시작 watchdog
====================================================

서버가 죽으면 자동 재시작. taskkill //F //IM python.exe 등으로 전체 Python이
죽어도 watchdog 자체는 별도 프로세스이므로 session-manager를 다시 살림.

사용법:
    python watchdog.py              # 콘솔 모드
    pythonw watchdog.py             # 백그라운드 모드 (창 없음)

동작:
    1. app.main 서버를 subprocess로 실행
    2. 프로세스 종료 감지 → 5초 후 재시작
    3. exit code 0 (정상 종료) → watchdog도 종료
    4. 60초 내 5번 연속 crash → rapid restart 감지 → 포기
"""

import subprocess
import sys
import time
import os
from pathlib import Path
from datetime import datetime

# 설정
RESTART_DELAY = 5          # 재시작 대기 초
MAX_RAPID_RESTARTS = 5     # rapid restart 최대 횟수
RAPID_WINDOW = 60          # rapid restart 감지 윈도우 (초)

SCRIPT_DIR = Path(__file__).parent.resolve()
VENV_PYTHON = SCRIPT_DIR / ".venv" / "Scripts" / "python.exe"
LOG_DIR = SCRIPT_DIR / "data" / "logs"
LOG_FILE = LOG_DIR / "watchdog.log"


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [watchdog] {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main():
    if not VENV_PYTHON.exists():
        log(f"ERROR: venv not found at {VENV_PYTHON}")
        sys.exit(1)

    restart_times: list[float] = []

    while True:
        start_time = time.time()
        log(f"Starting session-manager (recent restarts: {len(restart_times)})")

        try:
            proc = subprocess.Popen(
                [str(VENV_PYTHON), "-m", "app.main"],
                cwd=str(SCRIPT_DIR),
                # stdout/stderr 그대로 콘솔에 출력 (pythonw면 /dev/null)
            )
            exit_code = proc.wait()
        except KeyboardInterrupt:
            log("Watchdog interrupted by user (Ctrl+C)")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            break
        except Exception as e:
            log(f"ERROR: Failed to start server: {e}")
            exit_code = 1

        elapsed = time.time() - start_time
        log(f"Server exited with code {exit_code} (ran for {elapsed:.0f}s)")

        # 정상 종료 (exit code 0) → watchdog도 종료
        if exit_code == 0:
            log("Clean shutdown detected. Watchdog exiting.")
            break

        # rapid restart 감지
        now = time.time()
        restart_times = [t for t in restart_times if now - t < RAPID_WINDOW]
        restart_times.append(now)

        if len(restart_times) >= MAX_RAPID_RESTARTS:
            log(f"ERROR: {MAX_RAPID_RESTARTS} rapid restarts in {RAPID_WINDOW}s. Giving up.")
            sys.exit(1)

        log(f"Restarting in {RESTART_DELAY} seconds...")
        time.sleep(RESTART_DELAY)


if __name__ == "__main__":
    main()
