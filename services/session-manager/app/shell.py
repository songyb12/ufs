"""
app/shell.py — ShellSession class (ConPTY-based terminal via pywinpty).
"""

import asyncio
import logging
import os
import shutil
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

# ConPTY (Windows 터미널 에뮬레이션)
try:
    from winpty import PtyProcess
    HAS_WINPTY = True
except ImportError:
    PtyProcess = None  # type: ignore[assignment,misc]
    HAS_WINPTY = False

logger = logging.getLogger("session-manager.shell")


# ─── Shell 터미널 세션 (ConPTY) ──────────────────────────────────────────────────

class ShellSession:
    """ConPTY 기반 Shell 터미널 세션

    pywinpty를 사용하여 cmd.exe/powershell을 ConPTY로 실행.
    WebSocket으로 stdin/stdout을 양방향 스트리밍.
    """

    def __init__(self, shell_id: str, work_dir: str = ".",
                 shell_type: str = "cmd", cols: int = 120, rows: int = 30):
        self.id = shell_id
        self.work_dir = work_dir
        self.shell_type = shell_type  # "cmd" or "powershell"
        self.created_at = datetime.now().isoformat()
        self.alive = False
        self.cols = cols
        self.rows = rows
        self.pty: Optional[PtyProcess] = None
        self._read_thread: Optional[threading.Thread] = None
        self._buffer: deque = deque()  # 최근 출력 버퍼 (deque: popleft O(1))
        self._buffer_lock = threading.Lock()
        self._max_buffer = 50000  # 최대 버퍼 문자 수
        self._subscribers: list[asyncio.Queue] = []  # WebSocket 구독자 큐
        self._subscribers_lock = threading.Lock()  # _read_loop 스레드와의 경합 방지
        self._loop: Optional[asyncio.AbstractEventLoop] = None  # call_soon_threadsafe 용

    def start(self):
        """PTY 프로세스 시작"""
        if not HAS_WINPTY:
            raise RuntimeError("pywinpty not installed")

        if self.shell_type == "powershell":
            exe = shutil.which("powershell.exe") or "powershell.exe"
        else:
            exe = os.environ.get("COMSPEC", "cmd.exe")

        cwd = str(Path(self.work_dir).expanduser()) if self.work_dir not in (".",) else None

        self.pty = PtyProcess.spawn(
            exe,
            dimensions=(self.rows, self.cols),
            cwd=cwd,
        )
        self.alive = True
        try:
            self._loop = asyncio.get_running_loop()  # 스레드에서 call_soon_threadsafe 사용 위해 캡처
        except RuntimeError:
            self._loop = None  # 동기 컨텍스트에서 호출 시 폴백 (_push_data에서 None 처리)

        # stdout 읽기 스레드 시작
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()

    def _push_data(self, data: str):
        """버퍼에 저장 + 구독자에게 전달"""
        with self._buffer_lock:
            self._buffer.append(data)
            total = sum(len(s) for s in self._buffer)
            while total > self._max_buffer and len(self._buffer) > 1:
                removed = self._buffer.popleft()  # deque: O(1) (기존 list.pop(0)은 O(n))
                total -= len(removed)
        with self._subscribers_lock:
            subscribers_snapshot = list(self._subscribers)
        for q in subscribers_snapshot:
            try:
                # 스레드에서 asyncio.Queue에 안전하게 접근 (call_soon_threadsafe)
                if self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(q.put_nowait, data)
                else:
                    q.put_nowait(data)
            except Exception:
                pass

    def _read_loop(self):
        """PTY stdout을 읽어 버퍼에 저장 + WebSocket 구독자에게 전달

        pywinpty의 read()는 블로킹이므로 1바이트씩 읽되,
        짧은 간격으로 모아서 한 번에 전달 (효율성).
        """
        buf = []
        last_flush = time.time()
        FLUSH_INTERVAL = 0.05  # 50ms마다 flush

        while self.alive and self.pty and self.pty.isalive():
            try:
                ch = self.pty.read(1)
                if ch:
                    buf.append(ch)
                    now = time.time()
                    if now - last_flush >= FLUSH_INTERVAL or len(buf) >= 256:
                        self._push_data("".join(buf))
                        buf.clear()
                        last_flush = now
            except EOFError:
                break
            except Exception as e:
                logger.error("[shell %s] _read_loop unexpected error: %s", self.id, e)
                break

        # 남은 버퍼 flush
        if buf:
            self._push_data("".join(buf))

        self.alive = False

        # PTY 프로세스 확실히 종료 (좀비 방지)
        try:
            if self.pty and self.pty.isalive():
                self.pty.terminate()
        except Exception:
            pass

        # 종료 신호를 구독자에게 전달
        with self._subscribers_lock:
            subscribers_snapshot = list(self._subscribers)
        for q in subscribers_snapshot:
            try:
                q.put_nowait(None)
            except Exception:
                pass

    def write(self, data: str):
        """PTY stdin에 쓰기"""
        if self.pty and self.pty.isalive():
            self.pty.write(data)

    def resize(self, cols: int, rows: int):
        """터미널 크기 변경"""
        self.cols = cols
        self.rows = rows
        if self.pty and self.pty.isalive():
            self.pty.setwinsize(rows, cols)

    def subscribe(self) -> asyncio.Queue:
        """WebSocket 구독자 등록"""
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        with self._subscribers_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """WebSocket 구독자 해제"""
        with self._subscribers_lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def get_buffer(self) -> str:
        """현재 버퍼 내용 반환"""
        with self._buffer_lock:
            return "".join(self._buffer)

    def kill(self):
        """세션 종료"""
        self.alive = False
        if self.pty:
            try:
                if self.pty.isalive():
                    self.pty.terminate()
            except Exception:
                pass
            self.pty = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "shell_type": self.shell_type,
            "work_dir": self.work_dir,
            "created_at": self.created_at,
            "alive": self.alive,
            "cols": self.cols,
            "rows": self.rows,
        }
