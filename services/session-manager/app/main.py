"""
Claude Session Manager — main.py
==================================

FastAPI application entry point. Business logic is distributed across modules:

    app/session.py        ClaudeSession class, rate limiting, session cleanup
    app/shell.py          ShellSession class (ConPTY terminal via pywinpty)
    app/pipeline.py       PipelineRunner, PlanPhase — supervisor→worker loop
    app/pipeline_store.py SQLite checkpoint store for pipeline recovery
    app/models.py         Path constants, rate-limit constants, Pydantic models
    app/state.py          Shared mutable state (sessions, pipelines, shells)
    app/auth.py           Admin API key verification, browse-path allowlist
    app/screen.py         ScreenMonitor — periodic screenshot capture
    app/routes_api.py     /api/* REST endpoints (62 endpoints)
    app/routes_admin.py   /admin/* endpoints (status, restart, resume)
    app/routes_ws.py      /ws/* WebSocket endpoints (session output, shell I/O)
    app/main.py           lifespan, middleware, static mounts, entrypoint

Session lifecycle
-----------------
    1. POST /api/sessions → ClaudeSession created → worker_task started → save_state()
    2. POST /send → prompt queued → worker runs Claude CLI → output streamed
    3. Server shutdown → lifespan shutdown → all sessions killed (state files kept)
    4. Server restart → lifespan startup → *.json restored → start_worker()
    5. DELETE /api/sessions/{id}?remove=true → kill + state file deleted

Pipeline lifecycle
------------------
    1. POST /api/pipelines → PipelineRunner created → existing session bound as worker
    2. Supervisor (API or CLI) generates prompts from goal
    3. Prompts sent to worker → output collected → feedback to supervisor
    4. PIPELINE_DONE or max_iterations reached → exit
    5. Checkpoints persisted in pipeline_store.py (SQLite WAL)
    6. On restart: interrupted runs detected → manual resume via POST /admin/resume

Notes
-----
- Session state files: data/sessions/{session_id}.json
- sv-/pw-/ev- prefix files are zombies — deleted on lifespan startup
- Pipeline state is in-memory only (pipelines dict) — DB holds checkpoints
- ShellSession requires pywinpty — shell feature disabled if not installed
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# ─── 로깅 설정 ─────────────────────────────────────────────────────────────────

_log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)

logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("session-manager")

# ──────────────────────────────────────────────────────────────────────────────

# ─── Pipeline store (lifespan에서 직접 사용) ──────────────────────────────────

from app.pipeline_store import (
    get_resumable_runs, cleanup_old_runs, mark_interrupted,
)

# ─── Module imports ───────────────────────────────────────────────────────────

from app.models import (
    APP_DIR, DATA_DIR, LOGS_DIR, SESSIONS_DIR, UPLOADS_DIR, SCREENSHOTS_DIR,  # re-exported for tests
    TEMPLATES_FILE,  # re-exported for tests
    SESSION_TTL_SECONDS, CLEANUP_INTERVAL,
    MAX_SESSIONS_PER_CLIENT, MAX_SESSION_CREATES_PER_MINUTE,  # re-exported for tests
    find_claude_exe, _load_template,
    load_projects, save_projects,  # re-exported for tests
)
from app.state import (
    sessions, shell_sessions, pipelines, plan_phases,  # re-exported for tests
    _session_create_log, _shutting_down, CLAUDE_EXE,  # re-exported for tests
)

# Re-exports — tests import these from app.main for backward compatibility
from app.session import ClaudeSession, _cleanup_dead_sessions, _check_rate_limit
from app.shell import ShellSession, HAS_WINPTY
from app.pipeline import PipelineRunner, PlanPhase

# Routers
from app.routes_admin import router as admin_router
from app.routes_api import router as api_router
from app.routes_ws import router as ws_router


@asynccontextmanager
async def lifespan(app):
    global CLAUDE_EXE
    import app.state as _state
    CLAUDE_EXE = find_claude_exe()
    _state.CLAUDE_EXE = CLAUDE_EXE  # session.py reads from _state
    if CLAUDE_EXE:
        logger.info("Claude CLI: %s", CLAUDE_EXE)
    else:
        logger.warning("Claude CLI not found — session creation disabled")
    if HAS_WINPTY:
        logger.info("Shell Terminal: ConPTY (pywinpty)")
    else:
        logger.warning("Shell Terminal: unavailable (pywinpty not installed)")

    # 저장된 세션 복원
    restored = 0
    sv_cleaned = 0
    for sf in SESSIONS_DIR.glob("*.json"):
        sid = sf.stem
        try:
            # 좀비 세션 삭제 (sv-감독자, pw-worker, ev-이벤트, src-소스, cmp-비교, plan-sv-계획감독자)
            if any(sid.startswith(p) for p in ("sv-", "pw-", "ev-", "src-", "cmp-", "plan-sv-")):
                sf.unlink(missing_ok=True)
                sv_cleaned += 1
                continue

            session = ClaudeSession.load_state(sid)

            # 서버 재시작 시 파이프라인 바인딩 해제 (파이프라인은 메모리 전용)
            session.pipeline_id = None
            session.pipeline_role = None

            session.start_worker()
            sessions[session.id] = session
            session.save_state()
            restored += 1
        except Exception as e:
            logger.warning("Session restore failed (%s): %s", sf.name, e)
    if restored:
        logger.info("Restored %d session(s) from disk", restored)
    if sv_cleaned:
        logger.info("Cleaned %d supervisor zombie file(s)", sv_cleaned)

    # 자동 정리 태스크 시작
    cleanup_task = asyncio.create_task(_cleanup_dead_sessions())
    logger.info("Session cleanup: every %ds, TTL %ds", CLEANUP_INTERVAL, SESSION_TTL_SECONDS)

    # 이전 서버 종료 시 중단된 파이프라인 복구 대상 확인
    resumable = get_resumable_runs()
    if resumable:
        ids = [r["id"] for r in resumable]
        logger.warning("[recovery] %d interrupted pipeline(s) found: %s", len(resumable), ids)
        for r in resumable:
            # 이미 interrupted인 것도 포함하여 상태를 명확히 재확정
            mark_interrupted(r["id"])
        logger.warning("[recovery] All interrupted runs marked — manual resume required")

    # 30일 이상 된 completed/failed run 정리
    deleted = cleanup_old_runs(days=30)
    if deleted > 0:
        logger.info("[cleanup] Deleted %d old pipeline run(s) from DB", deleted)

    yield

    # 서버 종료 플래그 설정
    _state._shutting_down = True

    # 정리 태스크 중단
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # 서버 종료 시 실행 중인 파이프라인을 interrupted로 마킹 (재시작 후 복구 대상)
    for pid, pipe in list(pipelines.items()):
        if pipe.status in ("running", "idle"):
            mark_interrupted(pid)

    for session in sessions.values():
        await session.kill()
    for shell in list(shell_sessions.values()):
        shell.kill()


app = FastAPI(title="Claude Session Manager", lifespan=lifespan)
app.include_router(admin_router)
app.include_router(api_router)
app.include_router(ws_router)


_ACCESS_LOG = DATA_DIR / "access.log"

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    path = request.url.path
    if path == "/" or path.startswith("/api/imagegen/"):
        response.headers["cache-control"] = "no-store"
    else:
        # HTML 페이지(/)는 UFS Shell iframe에 삽입되므로 X-Frame-Options 제외
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # 페이지 접속(GET /)만 기록 — API/WS 호출 제외
    # asyncio.to_thread: 동기 파일 I/O가 이벤트 루프를 블로킹하지 않도록
    if request.method == "GET" and path == "/":
        ip = request.client.host if request.client else "unknown"
        ua = request.headers.get("user-agent", "-")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts}  {ip}  {ua}\n"
        await asyncio.to_thread(_write_access_log, line)
    return response


def _write_access_log(line: str) -> None:
    with open(_ACCESS_LOG, "a", encoding="utf-8") as f:
        f.write(line)


# 정적 파일 서빙 (업로드, 스크린샷)
# ADMIN_API_KEY 미설정(개발 모드): StaticFiles 직접 서빙
# ADMIN_API_KEY 설정(보안 모드): /api/media/{path}?mkey=... 엔드포인트를 통해 인증 후 서빙
if not os.environ.get("ADMIN_API_KEY"):
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
    app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")




# ─── API 엔드포인트 ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return _load_template("index.html")


@app.get("/health")
async def health():
    import sqlite3 as _sqlite3
    from app.pipeline_store import _DB_PATH
    db_ok = False
    try:
        conn = _sqlite3.connect(str(_DB_PATH), timeout=2)
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        pass
    return {
        "status": "healthy" if CLAUDE_EXE else "degraded",
        "sessions": len(sessions),
        "claude_cli": CLAUDE_EXE is not None,
        "db_ok": db_ok,
    }



# ─── 엔트리포인트 ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("SERVICE_PORT", "8006"))
    logger.info("Claude Session Manager starting on http://localhost:%d", port)
    uvicorn.run(app, host="0.0.0.0", port=port, timeout_graceful_shutdown=30)
