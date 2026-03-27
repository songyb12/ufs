"""
app/screen.py — ScreenMonitor class (Windows screen capture via mss + Pillow).
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models import SCREENSHOTS_DIR

logger = logging.getLogger("session-manager.screen")


# ─── 스크린 모니터링 ─────────────────────────────────────────────────────────────

class ScreenMonitor:
    """Windows 스크린 캡처 (mss + Pillow)"""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._interval = 30
        self._latest_path: Optional[Path] = None

    def capture(self) -> Path:
        # Lazy imports: mss and Pillow are optional dependencies.
        # Keeping them here avoids ImportError on servers where screen capture
        # is not used and these packages are not installed.
        import mss
        from PIL import Image

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filepath = SCREENSHOTS_DIR / f"screen_{ts}.jpg"

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            img = sct.grab(monitor)
            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            pil_img.save(str(filepath), "JPEG", quality=65)

        self._latest_path = filepath
        self._cleanup()
        return filepath

    def _cleanup(self):
        screenshots = sorted(SCREENSHOTS_DIR.glob("screen_*.jpg"))
        for old in screenshots[:-50]:
            old.unlink(missing_ok=True)

    async def start_periodic(self, interval: int = 30):
        self._interval = interval
        self._running = True
        if self._task:
            self._task.cancel()
        self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running:
            try:
                await asyncio.to_thread(self.capture)
            except Exception as e:
                logger.error("[monitor] capture error: %s", e)
            await asyncio.sleep(self._interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    @property
    def latest(self) -> Optional[Path]:
        return self._latest_path
