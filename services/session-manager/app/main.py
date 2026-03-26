"""
Claude Session Manager
Windows 네이티브 - Claude CLI 세션을 웹 UI로 관리하는 프로그램
"""

import asyncio
import json
import os
import re
import shlex
import shutil
import signal
import string
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

from app.pipeline_store import (
    create_run, update_stage, save_checkpoint,
    mark_complete, mark_failed, mark_interrupted, get_resumable_runs,
    cleanup_old_runs,
)

# ConPTY (Windows 터미널 에뮬레이션)
try:
    from winpty import PtyProcess
    HAS_WINPTY = True
except ImportError:
    HAS_WINPTY = False

# ─── 설정 ───────────────────────────────────────────────────────────────────────

APP_DIR = Path(__file__).parent.parent  # services/session-manager/
LOGS_DIR = APP_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
SESSIONS_DIR = DATA_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)
PROJECTS_FILE = DATA_DIR / "projects.json"

# 호스트 실행 시 .env 파일 로드 (Docker 외부)
_env_file = APP_DIR.parent.parent / ".env"  # ../../.env = 프로젝트 루트
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            value = value.strip()
            # 따옴표 제거 (큰따옴표/작은따옴표)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            os.environ.setdefault(key.strip(), value)

CLAUDE_EXE = None  # 런타임에 탐색


def load_projects() -> list[dict]:
    """저장된 프로젝트 목록 로드"""
    if PROJECTS_FILE.exists():
        try:
            return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # 손상된 파일 보존 후 빈 목록 반환
            PROJECTS_FILE.replace(PROJECTS_FILE.with_suffix(".json.bak"))
            return []
    return []


def save_projects(projects: list[dict]):
    """프로젝트 목록 저장 (원자적 쓰기 — partial write 방지)"""
    tmp = Path(str(PROJECTS_FILE) + ".tmp")
    tmp.write_text(json.dumps(projects, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, PROJECTS_FILE)


def find_claude_exe() -> str:
    """Claude CLI 실행 파일 경로 탐색"""
    # 1) PATH에서 찾기
    found = shutil.which("claude")
    if found:
        return found

    # 2) 알려진 설치 경로들 탐색
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    search_dirs = []

    if appdata:
        claude_code_dir = Path(appdata) / "Claude" / "claude-code"
        if claude_code_dir.exists():
            # 버전 폴더들 중 가장 최신 선택
            try:
                versions = sorted(claude_code_dir.iterdir(), reverse=True)
            except (PermissionError, OSError):
                versions = []
            for v in versions:
                exe = v / "claude.exe"
                if exe.exists():
                    return str(exe)

    if localappdata:
        # npm global install
        npm_exe = Path(localappdata) / "npm" / "claude.cmd"
        if npm_exe.exists():
            return str(npm_exe)

    return None


SESSION_TTL_SECONDS = 3600  # 1시간 비활성 세션 자동 정리
CLEANUP_INTERVAL = 300     # 5분마다 정리 실행
CMP_SESSION_TTL_SECONDS = 600  # 비교(cmp-*) 세션은 완료 후 10분 TTL


async def _cleanup_dead_sessions():
    """비활성 세션 자동 정리 태스크"""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        now = datetime.now()
        to_remove = []
        for sid, session in sessions.items():
            # supervisor 세션이 sessions dict에 남아있으면 즉시 정리 (TTL 무시)
            if session.pipeline_role == "supervisor":
                to_remove.append(sid)
                continue

            try:
                created = datetime.fromisoformat(session.created_at)
                elapsed = (now - created).total_seconds()
            except Exception:
                continue

            if not session.alive and not session.busy:
                # 죽은 세션 — 일반/cmp TTL 적용
                ttl = CMP_SESSION_TTL_SECONDS if sid.startswith("cmp-") else SESSION_TTL_SECONDS
                if elapsed > ttl:
                    to_remove.append(sid)
            elif sid.startswith("cmp-") and not session.busy and session._queue.empty():
                # cmp-* 세션: alive이지만 비교 완료(idle) → 단기 TTL 적용
                if elapsed > CMP_SESSION_TTL_SECONDS:
                    to_remove.append(sid)
            elif (sid.startswith("pw-") and not session.pipeline_id
                  and not session.busy and session._queue.empty()):
                # pw-* 세션: 파이프라인 종료 후 바인딩 해제된 idle worker → 단기 TTL 적용
                if elapsed > CMP_SESSION_TTL_SECONDS:
                    to_remove.append(sid)

        for sid in to_remove:
            s = sessions.pop(sid, None)
            if s is None:
                continue
            try:
                if s.alive:
                    await s.kill()
                s.delete_state()
            except Exception as e:
                print(f"  [cleanup] error removing session {sid}: {e}")
        if to_remove:
            print(f"  [cleanup] {len(to_remove)} dead session(s) removed")

        # 완료된 파이프라인도 정리
        pipe_remove = []
        for pid, pipe in list(pipelines.items()):
            if pipe.status in ("completed", "failed", "stopped"):
                try:
                    created = datetime.fromisoformat(pipe.created_at)
                    if (now - created).total_seconds() > SESSION_TTL_SECONDS:
                        pipe_remove.append(pid)
                except Exception:
                    pass
        for pid in pipe_remove:
            pipelines.pop(pid, None)
        if pipe_remove:
            print(f"  [cleanup] {len(pipe_remove)} finished pipeline(s) removed")

        # 죽은 Shell 세션 정리
        shell_remove = [sid for sid, sh in shell_sessions.items() if not sh.alive]
        for sid in shell_remove:
            shell_sessions.pop(sid, None)
        if shell_remove:
            print(f"  [cleanup] {len(shell_remove)} dead shell(s) removed")

        # _session_create_log 오래된 IP 항목 정리 (1시간 이상 된 타임스탬프 제거)
        old_threshold = time.time() - 3600
        stale_ips = []
        for ip, timestamps in _session_create_log.items():
            _session_create_log[ip] = [t for t in timestamps if t > old_threshold]
            if not _session_create_log[ip]:
                stale_ips.append(ip)
        for ip in stale_ips:
            del _session_create_log[ip]


@asynccontextmanager
async def lifespan(app):
    global CLAUDE_EXE
    CLAUDE_EXE = find_claude_exe()
    if CLAUDE_EXE:
        print(f"  Claude CLI: {CLAUDE_EXE}")
    else:
        print("  ⚠ Claude CLI not found — session creation disabled")
    if HAS_WINPTY:
        print(f"  Shell Terminal: ConPTY (pywinpty)")
    else:
        print(f"  Shell Terminal: unavailable (pywinpty not installed)")

    # 저장된 세션 복원
    restored = 0
    sv_cleaned = 0
    pw_converted = 0
    for sf in SESSIONS_DIR.glob("*.json"):
        sid = sf.stem
        try:
            # sv-* (감독자 좀비) → 복원하지 않고 삭제
            if sid.startswith("sv-"):
                sf.unlink(missing_ok=True)
                sv_cleaned += 1
                continue

            # pw-* (파이프라인 전용 worker) → 재시작 후 불필요, 삭제
            if sid.startswith("pw-"):
                sf.unlink(missing_ok=True)
                pw_converted += 1
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
            print(f"  ⚠ 세션 복원 실패 ({sf.name}): {e}")
    if restored:
        print(f"  Restored {restored} session(s) from disk")
    if sv_cleaned:
        print(f"  Cleaned {sv_cleaned} supervisor zombie file(s)")
    if pw_converted:
        print(f"  Cleaned up {pw_converted} orphan worker session file(s)")

    # 자동 정리 태스크 시작
    cleanup_task = asyncio.create_task(_cleanup_dead_sessions())
    print(f"  Session cleanup: every {CLEANUP_INTERVAL}s, TTL {SESSION_TTL_SECONDS}s")

    # 이전 서버 종료 시 중단된 파이프라인 복구 대상 확인
    resumable = get_resumable_runs()
    if resumable:
        ids = [r["id"] for r in resumable]
        print(f"  [RECOVERY] {len(resumable)}개의 중단된 파이프라인 발견: {ids}")
        for r in resumable:
            # 이미 interrupted인 것도 포함하여 상태를 명확히 재확정
            mark_interrupted(r["id"])
        print(f"  [RECOVERY] 모든 중단 run의 status를 interrupted로 확정 (수동 재개 필요)")

    # 30일 이상 된 completed/failed run 정리
    deleted = cleanup_old_runs(days=30)
    if deleted > 0:
        print(f"  [CLEANUP] 오래된 파이프라인 기록 {deleted}개 삭제")

    yield

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


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# 정적 파일 서빙 (업로드, 스크린샷)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")

# 활성 세션 관리
sessions: dict = {}
shell_sessions: dict = {}  # Shell 터미널 세션

# ─── Rate Limiting (인메모리) ───────────────────────────────────────────────────
MAX_SESSIONS_PER_CLIENT = int(os.environ.get("MAX_SESSIONS_PER_CLIENT", "10"))
MAX_SESSION_CREATES_PER_MINUTE = 10
_session_create_log: dict[str, list[float]] = {}  # IP → [timestamps]


def _check_rate_limit(client_ip: str):
    """세션 생성 rate limit 체크. 초과 시 HTTPException(429) raise."""
    now = time.time()

    # 1) 분당 생성 수 제한
    timestamps = _session_create_log.get(client_ip, [])
    timestamps = [t for t in timestamps if now - t < 60]  # 최근 1분만 유지
    if len(timestamps) >= MAX_SESSION_CREATES_PER_MINUTE:
        raise HTTPException(status_code=429, detail=f"분당 최대 {MAX_SESSION_CREATES_PER_MINUTE}개 세션 생성 제한 초과")

    # 2) 활성 Claude 세션 수 제한 (Shell은 별도 — CLI 프로세스 부하가 다름)
    active_count = sum(1 for s in sessions.values() if s.alive)
    if active_count >= MAX_SESSIONS_PER_CLIENT:
        raise HTTPException(status_code=429, detail=f"최대 활성 세션 수 초과 ({MAX_SESSIONS_PER_CLIENT}개, 현재 {active_count}개 활성)")

    # 기록 추가
    timestamps.append(now)
    _session_create_log[client_ip] = timestamps


# ─── Pydantic 요청 모델 ──────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    work_dir: str = "."
    model: str = ""
    prompt: str = ""
    skip_permissions: bool = False
    mcp_config: str = ""  # MCP 설정 파일 경로 (e.g. ~/.claude/mcp-config.json)

class SendCommandRequest(BaseModel):
    command: str = Field(..., min_length=1, description="실행할 프롬프트")
    attachments: list[str] = Field(default=[], description="첨부 파일 경로 목록")

class GitExecRequest(BaseModel):
    path: str = Field(..., min_length=1)
    command: str = Field(..., min_length=1)

class GitCloneRequest(BaseModel):
    url: str = Field(..., min_length=1)
    dest: str = ""

class ProjectRequest(BaseModel):
    path: str = Field(..., min_length=1)
    name: str = ""

class PipelineStartRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    supervisor_model: str = "sonnet"
    max_iterations: int = Field(default=20, ge=1, le=100)
    max_cycles: int = Field(default=100, ge=1, le=200)
    mode: str = Field(default="cli", pattern="^(api|cli)$")

class ShellCreateRequest(BaseModel):
    shell_type: str = Field(default="cmd", pattern="^(cmd|powershell)$")
    work_dir: str = "."
    cols: int = Field(default=120, ge=40, le=400)
    rows: int = Field(default=30, ge=10, le=200)

class RenameSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)

class ChangeModelRequest(BaseModel):
    model: str = Field(..., max_length=80, description="적용할 모델명 (예: sonnet, opus, haiku, 빈 문자열=CLI 기본값)")

class ForkSessionRequest(BaseModel):
    new_name: str = ""

class PromptTemplate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    prompt: str = Field(..., min_length=1)
    category: str = ""

class ClaudeMdRequest(BaseModel):
    content: str

class CompareRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    models: list[str] = Field(default=["sonnet", "opus", "haiku"])
    work_dir: str = "."
    skip_permissions: bool = True

class PlanPhaseStartRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    mode: str = Field(default="cli", pattern="^(api|cli)$")
    supervisor_model: str = "sonnet"

class PlanPhaseAnswerRequest(BaseModel):
    answers: dict[str, str]  # {"q1": "선택한 답변", "q2": "직접 입력", ...}

class PlanPhaseApproveRequest(BaseModel):
    plan_text: str | None = None  # 유저가 편집한 경우 (None이면 원본 사용)
    max_iterations: int = Field(default=20, ge=1, le=100)
    max_cycles: int = Field(default=100, ge=1, le=200)


# ─── 세션 클래스 ─────────────────────────────────────────────────────────────────

class ClaudeSession:
    """Claude CLI 세션 관리 (print 모드 + stream-json)

    각 세션은 작업 큐를 가지며, 프롬프트를 보내면 Claude CLI를
    -p --output-format stream-json 모드로 실행하여 결과를 스트리밍합니다.
    여러 프롬프트를 보내면 순차적으로 처리됩니다.
    --continue 옵션으로 이전 대화를 이어갑니다.
    """

    def __init__(self, session_id: str, work_dir: str, model: str = "",
                 no_tools: bool = False, skip_permissions: bool = False,
                 mcp_config: str = ""):
        self.id = session_id
        self.name = f"claude-{session_id}"
        self.work_dir = work_dir
        self.model = model  # e.g. "opus", "sonnet", "" = CLI default
        self.no_tools = no_tools  # True면 --tools "" (감독자용)
        self.skip_permissions = skip_permissions  # True면 --dangerously-skip-permissions
        self.mcp_config = mcp_config  # MCP 설정 파일 경로
        self.created_at = datetime.now().isoformat()
        self.alive = True
        self.busy = False  # 현재 Claude 실행 중인지
        self.process: Optional[asyncio.subprocess.Process] = None
        self.output_lines: list[dict] = []  # {type, text, timestamp}
        self.max_lines = 5000
        self.session_uuid: Optional[str] = None  # Claude 세션 ID (--continue 용)
        self.log_filename = f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.log_path = LOGS_DIR / self.log_filename
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._output_version = 0  # WebSocket 변경 감지용
        self.pending_question: Optional[dict] = None  # AskUserQuestion 대기 중
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.pipeline_id: Optional[str] = None       # 바인딩된 파이프라인 ID
        self.pipeline_role: Optional[str] = None      # None | "worker" | "supervisor"
        self._output_event: asyncio.Event = asyncio.Event()  # WS 이벤트 기반 wake-up

    @property
    def _save_path(self) -> Path:
        return SESSIONS_DIR / f"{self.id}.json"

    def save_state(self):
        """세션 상태를 디스크에 저장 (output_lines, session_uuid 등)"""
        try:
            state = {
                "id": self.id,
                "name": self.name,
                "work_dir": self.work_dir,
                "model": self.model,
                "skip_permissions": self.skip_permissions,
                "mcp_config": self.mcp_config,
                "session_uuid": self.session_uuid,
                "created_at": self.created_at,
                "output_lines": self.output_lines[-500:],  # 최근 500줄만 저장
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "pipeline_id": self.pipeline_id,
                "pipeline_role": self.pipeline_role,
            }
            self._save_path.write_text(
                json.dumps(state, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass  # 저장 실패가 메인 동작 방해 금지

    @classmethod
    def load_state(cls, session_id: str) -> "ClaudeSession":
        """디스크에서 세션 복원"""
        path = SESSIONS_DIR / f"{session_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        session = cls(
            data["id"], data["work_dir"], data.get("model", ""),
            skip_permissions=data.get("skip_permissions", False),
            mcp_config=data.get("mcp_config", ""),
        )
        session.name = data.get("name", session.name)
        session.session_uuid = data.get("session_uuid")
        session.output_lines = data.get("output_lines", [])
        session.created_at = data.get("created_at", session.created_at)
        session.total_input_tokens = data.get("total_input_tokens", 0)
        session.total_output_tokens = data.get("total_output_tokens", 0)
        session.pipeline_id = data.get("pipeline_id")
        session.pipeline_role = data.get("pipeline_role")
        session._output_version = len(session.output_lines)
        return session

    def delete_state(self):
        """디스크에서 세션 상태 삭제"""
        try:
            self._save_path.unlink(missing_ok=True)
        except Exception:
            pass

    def start_worker(self):
        self._worker_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        """큐에서 프롬프트를 꺼내 순차적으로 실행"""
        while self.alive:
            try:
                prompt = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            self.busy = True
            self.pending_question = None
            self._append_output("system", f">>> {prompt}")
            try:
                await self._run_claude(prompt)
            except Exception as e:
                self._append_output("error", f"예상치 못한 오류: {str(e)}")
            finally:
                # busy 상태가 절대 stuck 되지 않도록 보장
                self.busy = False
                self.process = None

    async def _run_claude(self, prompt: str, _retry_without_model: bool = False):
        """Claude CLI를 print 모드로 실행하여 결과 스트리밍

        안정성 개선:
        - stdout/stderr 동시 읽기 (deadlock 방지)
        - readline에 타임아웃 적용 (무한 대기 방지)
        - process.wait()에 타임아웃 적용
        - 프로세스 확실한 정리 보장
        """
        if not CLAUDE_EXE:
            self._append_output("error", "Claude CLI를 찾을 수 없습니다 (CLAUDE_EXE not set)")
            return

        use_model = self.model if not _retry_without_model else ""

        cmd = [CLAUDE_EXE, "-p", "--output-format", "stream-json", "--verbose"]
        if self.skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        if self.no_tools:
            cmd.extend(["--tools", ""])

        if use_model:
            cmd.extend(["--model", use_model])

        if self.mcp_config:
            _mcp_path = Path(self.mcp_config).resolve()
            _allowed_mcp = (APP_DIR, Path.home() / ".claude")
            if not any(_mcp_path.is_relative_to(base) for base in _allowed_mcp):
                raise RuntimeError(f"mcp_config 경로가 허용 범위 밖입니다: {_mcp_path}")
            cmd.extend(["--mcp-config", str(_mcp_path)])

        # 이전 세션 이어가기
        if self.session_uuid:
            cmd.extend(["--resume", self.session_uuid])

        cmd.append(prompt)

        stderr_lines = []

        try:
            # 중첩 세션 감지 방지: CLAUDECODE 환경변수 제거
            # ANTHROPIC_API_KEY 제거 → CLI가 OAuth 토큰(Pro/Max 구독) 사용
            env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "ANTHROPIC_API_KEY", "LLM_API_KEY")}
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(Path(self.work_dir).expanduser()) if self.work_dir not in (".",) else None,
                env=env,
                limit=10 * 1024 * 1024,  # 10MB - 큰 출력 처리
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )

            all_output = []

            async def _drain_stderr():
                """stderr를 별도로 비동기 읽기 (deadlock 방지)"""
                try:
                    while True:
                        line = await self.process.stderr.readline()
                        if not line:
                            break
                        decoded = line.decode("utf-8", errors="replace").strip()
                        if decoded:
                            stderr_lines.append(decoded)
                except Exception:
                    pass

            # stderr를 별도 태스크로 동시 읽기 시작
            stderr_task = asyncio.create_task(_drain_stderr())

            # stdout에서 stream-json 읽기 (타임아웃 적용)
            idle_timeout = 600  # 10분 무응답이면 포기
            while True:
                try:
                    line = await asyncio.wait_for(
                        self.process.stdout.readline(),
                        timeout=idle_timeout
                    )
                except asyncio.TimeoutError:
                    self._append_output("error",
                        f"Claude CLI가 {idle_timeout}초 동안 응답이 없어 중단합니다.")
                    await self._force_kill_process()
                    break

                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue

                all_output.append(decoded)
                try:
                    event = json.loads(decoded)
                    if isinstance(event, dict):
                        self._handle_stream_event(event)
                    else:
                        self._append_output("text", decoded)
                except json.JSONDecodeError:
                    self._append_output("text", decoded)

            # stderr 태스크 완료 대기 (최대 5초)
            try:
                await asyncio.wait_for(stderr_task, timeout=5)
            except asyncio.TimeoutError:
                stderr_task.cancel()

            # 프로세스 종료 대기 (최대 10초)
            if self.process and self.process.returncode is None:
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=10)
                except asyncio.TimeoutError:
                    self._append_output("system", "프로세스 종료 대기 시간 초과 → 강제 종료")
                    await self._force_kill_process()

            stderr_text = "\n".join(stderr_lines)

            # 모델 에러 감지 → 기본 모델로 자동 재시도
            combined = stderr_text + " " + " ".join(all_output)
            model_error = (
                "issue with the selected model" in combined
                or "model not found" in combined.lower()
                or "you may not have access" in combined
            )

            if model_error and use_model and not _retry_without_model:
                self._append_output("system",
                    f"모델 '{use_model}' 사용 불가 (구독 플랜 미지원 또는 모델명 오류) → 기본 모델로 전환합니다...")
                # 이후 프롬프트에서도 같은 에러 반복 방지 — 모델 설정 영구 변경
                self.model = ""
                self.process = None
                await self._run_claude(prompt, _retry_without_model=True)
                self.save_state()
                return

            if stderr_text:
                self._append_output("error", stderr_text)

        except asyncio.CancelledError:
            # 태스크 취소 시 프로세스 정리
            await self._force_kill_process()
            raise
        except Exception as e:
            self._append_output("error", f"실행 오류: {str(e)}")
            await self._force_kill_process()
        finally:
            self.process = None

    async def _force_kill_process(self):
        """프로세스를 확실하게 종료"""
        if not self.process:
            return
        try:
            if self.process.returncode is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    self.process.kill()
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        pass  # 최후의 수단 - OS가 정리하도록
        except ProcessLookupError:
            pass  # 이미 종료됨

    def _handle_stream_event(self, event: dict):
        """stream-json 이벤트 처리"""
        if not isinstance(event, dict):
            return
        etype = event.get("type", "")

        if etype == "system":
            # 세션 ID 캡처
            sid = event.get("session_id")
            if sid:
                self.session_uuid = sid
            return

        if etype == "assistant":
            msg = event.get("message", {})
            content_blocks = msg.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    self._append_output("assistant", block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_name = block.get("name", "unknown")
                    tool_input = block.get("input", {})
                    # 간결하게 표시
                    if tool_name == "Bash":
                        cmd = tool_input.get("command", "")
                        self._append_output("tool", f"[Bash] {cmd}")
                    elif tool_name in ("Read", "Write", "Edit"):
                        path = tool_input.get("file_path", "")
                        self._append_output("tool", f"[{tool_name}] {path}")
                    elif tool_name == "AskUserQuestion":
                        # 질문 내용을 풀어서 표시 + 클릭 가능 옵션 저장
                        questions = tool_input.get("questions", [])
                        self.pending_question = tool_input
                        for q in questions:
                            qtext = q.get("question", "")
                            self._append_output("tool", f"[질문] {qtext}")
                            options = q.get("options", [])
                            for i, opt in enumerate(options):
                                label = opt.get("label", "")
                                desc = opt.get("description", "")
                                self._append_output("tool", f"  {i+1}. {label} — {desc}")
                    elif tool_name == "Glob":
                        pattern = tool_input.get("pattern", "")
                        self._append_output("tool", f"[Glob] {pattern}")
                    elif tool_name == "Grep":
                        pattern = tool_input.get("pattern", "")
                        self._append_output("tool", f"[Grep] {pattern}")
                    elif tool_name == "Agent":
                        desc = tool_input.get("description", "")
                        self._append_output("tool", f"[Agent] {desc}")
                    elif tool_name == "TodoWrite":
                        todos = tool_input.get("todos", [])
                        items = ", ".join(t.get("content", "")[:40] for t in todos[:5])
                        self._append_output("tool", f"[TodoWrite] {items}")
                    else:
                        self._append_output("tool", f"[{tool_name}]")
            return

        if etype == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
                if text:
                    # 마지막 라인이 스트리밍 중이면 이어붙이기
                    if self.output_lines and self.output_lines[-1].get("streaming"):
                        self.output_lines[-1]["text"] += text
                        self._output_version += 1
                    else:
                        self._append_output("assistant", text, streaming=True)
            return

        if etype == "content_block_stop":
            # 스트리밍 완료
            if self.output_lines and self.output_lines[-1].get("streaming"):
                self.output_lines[-1]["streaming"] = False
                self._output_version += 1
            return

        if etype == "result":
            # 최종 결과
            result_text = event.get("result", "")
            sid = event.get("session_id")
            if sid:
                self.session_uuid = sid
            # 토큰 사용량 추적
            usage = event.get("usage", {})
            if usage:
                self.total_input_tokens += usage.get("input_tokens", 0)
                self.total_output_tokens += usage.get("output_tokens", 0)
            if result_text and not any(l["text"] == result_text for l in self.output_lines[-5:]):
                self._append_output("result", result_text)
            self._append_output("system", "--- Done ---")
            self.save_state()  # 실행 완료 시 상태 저장
            return

    def _append_output(self, otype: str, text: str, streaming: bool = False):
        """출력 라인 추가"""
        entry = {
            "type": otype,
            "text": text,
            "time": datetime.now().strftime("%H:%M:%S"),
            "streaming": streaming,
        }
        self.output_lines.append(entry)

        if len(self.output_lines) > self.max_lines:
            self.output_lines = self.output_lines[-self.max_lines:]

        self._output_version += 1
        self._output_event.set()  # WS 핸들러 즉시 wake-up

        # 로그 파일 기록 (에러 시 무시 - 이벤트 루프 차단 방지)
        try:
            _LOG_MAX = 10 * 1024 * 1024  # 10MB
            if self.log_path.exists() and self.log_path.stat().st_size >= _LOG_MAX:
                # 로테이션: 기존 파일을 .1로 교체, 새 파일 시작
                rotated = self.log_path.with_suffix(".log.1")
                self.log_path.replace(rotated)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"[{entry['time']}] [{otype}] {text}\n")
        except Exception:
            pass  # 로그 실패가 메인 동작을 방해하지 않도록

    async def send_prompt(self, prompt: str):
        """프롬프트를 큐에 추가"""
        if not self.alive:
            raise RuntimeError(f"세션 {self.id}가 종료된 상태입니다")
        await self._queue.put(prompt)

    async def interrupt(self):
        """현재 실행 중인 프로세스 중단"""
        if self.process and self.process.returncode is None:
            self._append_output("system", "--- Interrupting ---")
            try:
                if sys.platform == "win32":
                    self.process.terminate()
                else:
                    self.process.send_signal(signal.SIGINT)
                # 프로세스 종료 대기
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self.process.kill()
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=3)
                    except asyncio.TimeoutError:
                        pass
            except ProcessLookupError:
                pass  # 이미 종료됨
            self._append_output("system", "--- Interrupted ---")

    async def kill(self):
        """세션 종료"""
        self.alive = False
        await self._force_kill_process()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await asyncio.wait_for(self._worker_task, timeout=3)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        self.busy = False
        self._output_event.set()  # 대기 중인 WebSocket 핸들러를 즉시 깨워 종료 감지

    def get_formatted_output(self, lines: int = 200) -> str:
        """포맷된 출력 텍스트"""
        recent = self.output_lines[-lines:]
        parts = []
        for entry in recent:
            t = entry["time"]
            tp = entry["type"]
            text = entry["text"]
            if tp == "system":
                parts.append(f"\n{text}\n")
            elif tp == "assistant" or tp == "result":
                parts.append(text)
            elif tp == "tool":
                parts.append(f"\n  {text}\n")
            elif tp == "error":
                parts.append(f"\n[ERROR] {text}\n")
            else:
                parts.append(text)
        return "".join(parts)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "work_dir": self.work_dir,
            "model": self.model,
            "created_at": self.created_at,
            "alive": self.alive,
            "busy": self.busy,
            "log_file": self.log_filename,
            "has_session": self.session_uuid is not None,
            "queue_size": self._queue.qsize(),
            "skip_permissions": self.skip_permissions,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "pipeline_id": self.pipeline_id,
            "pipeline_role": self.pipeline_role,
        }

    def export_markdown(self) -> str:
        """대화 내역을 Markdown 형태로 내보내기"""
        lines = [f"# {self.name}", f"- Created: {self.created_at}",
                 f"- Model: {self.model or 'default'}",
                 f"- Working Dir: {self.work_dir}",
                 f"- Tokens: {self.total_input_tokens:,} in / {self.total_output_tokens:,} out",
                 "", "---", ""]
        for entry in self.output_lines:
            t = entry.get("time", "")
            tp = entry.get("type", "")
            text = entry.get("text", "")
            if tp == "system":
                lines.append(f"\n**{text}**\n")
            elif tp == "assistant" or tp == "result":
                lines.append(text)
            elif tp == "tool":
                lines.append(f"\n`{text}`\n")
            elif tp == "error":
                lines.append(f"\n> **ERROR:** {text}\n")
        return "\n".join(lines)


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
        self._loop = asyncio.get_running_loop()  # 스레드에서 call_soon_threadsafe 사용 위해 캡처

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
                print(f"[shell {self.id}] _read_loop unexpected error: {e}")
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


# ─── 파이프라인 엔진 (LLM API / CLI → CLI 루프) ──────────────────────────────────

pipelines: dict = {}
_shutting_down: bool = False  # POST /admin/restart 시 True — 신규 파이프라인 생성 차단

# 감독자 시스템 프롬프트 템플릿
_SUPERVISOR_SYSTEM = """당신은 텍스트 생성기입니다. 도구를 사용하지 마세요. 코드를 실행하지 마세요. 파일을 읽지 마세요.
오직 일반 텍스트만 출력하세요.

당신의 역할: 별도의 Claude Code CLI 작업자에게 보낼 프롬프트를 생성하는 것입니다.

## 목표
{goal}

## 출력 형식 (반드시 준수)
- 도구 호출(function_calls, Bash, Read, Glob 등)을 절대 하지 마세요
- XML 태그, 코드 블록, 함수 호출 형식을 절대 사용하지 마세요
- 한 번에 하나의 구체적인 프롬프트를 일반 텍스트로만 출력하세요
- 설명이나 머리말을 붙이지 마세요. 프롬프트 본문만 출력하세요

## 진행 규칙
- 이전 CLI 결과를 분석하여 다음 단계를 결정하세요
- 에러가 발생했으면 복구/수정 프롬프트를 생성하세요
- 사이클이 마지막({cycle}/{max_cycles})이 아닌 이상 절대 PIPELINE_DONE을 출력하지 마세요
- 진행 중인 작업이 없더라도 목표를 더 완성도 있게 다듬는 다음 프롬프트를 계속 생성하세요
- 목표가 완전히 달성되었고 마지막 사이클이면: PIPELINE_DONE: [완료 요약]

## 현재 상태
- 사이클: {cycle}/{max_cycles}
- 반복: {iteration}/{max_iterations}
- 작업자 CLI 작업 디렉토리: {work_dir}"""


# ─── 계획 수립 시스템 프롬프트 ────────────────────────────────────────────────────

_PLAN_QUESTIONS_SYSTEM = """당신은 소프트웨어 프로젝트 분석가입니다. 도구를 사용하지 마세요. 코드를 실행하지 마세요.
오직 JSON만 출력하세요.

사용자의 목표를 분석하고, 실행 계획을 세우기 전에 명확히 해야 할 질문들을 생성하세요.
사람은 실수하거나 놓치는 부분이 있으므로, 다양한 관점에서 질문하세요.

## 목표
{goal}

## 작업 디렉토리
{work_dir}

## 프로젝트 컨텍스트
{project_context}

## 출력 형식 (반드시 JSON만 출력)
```json
{{
  "questions": [
    {{
      "id": "q1",
      "question": "구체적인 질문 텍스트",
      "why": "이 질문이 중요한 이유 (한 줄)",
      "options": [
        {{"label": "선택지 제목", "description": "선택지 설명"}},
        {{"label": "선택지 제목", "description": "선택지 설명"}}
      ]
    }}
  ]
}}
```

## 규칙
- 5~10개의 질문을 생성하세요
- 각 질문에 2~4개의 예상 답변(options)을 제공하세요
- 프로젝트 컨텍스트를 참고하여 현실적인 옵션을 추천하세요
- 질문은 구체적이고 실행 가능해야 합니다
- 아키텍처, 기술 선택, 범위, 우선순위, 에러 처리, 테스트 등 다양한 관점을 포함하세요
- JSON 외의 텍스트(설명, 머리말, 꼬리말)를 절대 출력하지 마세요"""

_PLAN_GENERATION_SYSTEM = """당신은 소프트웨어 프로젝트 설계자입니다. 도구를 사용하지 마세요. 코드를 실행하지 마세요.
오직 마크다운 형식의 실행 계획만 출력하세요.

사용자의 목표와 질의응답 결과를 바탕으로, 구체적인 단계별 실행 계획을 생성하세요.

## 목표
{goal}

## 작업 디렉토리
{work_dir}

## 프로젝트 컨텍스트
{project_context}

## 질의응답 결과
{qa_summary}

## 출력 형식 (마크다운)
실행 계획을 다음 구조로 작성하세요:

### 요약
- 한 줄 요약

### 단계별 계획
1. **단계 제목** - 설명
   - 대상 파일/경로
   - 구체적 작업 내용
2. **단계 제목** - 설명
   ...

### 주의사항
- 리스크, 의존성, 주의점

### 예상 결과
- 완료 시 기대 결과

## 규칙
- 각 단계는 Claude CLI가 한 번의 프롬프트로 수행할 수 있는 크기여야 합니다
- 파일 경로와 작업 내용을 구체적으로 명시하세요
- 불필요한 단계를 추가하지 마세요
- 설명이나 머리말 없이 바로 계획을 출력하세요"""


class PipelineRunner:
    """감독자(API 또는 CLI)가 작업자 CLI를 반복 구동하는 파이프라인

    mode:
    - "api": Anthropic API (AsyncAnthropic)를 감독자로 사용
    - "cli": 별도 Claude CLI 세션을 감독자로 사용 (API Key 불필요)

    흐름:
    1. 감독자에게 질의 → 다음 프롬프트(또는 DONE) 생성
    2. 작업자 CLI 세션에 프롬프트 전달 → 실행 완료 대기
    3. 작업자 CLI 출력 수집 → 감독자에 전달
    4. 목표 달성 또는 최대 반복 시 종료
    """

    def __init__(self, source_session: ClaudeSession, goal: str,
                 supervisor_model: str, max_iterations: int,
                 mode: str = "api", max_cycles: int = 100):
        self.id = str(uuid.uuid4())[:8]
        self._source_session = source_session  # 원본 세션 (사용자가 선택한 세션)
        self.session: Optional[ClaudeSession] = None  # pw-* 전용 worker (start()에서 생성)
        self.goal = goal
        self.supervisor_model = supervisor_model
        self.max_iterations = max_iterations
        self.max_cycles = max_cycles
        self.current_cycle = 1
        self.mode = mode                # "api" | "cli"
        self.iteration = 0
        self.status = "idle"            # idle | running | completed | failed | stopped
        self.history: list[dict] = []
        self.summary = ""
        self.created_at = datetime.now().isoformat()
        self._task: Optional[asyncio.Task] = None
        self._stop_flag = False
        # CLI 감독자 전용
        self._supervisor_session: Optional[ClaudeSession] = None
        self._supervisor_retries = 0
        self._max_supervisor_retries = 3

    def _create_worker_session(self) -> ClaudeSession:
        """파이프라인 전용 worker 세션(pw-*) 생성

        원본 세션의 work_dir/model/skip_permissions/mcp_config를 상속.
        sessions dict에 등록하여 UI에서 실시간 출력 확인 가능.
        """
        src = self._source_session
        wid = f"pw-{self.id}"
        worker = ClaudeSession(
            wid, src.work_dir, src.model,
            skip_permissions=src.skip_permissions,
            mcp_config=src.mcp_config,
        )
        worker.name = f"pipeline-worker-{self.id}"
        worker.pipeline_id = self.id
        worker.pipeline_role = "worker"
        worker.start_worker()
        sessions[wid] = worker
        worker.save_state()
        return worker

    def start(self):
        self.status = "running"
        create_run(self.id, self._source_session.id, 0)
        try:
            # 전용 worker 세션 생성 (원본 세션은 계속 사용 가능)
            self.session = self._create_worker_session()
        except Exception as e:
            self.status = "failed"
            self._add_history("error", f"worker 세션 생성 실패: {str(e)}")
            raise  # 호출자(start_pipeline)에서 HTTPException으로 변환
        # 원본 세션에 파이프라인 바인딩 표시 (중복 시작 방지용)
        self._source_session.pipeline_id = self.id
        self._source_session.save_state()
        try:
            if self.mode == "cli":
                self._create_supervisor_session()
            self._task = asyncio.create_task(self._run_loop())
        except Exception:
            # supervisor 생성 또는 태스크 생성 실패 시 부분 상태 롤백
            sessions.pop(f"pw-{self.id}", None)
            self._source_session.pipeline_id = None
            self._source_session.save_state()
            raise

    def _create_supervisor_session(self):
        """감독자용 CLI 세션 생성 (도구 차단 — 텍스트만 출력)

        감독자 세션은 sessions dict에 등록하지 않고, save_state를 no-op으로
        오버라이드하여 좀비 파일을 방지한다.
        """
        sid = f"sv-{self.id}"
        sv = ClaudeSession(sid, self._source_session.work_dir, self.supervisor_model,
                           no_tools=True,
                           skip_permissions=self._source_session.skip_permissions)
        sv.pipeline_id = self.id
        sv.pipeline_role = "supervisor"
        sv.save_state = lambda: None  # 디스크에 좀비 파일 방지
        sv.start_worker()
        self._supervisor_session = sv
        self._add_history("system", f"감독자 CLI 세션 생성: {sid} (no-tools)")

    async def stop(self):
        self._stop_flag = True
        self.status = "stopped"
        self._add_history("system", "파이프라인이 사용자에 의해 중단되었습니다.")
        # 감독자/worker 세션 실행 중단 (finally에서 완전 정리됨)
        if self._supervisor_session:
            await self._supervisor_session.kill()
        if self.session:
            await self.session.interrupt()

    def _add_history(self, role: str, content: str):
        self.history.append({
            "role": role,
            "content": content,
            "iteration": self.iteration,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })

    async def _wait_for_session(self, session: ClaudeSession,
                                 timeout: int = 600) -> str:
        """특정 CLI 세션이 busy=False가 될 때까지 대기

        _output_version 기반으로 새 출력이 나오고 + busy가 끝날 때까지 대기.
        기존 방식(busy=True 감지 5초 대기)은 CLI 시작이 느릴 때 race condition 발생.
        """
        start = time.time()
        version_before = session._output_version

        # Phase 1: busy=True 또는 새 출력이 나올 때까지 대기 (최대 30초)
        for _ in range(60):
            if self._stop_flag:
                return "[파이프라인 중단됨]"
            if not session.alive:
                return "[세션 종료]"
            if session.busy or session._output_version != version_before:
                break
            await asyncio.sleep(0.5)

        # Phase 2: busy=False가 될 때까지 대기
        while session.busy:
            if self._stop_flag:
                return "[파이프라인 중단됨]"
            if not session.alive:
                return "[세션 종료]"
            if time.time() - start > timeout:
                self._add_history("system", f"세션 실행 시간 초과 ({timeout}초)")
                return "[시간 초과]"
            await asyncio.sleep(1)

        return session.get_formatted_output(100)

    # ─── 메인 루프 ─────────────────────────────────────

    async def _run_loop(self):
        """메인 파이프라인 루프 — mode에 따라 감독자 방식 분기, 자동 사이클"""
        last_output = ""
        _step = 0  # 전역 누적 스텝 (DB checkpoint 키)
        try:
            while not self._stop_flag:
                # 사이클 내 max_iterations 도달 → 자동 사이클 전환
                if self.iteration >= self.max_iterations:
                    if self.current_cycle < self.max_cycles:
                        self.current_cycle += 1
                        self.iteration = 0
                        self._supervisor_retries = 0
                        self._add_history("system",
                            f"=== 사이클 {self.current_cycle}/{self.max_cycles} 시작 ===")
                        continue
                    else:
                        total = (self.current_cycle - 1) * self.max_iterations + self.iteration
                        self.status = "completed"
                        self.summary = f"최대 사이클({self.max_cycles})×반복({self.max_iterations})={total}회 도달하여 종료"
                        self._add_history("system", self.summary)
                        mark_complete(self.id)
                        return

                self.iteration += 1
                _step = (self.current_cycle - 1) * self.max_iterations + self.iteration
                update_stage(self.id, _step, "running")

                # 1. 감독자 호출
                try:
                    supervisor_response = await self._call_supervisor(last_output)
                except Exception as e:
                    # CLI 모드: 감독자 hang/crash 시 자동 복구 시도
                    if self.mode == "cli" and self._supervisor_retries < self._max_supervisor_retries:
                        self._supervisor_retries += 1
                        self._add_history("system",
                            f"감독자 CLI 오류 → 복구 시도 ({self._supervisor_retries}/{self._max_supervisor_retries}): {str(e)}")
                        await self._recover_supervisor()
                        continue  # 같은 iteration 재시도
                    self._add_history("error", f"감독자 호출 실패: {str(e)}")
                    self.status = "failed"
                    mark_failed(self.id, _step, str(e))
                    return

                # 성공 시 재시도 카운터 리셋
                self._supervisor_retries = 0
                self._add_history("supervisor", supervisor_response)

                # 2. DONE 체크 (마지막 사이클에서만 허용)
                if "PIPELINE_DONE:" in supervisor_response:
                    if self.current_cycle >= self.max_cycles:
                        idx = supervisor_response.index("PIPELINE_DONE:")
                        self.summary = supervisor_response[idx + len("PIPELINE_DONE:"):].strip()
                        self.status = "completed"
                        self._add_history("system", f"파이프라인 완료: {self.summary}")
                        mark_complete(self.id)
                        return
                    else:
                        # 조기 DONE 무시 — 다음 iteration에서 supervisor 재호출
                        self._add_history("system",
                            f"감독자 조기 완료 신호 무시 (사이클 {self.current_cycle}/{self.max_cycles})")
                        last_output = f"[사이클 {self.current_cycle}/{self.max_cycles} 진행 중 — 계속 작업하세요]"
                        continue

                # 3. 작업자 CLI에 프롬프트 전달 (선택한 세션에 직접)
                await self.session.send_prompt(supervisor_response)

                # 4. 작업자 CLI 완료 대기
                last_output = await self._wait_for_session(self.session)
                # worker 세션이 비정상 종료된 경우 파이프라인 실패 처리
                if last_output == "[세션 종료]":
                    self.status = "failed"
                    self._add_history("error", "worker 세션(pw-*)이 예기치 않게 종료되었습니다.")
                    mark_failed(self.id, _step, "worker 세션 비정상 종료")
                    return
                self._add_history("cli_result", last_output)
                save_checkpoint(self.id, _step, {
                    "output": last_output,
                    "cycle": self.current_cycle,
                    "iteration": self.iteration,
                })

        except asyncio.CancelledError:
            # 외부 태스크 취소(서버 shutdown 등) — finally 정리 후 재전파
            self.status = "stopped"
            raise
        except Exception as e:
            # stop()이 이미 status="stopped"를 설정한 경우 덮어쓰지 않음
            if not self._stop_flag:
                self.status = "failed"
                mark_failed(self.id, _step, str(e))
            self._add_history("error", f"파이프라인 오류: {str(e)}")
        finally:
            # 감독자 CLI 세션 정리 (kill + 디스크에서 삭제)
            if self._supervisor_session:
                await self._supervisor_session.kill()
                self._supervisor_session.delete_state()

            # worker 세션(pw-*) 파이프라인 바인딩 해제 (세션 자체는 유지 — UI에서 출력 확인 가능)
            if self.session:
                self.session.pipeline_id = None
                self.session.pipeline_role = None
                self.session.save_state()

            # 원본 세션 파이프라인 바인딩 해제 (다시 일반 세션으로)
            if self._source_session:
                self._source_session.pipeline_id = None
                self._source_session.save_state()

    # ─── 감독자 호출 (모드별 분기) ─────────────────────

    async def _call_supervisor(self, last_output: str) -> str:
        if self.mode == "api":
            return await self._call_supervisor_api(last_output)
        else:
            return await self._call_supervisor_cli(last_output)

    async def _call_supervisor_api(self, last_output: str) -> str:
        """Anthropic API 비동기 호출"""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic 패키지 미설치. pip install anthropic")

        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 환경변수 미설정")
        client = anthropic.AsyncAnthropic(api_key=api_key)

        system_prompt = _SUPERVISOR_SYSTEM.format(
            goal=self.goal,
            cycle=self.current_cycle,
            max_cycles=self.max_cycles,
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            work_dir=self._source_session.work_dir,
        )

        messages = self._build_messages(last_output)

        response = await client.messages.create(
            model=self.supervisor_model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        )

        if not response.content:
            raise RuntimeError("Anthropic API가 빈 content를 반환했습니다")
        return response.content[0].text.strip()

    async def _call_supervisor_cli(self, last_output: str) -> str:
        """감독자 CLI 세션에 프롬프트 전달 → 결과 파싱"""
        sv = self._supervisor_session
        if not sv or not sv.alive:
            raise RuntimeError("감독자 CLI 세션이 종료됨")

        # 감독자에게 보낼 메시지 구성
        system_context = _SUPERVISOR_SYSTEM.format(
            goal=self.goal,
            cycle=self.current_cycle,
            max_cycles=self.max_cycles,
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            work_dir=self._source_session.work_dir,
        )

        if last_output:
            prompt = (
                f"{system_context}\n\n"
                f"---\n[사이클 {self.current_cycle}/{self.max_cycles} | 반복 {self.iteration}/{self.max_iterations}]\n"
                f"작업자 CLI 실행 결과 (최근):\n"
                f"{last_output[-3000:]}\n\n"
                f"위 결과를 분석하고, 다음에 작업자 CLI에 보낼 프롬프트를 생성하세요. "
                f"프롬프트 본문만 출력하세요."
            )
        else:
            prompt = (
                f"{system_context}\n\n"
                f"---\n[사이클 {self.current_cycle}/{self.max_cycles} | 반복 {self.iteration}/{self.max_iterations}]\n"
                f"목표를 달성하기 위한 첫 번째 작업자 CLI 프롬프트를 생성하세요. "
                f"프롬프트 본문만 출력하세요."
            )

        # 감독자 CLI에 전송
        await sv.send_prompt(prompt)

        # 감독자 CLI 완료 대기 (타임아웃 3분 — 감독자는 빨리 끝나야 함)
        result = await self._wait_for_session(sv, timeout=180)

        if result in ("[시간 초과]", "[파이프라인 중단됨]"):
            raise RuntimeError(f"감독자 CLI: {result}")

        # 결과에서 실제 응답 텍스트 추출
        # CLI output에는 시스템 메시지(">>> ...", "--- Done ---" 등)가 포함됨
        # assistant 타입의 마지막 출력만 추출
        return self._extract_cli_response(sv)

    def _extract_cli_response(self, sv: ClaudeSession) -> str:
        """감독자 CLI 세션의 출력에서 assistant 응답만 추출

        도구 호출 XML이 텍스트로 출력된 경우 필터링.
        """
        response_parts = []
        for entry in reversed(sv.output_lines):
            if entry["type"] in ("assistant", "result"):
                response_parts.insert(0, entry["text"])
            elif entry["type"] == "system" and ">>>" in entry["text"]:
                break  # 이전 프롬프트 경계에서 중단

        text = "\n".join(response_parts).strip()

        # function_calls XML 블록 제거
        text = re.sub(
            r'<function_calls>.*?</function_calls>',
            '', text, flags=re.DOTALL
        )
        # 잔여 XML 태그 제거
        text = re.sub(
            r'<function_response>.*?</function_response>',
            '', text, flags=re.DOTALL
        )
        # invoke 태그 등 잔여물
        text = re.sub(r'</?(?:invoke|parameter|function_calls|function_response)[^>]*>', '', text)

        text = text.strip()
        if not text:
            raise RuntimeError("감독자 CLI에서 응답을 추출하지 못함")
        return text

    async def _recover_supervisor(self):
        """감독자 CLI 세션 복구 — kill 후 재생성"""
        self._add_history("system", "감독자 CLI 세션 복구 중...")
        if self._supervisor_session:
            await self._supervisor_session.kill()
        self._create_supervisor_session()
        self._add_history("system", "감독자 CLI 세션 복구 완료")

    # ─── 유틸리티 ──────────────────────────────────────

    def _build_messages(self, last_output: str) -> list[dict]:
        """API 모드용 대화 히스토리 구성"""
        messages = []
        recent = [h for h in self.history if h["role"] in ("supervisor", "cli_result")]
        for h in recent[-10:]:
            if h["role"] == "supervisor":
                messages.append({"role": "assistant", "content": h["content"]})
            elif h["role"] == "cli_result":
                messages.append({"role": "user", "content": h["content"]})

        if last_output:
            user_msg = f"[사이클 {self.current_cycle}/{self.max_cycles} | 반복 {self.iteration}/{self.max_iterations}]\nCLI 실행 결과:\n{last_output[-3000:]}"
        else:
            user_msg = f"[사이클 {self.current_cycle}/{self.max_cycles} | 반복 {self.iteration}/{self.max_iterations}]\n목표를 달성하기 위한 첫 번째 프롬프트를 생성하세요."
        messages.append({"role": "user", "content": user_msg})
        return messages

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session.id if self.session else None,           # pw-* worker 세션 ID
            "source_session_id": self._source_session.id,                      # 원본 세션 ID
            "goal": self.goal,
            "supervisor_model": self.supervisor_model,
            "mode": self.mode,
            "status": self.status,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "current_cycle": self.current_cycle,
            "max_cycles": self.max_cycles,
            "total_iterations": (self.current_cycle - 1) * self.max_iterations + self.iteration,
            "summary": self.summary,
            "created_at": self.created_at,
            "history": self.history[-50:],
            "supervisor_retries": self._supervisor_retries,
        }


# ─── 계획 수립 엔진 (Plan Phase) ──────────────────────────────────────────────────

plan_phases: dict = {}

class PlanPhase:
    """목표 분석 → 질의 생성 → 답변 수집 → 실행계획 생성 → 승인 → 파이프라인 실행

    상태 머신:
    questions_generating → questions_ready → plan_generating → plan_ready → approved / error
    """

    def __init__(self, source_session: ClaudeSession, goal: str,
                 mode: str = "cli", supervisor_model: str = "sonnet"):
        self.id = f"plan-{str(uuid.uuid4())[:8]}"
        self._source_session = source_session
        self.goal = goal
        self.mode = mode
        self.supervisor_model = supervisor_model
        self.status = "idle"
        self.questions: list[dict] = []
        self.answers: dict[str, str] = {}
        self.plan_text = ""
        self.error = ""
        self.pipeline_id: str | None = None
        self.created_at = datetime.now().isoformat()
        self._task: Optional[asyncio.Task] = None
        self._supervisor_session: Optional[ClaudeSession] = None

    def start(self):
        """질문 생성 시작"""
        self.status = "questions_generating"
        self._task = asyncio.create_task(self._generate_questions())

    async def submit_answers(self, answers: dict[str, str]):
        """답변 제출 → 실행계획 생성 시작"""
        self.answers = answers
        self.status = "plan_generating"
        self._task = asyncio.create_task(self._generate_plan())

    async def approve(self, plan_text: str | None,
                      max_iterations: int, max_cycles: int) -> str:
        """계획 승인 → PipelineRunner 생성/시작"""
        if plan_text is not None:
            self.plan_text = plan_text

        # enriched goal 구성
        qa_text = "\n".join(
            f"Q: {self._find_question_text(qid)}\nA: {ans}"
            for qid, ans in self.answers.items()
        )
        enriched_goal = (
            f"## 원래 목표\n{self.goal}\n\n"
            f"## 명확화 Q&A\n{qa_text}\n\n"
            f"## 실행 계획\n{self.plan_text}"
        )

        session = self._source_session
        runner = PipelineRunner(session, enriched_goal, self.supervisor_model,
                                max_iterations, self.mode, max_cycles)
        pipelines[runner.id] = runner
        try:
            runner.start()
        except Exception:
            pipelines.pop(runner.id, None)
            raise
        self.pipeline_id = runner.id
        self.status = "approved"
        return runner.id

    async def regenerate(self):
        """계획 재생성"""
        self.status = "plan_generating"
        self._task = asyncio.create_task(self._generate_plan())

    # ─── LLM 호출 ──────────────────────────────────────

    async def _generate_questions(self):
        """LLM으로 질의 생성"""
        try:
            project_context = self._get_project_context()
            system_prompt = _PLAN_QUESTIONS_SYSTEM.format(
                goal=self.goal,
                work_dir=self._source_session.work_dir,
                project_context=project_context,
            )
            messages = [{"role": "user", "content": f"다음 목표에 대해 명확화 질문을 생성해주세요:\n{self.goal}"}]
            raw = await self._call_llm(system_prompt, messages)
            self.questions = self._parse_questions_json(raw)
            self.status = "questions_ready"
        except Exception as e:
            self.error = str(e)
            self.status = "error"
        finally:
            await self._cleanup_supervisor()

    async def _generate_plan(self):
        """LLM으로 실행계획 생성"""
        try:
            project_context = self._get_project_context()
            qa_summary = "\n".join(
                f"Q: {self._find_question_text(qid)}\nA: {ans}"
                for qid, ans in self.answers.items()
            )
            system_prompt = _PLAN_GENERATION_SYSTEM.format(
                goal=self.goal,
                work_dir=self._source_session.work_dir,
                project_context=project_context,
                qa_summary=qa_summary,
            )
            messages = [{"role": "user", "content": f"목표와 Q&A를 바탕으로 실행 계획을 생성해주세요."}]
            raw = await self._call_llm(system_prompt, messages)
            self.plan_text = raw.strip()
            self.status = "plan_ready"
        except Exception as e:
            self.error = str(e)
            self.status = "error"
        finally:
            await self._cleanup_supervisor()

    async def _call_llm(self, system_prompt: str, messages: list[dict]) -> str:
        """API/CLI 모드 분기 LLM 호출"""
        if self.mode == "api":
            return await self._call_llm_api(system_prompt, messages)
        else:
            return await self._call_llm_cli(system_prompt, messages)

    async def _call_llm_api(self, system_prompt: str, messages: list[dict]) -> str:
        """Anthropic API 비동기 호출"""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic 패키지 미설치. pip install anthropic")

        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 환경변수 미설정")
        client = anthropic.AsyncAnthropic(api_key=api_key)

        response = await client.messages.create(
            model=self.supervisor_model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        )
        if not response.content:
            raise RuntimeError("Anthropic API가 빈 content를 반환했습니다")
        return response.content[0].text.strip()

    async def _call_llm_cli(self, system_prompt: str, messages: list[dict]) -> str:
        """CLI 세션으로 LLM 호출"""
        if not CLAUDE_EXE:
            raise RuntimeError("Claude CLI를 찾을 수 없습니다")

        sid = f"plan-sv-{self.id}"
        sv = ClaudeSession(sid, self._source_session.work_dir, self.supervisor_model,
                           no_tools=True,
                           skip_permissions=self._source_session.skip_permissions)
        sv.save_state = lambda: None
        sv.start_worker()
        self._supervisor_session = sv

        prompt = f"{system_prompt}\n\n---\n{messages[0]['content']}"
        await sv.send_prompt(prompt)

        # 완료 대기 — Phase 1: 세션 시작 감지, Phase 2: 완료 대기
        start_wait = time.time()
        version_before = sv._output_version

        # Phase 1: busy=True 또는 새 출력이 나올 때까지 최대 30초 대기 (CLI 시작 지연 대비)
        for _ in range(60):
            if sv.busy or sv._output_version != version_before:
                break
            await asyncio.sleep(0.5)

        # Phase 2: busy=False가 될 때까지 최대 3분 대기
        while sv.busy:
            if time.time() - start_wait > 180:
                break
            await asyncio.sleep(1)

        # 응답 추출: 마지막 프롬프트 경계(>>> 시스템 메시지) 이후의 assistant/result만 수집
        response_parts = []
        for entry in reversed(sv.output_lines):
            if entry["type"] in ("assistant", "result"):
                response_parts.insert(0, entry["text"])
            elif entry["type"] == "system" and ">>>" in entry["text"]:
                break  # 프롬프트 전송 경계 — 이전 출력 제외
        result = "\n".join(response_parts).strip()

        if not result:
            raise RuntimeError("CLI 감독자가 빈 응답을 반환했습니다")
        return result

    async def _cleanup_supervisor(self):
        """CLI 감독자 세션 정리"""
        if self._supervisor_session:
            sv = self._supervisor_session
            self._supervisor_session = None  # 중복 정리 방지
            try:
                await sv.kill()
            except Exception:
                pass

    # ─── 유틸리티 ──────────────────────────────────────

    def _get_project_context(self) -> str:
        """CLAUDE.md 등에서 프로젝트 컨텍스트 추출"""
        context_parts = []
        work_dir = self._source_session.work_dir
        for name in ["CLAUDE.md", "README.md"]:
            fpath = os.path.join(work_dir, name)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read(3000)
                    context_parts.append(f"=== {name} ===\n{content}")
                except Exception:
                    pass
        return "\n\n".join(context_parts) if context_parts else "(프로젝트 컨텍스트 없음)"

    def _find_question_text(self, qid: str) -> str:
        """질문 ID로 질문 텍스트 찾기"""
        for q in self.questions:
            if q.get("id") == qid:
                return q.get("question", qid)
        return qid

    def _parse_questions_json(self, raw: str) -> list[dict]:
        """LLM 응답에서 질문 JSON 파싱"""
        # markdown code fence 제거
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
        text = match.group(1) if match else raw

        try:
            data = json.loads(text.strip())
        except json.JSONDecodeError:
            # 한 번 더 시도: 앞뒤 텍스트 제거 후 JSON 블록만 추출
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise RuntimeError(f"JSON 파싱 실패: {text[:200]}")

        questions = data.get("questions", [])
        for i, q in enumerate(questions):
            q.setdefault("id", f"q{i+1}")
            q.setdefault("question", "")
            q.setdefault("why", "")
            q.setdefault("options", [])
        return questions

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self._source_session.id,
            "goal": self.goal,
            "mode": self.mode,
            "supervisor_model": self.supervisor_model,
            "status": self.status,
            "questions": self.questions,
            "answers": self.answers,
            "plan_text": self.plan_text,
            "error": self.error,
            "pipeline_id": self.pipeline_id,
            "created_at": self.created_at,
        }


# ─── API 엔드포인트 ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return FRONTEND_HTML


@app.get("/health")
async def health():
    return {
        "status": "healthy" if CLAUDE_EXE else "degraded",
        "sessions": len(sessions),
        "claude_cli": CLAUDE_EXE is not None,
    }


@app.get("/api/stats")
async def stats():
    """서버 통계 — 세션, 파이프라인, Shell 상태 요약"""
    active_sessions = sum(1 for s in sessions.values() if s.alive)
    busy_sessions = sum(1 for s in sessions.values() if s.busy)
    running_pipelines = sum(1 for p in pipelines.values() if p.status == "running")
    active_shells = sum(1 for sh in shell_sessions.values() if sh.alive)
    return {
        "sessions": {"total": len(sessions), "active": active_sessions, "busy": busy_sessions},
        "pipelines": {"total": len(pipelines), "running": running_pipelines},
        "shells": {"total": len(shell_sessions), "active": active_shells},
        "claude_cli": CLAUDE_EXE is not None,
        "shell_available": HAS_WINPTY,
    }


@app.get("/api/sessions")
async def list_sessions():
    return [s.to_dict() for s in list(sessions.values())]


@app.post("/api/sessions")
async def create_session(body: CreateSessionRequest, request: Request):
    if not CLAUDE_EXE:
        raise HTTPException(status_code=503, detail="Claude CLI not available")

    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    session_id = str(uuid.uuid4())[:8]
    session = ClaudeSession(session_id, body.work_dir, body.model,
                            skip_permissions=body.skip_permissions,
                            mcp_config=body.mcp_config)
    session.start_worker()
    sessions[session_id] = session
    session.save_state()  # 생성 시 저장

    if body.prompt:
        await session.send_prompt(body.prompt)

    return {"id": session_id, "name": session.name, "status": "created"}


@app.delete("/api/sessions/{session_id}")
async def kill_session(session_id: str, remove: bool = Query(False)):
    """세션 종료. remove=true면 목록에서도 제거"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    session = sessions[session_id]
    await session.kill()
    if remove:
        session.delete_state()  # 디스크에서도 삭제
        del sessions[session_id]
        return {"status": "removed"}
    session.save_state()  # kill 상태 저장
    return {"status": "killed"}


@app.post("/api/sessions/{session_id}/send")
async def send_command(session_id: str, body: SendCommandRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")

    prompt = body.command
    if body.attachments:
        safe_paths = []
        for p in body.attachments:
            try:
                resolved = Path(p).resolve()
                if resolved.is_relative_to(UPLOADS_DIR) or resolved.is_relative_to(SCREENSHOTS_DIR):
                    safe_paths.append(str(resolved))
                # else: 범위 밖 경로 무시
            except Exception:
                pass
        if safe_paths:
            file_refs = "\n".join(f"- {p}" for p in safe_paths)
            prompt = f"다음 파일을 확인하세요:\n{file_refs}\n\n{prompt}"

    session = sessions[session_id]
    if not session.alive:
        raise HTTPException(status_code=409, detail="세션이 종료된 상태입니다")
    await session.send_prompt(prompt)
    return {"status": "queued", "queue_size": session._queue.qsize()}


@app.post("/api/sessions/{session_id}/upload")
async def upload_file(session_id: str, file: UploadFile = File(...)):
    """파일 업로드 — 이미지, PDF, 텍스트 등"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")

    allowed = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".pdf", ".txt", ".md"}
    ext = Path(file.filename or "unknown").suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"허용되지 않은 파일 형식: {ext}")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="파일 크기 10MB 초과")

    # 파일명 정규화 — path traversal 차단
    raw_name = file.filename or "upload"
    base_name = os.path.basename(raw_name.replace("\\", "/"))  # Windows 경로 구분자도 처리
    if not base_name or ".." in base_name:
        raise HTTPException(status_code=400, detail="잘못된 파일명")

    session_dir = UPLOADS_DIR / session_id
    session_dir.mkdir(exist_ok=True)
    if session_dir.exists() and len(list(session_dir.iterdir())) >= 50:
        raise HTTPException(status_code=429, detail="업로드 파일 수 한도 초과 (최대 50개)")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{ts}_{base_name}"
    filepath = session_dir / safe_name

    # resolved path가 upload 디렉토리 밖이면 거부 (심볼릭 링크 등 우회 방지)
    if not filepath.resolve().is_relative_to(session_dir.resolve()):
        raise HTTPException(status_code=400, detail="잘못된 파일 경로")

    filepath.write_bytes(content)

    return {
        "filename": safe_name,
        "path": str(filepath.resolve()),
        "url": f"/uploads/{session_id}/{safe_name}",
        "size": len(content),
    }


@app.post("/api/sessions/{session_id}/interrupt")
async def interrupt_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    await sessions[session_id].interrupt()
    return {"status": "interrupted"}


@app.get("/api/sessions/{session_id}/output")
async def get_output(session_id: str, lines: int = Query(200, ge=1, le=5000)):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    output = sessions[session_id].get_formatted_output(lines)
    return {"output": output}


@app.patch("/api/sessions/{session_id}/rename")
async def rename_session(session_id: str, body: RenameSessionRequest):
    """세션 이름 변경"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    sessions[session_id].name = body.name.strip()
    sessions[session_id].save_state()
    return {"status": "renamed", "name": body.name.strip()}


@app.patch("/api/sessions/{session_id}/model")
async def change_session_model(session_id: str, body: ChangeModelRequest):
    """세션 모델 변경"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    new_model = body.model.strip()
    sessions[session_id].model = new_model
    # 다음 실행부터 새 모델 적용 (session_uuid 리셋하여 새 세션으로)
    sessions[session_id].session_uuid = None
    sessions[session_id].save_state()
    return {"status": "model_changed", "model": new_model}


@app.get("/api/sessions/{session_id}/export")
async def export_session(session_id: str):
    """세션 대화를 Markdown으로 내보내기"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    md = sessions[session_id].export_markdown()
    return {"markdown": md, "name": sessions[session_id].name}


@app.post("/api/sessions/{session_id}/fork")
async def fork_session(session_id: str, body: ForkSessionRequest, request: Request):
    """세션 복제 — 대화 기록과 session_uuid를 복사하여 분기"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)
    src = sessions[session_id]
    new_id = str(uuid.uuid4())[:8]
    forked = ClaudeSession(new_id, src.work_dir, src.model,
                           skip_permissions=src.skip_permissions,
                           mcp_config=src.mcp_config)
    forked.name = body.new_name or f"{src.name}-fork"
    forked.session_uuid = src.session_uuid  # 같은 대화 이어가기 가능
    forked.output_lines = list(src.output_lines)  # 히스토리 복사
    forked.total_input_tokens = src.total_input_tokens
    forked.total_output_tokens = src.total_output_tokens
    forked._output_version = len(forked.output_lines)
    forked._append_output("system", f"=== Forked from {src.name} ===")
    forked.start_worker()
    sessions[new_id] = forked
    forked.save_state()
    return {"id": new_id, "name": forked.name, "status": "forked"}


# ─── 프롬프트 템플릿 ──────────────────────────────────────────────────────────
TEMPLATES_FILE = DATA_DIR / "templates.json"


def _load_templates() -> list[dict]:
    if TEMPLATES_FILE.exists():
        try:
            return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # 손상된 파일 보존 후 빈 목록 반환
            TEMPLATES_FILE.replace(TEMPLATES_FILE.with_suffix(".json.bak"))
            return []
    return []


def _save_templates(templates: list[dict]):
    """템플릿 저장 (원자적 쓰기 — partial write 방지)"""
    tmp = Path(str(TEMPLATES_FILE) + ".tmp")
    tmp.write_text(json.dumps(templates, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, TEMPLATES_FILE)


@app.get("/api/templates")
async def list_templates():
    return _load_templates()


@app.post("/api/templates")
async def create_template(body: PromptTemplate):
    templates = _load_templates()
    entry = {"id": str(uuid.uuid4())[:8], "name": body.name,
             "prompt": body.prompt, "category": body.category,
             "created_at": datetime.now().isoformat()}
    templates.append(entry)
    _save_templates(templates)
    return entry


@app.delete("/api/templates/{template_id}")
async def delete_template(template_id: str):
    templates = _load_templates()
    templates = [t for t in templates if t.get("id") != template_id]
    _save_templates(templates)
    return {"status": "deleted"}


# ─── CLAUDE.md 편집 ──────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/claude-md")
async def get_claude_md(session_id: str):
    """세션 작업 디렉토리의 CLAUDE.md 읽기"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    work_dir = sessions[session_id].work_dir
    claude_md = Path(work_dir) / "CLAUDE.md"
    content = ""
    if claude_md.exists():
        try:
            content = claude_md.read_text(encoding="utf-8")
        except Exception as e:
            print(f"ERROR [get_claude_md]: {e}")
            raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다")
    return {"content": content, "path": str(claude_md)}


@app.put("/api/sessions/{session_id}/claude-md")
async def update_claude_md(session_id: str, body: ClaudeMdRequest):
    """세션 작업 디렉토리의 CLAUDE.md 저장"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    work_dir = sessions[session_id].work_dir
    claude_md = Path(work_dir) / "CLAUDE.md"
    try:
        claude_md.write_text(body.content, encoding="utf-8")
    except Exception as e:
        print(f"ERROR [update_claude_md]: {e}")
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다")
    return {"status": "saved", "path": str(claude_md)}


# ─── 멀티 모델 비교 ──────────────────────────────────────────────────────────

@app.post("/api/compare")
async def compare_models(body: CompareRequest, request: Request):
    """같은 프롬프트를 여러 모델에 보내고 결과 비교"""
    if not CLAUDE_EXE:
        raise HTTPException(status_code=503, detail="Claude CLI not available")
    client_ip = request.client.host if request.client else "unknown"
    model_count = len(body.models[:4])
    # 생성할 세션 수만큼 여유가 있는지 사전 확인 (rate limit 1회 체크 후 N개 생성 우회 방지)
    active_count = sum(1 for s in sessions.values() if s.alive)
    if active_count + model_count > MAX_SESSIONS_PER_CLIENT:
        raise HTTPException(
            status_code=429,
            detail=f"세션 한도 초과: 현재 {active_count}개 활성, {model_count}개 추가 시 한도({MAX_SESSIONS_PER_CLIENT}) 초과"
        )
    _check_rate_limit(client_ip)

    results = {}
    for model in body.models[:4]:  # 최대 4개
        sid = f"cmp-{str(uuid.uuid4())[:6]}"
        session = ClaudeSession(sid, body.work_dir, model,
                                skip_permissions=body.skip_permissions)
        session.name = f"compare-{model}"
        session.start_worker()
        sessions[sid] = session
        await session.send_prompt(body.prompt)
        results[model] = sid

    return {"status": "started", "sessions": results}


@app.websocket("/ws/{session_id}")
async def websocket_output(websocket: WebSocket, session_id: str):
    await websocket.accept()

    if session_id not in sessions:
        await websocket.send_json({"error": "세션 없음"})
        await websocket.close()
        return

    session = sessions[session_id]
    last_version = -1
    dead_count = 0  # 죽은 세션 감지 카운터 (각 카운트 ≈ 30초)

    try:
        while True:
            # 세션이 목록에서 제거되었으면 종료
            if session_id not in sessions:
                await websocket.send_json({"error": "세션 제거됨"})
                break

            if session._output_version != last_version:
                # 새 출력 있음 → 이벤트 클리어 후 즉시 전송 (clear를 send 전에 수행해야
                # send 완료 ~ clear 사이에 도착한 이벤트를 소실하지 않음)
                session._output_event.clear()
                try:
                    output = session.get_formatted_output(200)
                    msg = {
                        "output": output,
                        "alive": session.alive,
                        "busy": session.busy,
                        "queue_size": session._queue.qsize(),
                        "tokens": {
                            "input": session.total_input_tokens,
                            "output": session.total_output_tokens,
                        },
                    }
                    if session.pending_question:
                        msg["pending_question"] = session.pending_question
                    await asyncio.wait_for(
                        websocket.send_json(msg),
                        timeout=5  # WebSocket 전송 타임아웃
                    )
                    last_version = session._output_version
                    dead_count = 0
                except asyncio.TimeoutError:
                    break  # 클라이언트 응답 없음 → 연결 종료
            else:
                # 변경 없음 → 이벤트 대기 (최대 30초, 연결 유지 ping 역할)
                session._output_event.clear()
                try:
                    await asyncio.wait_for(session._output_event.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass  # timeout → 죽은 세션 체크 후 루프 재진입

                # 죽은 세션이 30초 이상 응답 없으면 종료 (3회 × 30초 = 90초)
                if not session.alive and not session.busy:
                    dead_count += 1
                    if dead_count > 3:
                        break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[ws/output:{session_id}] unexpected error: {e}")


# ─── 로그 관리 ───────────────────────────────────────────────────────────────────

@app.get("/api/logs")
async def list_logs():
    logs = []
    for f in sorted(LOGS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = f.stat()
        logs.append({
            "filename": f.name,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return logs


@app.get("/api/logs/{filename}")
async def get_log(filename: str, search: Optional[str] = Query(None)):
    # 보안: path traversal 방지 — 파일명에 경로 구분자나 상위 디렉토리 참조 차단
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="잘못된 파일명")
    log_path = (LOGS_DIR / filename).resolve()
    if not log_path.is_relative_to(LOGS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="잘못된 파일명")
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="로그 없음")

    content = log_path.read_text(encoding="utf-8", errors="replace")

    if search:
        lines = content.split("\n")
        matched = [l for l in lines if search.lower() in l.lower()]
        return {"filename": filename, "search": search, "matches": len(matched), "content": "\n".join(matched)}

    return {"filename": filename, "content": content}


# ─── 폴더 탐색 & 프로젝트 관리 ──────────────────────────────────────────────────

@app.get("/api/browse")
async def browse_folder(path: str = Query("")):
    """폴더 탐색 - 하위 디렉토리 목록 반환"""
    if not path:
        # 기본: 드라이브 목록 (Windows)
        if sys.platform == "win32":
            drives = []
            for letter in string.ascii_uppercase:
                dp = Path(f"{letter}:\\")
                if dp.exists():
                    drives.append({"name": f"{letter}:\\", "path": f"{letter}:\\", "type": "drive"})
            return {"current": "", "parent": "", "items": drives}
        else:
            path = "/"

    folder = Path(path)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="유효하지 않은 경로")

    items = []
    try:
        for entry in sorted(folder.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                # git 프로젝트인지 확인
                is_git = (entry / ".git").exists()
                items.append({
                    "name": entry.name,
                    "path": str(entry),
                    "type": "project" if is_git else "folder",
                })
    except PermissionError:
        pass

    parent = str(folder.parent) if folder.parent != folder else ""

    return {"current": str(folder), "parent": parent, "items": items}


@app.get("/api/projects")
async def get_projects():
    """저장된 프로젝트 목록"""
    return load_projects()


@app.post("/api/projects")
async def add_project(body: ProjectRequest):
    """프로젝트 즐겨찾기 추가"""
    path = body.path
    name = body.name or Path(path).name

    if not Path(path).exists():
        raise HTTPException(status_code=400, detail="유효하지 않은 경로")

    projects = load_projects()
    # 중복 방지
    if any(p["path"] == path for p in projects):
        return {"status": "already_exists"}

    projects.append({
        "name": name,
        "path": path,
        "added_at": datetime.now().isoformat(),
    })
    save_projects(projects)
    return {"status": "added"}


@app.delete("/api/projects")
async def remove_project(body: ProjectRequest):
    """프로젝트 즐겨찾기 삭제"""
    path = body.path
    projects = load_projects()
    projects = [p for p in projects if p["path"] != path]
    save_projects(projects)
    return {"status": "removed"}


# ─── Git 연동 ─────────────────────────────────────────────────────────────────────

async def run_git(args: list[str], cwd: str) -> dict:
    """git 명령 실행 헬퍼"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        return {
            "ok": proc.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace").strip(),
            "stderr": stderr.decode("utf-8", errors="replace").strip(),
        }
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return {"ok": False, "stdout": "", "stderr": "Timeout (30s)"}
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": "git not found"}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e)}


async def run_gh(args: list[str], cwd: str) -> dict:
    """gh CLI 명령 실행 헬퍼"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "gh", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        return {
            "ok": proc.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace").strip(),
            "stderr": stderr.decode("utf-8", errors="replace").strip(),
        }
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return {"ok": False, "stdout": "", "stderr": "Timeout (30s)"}
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": "gh CLI not found — gh를 설치하거나 PATH에 추가하세요"}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e)}


@app.get("/api/git/status")
async def git_status(path: str = Query(...)):
    """git status --porcelain + branch info"""
    if not Path(path).exists():
        raise HTTPException(status_code=400, detail="경로 없음")

    # 4개 git 명령을 병렬 실행 (순차 실행 시 멈춤/느림 방지)
    branch_res, status_res, remote_res, behind_res = await asyncio.gather(
        run_git(["branch", "--show-current"], path),
        run_git(["status", "--porcelain", "-u"], path),
        run_git(["log", "--oneline", "@{u}..HEAD"], path),
        run_git(["log", "--oneline", "HEAD..@{u}"], path),
    )

    ahead = len(remote_res["stdout"].splitlines()) if remote_res["ok"] and remote_res["stdout"] else 0
    behind = len(behind_res["stdout"].splitlines()) if behind_res["ok"] and behind_res["stdout"] else 0

    # 파일별 상태 파싱
    files = []
    if status_res["ok"] and status_res["stdout"]:
        for line in status_res["stdout"].splitlines():
            if len(line) >= 4:
                xy = line[:2]
                fname = line[3:]
                files.append({"status": xy.strip(), "file": fname})

    return {
        "branch": branch_res["stdout"] if branch_res["ok"] else "unknown",
        "files": files,
        "ahead": ahead,
        "behind": behind,
        "clean": len(files) == 0,
    }


@app.get("/api/git/log")
async def git_log(path: str = Query(...), limit: int = Query(20)):
    """git log 최근 커밋 목록"""
    if not Path(path).exists():
        raise HTTPException(status_code=400, detail="경로 없음")

    res = await run_git([
        "log", f"-{limit}", "--format=%H|%h|%an|%ar|%s"
    ], path)

    commits = []
    if res["ok"] and res["stdout"]:
        for line in res["stdout"].splitlines():
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0],
                    "short": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                    "message": parts[4],
                })

    return {"commits": commits}


@app.get("/api/git/branches")
async def git_branches(path: str = Query(...)):
    """브랜치 목록"""
    if not Path(path).exists():
        raise HTTPException(status_code=400, detail="경로 없음")

    res = await run_git(["branch", "-a", "--format=%(refname:short)|%(HEAD)"], path)
    branches = []
    current = ""
    if res["ok"] and res["stdout"]:
        for line in res["stdout"].splitlines():
            parts = line.split("|", 1)
            name = parts[0].strip()
            is_current = len(parts) > 1 and parts[1].strip() == "*"
            if is_current:
                current = name
            branches.append({"name": name, "current": is_current})

    return {"branches": branches, "current": current}


@app.get("/api/git/diff")
async def git_diff(path: str = Query(...), cached: bool = Query(False)):
    """git diff (staged or unstaged)"""
    if not Path(path).exists():
        raise HTTPException(status_code=400, detail="경로 없음")

    args = ["diff", "--stat"]
    if cached:
        args.append("--cached")
    res = await run_git(args, path)
    return {"diff": res["stdout"] if res["ok"] else res["stderr"]}


@app.post("/api/git/exec")
async def git_exec(body: GitExecRequest):
    """git 명령 실행 (commit, push, pull, checkout 등)"""
    path = body.path
    command = body.command

    if not Path(path).exists():
        raise HTTPException(status_code=400, detail="경로 없음")

    # 보안: allow-list 기반 git 명령 제어 (shell injection 방지)
    try:
        parts = shlex.split(command)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"명령어 파싱 오류: {e}")

    if not parts:
        raise HTTPException(status_code=400, detail="명령어 필요")

    subcommand = parts[0]

    # 읽기 전용 (항상 허용)
    READONLY_COMMANDS = {"status", "log", "diff", "show", "branch", "remote", "fetch", "tag"}
    # 쓰기 명령 (ALLOW_GIT_WRITE=true 환경변수 필요, 기본 허용)
    WRITE_COMMANDS = {
        "add", "commit", "push", "pull", "checkout", "switch",
        "merge", "rebase", "stash", "restore", "cherry-pick", "revert",
    }
    # 절대 금지
    FORBIDDEN_COMMANDS = {"clean", "gc", "filter-branch", "reflog"}

    if subcommand in FORBIDDEN_COMMANDS:
        raise HTTPException(status_code=403, detail=f"금지된 git 명령: {subcommand}")

    if subcommand not in READONLY_COMMANDS and subcommand not in WRITE_COMMANDS:
        raise HTTPException(status_code=403, detail=f"허용되지 않은 git 명령: {subcommand}. 허용: {', '.join(sorted(READONLY_COMMANDS | WRITE_COMMANDS))}")

    if subcommand in WRITE_COMMANDS:
        allow_write = os.environ.get("ALLOW_GIT_WRITE", "true").lower() == "true"
        if not allow_write:
            raise HTTPException(status_code=403, detail=f"쓰기 명령 비활성화됨: {subcommand} (ALLOW_GIT_WRITE=true 필요)")

    # 위험한 플래그 차단 (쓰기 명령에서만)
    DANGEROUS_FLAGS = {"--force", "-f", "--force-with-lease", "--hard", "--no-verify", "-D", "--delete"}
    if subcommand in WRITE_COMMANDS:
        for flag in parts[1:]:
            if flag in DANGEROUS_FLAGS:
                raise HTTPException(status_code=403, detail=f"차단된 플래그: {flag} (명령: git {subcommand})")

    # subprocess_exec로 실행 (shell=False — injection 불가)
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", *parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=path,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        return {
            "ok": proc.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace").strip(),
            "stderr": stderr.decode("utf-8", errors="replace").strip(),
        }
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return {"ok": False, "stdout": "", "stderr": "Timeout (60s)"}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e)}


@app.get("/api/git/prs")
async def git_prs(path: str = Query(...), state: str = Query("open")):
    """GitHub PR 목록 (gh CLI 필요)"""
    if not Path(path).exists():
        raise HTTPException(status_code=400, detail="경로 없음")

    res = await run_gh([
        "pr", "list", "--state", state,
        "--json", "number,title,author,state,url,createdAt,headRefName",
        "--limit", "20"
    ], path)

    if res["ok"] and res["stdout"]:
        try:
            return {"prs": json.loads(res["stdout"])}
        except json.JSONDecodeError:
            return {"prs": [], "error": res["stdout"]}

    return {"prs": [], "error": res["stderr"]}


@app.get("/api/git/issues")
async def git_issues(path: str = Query(...), state: str = Query("open")):
    """GitHub Issue 목록 (gh CLI 필요)"""
    if not Path(path).exists():
        raise HTTPException(status_code=400, detail="경로 없음")

    res = await run_gh([
        "issue", "list", "--state", state,
        "--json", "number,title,author,state,url,createdAt,labels",
        "--limit", "20"
    ], path)

    if res["ok"] and res["stdout"]:
        try:
            return {"issues": json.loads(res["stdout"])}
        except json.JSONDecodeError:
            return {"issues": [], "error": res["stdout"]}

    return {"issues": [], "error": res["stderr"]}


@app.get("/api/git/remote")
async def git_remote(path: str = Query(...)):
    """Remote 정보 조회"""
    if not Path(path).exists():
        raise HTTPException(status_code=400, detail="경로 없음")

    # git remote와 gh repo view를 병렬 실행
    res, gh_res = await asyncio.gather(
        run_git(["remote", "-v"], path),
        run_gh(["repo", "view", "--json", "name,owner,url,description,defaultBranchRef,stargazerCount,forkCount,isPrivate"], path),
    )
    remotes = []
    if res["ok"] and res["stdout"]:
        seen = set()
        for line in res["stdout"].splitlines():
            parts = line.split()
            if len(parts) >= 2:
                key = f"{parts[0]}|{parts[1]}"
                if key not in seen:
                    seen.add(key)
                    remotes.append({"name": parts[0], "url": parts[1]})

    # GitHub repo 정보 (gh CLI)
    gh_info = None
    if gh_res["ok"] and gh_res["stdout"]:
        try:
            gh_info = json.loads(gh_res["stdout"])
        except json.JSONDecodeError:
            pass

    return {"remotes": remotes, "github": gh_info}


@app.get("/api/git/gh-auth")
async def gh_auth_status():
    """gh CLI 인증 상태 확인"""
    res = await run_gh(["auth", "status"], ".")
    # gh auth status는 stderr에 출력함
    output = res["stderr"] or res["stdout"]
    logged_in = "Logged in" in output
    return {"ok": logged_in, "output": output}


@app.post("/api/git/clone")
async def git_clone(body: GitCloneRequest):
    """GitHub repo 클론"""
    url = body.url.strip()
    dest = body.dest.strip()

    # URL 프로토콜 검증 — https:// 또는 git@ 만 허용 (file://, ftp:// 등 차단)
    if not (url.startswith("https://") or url.startswith("git@")):
        raise HTTPException(status_code=400, detail="허용되지 않은 URL 프로토콜. https:// 또는 git@ 만 사용 가능 (http:// 차단)")

    # 셸 메타문자 차단 (command injection 방지)
    if re.search(r'[;|&$`\'"\\\n\r]', url):
        raise HTTPException(status_code=400, detail="URL에 허용되지 않은 문자가 포함됨")

    # dest가 없으면 현재 디렉토리에 repo 이름으로
    if dest:
        dest_path = Path(dest).resolve()
        # path traversal 및 시스템 디렉토리 보호:
        # 절대 경로로 정규화 후 홈 디렉토리 또는 프로젝트 루트 하위여야 함
        _allowed_clone_roots = (Path.home(), APP_DIR.parent.parent)
        if not any(dest_path.is_relative_to(r) for r in _allowed_clone_roots):
            raise HTTPException(
                status_code=400,
                detail=f"허용되지 않는 대상 경로입니다. 홈 디렉토리 또는 프로젝트 루트 하위만 허용됩니다."
            )
    else:
        # URL에서 repo 이름 추출
        repo_name = url.rstrip("/").split("/")[-1].replace(".git", "").strip()
        if not repo_name:
            raise HTTPException(status_code=400, detail="URL에서 repo 이름을 추출할 수 없습니다")
        dest_path = Path(".").resolve() / repo_name

    if dest_path.exists():
        try:
            not_empty = any(dest_path.iterdir())
        except PermissionError:
            raise HTTPException(status_code=400, detail=f"디렉토리 접근 권한 없음: {dest_path}")
        if not_empty:
            raise HTTPException(status_code=400, detail=f"디렉토리가 이미 존재함: {dest_path}")

    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", url, str(dest_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        ok = proc.returncode == 0
        return {
            "ok": ok,
            "path": str(dest_path.resolve()) if ok else "",
            "stdout": stdout.decode("utf-8", errors="replace").strip(),
            "stderr": stderr.decode("utf-8", errors="replace").strip(),
        }
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return {"ok": False, "path": "", "stdout": "", "stderr": "Timeout (120s)"}
    except Exception as e:
        return {"ok": False, "path": "", "stdout": "", "stderr": str(e)}


@app.get("/api/git/gh-repos")
async def gh_repos(query: str = Query("")):
    """GitHub repo 검색 또는 내 repo 목록"""
    if query:
        res = await run_gh(["search", "repos", query, "--json", "fullName,description,url,stargazersCount,isPrivate,updatedAt", "--limit", "10"], ".")
    else:
        res = await run_gh(["repo", "list", "--json", "name,owner,url,description,isPrivate,updatedAt", "--limit", "20"], ".")

    if res["ok"] and res["stdout"]:
        try:
            return {"repos": json.loads(res["stdout"])}
        except json.JSONDecodeError:
            return {"repos": [], "error": res["stdout"]}

    return {"repos": [], "error": res["stderr"]}


# ─── 파이프라인 API ────────────────────────────────────────────────────────────────

@app.post("/api/pipelines")
async def start_pipeline(body: PipelineStartRequest):
    """파이프라인 시작 — 감독자(API 또는 CLI)가 작업자 CLI를 반복 구동"""
    if _shutting_down:
        raise HTTPException(status_code=503, detail="서버 종료 준비 중 — 신규 파이프라인 생성 불가")
    if body.session_id not in sessions:
        raise HTTPException(status_code=400, detail="유효한 세션 ID 필요")
    if body.mode == "api":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=400, detail="API 모드에서는 ANTHROPIC_API_KEY 환경변수 필요")
    if body.mode == "cli" and not CLAUDE_EXE:
        raise HTTPException(status_code=400, detail="CLI 모드에서는 Claude CLI 필요")

    session = sessions[body.session_id]

    # 세션이 이미 파이프라인에 바인딩되어 있으면 충돌 방지
    if session.pipeline_id:
        raise HTTPException(
            status_code=409,
            detail=f"Session already bound to pipeline {session.pipeline_id}")

    runner = PipelineRunner(session, body.goal, body.supervisor_model,
                            body.max_iterations, body.mode, body.max_cycles)
    pipelines[runner.id] = runner
    try:
        runner.start()
    except Exception as e:
        pipelines.pop(runner.id, None)
        raise HTTPException(status_code=500, detail=f"파이프라인 시작 실패: {str(e)}")

    return {
        "pipeline_id": runner.id,
        "session_id": session.id,
        "worker_session_id": runner.session.id if runner.session else None,  # pw-* worker
        "status": runner.status,
        "mode": body.mode,
    }


# 하위호환: 기존 /api/pipeline/start 경로 유지
@app.post("/api/pipeline/start")
async def start_pipeline_compat(body: PipelineStartRequest):
    return await start_pipeline(body)


@app.get("/api/pipelines")
async def list_pipelines():
    return [p.to_dict() for p in pipelines.values()]


@app.get("/api/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    if pipeline_id not in pipelines:
        raise HTTPException(status_code=404, detail="파이프라인 없음")
    return pipelines[pipeline_id].to_dict()


# 하위호환
@app.get("/api/pipeline/{pipeline_id}")
async def get_pipeline_compat(pipeline_id: str):
    return await get_pipeline(pipeline_id)


@app.post("/api/pipelines/{pipeline_id}/stop")
async def stop_pipeline(pipeline_id: str):
    if pipeline_id not in pipelines:
        raise HTTPException(status_code=404, detail="파이프라인 없음")
    await pipelines[pipeline_id].stop()
    return {"status": "stopped"}


# 하위호환
@app.post("/api/pipeline/{pipeline_id}/stop")
async def stop_pipeline_compat(pipeline_id: str):
    return await stop_pipeline(pipeline_id)


@app.delete("/api/pipelines/{pipeline_id}")
async def remove_pipeline(pipeline_id: str):
    if pipeline_id not in pipelines:
        raise HTTPException(status_code=404, detail="파이프라인 없음")
    p = pipelines[pipeline_id]
    if p.status == "running":
        await p.stop()
    del pipelines[pipeline_id]
    return {"status": "removed"}


# ─── 계획 수립 API ─────────────────────────────────────────────────────────────────

@app.post("/api/plan-phases")
async def create_plan_phase(body: PlanPhaseStartRequest):
    """계획 수립 시작 — 질문 생성 개시"""
    if body.session_id not in sessions:
        raise HTTPException(status_code=400, detail="유효한 세션 ID 필요")
    if body.mode == "api":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=400, detail="API 모드에서는 ANTHROPIC_API_KEY 환경변수 필요")
    if body.mode == "cli" and not CLAUDE_EXE:
        raise HTTPException(status_code=400, detail="CLI 모드에서는 Claude CLI 필요")

    session = sessions[body.session_id]
    phase = PlanPhase(session, body.goal, body.mode, body.supervisor_model)
    plan_phases[phase.id] = phase
    phase.start()

    return {"plan_id": phase.id, "status": phase.status}


@app.get("/api/plan-phases")
async def list_plan_phases():
    """활성 plan phase 목록"""
    # 1시간 이상 된 항목 자동 만료
    now = datetime.now()
    expired = [
        pid for pid, p in plan_phases.items()
        if (now - datetime.fromisoformat(p.created_at)).total_seconds() > 3600
        and p.status not in ("approved",)
    ]
    for pid in expired:
        del plan_phases[pid]
    return [p.to_dict() for p in plan_phases.values()]


@app.get("/api/plan-phases/{plan_id}")
async def get_plan_phase(plan_id: str):
    """특정 plan phase 상태 조회 (폴링용)"""
    if plan_id not in plan_phases:
        raise HTTPException(status_code=404, detail="Plan phase 없음")
    return plan_phases[plan_id].to_dict()


@app.post("/api/plan-phases/{plan_id}/answers")
async def submit_plan_answers(plan_id: str, body: PlanPhaseAnswerRequest):
    """답변 제출 → 실행계획 생성 시작"""
    if plan_id not in plan_phases:
        raise HTTPException(status_code=404, detail="Plan phase 없음")
    phase = plan_phases[plan_id]
    if phase.status != "questions_ready":
        raise HTTPException(status_code=409, detail=f"현재 상태({phase.status})에서는 답변 제출 불가")
    await phase.submit_answers(body.answers)
    return {"status": phase.status}


@app.post("/api/plan-phases/{plan_id}/approve")
async def approve_plan_phase(plan_id: str, body: PlanPhaseApproveRequest):
    """계획 승인 → 파이프라인 시작"""
    if plan_id not in plan_phases:
        raise HTTPException(status_code=404, detail="Plan phase 없음")
    phase = plan_phases[plan_id]
    if phase.status != "plan_ready":
        raise HTTPException(status_code=409, detail=f"현재 상태({phase.status})에서는 승인 불가")

    try:
        pipeline_id = await phase.approve(body.plan_text, body.max_iterations, body.max_cycles)
        return {
            "status": "approved",
            "pipeline_id": pipeline_id,
            "worker_session_id": pipelines[pipeline_id].session.id if pipelines.get(pipeline_id) and pipelines[pipeline_id].session else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파이프라인 시작 실패: {str(e)}")


@app.post("/api/plan-phases/{plan_id}/regenerate")
async def regenerate_plan(plan_id: str):
    """계획 재생성"""
    if plan_id not in plan_phases:
        raise HTTPException(status_code=404, detail="Plan phase 없음")
    phase = plan_phases[plan_id]
    if phase.status not in ("plan_ready", "error"):
        raise HTTPException(status_code=409, detail=f"현재 상태({phase.status})에서는 재생성 불가")
    await phase.regenerate()
    return {"status": phase.status}


@app.delete("/api/plan-phases/{plan_id}")
async def delete_plan_phase(plan_id: str):
    """Plan phase 삭제"""
    if plan_id not in plan_phases:
        raise HTTPException(status_code=404, detail="Plan phase 없음")
    phase = plan_phases[plan_id]
    await phase._cleanup_supervisor()
    del plan_phases[plan_id]
    return {"status": "removed"}


# ─── 스크린 모니터링 ─────────────────────────────────────────────────────────────

class ScreenMonitor:
    """Windows 스크린 캡처 (mss + Pillow)"""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._interval = 30
        self._latest_path: Optional[Path] = None

    def capture(self) -> Path:
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
                print(f"  [monitor] capture error: {e}")
            await asyncio.sleep(self._interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    @property
    def latest(self) -> Optional[Path]:
        return self._latest_path


screen_monitor = ScreenMonitor()


@app.post("/api/monitor/start")
async def monitor_start(interval: int = Query(30, ge=5, le=300)):
    await screen_monitor.start_periodic(interval)
    return {"status": "started", "interval": interval}


@app.post("/api/monitor/stop")
async def monitor_stop():
    await screen_monitor.stop()
    return {"status": "stopped"}


@app.get("/api/monitor/capture")
async def monitor_capture():
    try:
        path = await asyncio.to_thread(screen_monitor.capture)
        return {"path": str(path), "url": f"/screenshots/{path.name}",
                "timestamp": datetime.now().isoformat()}
    except ImportError:
        raise HTTPException(status_code=503, detail="mss/Pillow 미설치. pip install mss Pillow")
    except Exception as e:
        print(f"ERROR [capture_screen]: {e}")
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다")


@app.get("/api/monitor/latest")
async def monitor_latest():
    if screen_monitor.latest and screen_monitor.latest.exists():
        return {"path": str(screen_monitor.latest), "url": f"/screenshots/{screen_monitor.latest.name}"}
    return {"path": None, "url": None}


# ─── Admin API ──────────────────────────────────────────────────────────────────

@app.get("/admin/status")
async def admin_status():
    """서버 상태 및 재시작 안전 여부 반환"""
    active = sum(1 for p in pipelines.values() if p.status == "running")
    return {
        "active_pipelines": active,
        "resumable_runs": get_resumable_runs(),
        "safe_to_restart": active == 0,
        "shutting_down": _shutting_down,
    }


@app.post("/admin/restart")
async def admin_restart():
    """실행 중인 파이프라인 완료 대기 후 프로세스 재시작 (os.execv)"""
    global _shutting_down
    _shutting_down = True

    # 실행 중인 파이프라인이 완료될 때까지 폴링 (최대 5분)
    deadline = time.time() + 300
    while time.time() < deadline:
        running = [p for p in pipelines.values() if p.status == "running"]
        if not running:
            break
        await asyncio.sleep(2)

    # 아직 실행 중인 파이프라인은 interrupted로 마킹 후 강제 종료
    for p in list(pipelines.values()):
        if p.status == "running":
            mark_interrupted(p.id)
            await p.stop()

    # 프로세스 재시작 (비동기로 짧게 지연하여 응답 반환 후 실행)
    async def _do_restart():
        await asyncio.sleep(0.5)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    asyncio.create_task(_do_restart())
    return {"status": "restarting", "message": "0.5초 후 프로세스 재시작"}


@app.post("/admin/resume/{run_id}")
async def admin_resume(run_id: str):
    """중단된 파이프라인의 체크포인트 조회 및 재개 힌트 반환"""
    runs = get_resumable_runs()
    matched = next((r for r in runs if r["id"] == run_id), None)
    if matched is None:
        raise HTTPException(status_code=404, detail=f"재개 가능한 run_id 없음: {run_id}")
    next_stage = matched["current_stage"] + 1
    return {
        "id": matched["id"],
        "session_id": matched["session_id"],
        "current_stage": matched["current_stage"],
        "stage_outputs": matched["stage_outputs"],
        "updated_at": matched.get("updated_at"),
        "resume_hint": (
            f"세션 {matched['session_id']}에서 "
            f"스테이지 {next_stage}부터 새 파이프라인을 시작하세요"
        ),
    }


# ─── Shell 터미널 API ────────────────────────────────────────────────────────────

@app.post("/api/shells")
async def create_shell(body: ShellCreateRequest, request: Request):
    if not HAS_WINPTY:
        raise HTTPException(status_code=503, detail="pywinpty not installed — Shell 사용 불가")

    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    shell_id = str(uuid.uuid4())[:8]
    shell = ShellSession(shell_id, body.work_dir, body.shell_type, body.cols, body.rows)
    try:
        shell.start()
    except Exception as e:
        print(f"ERROR [create_shell]: {e}")
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다")
    shell_sessions[shell_id] = shell
    return shell.to_dict()


# 하위호환
@app.post("/api/shell/create")
async def create_shell_compat(body: ShellCreateRequest, request: Request):
    return await create_shell(body, request)


@app.get("/api/shells")
async def list_shells():
    return [s.to_dict() for s in list(shell_sessions.values())]


@app.delete("/api/shells/{shell_id}")
async def kill_shell(shell_id: str):
    if shell_id not in shell_sessions:
        raise HTTPException(status_code=404, detail="Shell 세션 없음")
    shell_sessions[shell_id].kill()
    del shell_sessions[shell_id]
    return {"status": "killed"}


# 하위호환
@app.delete("/api/shell/{shell_id}")
async def kill_shell_compat(shell_id: str):
    return await kill_shell(shell_id)


@app.websocket("/ws/shell/{shell_id}")
async def websocket_shell(websocket: WebSocket, shell_id: str):
    """Shell PTY와 xterm.js 사이의 양방향 WebSocket 브릿지"""
    await websocket.accept()

    if shell_id not in shell_sessions:
        await websocket.send_json({"error": "Shell 세션 없음"})
        await websocket.close()
        return

    shell = shell_sessions[shell_id]
    if not shell.alive:
        await websocket.send_json({"error": "Shell 세션이 종료됨"})
        await websocket.close()
        return

    output_queue = shell.subscribe()

    async def _send_output():
        """PTY → WebSocket (stdout 스트리밍)"""
        try:
            while True:
                data = await output_queue.get()
                if data is None:
                    break  # 세션 종료
                await websocket.send_text(data)
        except Exception:
            pass

    send_task = asyncio.create_task(_send_output())

    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            # 텍스트: 키 입력
            if "text" in msg:
                text = msg["text"]
                # resize JSON 메시지 감지: {"type": "resize", "rows": N, "cols": N}
                if text.startswith('{"'):
                    try:
                        payload = json.loads(text)
                        if payload.get("type") == "resize":
                            cols = max(40, min(400, int(payload["cols"])))
                            rows = max(10, min(200, int(payload["rows"])))
                            shell.resize(cols, rows)
                        else:
                            shell.write(text)
                    except Exception:
                        shell.write(text)
                else:
                    shell.write(text)
            elif "bytes" in msg:
                shell.write(msg["bytes"].decode("utf-8", errors="replace"))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[ws/shell:{shell_id}] unexpected error: {e}")
    finally:
        shell.unsubscribe(output_queue)
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass


# ─── 프론트엔드 ──────────────────────────────────────────────────────────────────

FRONTEND_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Session Manager</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/css/xterm.min.css">
<script src="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@xterm/addon-fit@0.10.0/lib/addon-fit.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@xterm/addon-web-links@0.11.0/lib/addon-web-links.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
    --bg: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --accent: #58a6ff;
    --accent-hover: #79c0ff;
    --green: #3fb950;
    --red: #f85149;
    --orange: #d29922;
    --purple: #bc8cff;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    overflow: hidden;
}

.app {
    display: grid;
    grid-template-columns: 320px 1fr;
    grid-template-rows: 56px 1fr;
    height: 100vh;
}

.header {
    grid-column: 1 / -1;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
}

.header h1 {
    font-size: 16px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
}

.header h1 .icon { font-size: 20px; }
.header-actions { display: flex; gap: 8px; }

.sidebar {
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.sidebar-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.sidebar-header h2 {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-dim);
}

.session-list { flex: 1; overflow-y: auto; padding: 8px; }

.session-item {
    padding: 10px 12px;
    border-radius: 6px;
    cursor: pointer;
    margin-bottom: 4px;
    border: 1px solid transparent;
    transition: all 0.15s;
}

.session-item:hover { background: var(--bg-tertiary); }
.session-item.active { background: var(--bg-tertiary); border-color: var(--accent); }

.session-item .session-name { font-size: 13px; font-weight: 500; margin-bottom: 4px; }

.session-item .session-meta {
    font-size: 11px;
    color: var(--text-dim);
    display: flex;
    align-items: center;
    gap: 6px;
}

.status-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.status-dot.alive { background: var(--green); }
.status-dot.busy { background: var(--orange); animation: pulse 1s infinite; }
.status-dot.dead { background: var(--red); }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

.tab-bar {
    display: flex;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
}

.tab {
    padding: 8px 16px;
    font-size: 13px;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    color: var(--text-dim);
    transition: all 0.15s;
}
.tab:hover { color: var(--text); }
.tab.active { color: var(--text); border-bottom-color: var(--accent); }

.main { display: flex; flex-direction: column; overflow: hidden; }

.terminal-container { flex: 1; overflow: hidden; display: flex; flex-direction: column; }

.terminal-output {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    background: var(--bg);
}

.terminal-input-bar {
    display: flex;
    border-top: 1px solid var(--border);
    background: var(--bg-secondary);
    padding: 8px 12px;
    gap: 8px;
    align-items: flex-end;
}

.terminal-input-bar textarea {
    flex: 1;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 12px;
    color: var(--text);
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 13px;
    outline: none;
    resize: none;
    min-height: 38px;
    max-height: 200px;
    overflow-y: auto;
    line-height: 1.4;
}

.terminal-input-bar textarea:focus { border-color: var(--accent); }

.logs-container { flex: 1; overflow: hidden; display: none; flex-direction: column; }
.logs-container.active { display: flex; }
.terminal-container.hidden { display: none; }

#claudeTerminal { display: flex; flex-direction: column; flex: 1; overflow: hidden; }

/* Terminal 모드 선택기 */
.terminal-mode-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
    font-size: 12px;
}
.terminal-mode-bar label { color: var(--text-dim); }
.terminal-mode-bar select {
    background: var(--bg-tertiary);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 12px;
    outline: none;
}
.terminal-mode-bar .shell-type-select { margin-left: 8px; }
.terminal-mode-bar .shell-actions { margin-left: auto; display: flex; gap: 6px; }

/* Shell 터미널 (xterm.js) */
#shellContainer {
    flex: 1;
    overflow: hidden;
    display: none;
    background: #000;
}
#shellContainer.active { display: flex; }
#shellContainer .xterm { width: 100%; height: 100%; }

.logs-search {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    gap: 8px;
}

.logs-search input {
    flex: 1;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 12px;
    color: var(--text);
    font-size: 13px;
    outline: none;
}

.logs-list { flex: 1; overflow-y: auto; padding: 8px 16px; }

.log-item {
    padding: 8px 12px;
    border-radius: 6px;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2px;
}

.log-item:hover { background: var(--bg-tertiary); }
.log-item .log-name { font-size: 13px; font-family: monospace; }
.log-item .log-meta { font-size: 11px; color: var(--text-dim); }

.log-viewer {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    font-family: monospace;
    font-size: 13px;
    line-height: 1.5;
    white-space: pre-wrap;
    display: none;
}

.modal-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.6);
    z-index: 100;
    justify-content: center;
    align-items: center;
}

.modal-overlay.active { display: flex; }

.modal {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    width: 450px;
    max-width: 90%;
}

.modal h3 { font-size: 16px; margin-bottom: 16px; }

.modal label {
    display: block;
    font-size: 12px;
    color: var(--text-dim);
    margin-bottom: 4px;
    margin-top: 12px;
}

.modal input, .modal textarea {
    width: 100%;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 12px;
    color: var(--text);
    font-size: 13px;
    outline: none;
}

.modal textarea { height: 80px; resize: vertical; font-family: monospace; }

.modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 20px;
}

.btn {
    padding: 6px 14px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-tertiary);
    color: var(--text);
    font-size: 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: all 0.15s;
}

.btn:hover { background: var(--border); }

.btn-primary {
    background: var(--accent);
    border-color: var(--accent);
    color: #000;
    font-weight: 600;
}
.btn-primary:hover { background: var(--accent-hover); }

.btn-danger { color: var(--red); }
.btn-danger:hover { background: rgba(248,81,73,0.15); }

.btn-small { padding: 4px 8px; font-size: 11px; }

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-dim);
    gap: 12px;
}

.empty-state .icon { font-size: 48px; opacity: 0.3; }
.empty-state p { font-size: 14px; }

::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }

/* ===== Mobile Responsive ===== */
.mobile-menu-btn {
    display: none;
    background: none;
    border: none;
    color: var(--text);
    font-size: 22px;
    cursor: pointer;
    padding: 4px 8px;
    line-height: 1;
}

.sidebar-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5);
    z-index: 90;
}
.sidebar-overlay.active { display: block; }

.sidebar .sidebar-close {
    display: none;
    background: none;
    border: none;
    color: var(--text-dim);
    font-size: 18px;
    cursor: pointer;
    padding: 4px;
}

@media (max-width: 768px) {
    .app {
        grid-template-columns: 1fr;
    }

    .mobile-menu-btn { display: block; }

    .sidebar {
        position: fixed;
        top: 0; left: 0; bottom: 0;
        width: 280px;
        z-index: 100;
        transform: translateX(-100%);
        transition: transform 0.25s ease;
        box-shadow: none;
    }
    .sidebar.open {
        transform: translateX(0);
        box-shadow: 4px 0 24px rgba(0,0,0,0.4);
    }
    .sidebar .sidebar-close { display: block; }

    .header h1 { font-size: 14px; }
    .header h1 .icon { font-size: 16px; }
    .header { padding: 0 12px; }

    .tab-bar { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .tab { padding: 8px 12px; font-size: 12px; white-space: nowrap; flex-shrink: 0; }

    .terminal-input-bar { padding: 6px 8px; gap: 6px; }
    .terminal-input-bar textarea { padding: 8px 10px; font-size: 14px; }

    .terminal-output { padding: 10px; font-size: 12px; }

    .terminal-mode-bar { flex-wrap: wrap; gap: 6px; padding: 6px 10px; }
    .terminal-mode-bar .shell-actions { margin-left: 0; width: 100%; justify-content: flex-end; }

    .session-actions { flex-wrap: wrap; gap: 4px; padding: 6px 10px; }

    .git-toolbar { flex-direction: column; gap: 6px; padding: 8px 12px; }
    .git-toolbar .git-path-input { min-width: 0; width: 100%; }

    .git-panels { padding: 10px; }
    .git-commit-item { flex-wrap: wrap; gap: 4px; }
    .git-commit-meta { width: 100%; }

    .git-cmd-bar { padding: 8px 10px; }

    .modal { width: calc(100% - 32px); padding: 16px; }

    .logs-search { padding: 8px 10px; }

    .git-panel-header { padding: 8px 10px; font-size: 12px; flex-wrap: wrap; gap: 6px; }

    .pr-item, .issue-item { flex-wrap: wrap; gap: 4px; padding: 6px 10px; }

    .remote-info { padding: 8px 10px; }
    .clone-section { padding: 8px 10px; flex-wrap: wrap; }

    .empty-state .icon { font-size: 36px; }
    .empty-state p { font-size: 13px; }
}

.session-actions {
    display: flex;
    gap: 4px;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border);
    align-items: center;
}

.status-badge {
    margin-left: auto;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    background: var(--bg-tertiary);
    color: var(--text-dim);
}
.status-badge.busy {
    background: rgba(210,153,34,0.2);
    color: var(--orange);
}

/* 폴더 탐색기 */
.browser-panel {
    border: 1px solid var(--border);
    border-radius: 6px;
    margin-top: 8px;
    max-height: 250px;
    overflow-y: auto;
    background: var(--bg);
}

.browser-breadcrumb {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 10px;
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border);
    font-size: 11px;
    color: var(--text-dim);
    flex-wrap: wrap;
}

.browser-breadcrumb span {
    cursor: pointer;
    color: var(--accent);
}
.browser-breadcrumb span:hover { text-decoration: underline; }

.browser-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    cursor: pointer;
    font-size: 12px;
    border-bottom: 1px solid var(--border);
}
.browser-item:last-child { border-bottom: none; }
.browser-item:hover { background: var(--bg-tertiary); }

.browser-item .icon { font-size: 14px; width: 18px; text-align: center; flex-shrink: 0; }
.browser-item .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.browser-item .actions { display: flex; gap: 4px; }
.browser-item .star-btn {
    background: none; border: none; cursor: pointer;
    color: var(--text-dim); font-size: 14px; padding: 0 2px;
}
.browser-item .star-btn:hover { color: var(--orange); }
.browser-item .star-btn.starred { color: var(--orange); }

/* 프로젝트 목록 */
.projects-section { margin-top: 12px; }
.projects-section h4 {
    font-size: 11px; color: var(--text-dim); text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 6px;
}

.project-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    margin: 2px 4px 2px 0;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 14px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
}
.project-chip:hover {
    border-color: var(--accent);
    background: rgba(88,166,255,0.1);
}
.project-chip .remove {
    font-size: 10px; color: var(--text-dim); cursor: pointer;
    margin-left: 2px;
}
.project-chip .remove:hover { color: var(--red); }

/* Git 탭 */
.git-container { flex: 1; overflow: hidden; display: none; flex-direction: column; }
.git-container.active { display: flex; }

.git-toolbar {
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-secondary);
    flex-wrap: wrap;
}

.git-toolbar .git-path-input {
    flex: 1;
    min-width: 200px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 10px;
    color: var(--text);
    font-size: 12px;
    font-family: monospace;
    outline: none;
}
.git-toolbar .git-path-input:focus { border-color: var(--accent); }

.git-panels { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; }

.git-panel {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
}

.git-panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    font-weight: 600;
}

.git-panel-body { padding: 0; }
.git-panel-body.padded { padding: 12px 14px; }

.git-branch-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(88,166,255,0.15);
    color: var(--accent);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-family: monospace;
}

.git-sync-info {
    font-size: 11px;
    color: var(--text-dim);
    display: flex;
    gap: 10px;
}
.git-sync-info .ahead { color: var(--green); }
.git-sync-info .behind { color: var(--orange); }

.git-file-list { list-style: none; max-height: 200px; overflow-y: auto; }

.git-file-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 14px;
    font-size: 12px;
    font-family: monospace;
    border-bottom: 1px solid var(--border);
}
.git-file-item:last-child { border-bottom: none; }

.git-file-status {
    display: inline-block;
    width: 22px;
    text-align: center;
    font-weight: 700;
    font-size: 11px;
    border-radius: 3px;
    padding: 1px 0;
}
.git-file-status.M { color: var(--orange); }
.git-file-status.A { color: var(--green); }
.git-file-status.D { color: var(--red); }
.git-file-status.U, .git-file-status.QQ { color: var(--text-dim); }

.git-commit-list { list-style: none; max-height: 300px; overflow-y: auto; }

.git-commit-item {
    display: flex;
    gap: 10px;
    padding: 6px 14px;
    font-size: 12px;
    border-bottom: 1px solid var(--border);
    align-items: baseline;
}
.git-commit-item:last-child { border-bottom: none; }

.git-commit-hash {
    font-family: monospace;
    color: var(--accent);
    flex-shrink: 0;
    font-size: 11px;
}

.git-commit-msg { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.git-commit-meta { color: var(--text-dim); font-size: 11px; flex-shrink: 0; white-space: nowrap; }

.git-cmd-bar {
    display: flex;
    gap: 8px;
    padding: 10px 16px;
    border-top: 1px solid var(--border);
    background: var(--bg-secondary);
}

.git-cmd-bar input {
    flex: 1;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 10px;
    color: var(--text);
    font-family: monospace;
    font-size: 12px;
    outline: none;
}
.git-cmd-bar input:focus { border-color: var(--accent); }

.git-cmd-output {
    background: var(--bg);
    padding: 8px 14px;
    font-family: monospace;
    font-size: 12px;
    white-space: pre-wrap;
    max-height: 150px;
    overflow-y: auto;
    border-top: 1px solid var(--border);
    display: none;
    line-height: 1.5;
}
.git-cmd-output.visible { display: block; }
.git-cmd-output.error { color: var(--red); }

.pr-list, .issue-list { list-style: none; max-height: 250px; overflow-y: auto; }

.pr-item, .issue-item {
    display: flex;
    gap: 8px;
    padding: 8px 14px;
    font-size: 12px;
    border-bottom: 1px solid var(--border);
    align-items: center;
}
.pr-item:last-child, .issue-item:last-child { border-bottom: none; }
.pr-item:hover, .issue-item:hover { background: var(--bg-tertiary); }

.pr-number, .issue-number {
    font-family: monospace;
    color: var(--accent);
    flex-shrink: 0;
    font-weight: 600;
}

.pr-title, .issue-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.pr-branch {
    font-size: 10px;
    background: var(--bg-tertiary);
    padding: 1px 6px;
    border-radius: 8px;
    color: var(--text-dim);
    font-family: monospace;
}

.issue-label {
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 8px;
    background: var(--purple);
    color: #000;
    font-weight: 600;
}

.pr-item a, .issue-item a { color: var(--accent); text-decoration: none; font-size: 11px; }
.pr-item a:hover, .issue-item a:hover { text-decoration: underline; }

.remote-info {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    padding: 10px 14px;
    font-size: 12px;
}
.remote-info-item {
    display: flex;
    align-items: center;
    gap: 6px;
}
.remote-info-item .label { color: var(--text-dim); }
.remote-info-item .value { font-family: monospace; color: var(--accent); }
.remote-info-item a { color: var(--accent); text-decoration: none; }
.remote-info-item a:hover { text-decoration: underline; }

.gh-repo-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
}
.gh-repo-badge.private { background: rgba(210,153,34,0.2); color: var(--orange); }
.gh-repo-badge.public { background: rgba(63,185,80,0.2); color: var(--green); }

.gh-stat {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 11px;
    color: var(--text-dim);
    margin-left: 8px;
}

.clone-section {
    padding: 10px 14px;
    display: flex;
    gap: 8px;
    align-items: center;
}
.clone-section input {
    flex: 1;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 10px;
    color: var(--text);
    font-family: monospace;
    font-size: 12px;
    outline: none;
}
.clone-section input:focus { border-color: var(--accent); }

.gh-repo-list { list-style: none; max-height: 250px; overflow-y: auto; }
.gh-repo-item {
    display: flex;
    gap: 8px;
    padding: 8px 14px;
    font-size: 12px;
    border-bottom: 1px solid var(--border);
    align-items: center;
    cursor: pointer;
}
.gh-repo-item:last-child { border-bottom: none; }
.gh-repo-item:hover { background: var(--bg-tertiary); }
.gh-repo-name { font-weight: 600; color: var(--accent); flex-shrink: 0; }
.gh-repo-desc { flex: 1; color: var(--text-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gh-auth-status {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    font-size: 12px;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
}
.gh-auth-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}
.gh-auth-dot.ok { background: var(--green); }
.gh-auth-dot.fail { background: var(--red); }

/* ===== Admin Panel ===== */
.admin-panel {
    padding: 10px 12px;
    border-top: 1px solid var(--border);
    font-size: 12px;
    flex-shrink: 0;
}
.admin-panel-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-dim);
    margin-bottom: 8px;
}
.admin-stats {
    display: flex;
    align-items: center;
    gap: 5px;
    margin-bottom: 8px;
    flex-wrap: wrap;
}
.admin-badge {
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 10px;
    background: var(--bg-tertiary);
    color: var(--text-dim);
}
.admin-badge.warn { background: rgba(210,153,34,0.2); color: var(--orange); }
.admin-badge.good { background: rgba(63,185,80,0.15); color: var(--green); }
.btn-restart {
    width: 100%;
    justify-content: center;
    margin-bottom: 6px;
}
.btn-restart:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-restart.safe { color: var(--green); border-color: var(--green); }
.resumable-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
    max-height: 110px;
    overflow-y: auto;
}
.resumable-item {
    padding: 5px 8px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 6px;
}
.resumable-item-info {
    font-size: 11px;
    color: var(--text-dim);
    font-family: monospace;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>
</head>
<body>

<div class="app">
    <div class="header">
        <div style="display:flex;align-items:center;gap:8px">
            <button class="mobile-menu-btn" onclick="toggleSidebar()" aria-label="Menu">&#9776;</button>
            <h1><span class="icon">&#9654;</span> Claude Session Manager</h1>
        </div>
        <div class="header-actions">
            <button class="btn" onclick="refreshSessions()">&#8635; Refresh</button>
        </div>
    </div>

    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <div class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <div style="display:flex;align-items:center;gap:8px">
                <button class="sidebar-close" onclick="toggleSidebar()" aria-label="Close">&#10005;</button>
                <h2>Sessions</h2>
            </div>
            <button class="btn btn-primary btn-small" onclick="showNewSessionModal()">+ New</button>
        </div>
        <div class="session-list" id="sessionList">
            <div class="empty-state"><p>No sessions</p></div>
        </div>

        <!-- Admin Panel -->
        <div class="admin-panel">
            <div class="admin-panel-title">Admin</div>
            <div class="admin-stats" id="adminStats">
                <span class="admin-badge" id="adminActiveBadge">실행 중: 0개</span>
            </div>
            <button class="btn btn-small btn-restart" id="adminRestartBtn"
                    onclick="adminRestart()" disabled>
                &#8635; 안전 재시작
            </button>
            <div class="resumable-list" id="resumableList" style="display:none"></div>
        </div>
    </div>

    <div class="main">
        <div class="tab-bar">
            <div class="tab active" onclick="switchTab('terminal')">Terminal</div>
            <div class="tab" onclick="switchTab('git')">Git</div>
            <div class="tab" onclick="switchTab('logs')">Logs</div>
            <div class="tab" onclick="switchTab('pipeline')">Pipeline</div>
        </div>

        <div class="session-actions" id="sessionActions" style="display:none">
            <button class="btn btn-small" onclick="interruptSession()">Stop</button>
            <button class="btn btn-small" onclick="renameSession()" title="이름 변경">&#9998;</button>
            <button class="btn btn-small" onclick="forkSession()" title="세션 분기">&#9095;</button>
            <button class="btn btn-small" onclick="exportSession()" title="대화 내보내기">&#8615;</button>
            <button class="btn btn-small" onclick="showClaudeMdEditor()" title="CLAUDE.md 편집">&#128221;</button>
            <button class="btn btn-small" onclick="showTemplates()" title="프롬프트 템플릿">&#9776;</button>
            <button class="btn btn-small" onclick="showCompare()" title="모델 비교">&#8644;</button>
            <button class="btn btn-small btn-danger" onclick="killSession()">Kill</button>
            <button class="btn btn-small" onclick="removeSession()" style="color:var(--text-dim)" title="Remove">&#128465;</button>
            <span class="status-badge" id="statusBadge">Idle</span>
            <span id="tokenBadge" style="font-size:10px;color:var(--text-dim);margin-left:auto"></span>
        </div>

        <div class="terminal-container" id="terminalView">
            <div class="terminal-mode-bar">
                <label>Mode:</label>
                <select id="terminalMode" onchange="onTerminalModeChange()">
                    <option value="claude">Claude CLI</option>
                    <option value="shell">Shell Terminal</option>
                </select>
                <span id="shellTypeGroup" style="display:none">
                    <label class="shell-type-select">Shell:</label>
                    <select id="shellTypeSelect">
                        <option value="cmd">CMD</option>
                        <option value="powershell">PowerShell</option>
                    </select>
                </span>
                <span class="shell-actions" id="shellActions" style="display:none">
                    <button class="btn btn-small btn-primary" onclick="createShellSession()">&#9654; Connect</button>
                    <button class="btn btn-small btn-danger" onclick="killShellSession()" style="display:none" id="shellKillBtn">&#10005; Kill</button>
                </span>
            </div>
            <!-- Claude CLI 모드 -->
            <div id="claudeTerminal">
                <div class="terminal-output" id="terminalOutput">
                    <div class="empty-state">
                        <span class="icon">&#9000;</span>
                        <p>Select or create a session to start</p>
                    </div>
                </div>
                <div id="questionPanel" style="display:none;border-top:1px solid var(--border);background:var(--bg-tertiary);padding:10px 12px;max-height:220px;overflow-y:auto"></div>
                <div class="terminal-input-bar">
                    <input type="file" id="fileUploadInput" multiple accept="image/*,.pdf,.txt,.md"
                           style="display:none" onchange="handleFileSelect(event)">
                    <button class="btn btn-small" onclick="document.getElementById('fileUploadInput').click()"
                            title="파일 첨부" style="align-self:flex-end;margin-bottom:2px;font-size:14px;padding:4px 6px">&#128206;</button>
                    <button class="btn btn-small" onclick="toggleMonitorPanel()"
                            title="스크린 모니터" style="align-self:flex-end;margin-bottom:2px;font-size:14px;padding:4px 6px">&#128247;</button>
                    <div style="flex:1;display:flex;flex-direction:column;min-width:0">
                        <div id="attachmentPreview" style="display:none;padding:4px 0;gap:4px;flex-wrap:wrap"></div>
                        <textarea id="commandInput" rows="1" placeholder="Enter prompt for Claude... (Shift+Enter = 줄바꿈)"
                                  onkeydown="handleInputKeydown(event)"
                                  ondragover="event.preventDefault();this.style.borderColor='var(--accent)'"
                                  ondragleave="this.style.borderColor='var(--border)'"
                                  ondrop="handleFileDrop(event)"></textarea>
                    </div>
                    <button class="btn btn-primary btn-small" onclick="sendCommand()" style="align-self:flex-end;margin-bottom:2px">Send</button>
                </div>
            </div>
            <!-- Shell 모드 (xterm.js) -->
            <div id="shellContainer">
                <div id="shellTerminal" style="width:100%;height:100%"></div>
            </div>
        </div>

        <div class="git-container" id="gitView">
            <div class="git-toolbar">
                <span style="font-size:12px;color:var(--text-dim)">Repository:</span>
                <input type="text" class="git-path-input" id="gitRepoPath" placeholder="e.g. D:\projects\myapp"
                       onkeydown="if(event.key==='Enter')loadGitInfo()">
                <button class="btn btn-small" onclick="loadGitInfo()">Load</button>
                <button class="btn btn-small" onclick="loadGitInfo()">&#8635;</button>
            </div>
            <div id="gitProjectChips" style="padding:6px 16px;display:flex;gap:6px;flex-wrap:wrap;border-bottom:1px solid var(--border);background:var(--bg-secondary)"></div>
            <div class="git-panels" id="gitPanels">
                <!-- Status -->
                <div class="git-panel">
                    <div class="git-panel-header">
                        <span>Status</span>
                        <div style="display:flex;gap:8px;align-items:center">
                            <span class="git-branch-badge" id="gitBranch">-</span>
                            <span class="git-sync-info" id="gitSync"></span>
                        </div>
                    </div>
                    <div class="git-panel-body">
                        <ul class="git-file-list" id="gitFileList">
                            <li style="padding:12px 14px;color:var(--text-dim);font-size:12px">Load a repository to see status</li>
                        </ul>
                    </div>
                </div>

                <!-- Commits -->
                <div class="git-panel">
                    <div class="git-panel-header">
                        <span>Recent Commits</span>
                    </div>
                    <div class="git-panel-body">
                        <ul class="git-commit-list" id="gitCommitList"></ul>
                    </div>
                </div>

                <!-- PRs -->
                <div class="git-panel">
                    <div class="git-panel-header">
                        <span>Pull Requests</span>
                        <div style="display:flex;gap:4px">
                            <button class="btn btn-small" onclick="loadGitPRs('open')">Open</button>
                            <button class="btn btn-small" onclick="loadGitPRs('closed')">Closed</button>
                        </div>
                    </div>
                    <div class="git-panel-body">
                        <ul class="pr-list" id="gitPRList">
                            <li style="padding:12px 14px;color:var(--text-dim);font-size:12px">gh CLI required</li>
                        </ul>
                    </div>
                </div>

                <!-- Issues -->
                <div class="git-panel">
                    <div class="git-panel-header">
                        <span>Issues</span>
                        <div style="display:flex;gap:4px">
                            <button class="btn btn-small" onclick="loadGitIssues('open')">Open</button>
                            <button class="btn btn-small" onclick="loadGitIssues('closed')">Closed</button>
                        </div>
                    </div>
                    <div class="git-panel-body">
                        <ul class="issue-list" id="gitIssueList">
                            <li style="padding:12px 14px;color:var(--text-dim);font-size:12px">gh CLI required</li>
                        </ul>
                    </div>
                </div>

                <!-- Remote / GitHub -->
                <div class="git-panel">
                    <div class="git-panel-header">
                        <span>Remote / GitHub</span>
                        <div style="display:flex;gap:4px">
                            <button class="btn btn-small" onclick="checkGhAuth()">Auth Status</button>
                            <button class="btn btn-small" onclick="loadRemoteInfo()">Refresh</button>
                        </div>
                    </div>
                    <div class="git-panel-body">
                        <div id="ghAuthBar" class="gh-auth-status" style="display:none"></div>
                        <div id="gitRemoteInfo" class="remote-info">
                            <span style="color:var(--text-dim)">Load a repository to see remote info</span>
                        </div>
                    </div>
                </div>

                <!-- Clone / Search -->
                <div class="git-panel">
                    <div class="git-panel-header">
                        <span>Clone / Search GitHub</span>
                    </div>
                    <div class="git-panel-body">
                        <div class="clone-section">
                            <input type="text" id="ghCloneUrl" placeholder="GitHub URL or owner/repo or search query..."
                                   onkeydown="if(event.key==='Enter')handleCloneSearch()">
                            <button class="btn btn-small" onclick="handleCloneSearch()">Search</button>
                            <button class="btn btn-primary btn-small" onclick="cloneRepo()">Clone</button>
                        </div>
                        <div class="clone-section" style="border-top:1px solid var(--border)">
                            <span style="font-size:11px;color:var(--text-dim);white-space:nowrap">Clone to:</span>
                            <input type="text" id="ghCloneDest" placeholder="(optional) destination path, e.g. D:\projects\myrepo">
                        </div>
                        <ul class="gh-repo-list" id="ghRepoList"></ul>
                    </div>
                </div>
            </div>
            <div class="git-cmd-output" id="gitCmdOutput"></div>
            <div class="git-cmd-bar">
                <span style="font-size:12px;color:var(--text-dim);white-space:nowrap">git</span>
                <input type="text" id="gitCmdInput" placeholder="e.g. pull, push, commit -m 'message', checkout main ..."
                       onkeydown="if(event.key==='Enter')runGitCmd()">
                <button class="btn btn-primary btn-small" onclick="runGitCmd()">Run</button>
            </div>
        </div>

        <div class="logs-container" id="logsView">
            <div class="logs-search">
                <input type="text" id="logSearchInput" placeholder="Search logs..."
                       onkeydown="if(event.key==='Enter')searchLogs()">
                <button class="btn btn-small" onclick="searchLogs()">Search</button>
                <button class="btn btn-small" onclick="loadLogs()">&#8635;</button>
            </div>
            <div class="logs-list" id="logsList"></div>
            <div class="log-viewer" id="logViewer"></div>
        </div>

        <div class="pipeline-container" id="pipelineView" style="display:none;flex-direction:column;height:100%;overflow:hidden">
            <!-- 설정 영역 -->
            <div style="padding:12px 16px;border-bottom:1px solid var(--border);background:var(--bg-secondary)">
                <div style="margin-bottom:8px">
                    <label style="font-size:12px;color:var(--text-dim);display:block;margin-bottom:4px">목표 (Goal)</label>
                    <textarea id="pipelineGoal" rows="3" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:8px;font-size:13px;resize:vertical;font-family:inherit" placeholder="예: UFS 전체 서비스 테스트 실행하고 결과 정리해줘"></textarea>
                </div>
                <div style="display:flex;gap:8px;align-items:end;flex-wrap:wrap">
                    <div style="width:120px">
                        <label style="font-size:11px;color:var(--text-dim);display:block;margin-bottom:3px">감독자 모드</label>
                        <select id="pipelineMode" onchange="onPipelineModeChange()" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:6px 8px;font-size:12px">
                            <option value="cli">CLI (무료)</option>
                            <option value="api">API (유료)</option>
                        </select>
                    </div>
                    <div style="flex:1;min-width:150px">
                        <label style="font-size:11px;color:var(--text-dim);display:block;margin-bottom:3px">감독자 모델</label>
                        <select id="pipelineSupervisorModel" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:6px 8px;font-size:12px">
                            <option value="sonnet">Sonnet (latest)</option>
                            <option value="haiku">Haiku (latest)</option>
                            <option value="opus">Opus (latest)</option>
                        </select>
                    </div>
                    <div style="width:100px">
                        <label style="font-size:11px;color:var(--text-dim);display:block;margin-bottom:3px" title="한 사이클당 반복 횟수">반복 (1사이클)</label>
                        <input type="number" id="pipelineMaxIter" value="20" min="1" max="100" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:6px 8px;font-size:12px">
                    </div>
                    <div style="width:100px">
                        <label style="font-size:11px;color:var(--text-dim);display:block;margin-bottom:3px" title="사이클 반복 횟수 (20×100=최대2000회)">사이클 수</label>
                        <input type="number" id="pipelineMaxCycles" value="100" min="1" max="200" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:6px 8px;font-size:12px">
                    </div>
                    <div id="pipelineApiKeyGroup" style="flex:1;min-width:180px;display:none">
                        <label style="font-size:11px;color:var(--text-dim);display:block;margin-bottom:3px">API Key</label>
                        <span style="font-size:11px;color:var(--text-dim)">서버 환경변수(ANTHROPIC_API_KEY) 사용</span>
                    </div>
                    <button class="btn btn-small" onclick="startPlanPhase()" id="planPhaseBtn" style="background:var(--purple);color:white">&#128203; Plan</button>
                    <button class="btn btn-primary btn-small" onclick="startPipeline()" id="pipelineStartBtn">&#9654; Start</button>
                    <button class="btn btn-small btn-danger" onclick="stopPipeline()" id="pipelineStopBtn" style="display:none">&#9632; Stop</button>
                </div>
            </div>

            <!-- Plan Phase 컨테이너 -->
            <div id="planPhaseContainer" style="display:none;padding:16px;border-bottom:1px solid var(--border);max-height:65vh;overflow-y:auto;background:var(--bg)">
                <div id="planPhaseContent"></div>
            </div>

            <!-- 파이프라인 목록 (여러개일 때) -->
            <div id="pipelineListBar" style="padding:6px 16px;border-bottom:1px solid var(--border)"></div>

            <!-- 상태 바 -->
            <div id="pipelineStatusBar" style="padding:8px 16px;background:var(--bg-tertiary);border-bottom:1px solid var(--border);display:none">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                    <span id="pipelineStatusText" style="font-size:13px;font-weight:500">Idle</span>
                    <span id="pipelineIterText" style="font-size:12px;color:var(--text-dim)">0/20</span>
                </div>
                <div style="background:var(--bg);border-radius:3px;height:6px;overflow:hidden">
                    <div id="pipelineProgressBar" style="background:var(--accent);height:100%;width:0%;transition:width 0.3s"></div>
                </div>
                <div id="pipelineSessionInfo" style="font-size:11px;color:var(--text-dim);margin-top:4px"></div>
            </div>

            <!-- 히스토리 -->
            <div id="pipelineHistory" style="flex:1;overflow-y:auto;padding:12px 16px">
                <div style="text-align:center;padding:40px;color:var(--text-dim)">
                    <p style="font-size:14px">LLM 감독자가 Claude CLI를 자동으로 구동합니다</p>
                    <p style="font-size:12px;margin-top:8px">세션을 선택하고, 목표를 입력한 후 Start를 누르세요</p>
                </div>
            </div>

            <!-- 요약 -->
            <div id="pipelineSummary" style="display:none;padding:12px 16px;background:var(--bg-secondary);border-top:1px solid var(--border)">
                <div style="font-size:12px;color:var(--green);font-weight:600;margin-bottom:4px">&#10003; 완료 요약</div>
                <div id="pipelineSummaryText" style="font-size:13px;line-height:1.5"></div>
            </div>
        </div>
    </div>
</div>

<div class="modal-overlay" id="newSessionModal">
    <div class="modal" style="width:550px">
        <h3>New Claude Session</h3>

        <div class="projects-section" id="projectsSection"></div>

        <label>Working Directory</label>
        <div style="display:flex;gap:6px">
            <input type="text" id="newWorkDir" value="." placeholder="e.g. D:\projects\myapp" style="flex:1">
            <button class="btn btn-small" onclick="toggleBrowser()">Browse</button>
        </div>

        <div class="browser-panel" id="browserPanel" style="display:none">
            <div class="browser-breadcrumb" id="browserBreadcrumb"></div>
            <div id="browserItems"></div>
        </div>

        <label>Model</label>
        <select id="newModel" style="width:100%;padding:8px 10px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:13px;outline:none;cursor:pointer">
            <option value="">Default (CLI default)</option>
            <option value="sonnet">Sonnet (latest)</option>
            <option value="opus">Opus (Max 플랜 전용)</option>
            <option value="haiku">Haiku (latest)</option>
        </select>

        <label style="display:flex;align-items:center;gap:8px;margin:8px 0;cursor:pointer">
            <input type="checkbox" id="newSkipPermissions" checked style="width:16px;height:16px;accent-color:var(--accent);cursor:pointer">
            <span style="font-size:13px">권한 자동 승인 <span style="color:var(--text-dim);font-size:11px">(도구 사용 시 묻지 않음)</span></span>
        </label>

        <label>MCP Config <span style="color:var(--text-dim);font-size:11px">(optional — MCP 서버 설정 파일 경로)</span></label>
        <input type="text" id="newMcpConfig" value="" placeholder="e.g. C:\Users\you\.claude\mcp-config.json" style="width:100%;padding:8px 10px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:13px">

        <label>Initial Prompt (optional)</label>
        <textarea id="newPrompt" placeholder="e.g. Help me fix the login bug"></textarea>
        <div class="modal-actions">
            <button class="btn" onclick="hideNewSessionModal()">Cancel</button>
            <button class="btn btn-primary" onclick="createSession()">Create</button>
        </div>
    </div>
</div>

<!-- 템플릿 모달 -->
<div class="modal-overlay" id="templateModal">
    <div class="modal" style="width:600px;max-height:80vh;display:flex;flex-direction:column">
        <h3>프롬프트 템플릿</h3>
        <div style="display:flex;gap:8px;margin-bottom:12px">
            <input type="text" id="tplName" placeholder="템플릿 이름" style="flex:1;padding:6px 10px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:12px">
            <input type="text" id="tplCategory" placeholder="카테고리" style="width:120px;padding:6px 10px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:12px">
        </div>
        <textarea id="tplPrompt" rows="4" placeholder="프롬프트 내용..." style="width:100%;padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:12px;resize:vertical;margin-bottom:8px"></textarea>
        <div style="display:flex;gap:6px;margin-bottom:12px">
            <button class="btn btn-primary btn-small" onclick="saveTemplate()">저장</button>
        </div>
        <div id="templateList" style="flex:1;overflow-y:auto;border-top:1px solid var(--border);padding-top:8px"></div>
        <div class="modal-actions"><button class="btn" onclick="hideModal('templateModal')">닫기</button></div>
    </div>
</div>

<!-- CLAUDE.md 편집 모달 -->
<div class="modal-overlay" id="claudeMdModal">
    <div class="modal" style="width:700px;max-height:85vh;display:flex;flex-direction:column">
        <h3>CLAUDE.md 편집</h3>
        <div id="claudeMdPath" style="font-size:11px;color:var(--text-dim);margin-bottom:8px"></div>
        <textarea id="claudeMdContent" style="flex:1;min-height:300px;width:100%;padding:10px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);font-family:'Cascadia Code','Consolas',monospace;font-size:12px;resize:vertical;line-height:1.5"></textarea>
        <div class="modal-actions">
            <button class="btn" onclick="hideModal('claudeMdModal')">취소</button>
            <button class="btn btn-primary" onclick="saveClaudeMd()">저장</button>
        </div>
    </div>
</div>

<!-- 모델 비교 모달 -->
<div class="modal-overlay" id="compareModal">
    <div class="modal" style="width:650px;max-height:85vh;display:flex;flex-direction:column">
        <h3>멀티 모델 비교</h3>
        <textarea id="comparePrompt" rows="3" placeholder="비교할 프롬프트..." style="width:100%;padding:8px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:12px;resize:vertical;margin-bottom:8px"></textarea>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
            <label style="font-size:12px;display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" class="cmpModel" value="sonnet" checked> Sonnet</label>
            <label style="font-size:12px;display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" class="cmpModel" value="opus" checked> Opus</label>
            <label style="font-size:12px;display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" class="cmpModel" value="haiku" checked> Haiku</label>
        </div>
        <div style="display:flex;gap:6px;margin-bottom:10px">
            <button class="btn btn-primary btn-small" onclick="startCompare()">비교 시작</button>
        </div>
        <div id="compareResults" style="flex:1;overflow-y:auto"></div>
        <div class="modal-actions"><button class="btn" onclick="hideModal('compareModal')">닫기</button></div>
    </div>
</div>

<!-- 스크린 모니터 패널 -->
<div id="monitorPanel" style="display:none;position:fixed;bottom:60px;right:20px;width:420px;max-height:400px;background:var(--bg-secondary);border:1px solid var(--border);border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,0.4);z-index:1000;overflow:hidden">
    <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--bg-tertiary);border-bottom:1px solid var(--border)">
        <span style="font-weight:600;font-size:13px;color:var(--text)">&#128247; Screen Monitor</span>
        <button onclick="toggleMonitorPanel()" style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:16px">&times;</button>
    </div>
    <div style="padding:8px">
        <img id="monitorImage" style="width:100%;border-radius:4px;display:none;cursor:pointer" onclick="window.open(this.src)">
        <div id="monitorPlaceholder" style="text-align:center;color:var(--text-dim);padding:30px;font-size:12px">캡처된 스크린샷이 없습니다</div>
        <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">
            <button class="btn btn-small" onclick="captureScreen()">Capture Now</button>
            <button class="btn btn-small btn-primary" id="monitorStartBtn" onclick="startMonitor()">Auto Start</button>
            <button class="btn btn-small btn-danger" id="monitorStopBtn" onclick="stopMonitor()" style="display:none">Auto Stop</button>
            <button class="btn btn-small" onclick="attachScreenshot()" title="프롬프트에 첨부">Attach</button>
            <select id="monitorInterval" style="padding:3px 6px;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;font-size:11px">
                <option value="10">10초</option>
                <option value="30" selected>30초</option>
                <option value="60">60초</option>
                <option value="120">2분</option>
            </select>
        </div>
    </div>
</div>

<script>
let activeSessionId = localStorage.getItem('sm_activeSessionId') || null;
let ws = null;
let autoScroll = true;

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
}

// Auto-detect API base: direct access (port 8006) uses /api,
// shell iframe (port 3000) uses /api/claude proxy prefix
const API_BASE = window.location.port === '8006' ? '/api' : '/api/claude/api';
// 정적 파일(screenshots, uploads)은 Session Manager에서 직접 서빙
const STATIC_BASE = window.location.port === '8006' ? '' : '/api/claude';

async function api(method, path, body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API_BASE}${path}`, opts);
    let data;
    try {
        data = await res.json();
    } catch (_) {
        return { error: 'Invalid server response', status: res.status };
    }
    // FastAPI HTTPException: {"detail":"..."} → {"error":"..."} 로 정규화
    if (!res.ok && data.detail && !data.error) data.error = data.detail;
    return data;
}

function staticUrl(path) {
    return `${STATIC_BASE}${path}`;
}

async function refreshSessions() {
    const list = await api('GET', '/sessions');
    if (!Array.isArray(list)) return;  // API 오류 시 렌더 스킵
    const el = document.getElementById('sessionList');

    // activeSessionId가 현재 목록에 없으면 초기화
    if (activeSessionId && !list.find(s => s.id === activeSessionId)) {
        activeSessionId = null;
        try { localStorage.removeItem('sm_activeSessionId'); } catch(e) {}
        document.getElementById('sessionActions').style.display = 'none';
        if (list.length > 0) selectSession(list[0].id);
    }

    if (list.length === 0) {
        el.innerHTML = '<div class="empty-state"><p>No sessions</p></div>';
        return;
    }

    el.innerHTML = list.map(s => {
        let statusClass = s.alive ? (s.busy ? 'busy' : 'alive') : 'dead';
        let statusText = s.alive ? (s.busy ? 'Working...' : 'Ready') : 'Stopped';
        let queueInfo = s.queue_size > 0 ? ` (${s.queue_size} queued)` : '';

        return `
        <div class="session-item ${s.id === activeSessionId ? 'active' : ''}"
             onclick="selectSession('${s.id}')">
            <div class="session-name">${escHtml(s.name)}</div>
            <div class="session-meta">
                <span class="status-dot ${statusClass}"></span>
                ${statusText}${queueInfo}
                &middot; ${escHtml(s.work_dir)}
                ${s.model ? `&middot; <span style="color:var(--purple)">${escHtml(s.model.replace('claude-','').split('-202')[0])}</span>` : ''}
                ${s.skip_permissions ? '&middot; <span style="color:var(--green);font-size:10px" title="권한 자동 승인">&#9989;</span>' : ''}
                ${(s.total_input_tokens + s.total_output_tokens) > 0 ? `&middot; <span style="font-size:10px;color:var(--text-dim)" title="토큰: ${s.total_input_tokens} in / ${s.total_output_tokens} out">${formatTokens(s.total_input_tokens + s.total_output_tokens)}</span>` : ''}
            </div>
        </div>`;
    }).join('');
}

function selectSession(id) {
    activeSessionId = id;
    try { localStorage.setItem('sm_activeSessionId', id); } catch(e) { console.warn('localStorage 저장 실패', e); }
    document.getElementById('sessionActions').style.display = 'flex';
    refreshSessions();
    connectWebSocket(id);
    // 세션 전환 시 파이프라인 상태 갱신
    if (pipelinePollTimer) { clearInterval(pipelinePollTimer); pipelinePollTimer = null; }
    activePipelineId = getActivePipelineForSession();
    // 현재 pipeline 탭이 활성이면 바로 리로드
    const pipelineView = document.getElementById('pipelineView');
    if (pipelineView && pipelineView.style.display !== 'none') {
        loadPipelinesForSession();
    }
    // Auto-close sidebar on mobile
    if (window.innerWidth <= 768) {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebarOverlay');
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
    }
}

let wsReconnectTimer = null;
let wsReconnectAttempts = 0;

let wsConnectId = 0;  // 연결 ID — 세션 전환 시 stale 메시지 차단

function connectWebSocket(sessionId) {
    wsConnectId++;  // 새 연결 ID 발급 — 이전 WS 메시지 무시
    if (ws) {
        ws.onmessage = null;  // 즉시 메시지 수신 차단
        ws.onclose = null;    // 자동 재연결 차단
        ws.close();
        ws = null;
    }
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
    wsReconnectAttempts = 0;

    // 터미널 초기화 — 이전 세션 출력 잔상 제거
    document.getElementById('terminalOutput').textContent = 'Connecting...';

    _doConnect(sessionId);
}

function _doConnect(sessionId) {
    // stale reconnect 차단: 타이머가 이미 큐에 들어간 후 세션 전환된 경우
    if (activeSessionId !== sessionId) return;
    const myConnectId = wsConnectId;  // 클로저에 캡처
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsBase = window.location.port === '8006' ? '' : '/svc/claude';
    ws = new WebSocket(`${proto}//${location.host}${wsBase}/ws/${sessionId}`);

    ws.onopen = () => { wsReconnectAttempts = 0; };

    ws.onmessage = (e) => {
        // 세션 전환 후 도착한 stale 메시지 차단 (이중 검증)
        if (myConnectId !== wsConnectId) return;
        if (activeSessionId !== sessionId) return;  // activeSessionId 불일치 시 무시
        let data;
        try { data = JSON.parse(e.data); }
        catch (_) { console.warn('WS: JSON 파싱 실패', e.data?.substring?.(0, 100)); return; }
        if (data.error) {
            ws.close();
            ws = null;
            return;
        }
        if (data.output !== undefined) {
            const el = document.getElementById('terminalOutput');
            el.textContent = data.output;

            // AskUserQuestion 클릭 가능 옵션 렌더
            const qPanel = document.getElementById('questionPanel');
            if (data.pending_question && !data.busy) {
                renderQuestionPanel(data.pending_question);
            } else {
                qPanel.style.display = 'none';
            }

            if (autoScroll) el.scrollTop = el.scrollHeight;
        }
        // 상태 배지 업데이트
        const badge = document.getElementById('statusBadge');
        if (data.busy) {
            badge.textContent = 'Working...';
            badge.className = 'status-badge busy';
        } else {
            let q = data.queue_size || 0;
            badge.textContent = q > 0 ? `${q} queued` : 'Idle';
            badge.className = 'status-badge';
        }
        // 토큰 표시
        if (data.tokens) {
            const tb = document.getElementById('tokenBadge');
            if (tb) tb.textContent = `${formatTokens(data.tokens.input + data.tokens.output)} tokens`;
        }
    };

    ws.onclose = () => {
        // 세션 전환으로 닫힌 경우 재연결 차단
        if (myConnectId !== wsConnectId) return;
        ws = null;
        // 자동 재연결 (최대 10회, 점진적 대기)
        if (activeSessionId === sessionId && wsReconnectAttempts < 10) {
            wsReconnectAttempts++;
            const delay = Math.min(1000 * wsReconnectAttempts, 5000);
            wsReconnectTimer = setTimeout(() => _doConnect(sessionId), delay);
        }
    };
    ws.onerror = () => { /* onclose에서 처리 */ };
}

async function createSession() {
    const work_dir = document.getElementById('newWorkDir').value || '.';
    const prompt = document.getElementById('newPrompt').value || '';
    const model = document.getElementById('newModel').value || '';
    const skip_permissions = document.getElementById('newSkipPermissions').checked;
    const mcp_config = document.getElementById('newMcpConfig').value || '';
    const result = await api('POST', '/sessions', { work_dir, prompt, model, skip_permissions, mcp_config });

    if (result.error) {
        alert('Error: ' + result.error);
        return;
    }

    hideNewSessionModal();
    await refreshSessions();
    selectSession(result.id);
}

async function killSession() {
    if (!activeSessionId) return;
    if (!confirm('Kill this session?')) return;
    await api('DELETE', `/sessions/${activeSessionId}`);
    refreshSessions();
}

async function removeSession() {
    if (!activeSessionId) return;
    if (!confirm('Remove this session from list?')) return;
    await api('DELETE', `/sessions/${activeSessionId}?remove=true`);
    activeSessionId = null;
    localStorage.removeItem('sm_activeSessionId');
    document.getElementById('sessionActions').style.display = 'none';
    document.getElementById('terminalOutput').innerHTML = '<div class="empty-state"><span class="icon">&#9000;</span><p>Select or create a session to start</p></div>';
    if (ws) { ws.onmessage = null; ws.onclose = null; ws.close(); ws = null; }
    refreshSessions();
}

// ─── 파일 첨부 ──────────────────────────────────────────────
let pendingAttachments = [];

async function handleFileSelect(event) {
    for (const file of event.target.files) await uploadFile(file);
    event.target.value = '';
}

async function handleFileDrop(event) {
    event.preventDefault();
    event.target.style.borderColor = 'var(--border)';
    for (const file of event.dataTransfer.files) await uploadFile(file);
}

async function uploadFile(file) {
    if (!activeSessionId) { alert('세션을 선택하세요'); return; }
    if (file.size > 10 * 1024 * 1024) { alert('파일 크기는 10MB 이하여야 합니다'); return; }
    const _allowedExts = ['png','jpg','jpeg','gif','bmp','webp','pdf','txt','md'];
    const _ext = file.name.split('.').pop()?.toLowerCase() || '';
    if (!_allowedExts.includes(_ext)) { alert('지원하지 않는 파일 형식입니다'); return; }
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch(`${API_BASE}/sessions/${activeSessionId}/upload`, {
            method: 'POST', body: formData
        });
        const data = await res.json();
        if (!res.ok) { alert(data.detail || 'Upload failed'); return; }
        pendingAttachments.push(data);
        renderAttachmentPreview();
    } catch (e) { alert('Upload error: ' + e.message); }
}

function renderAttachmentPreview() {
    const el = document.getElementById('attachmentPreview');
    if (pendingAttachments.length === 0) { el.style.display = 'none'; return; }
    el.style.display = 'flex';
    el.innerHTML = pendingAttachments.map((a, i) =>
        `<div style="background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;padding:2px 6px;font-size:11px;display:flex;align-items:center;gap:4px">` +
        (a.url.match(/\.(jpg|jpeg|png|gif|webp)$/i)
            ? `<img src="${staticUrl(a.url)}" style="height:24px;border-radius:2px">` : '&#128196;') +
        `<span>${escapeHtml(a.filename)}</span>` +
        `<span onclick="removeAttachment(${i})" style="cursor:pointer;color:var(--red)">&times;</span>` +
        `</div>`
    ).join('');
}

function removeAttachment(index) {
    pendingAttachments.splice(index, 1);
    renderAttachmentPreview();
}

// 클립보드 이미지 붙여넣기
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('commandInput');
    if (input) input.addEventListener('paste', async (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;
        for (const item of items) {
            if (item.type.startsWith('image/')) {
                e.preventDefault();
                const blob = item.getAsFile();
                const ext = item.type.split('/')[1] || 'png';
                const file = new File([blob], `clipboard_${Date.now()}.${ext}`, {type: item.type});
                await uploadFile(file);
            }
        }
    });
});

// ─── 스크린 모니터 ──────────────────────────────────────────
let monitorAutoRefresh = null;

function toggleMonitorPanel() {
    const panel = document.getElementById('monitorPanel');
    panel.style.display = panel.style.display === 'none' ? '' : 'none';
}

async function captureScreen() {
    try {
        const data = await api('GET', '/monitor/capture');
        if (data.url) {
            const img = document.getElementById('monitorImage');
            img.src = staticUrl(data.url) + '?t=' + Date.now();
            img.style.display = '';
            img._path = data.path;
            document.getElementById('monitorPlaceholder').style.display = 'none';
        }
    } catch (e) { alert('캡처 실패: ' + (e.message || e)); }
}

async function startMonitor() {
    const interval = parseInt(document.getElementById('monitorInterval').value) || 30;
    await api('POST', `/monitor/start?interval=${interval}`);
    document.getElementById('monitorStartBtn').style.display = 'none';
    document.getElementById('monitorStopBtn').style.display = '';
    // 프론트엔드 자동 갱신
    if (monitorAutoRefresh) clearInterval(monitorAutoRefresh);
    monitorAutoRefresh = setInterval(async () => {
        const data = await api('GET', '/monitor/latest');
        if (data.url) {
            const img = document.getElementById('monitorImage');
            img.src = staticUrl(data.url) + '?t=' + Date.now();
            img.style.display = '';
            document.getElementById('monitorPlaceholder').style.display = 'none';
        }
    }, (interval + 2) * 1000);
    captureScreen();
}

async function stopMonitor() {
    await api('POST', '/monitor/stop');
    document.getElementById('monitorStartBtn').style.display = '';
    document.getElementById('monitorStopBtn').style.display = 'none';
    if (monitorAutoRefresh) { clearInterval(monitorAutoRefresh); monitorAutoRefresh = null; }
}

async function attachScreenshot() {
    let data = await api('GET', '/monitor/latest');
    if (!data.path) data = await api('GET', '/monitor/capture');
    if (data.path) {
        pendingAttachments.push({ filename: 'screenshot.jpg', path: data.path, url: data.url });
        renderAttachmentPreview();
    }
}

function handleInputKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendCommand();
    }
    // 입력 후 높이 자동 조절
    requestAnimationFrame(() => {
        const el = e.target;
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    });
}

let isSending = false;

async function sendCommand() {
    if (!activeSessionId) return;
    if (isSending) return;
    const input = document.getElementById('commandInput');
    const command = input.value.trim();
    if (!command && pendingAttachments.length === 0) return;

    const body = { command: command || '첨부된 파일을 확인하세요.' };
    if (pendingAttachments.length > 0) {
        body.attachments = pendingAttachments.map(a => a.path);
    }

    isSending = true;
    try {
        await api('POST', `/sessions/${activeSessionId}/send`, body);
        input.value = '';
        input.style.height = '38px';
        pendingAttachments = [];
        renderAttachmentPreview();
    } finally {
        isSending = false;
    }
}

function renderQuestionPanel(questionData) {
    const panel = document.getElementById('questionPanel');
    const questions = questionData.questions || [];
    if (questions.length === 0) { panel.style.display = 'none'; return; }

    let html = '<div style="font-size:12px;color:var(--accent);font-weight:600;margin-bottom:8px">&#10067; Claude가 질문합니다 — 클릭으로 답변하세요</div>';

    for (const q of questions) {
        html += `<div style="font-size:13px;color:var(--text);margin-bottom:6px;font-weight:500">${escapeHtml(q.question)}</div>`;
        html += '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px">';
        const opts = q.options || [];
        for (const opt of opts) {
            const label = opt.label || '';
            const desc = opt.description || '';
            html += `<button onclick="answerQuestion('${escapeHtml(label)}')"
                style="padding:6px 12px;background:var(--bg-secondary);border:1px solid var(--border);border-radius:6px;color:var(--text);cursor:pointer;font-size:12px;text-align:left;transition:all 0.15s;max-width:280px"
                onmouseover="this.style.borderColor='var(--accent)';this.style.color='var(--accent)'"
                onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--text)'"
                title="${escapeHtml(desc)}">
                <div style="font-weight:500">${escapeHtml(label)}</div>
                ${desc ? `<div style="font-size:11px;color:var(--text-dim);margin-top:2px">${escapeHtml(desc)}</div>` : ''}
            </button>`;
        }
        // "직접 입력" 버튼
        html += `<button onclick="document.getElementById('commandInput').focus()"
            style="padding:6px 12px;background:var(--bg);border:1px dashed var(--border);border-radius:6px;color:var(--text-dim);cursor:pointer;font-size:12px"
            title="직접 답변 입력">
            <div style="font-weight:500">직접 입력...</div>
        </button>`;
        html += '</div>';
    }
    panel.innerHTML = html;
    panel.style.display = '';
}

function answerQuestion(answer) {
    if (!activeSessionId) return;
    api('POST', `/sessions/${activeSessionId}/send`, { command: answer });
    document.getElementById('questionPanel').style.display = 'none';
}

async function interruptSession() {
    if (!activeSessionId) return;
    await api('POST', `/sessions/${activeSessionId}/interrupt`);
}

// ─── 유틸리티 함수 ─────────────────────────────────────────────
function formatTokens(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
}

function hideModal(id) {
    document.getElementById(id).classList.remove('active');
}

// ─── 세션 이름 변경 ─────────────────────────────────────────────
async function renameSession() {
    if (!activeSessionId) return;
    const name = prompt('새 세션 이름:');
    if (!name) return;
    await api('PATCH', `/sessions/${activeSessionId}/rename`, { name });
    refreshSessions();
}

// ─── 세션 분기(Fork) ────────────────────────────────────────────
async function forkSession() {
    if (!activeSessionId) return;
    const name = prompt('분기 세션 이름 (비워두면 자동 생성):') || '';
    const res = await api('POST', `/sessions/${activeSessionId}/fork`, { new_name: name });
    if (res.id) {
        await refreshSessions();
        selectSession(res.id);
    }
}

// ─── 대화 내보내기 ──────────────────────────────────────────────
async function exportSession() {
    if (!activeSessionId) return;
    const res = await api('GET', `/sessions/${activeSessionId}/export`);
    if (!res.markdown) return;
    const blob = new Blob([res.markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${res.name || 'session'}.md`;
    a.click();
    URL.revokeObjectURL(url);
}

// ─── 프롬프트 템플릿 ────────────────────────────────────────────
async function showTemplates() {
    document.getElementById('templateModal').classList.add('active');
    await loadTemplateList();
}

// 템플릿 프롬프트를 인덱스로 참조 — onclick에 사용자 데이터 직접 삽입 방지
let _tplPrompts = [];

async function loadTemplateList() {
    const templates = await api('GET', '/templates');
    const el = document.getElementById('templateList');
    if (!Array.isArray(templates) || templates.length === 0) {
        el.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:20px;font-size:13px">저장된 템플릿이 없습니다</div>';
        return;
    }
    // 카테고리별 그룹핑
    _tplPrompts = [];  // 인덱스 배열 초기화
    const groups = {};
    for (const t of templates) {
        const cat = t.category || '기타';
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(t);
    }
    let html = '';
    for (const [cat, items] of Object.entries(groups)) {
        html += `<div style="font-size:11px;color:var(--accent);font-weight:600;margin:8px 0 4px">${escapeHtml(cat)}</div>`;
        for (const t of items) {
            const promptIdx = _tplPrompts.length;
            _tplPrompts.push(t.prompt);  // 사용자 데이터는 배열에 저장, onclick엔 숫자 인덱스만
            html += `<div style="display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:4px;cursor:pointer;margin-bottom:4px;background:var(--bg-secondary)" onmouseover="this.style.background='var(--bg-tertiary)'" onmouseout="this.style.background='var(--bg-secondary)'">
                <div style="flex:1;min-width:0" onclick="useTemplate(_tplPrompts[${promptIdx}])">
                    <div style="font-size:13px;font-weight:500;color:var(--text)">${escapeHtml(t.name)}</div>
                    <div style="font-size:11px;color:var(--text-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(t.prompt.substring(0, 80))}</div>
                </div>
                <button onclick="deleteTemplate('${t.id}')" class="btn btn-small" style="font-size:10px;color:var(--red);padding:2px 6px" title="삭제">&#10005;</button>
            </div>`;
        }
    }
    el.innerHTML = html;
}

async function saveTemplate() {
    const name = document.getElementById('tplName').value.trim();
    const prompt = document.getElementById('tplPrompt').value.trim();
    const category = document.getElementById('tplCategory').value.trim();
    if (!name || !prompt) { alert('이름과 프롬프트를 입력하세요'); return; }
    await api('POST', '/templates', { name, prompt, category });
    document.getElementById('tplName').value = '';
    document.getElementById('tplPrompt').value = '';
    document.getElementById('tplCategory').value = '';
    await loadTemplateList();
}

async function deleteTemplate(id) {
    await api('DELETE', `/templates/${id}`);
    await loadTemplateList();
}

function useTemplate(prompt) {
    const el = document.getElementById('commandInput');
    el.value = prompt.replace(/\\n/g, '\n');
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    hideModal('templateModal');
    el.focus();
}

// ─── CLAUDE.md 편집기 ───────────────────────────────────────────
async function showClaudeMdEditor() {
    if (!activeSessionId) return;
    const res = await api('GET', `/sessions/${activeSessionId}/claude-md`);
    document.getElementById('claudeMdPath').textContent = res.path || '';
    document.getElementById('claudeMdContent').value = res.content || '';
    document.getElementById('claudeMdModal').classList.add('active');
}

async function saveClaudeMd() {
    if (!activeSessionId) return;
    const content = document.getElementById('claudeMdContent').value;
    const res = await api('PUT', `/sessions/${activeSessionId}/claude-md`, { content });
    if (res.status === 'saved') {
        hideModal('claudeMdModal');
    } else {
        alert('저장 실패: ' + (res.detail || ''));
    }
}

// ─── 멀티 모델 비교 ────────────────────────────────────────────
async function showCompare() {
    document.getElementById('compareModal').classList.add('active');
    document.getElementById('compareResults').innerHTML = '';
}

let compareSessionIds = {};
let comparePollTimer = null;

async function startCompare() {
    const prompt = document.getElementById('comparePrompt').value.trim();
    if (!prompt) { alert('프롬프트를 입력하세요'); return; }
    const models = [...document.querySelectorAll('.cmpModel:checked')].map(cb => cb.value);
    if (models.length === 0) { alert('최소 1개 모델을 선택하세요'); return; }

    // 현재 세션의 work_dir 사용
    let work_dir = '.';
    if (activeSessionId) {
        const sessions = await api('GET', '/sessions');
        const s = Array.isArray(sessions) ? sessions.find(s => s.id === activeSessionId) : null;
        if (s) work_dir = s.work_dir;
    }

    const res = await api('POST', '/compare', { prompt, models, work_dir, skip_permissions: true });
    if (res.error) { alert(res.error); return; }
    compareSessionIds = res.sessions; // {model: sessionId}
    document.getElementById('compareResults').innerHTML = models.map(m =>
        `<div style="margin-bottom:12px">
            <div style="font-size:12px;font-weight:600;color:var(--purple);margin-bottom:4px">${m}</div>
            <pre id="cmpResult_${m}" style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px;font-size:11px;color:var(--text);max-height:300px;overflow-y:auto;white-space:pre-wrap;min-height:60px">실행 중...</pre>
        </div>`
    ).join('');

    if (comparePollTimer) clearInterval(comparePollTimer);
    comparePollTimer = setInterval(pollCompare, 2000);
}

async function pollCompare() {
    let allDone = true;
    // /sessions를 루프 외부에서 1회만 호출 (이전: 모델 수만큼 반복 호출)
    let sessions = [];
    try {
        const res = await api('GET', '/sessions');
        sessions = Array.isArray(res) ? res : [];
    } catch (e) { allDone = false; }
    for (const [model, sid] of Object.entries(compareSessionIds)) {
        try {
            const data = await api('GET', `/sessions/${sid}/output`);
            const el = document.getElementById(`cmpResult_${model}`);
            if (el) el.textContent = data.output || '(대기 중...)';
        } catch (e) {}
        const s = sessions.find(s => s.id === sid);
        if (!s || s.busy) allDone = false;
    }
    if (allDone) {
        clearInterval(comparePollTimer);
        comparePollTimer = null;
    }
}

function showNewSessionModal() {
    document.getElementById('newSessionModal').classList.add('active');
    document.getElementById('newWorkDir').focus();
    loadProjects();
}

function hideNewSessionModal() {
    document.getElementById('newSessionModal').classList.remove('active');
    document.getElementById('browserPanel').style.display = 'none';
}

// ─── 폴더 탐색기 ────────────────────────────────────────────────────

let browserOpen = false;
let currentBrowsePath = '';
let starredPaths = new Set();

function toggleBrowser() {
    browserOpen = !browserOpen;
    document.getElementById('browserPanel').style.display = browserOpen ? 'block' : 'none';
    if (browserOpen) browseTo('');
}

async function browseTo(path) {
    currentBrowsePath = path;
    const data = await api('GET', `/browse?path=${encodeURIComponent(path)}`);
    if (data.error) return;

    // 프로젝트 목록에서 starred 경로 가져오기
    const projects = await api('GET', '/projects');
    starredPaths = new Set(Array.isArray(projects) ? projects.map(p => p.path) : []);

    // 빵 부스러기 네비게이션
    const bc = document.getElementById('browserBreadcrumb');
    if (data.current) {
        let parts = data.current.replace(/\\/g, '/').split('/').filter(Boolean);
        let accumulated = '';
        let crumbs = '<span onclick="browseTo(\'\')">Drives</span>';
        for (let i = 0; i < parts.length; i++) {
            accumulated += parts[i] + (i === 0 && parts[i].endsWith(':') ? '\\' : '\\');
            crumbs += ` / <span onclick="browseTo('${accumulated.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}')">${escHtml(parts[i])}</span>`;
        }
        bc.innerHTML = crumbs;
    } else {
        bc.innerHTML = '<span>Drives</span>';
    }

    // 아이템 목록
    const el = document.getElementById('browserItems');
    if (data.parent) {
        el.innerHTML = `<div class="browser-item" onclick="browseTo('${data.parent.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}')">
            <span class="icon">&#8592;</span><span class="name">..</span></div>`;
    } else {
        el.innerHTML = '';
    }

    el.innerHTML += data.items.map(item => {
        let icon = item.type === 'drive' ? '&#128430;' : item.type === 'project' ? '&#128193;' : '&#128194;';
        let isStarred = starredPaths.has(item.path);
        const safePath = item.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const safeName = item.name.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        return `<div class="browser-item">
            <span class="icon">${icon}</span>
            <span class="name" onclick="onBrowserItemClick('${safePath}', '${item.type}')">${escHtml(item.name)}${item.type === 'project' ? ' (git)' : ''}</span>
            <span class="actions">
                ${item.type !== 'drive' ? `<span class="star-btn ${isStarred ? 'starred' : ''}" onclick="toggleStar('${safePath}', '${safeName}')">&#9733;</span>` : ''}
                <button class="btn btn-small" onclick="selectFolder('${safePath}')">Select</button>
            </span>
        </div>`;
    }).join('');
}

function onBrowserItemClick(path, type) {
    browseTo(path);
}

function selectFolder(path) {
    document.getElementById('newWorkDir').value = path;
    document.getElementById('browserPanel').style.display = 'none';
    browserOpen = false;
}

async function toggleStar(path, name) {
    if (starredPaths.has(path)) {
        await api('DELETE', '/projects', { path });
        starredPaths.delete(path);
    } else {
        await api('POST', '/projects', { path, name });
        starredPaths.add(path);
    }
    loadProjects();
    if (browserOpen) browseTo(currentBrowsePath);
}

// ─── 프로젝트 관리 ──────────────────────────────────────────────────

async function loadProjects() {
    const projects = await api('GET', '/projects');
    const el = document.getElementById('projectsSection');

    if (!Array.isArray(projects) || projects.length === 0) {
        el.innerHTML = '';
        return;
    }

    el.innerHTML = `<h4>Saved Projects</h4>` +
        projects.map(p => {
            const safePath = p.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
            return `
            <span class="project-chip" onclick="selectFolder('${safePath}')">
                &#128193; ${escHtml(p.name)}
                <span class="remove" onclick="event.stopPropagation(); removeProject('${safePath}')">&#10005;</span>
            </span>
        `;
        }).join('');
}

async function removeProject(path) {
    await api('DELETE', '/projects', { path });
    loadProjects();
}

function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    event.target.closest('.tab').classList.add('active');  // 자식 클릭 시에도 탭 div에 active 적용

    document.getElementById('terminalView').classList.add('hidden');
    document.getElementById('logsView').classList.remove('active');
    document.getElementById('gitView').classList.remove('active');
    document.getElementById('pipelineView').style.display = 'none';

    if (tab === 'terminal') {
        document.getElementById('terminalView').classList.remove('hidden');
    } else if (tab === 'git') {
        document.getElementById('gitView').classList.add('active');
        autoFillGitPath();
        loadGitProjects();
    } else if (tab === 'logs') {
        document.getElementById('logsView').classList.add('active');
        loadLogs();
    } else if (tab === 'pipeline') {
        document.getElementById('pipelineView').style.display = 'flex';
        loadPipelinesForSession();
    }
}

// ─── Git 연동 ────────────────────────────────────────────────────────

function getGitPath() {
    return document.getElementById('gitRepoPath').value.trim();
}

function autoFillGitPath() {
    const input = document.getElementById('gitRepoPath');
    if (input.value.trim()) return; // 이미 입력되어 있으면 스킵

    // 1) 활성 세션의 work_dir 사용
    if (activeSessionId) {
        const item = document.querySelector('.session-item.active .session-meta');
        if (item) {
            const meta = item.textContent;
            const parts = meta.split('·');
            if (parts.length > 1) {
                const wd = parts[1].trim();  // work_dir는 항상 두 번째 파트 (parts[0]=상태, parts[1]=work_dir)
                if (wd && wd !== '.') {
                    input.value = wd;
                    return;
                }
            }
        }
    }
}

async function loadGitProjects() {
    const projects = await api('GET', '/projects');
    const el = document.getElementById('gitProjectChips');

    if (!Array.isArray(projects) || projects.length === 0) {
        el.style.display = 'none';
        return;
    }

    el.style.display = 'flex';
    el.innerHTML = projects.map(p => {
        const safePath = p.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        return `<span class="project-chip" onclick="selectGitRepo('${safePath}')">&#128193; ${escHtml(p.name)}</span>`;
    }).join('');
}

function selectGitRepo(path) {
    document.getElementById('gitRepoPath').value = path;
    loadGitInfo();
}

async function loadGitInfo() {
    const path = getGitPath();
    if (!path) { alert('Repository 경로를 입력하세요'); return; }

    await Promise.all([loadGitStatus(path), loadGitLog(path), loadGitPRs('open'), loadGitIssues('open'), loadRemoteInfo()]);
}

async function loadGitStatus(path) {
    path = path || getGitPath();
    if (!path) return;
    const data = await api('GET', `/git/status?path=${encodeURIComponent(path)}`);
    if (data.error) { console.error(data.error); return; }

    document.getElementById('gitBranch').textContent = data.branch;

    const syncEl = document.getElementById('gitSync');
    let syncParts = [];
    if (data.ahead > 0) syncParts.push(`<span class="ahead">↑${data.ahead}</span>`);
    if (data.behind > 0) syncParts.push(`<span class="behind">↓${data.behind}</span>`);
    syncEl.innerHTML = syncParts.join('') || '<span>in sync</span>';

    const listEl = document.getElementById('gitFileList');
    if (data.files.length === 0) {
        listEl.innerHTML = '<li style="padding:12px 14px;color:var(--green);font-size:12px">Working tree clean</li>';
    } else {
        listEl.innerHTML = data.files.map(f => {
            let cls = f.status.includes('M') ? 'M' : f.status.includes('A') ? 'A' : f.status.includes('D') ? 'D' : f.status === '??' ? 'QQ' : 'U';
            return `<li class="git-file-item"><span class="git-file-status ${cls}">${f.status}</span><span>${escHtml(f.file)}</span></li>`;
        }).join('');
    }
}

async function loadGitLog(path) {
    path = path || getGitPath();
    if (!path) return;
    const data = await api('GET', `/git/log?path=${encodeURIComponent(path)}&limit=15`);
    if (data.error) return;

    const el = document.getElementById('gitCommitList');
    if (!data.commits || data.commits.length === 0) {
        el.innerHTML = '<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">No commits</li>';
        return;
    }

    el.innerHTML = data.commits.map(c =>
        `<li class="git-commit-item">
            <span class="git-commit-hash">${c.short}</span>
            <span class="git-commit-msg">${escHtml(c.message)}</span>
            <span class="git-commit-meta">${escHtml(c.author)} · ${escHtml(c.date)}</span>
        </li>`
    ).join('');
}

async function loadGitPRs(state) {
    const path = getGitPath();
    if (!path) return;
    const data = await api('GET', `/git/prs?path=${encodeURIComponent(path)}&state=${state}`);
    const el = document.getElementById('gitPRList');

    if (data.error && (!data.prs || data.prs.length === 0)) {
        el.innerHTML = `<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">${escHtml(data.error)}</li>`;
        return;
    }

    if (!data.prs || data.prs.length === 0) {
        el.innerHTML = `<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">No ${state} PRs</li>`;
        return;
    }

    el.innerHTML = data.prs.map(pr =>
        `<li class="pr-item">
            <span class="pr-number">#${pr.number}</span>
            <span class="pr-title">${escHtml(pr.title)}</span>
            ${pr.headRefName ? `<span class="pr-branch">${escHtml(pr.headRefName)}</span>` : ''}
            <a href="${pr.url && pr.url.startsWith('https://') ? pr.url : '#'}" target="_blank">Open</a>
        </li>`
    ).join('');
}

async function loadGitIssues(state) {
    const path = getGitPath();
    if (!path) return;
    const data = await api('GET', `/git/issues?path=${encodeURIComponent(path)}&state=${state}`);
    const el = document.getElementById('gitIssueList');

    if (data.error && (!data.issues || data.issues.length === 0)) {
        el.innerHTML = `<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">${escHtml(data.error)}</li>`;
        return;
    }

    if (!data.issues || data.issues.length === 0) {
        el.innerHTML = `<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">No ${state} issues</li>`;
        return;
    }

    el.innerHTML = data.issues.map(issue => {
        let labels = (issue.labels || []).map(l =>
            `<span class="issue-label" style="background:${l.color ? '#'+l.color : 'var(--purple)'}">${escHtml(l.name)}</span>`
        ).join(' ');
        return `<li class="issue-item">
            <span class="issue-number">#${issue.number}</span>
            <span class="issue-title">${escHtml(issue.title)}</span>
            ${labels}
            <a href="${issue.url && issue.url.startsWith('https://') ? issue.url : '#'}" target="_blank">Open</a>
        </li>`;
    }).join('');
}

// ─── Remote GitHub ────────────────────────────────────────────────

async function checkGhAuth() {
    const bar = document.getElementById('ghAuthBar');
    bar.style.display = 'flex';
    bar.innerHTML = '<span style="color:var(--text-dim)">Checking gh auth...</span>';

    const data = await api('GET', '/git/gh-auth');
    const dot = data.ok ? '<span class="gh-auth-dot ok"></span>' : '<span class="gh-auth-dot fail"></span>';
    const msg = data.ok ? 'GitHub CLI: Authenticated' : 'GitHub CLI: Not authenticated (run <code>gh auth login</code>)';
    bar.innerHTML = `${dot}<span>${msg}</span>`;
}

async function loadRemoteInfo() {
    const path = getGitPath();
    if (!path) return;

    const el = document.getElementById('gitRemoteInfo');
    el.innerHTML = '<span style="color:var(--text-dim)">Loading...</span>';

    const data = await api('GET', `/git/remote?path=${encodeURIComponent(path)}`);

    let html = '';

    // Remote URLs
    if (data.remotes && data.remotes.length > 0) {
        html += data.remotes.map(r =>
            `<div class="remote-info-item">
                <span class="label">${escHtml(r.name)}:</span>
                <span class="value">${escHtml(r.url)}</span>
            </div>`
        ).join('');
    } else {
        html += '<div class="remote-info-item"><span class="label">No remotes configured</span></div>';
    }

    // GitHub repo info
    if (data.github) {
        const gh = data.github;
        const vis = gh.isPrivate ? '<span class="gh-repo-badge private">Private</span>' : '<span class="gh-repo-badge public">Public</span>';
        const defBranch = gh.defaultBranchRef ? gh.defaultBranchRef.name : '-';
        html += `<div style="width:100%;margin-top:6px;padding-top:8px;border-top:1px solid var(--border);display:flex;flex-wrap:wrap;gap:10px;align-items:center">
            <a href="${gh.url && gh.url.startsWith('https://') ? gh.url : '#'}" target="_blank" style="color:var(--accent);font-weight:600;text-decoration:none">${escHtml(gh.owner?.login || '')}/${escHtml(gh.name)}</a>
            ${vis}
            <span class="gh-stat">&#9733; ${gh.stargazerCount || 0}</span>
            <span class="gh-stat">&#128259; ${gh.forkCount || 0}</span>
            <span class="gh-stat">default: ${escHtml(defBranch)}</span>
        </div>`;
        if (gh.description) {
            html += `<div style="width:100%;font-size:11px;color:var(--text-dim);margin-top:2px">${escHtml(gh.description)}</div>`;
        }
    }

    el.innerHTML = html || '<span style="color:var(--text-dim)">No remote info</span>';
}

async function handleCloneSearch() {
    const input = document.getElementById('ghCloneUrl').value.trim();
    if (!input) return;

    // If it looks like a URL or owner/repo, treat as direct ref; otherwise search
    const isUrl = input.startsWith('http') || input.startsWith('git@') || /^[\w.-]+\/[\w.-]+$/.test(input);
    if (isUrl) {
        // URL/owner-repo 형식 — 리스트에 안내 표시 후 Clone 버튼 대기
        document.getElementById('ghRepoList').innerHTML =
            '<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">&#10003; Clone 준비 완료 — 아래 Clone 버튼을 누르세요.</li>';
        return;
    }

    // Search GitHub repos
    const el = document.getElementById('ghRepoList');
    el.innerHTML = '<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">Searching...</li>';

    const data = await api('GET', `/git/gh-repos?query=${encodeURIComponent(input)}`);
    if (data.error && (!data.repos || data.repos.length === 0)) {
        el.innerHTML = `<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">${escHtml(data.error)}</li>`;
        return;
    }

    if (!data.repos || data.repos.length === 0) {
        el.innerHTML = '<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">No repos found</li>';
        return;
    }

    el.innerHTML = data.repos.map(r => {
        const name = r.fullName || `${r.owner?.login || ''}/${r.name}`;
        const url = r.url || '';
        const desc = r.description || '';
        const vis = r.isPrivate ? '<span class="gh-repo-badge private">Private</span>' : '<span class="gh-repo-badge public">Public</span>';
        const safeUrl = url.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        return `<li class="gh-repo-item" onclick="selectGhRepo('${safeUrl}')">
            <span class="gh-repo-name">${escHtml(name)}</span>
            ${vis}
            <span class="gh-repo-desc">${escHtml(desc)}</span>
        </li>`;
    }).join('');
}

function selectGhRepo(url) {
    document.getElementById('ghCloneUrl').value = url;
}

async function cloneRepo() {
    const url = document.getElementById('ghCloneUrl').value.trim();
    const dest = document.getElementById('ghCloneDest').value.trim();
    if (!url) { alert('Clone URL을 입력하세요'); return; }

    const outputEl = document.getElementById('gitCmdOutput');
    outputEl.textContent = `$ git clone ${url}${dest ? ' ' + dest : ''}\nCloning...`;
    outputEl.className = 'git-cmd-output visible';

    const data = await api('POST', '/git/clone', { url, dest });

    let output = `$ git clone ${url}${dest ? ' ' + dest : ''}\n`;
    if (data.stdout) output += data.stdout + '\n';
    if (data.stderr) output += data.stderr + '\n';
    if (data.ok) {
        output += `\nCloned to: ${data.path}`;
        // Auto-set as repo path
        document.getElementById('gitRepoPath').value = data.path;
        loadGitInfo();
    } else {
        output += '(failed)';
    }

    outputEl.textContent = output;
    outputEl.className = 'git-cmd-output visible' + (data.ok ? '' : ' error');
}

async function loadMyRepos() {
    const el = document.getElementById('ghRepoList');
    el.innerHTML = '<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">Loading your repos...</li>';

    const data = await api('GET', '/git/gh-repos');
    if (!data.repos || data.repos.length === 0) {
        el.innerHTML = `<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">${escHtml(data.error || 'No repos found')}</li>`;
        return;
    }

    el.innerHTML = data.repos.map(r => {
        const name = r.fullName || `${r.owner?.login || ''}/${r.name}`;
        const url = r.url || '';
        const desc = r.description || '';
        const vis = r.isPrivate ? '<span class="gh-repo-badge private">Private</span>' : '<span class="gh-repo-badge public">Public</span>';
        const safeUrl = url.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        return `<li class="gh-repo-item" onclick="selectGhRepo('${safeUrl}')">
            <span class="gh-repo-name">${escHtml(name)}</span>
            ${vis}
            <span class="gh-repo-desc">${escHtml(desc)}</span>
        </li>`;
    }).join('');
}

async function runGitCmd() {
    const path = getGitPath();
    const cmd = document.getElementById('gitCmdInput').value.trim();
    if (!path) { alert('Repository 경로를 입력하세요'); return; }
    if (!cmd) return;

    const outputEl = document.getElementById('gitCmdOutput');
    outputEl.textContent = `$ git ${cmd}\nRunning...`;
    outputEl.className = 'git-cmd-output visible';

    const data = await api('POST', '/git/exec', { path, command: cmd });

    let output = `$ git ${cmd}\n`;
    if (data.stdout) output += data.stdout + '\n';
    if (data.stderr) output += data.stderr + '\n';
    if (data.ok) output += '(success)';
    else output += '(failed)';

    outputEl.textContent = output;
    outputEl.className = 'git-cmd-output visible' + (data.ok ? '' : ' error');

    document.getElementById('gitCmdInput').value = '';
    // refresh status
    loadGitStatus(path);
    loadGitLog(path);
}

function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

let _logFilenames = [];

async function loadLogs() {
    const logs = await api('GET', '/logs');
    const el = document.getElementById('logsList');
    document.getElementById('logViewer').style.display = 'none';
    el.style.display = 'block';

    if (!Array.isArray(logs) || logs.length === 0) {
        el.innerHTML = '<div class="empty-state"><p>No logs yet</p></div>';
        return;
    }

    _logFilenames = [];
    el.innerHTML = logs.map(l => {
        const idx = _logFilenames.length;
        _logFilenames.push(l.filename);
        return `
        <div class="log-item" onclick="viewLog(_logFilenames[${idx}])">
            <span class="log-name">${escHtml(l.filename)}</span>
            <span class="log-meta">${formatSize(l.size)} &middot; ${formatDate(l.modified)}</span>
        </div>`;
    }).join('');
}

async function viewLog(filename) {
    const data = await api('GET', `/logs/${encodeURIComponent(filename)}`);
    document.getElementById('logsList').style.display = 'none';
    const viewer = document.getElementById('logViewer');
    viewer.style.display = 'block';
    viewer.textContent = data.content || 'Empty log';
}

let _searchLogsTimer = null;
async function searchLogs() {
    // 300ms 디바운스 — 연속 클릭/Enter 시 마지막 호출만 실행
    clearTimeout(_searchLogsTimer);
    await new Promise(resolve => { _searchLogsTimer = setTimeout(resolve, 300); });

    const query = document.getElementById('logSearchInput').value;
    if (!query) { loadLogs(); return; }

    const logs = await api('GET', '/logs');
    if (!Array.isArray(logs)) return;
    const viewer = document.getElementById('logViewer');
    const listEl = document.getElementById('logsList');
    listEl.style.display = 'none';
    viewer.style.display = 'block';
    viewer.textContent = '검색 중...';

    // 순차 N회 호출 → Promise.all 병렬 호출로 교체
    const responses = await Promise.all(
        logs.map(log => api('GET', `/logs/${encodeURIComponent(log.filename)}?search=${encodeURIComponent(query)}`))
    );

    const results = [];
    responses.forEach((data, i) => {
        if (data.matches > 0) {
            results.push(`=== ${logs[i].filename} (${data.matches} matches) ===\n${data.content}`);
        }
    });

    viewer.textContent = results.length > 0 ? results.join('\n\n') : 'No matches found.';
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + 'KB';
    return (bytes / 1048576).toFixed(1) + 'MB';
}

function formatDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
}

// 스크롤 감지 - 사용자가 위로 스크롤하면 자동 스크롤 중지
document.getElementById('terminalOutput')?.addEventListener('scroll', function() {
    const el = this;
    autoScroll = (el.scrollTop + el.clientHeight >= el.scrollHeight - 50);
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hideNewSessionModal();
    if (e.key === 'n' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        showNewSessionModal();
    }
});

refreshSessions().then(() => {
    // 이전에 선택했던 세션 복원
    if (activeSessionId) {
        selectSession(activeSessionId);
    }
});
window._refreshSessionsTimer = setInterval(refreshSessions, 5000);

// ─── Pipeline ──────────────────────────────────────────────────────
// 세션별 파이프라인 관리
let activePipelineId = null;
let pipelinePollTimer = null;
const sessionPipelineMap = (() => { try { return JSON.parse(localStorage.getItem('sm_sessionPipelineMap') || '{}'); } catch(e) { return {}; } })();

function getActivePipelineForSession() {
    return activeSessionId ? (sessionPipelineMap[activeSessionId] || null) : null;
}

function setActivePipelineForSession(pipelineId) {
    activePipelineId = pipelineId;
    if (activeSessionId) {
        sessionPipelineMap[activeSessionId] = pipelineId;
        try { localStorage.setItem('sm_sessionPipelineMap', JSON.stringify(sessionPipelineMap)); } catch(e) { console.warn('localStorage 저장 실패', e); }
    }
}

function onPipelineModeChange() {
    const mode = document.getElementById('pipelineMode').value;
    document.getElementById('pipelineApiKeyGroup').style.display = mode === 'api' ? '' : 'none';
}

async function loadPipelinesForSession() {
    /* Pipeline 탭 진입 시 현재 세션의 파이프라인 목록 로드 */
    // 세션별 파이프라인 ID 복원
    activePipelineId = getActivePipelineForSession();

    // 이전 폴링 중지
    if (pipelinePollTimer) { clearInterval(pipelinePollTimer); pipelinePollTimer = null; }

    // UI 초기화
    document.getElementById('pipelineStartBtn').style.display = '';
    document.getElementById('pipelineStopBtn').style.display = 'none';
    document.getElementById('pipelineStatusBar').style.display = 'none';
    document.getElementById('pipelineSummary').style.display = 'none';
    document.getElementById('pipelineListBar').innerHTML = '';

    try {
        const all = await api('GET', '/pipelines');
        if (!Array.isArray(all)) return;
        // 현재 세션의 파이프라인만 필터
        const mine = activeSessionId ? all.filter(p => p.session_id === activeSessionId || p.worker_session_id === activeSessionId) : all;

        if (mine.length === 0) {
            activePipelineId = null;
            document.getElementById('pipelineHistory').innerHTML =
                '<div style="text-align:center;padding:40px;color:var(--text-dim)">' +
                '<p style="font-size:14px">LLM 감독자가 Claude CLI를 자동으로 구동합니다</p>' +
                '<p style="font-size:12px;margin-top:8px">세션을 선택하고, 목표를 입력한 후 Start를 누르세요</p></div>';
            return;
        }

        // 가장 최근 running 파이프라인이 있으면 자동 선택
        const running = mine.find(p => p.status === 'running');
        const latest = running || mine[mine.length - 1];
        if (latest && (!activePipelineId || !mine.find(p => p.id === activePipelineId))) {
            activePipelineId = latest.id;
            setActivePipelineForSession(activePipelineId);
        }

        // 파이프라인 목록 (항상 표시 — 세션별 히스토리)
        let listHtml = '<div style="display:flex;gap:6px;flex-wrap:wrap">';
        for (const p of mine) {
            const active = p.id === activePipelineId;
            const color = { running:'var(--orange)', completed:'var(--green)', failed:'var(--red)', stopped:'var(--text-dim)' }[p.status] || 'var(--text-dim)';
            const cycleInfo = p.max_cycles > 1 ? ` C${p.current_cycle}` : '';
            listHtml += `<button onclick="selectPipeline('${p.id}')" class="btn btn-small" style="font-size:11px;${active?'border-color:var(--accent);color:var(--accent)':''}">` +
                `<span style="color:${color}">&#9679;</span> #${p.id.substring(0,6)} (iter ${p.iteration}/${p.max_iterations}${cycleInfo})</button>`;
        }
        listHtml += '</div>';
        document.getElementById('pipelineListBar').innerHTML = listHtml;

        if (activePipelineId) {
            // 현재 파이프라인 상태 복원
            document.getElementById('pipelineStatusBar').style.display = '';
            pollPipeline();
            const ap = mine.find(p => p.id === activePipelineId);
            if (ap && ap.status === 'running') {
                document.getElementById('pipelineStartBtn').style.display = 'none';
                document.getElementById('pipelineStopBtn').style.display = '';
                startPipelinePolling();
            }
        }
    } catch (e) { console.error('loadPipelinesForSession error:', e); }
}

function selectPipeline(id) {
    setActivePipelineForSession(id);
    if (pipelinePollTimer) { clearInterval(pipelinePollTimer); pipelinePollTimer = null; }
    // UI 리셋
    document.getElementById('pipelineStartBtn').style.display = '';
    document.getElementById('pipelineStopBtn').style.display = 'none';
    document.getElementById('pipelineSummary').style.display = 'none';
    document.getElementById('pipelineStatusBar').style.display = '';
    pollPipeline();
    // running이면 폴링 재개
    api('GET', `/pipelines/${id}`).then(data => {
        if (data.status === 'running') {
            document.getElementById('pipelineStartBtn').style.display = 'none';
            document.getElementById('pipelineStopBtn').style.display = '';
            startPipelinePolling();
        }
    });
}

async function startPipeline() {
    if (!activeSessionId) {
        alert('먼저 세션을 선택하세요');
        return;
    }
    const goal = document.getElementById('pipelineGoal').value.trim();
    if (!goal) { alert('목표를 입력하세요'); return; }

    const mode = document.getElementById('pipelineMode').value;
    const body = {
        session_id: activeSessionId,
        goal: goal,
        mode: mode,
        supervisor_model: document.getElementById('pipelineSupervisorModel').value,
        max_iterations: parseInt(document.getElementById('pipelineMaxIter').value) || 20,
        max_cycles: parseInt(document.getElementById('pipelineMaxCycles').value) || 100,
    };

    try {
        const res = await api('POST', '/pipelines', body);
        if (res.error) { alert(res.error); return; }
        setActivePipelineForSession(res.pipeline_id);
        document.getElementById('pipelineStartBtn').style.display = 'none';
        document.getElementById('pipelineStopBtn').style.display = '';
        document.getElementById('pipelineStatusBar').style.display = '';
        document.getElementById('pipelineSummary').style.display = 'none';
        document.getElementById('pipelineHistory').innerHTML = '';
        startPipelinePolling();
        // pw-* worker 세션으로 자동 전환하여 파이프라인 출력 즉시 확인
        if (res.worker_session_id) {
            try { await refreshSessions(); } catch (_) { /* 갱신 실패해도 선택은 진행 */ }
            selectSession(res.worker_session_id);
        }
    } catch (e) {
        alert('파이프라인 시작 실패: ' + e.message);
    }
}

async function stopPipeline() {
    if (!activePipelineId) return;
    try {
        await api('POST', `/pipelines/${activePipelineId}/stop`);
    } catch (e) { console.error(e); }
}

function startPipelinePolling() {
    if (pipelinePollTimer) clearInterval(pipelinePollTimer);
    pipelinePollTimer = setInterval(pollPipeline, 1500);
    pollPipeline();
}

async function pollPipeline() {
    if (!activePipelineId) return;
    try {
        const data = await api('GET', `/pipelines/${activePipelineId}`);
        if (data.error) {
            // 파이프라인 없음(404) 등 → 폴링 중지
            clearInterval(pipelinePollTimer);
            pipelinePollTimer = null;
            return;
        }

        // 상태 업데이트 (사이클 포함)
        const totalMax = data.max_cycles * data.max_iterations;
        const totalIter = data.total_iterations || ((data.current_cycle - 1) * data.max_iterations + data.iteration);
        const pct = totalMax > 0 ? Math.round((totalIter / totalMax) * 100) : 0;
        document.getElementById('pipelineProgressBar').style.width = pct + '%';
        const cycleText = data.max_cycles > 1 ? `Cycle ${data.current_cycle}/${data.max_cycles} | ` : '';
        document.getElementById('pipelineIterText').textContent = `${cycleText}Iter ${data.iteration}/${data.max_iterations} (${totalIter} total)`;

        const statusColors = { running: 'var(--orange)', completed: 'var(--green)', failed: 'var(--red)', stopped: 'var(--text-dim)' };
        const modeLabel = data.mode === 'cli' ? 'CLI' : 'API';
        const statusLabels = { running: `실행 중 [${modeLabel}]...`, completed: '완료', failed: '실패', stopped: '중단됨', idle: '대기' };
        const stEl = document.getElementById('pipelineStatusText');
        stEl.textContent = statusLabels[data.status] || data.status;
        stEl.style.color = statusColors[data.status] || 'var(--text)';

        // 세션 정보 표시
        const infoEl = document.getElementById('pipelineSessionInfo');
        if (infoEl) infoEl.textContent = `세션: ${data.session_id} | 모드: ${modeLabel} | 모델: ${data.supervisor_model}`;

        // 히스토리 렌더
        renderPipelineHistory(data.history);

        // 완료/실패/중단 시 폴링 중지
        if (data.status !== 'running') {
            clearInterval(pipelinePollTimer);
            pipelinePollTimer = null;
            document.getElementById('pipelineStartBtn').style.display = '';
            document.getElementById('pipelineStopBtn').style.display = 'none';

            if (data.summary) {
                document.getElementById('pipelineSummary').style.display = '';
                document.getElementById('pipelineSummaryText').textContent = data.summary;
            }
        }
    } catch (e) { console.error('Pipeline poll error:', e); }
}

function renderPipelineHistory(history) {
    const el = document.getElementById('pipelineHistory');
    let html = '';
    let currentIter = 0;

    for (const h of history) {
        if (h.iteration > currentIter) {
            currentIter = h.iteration;
            html += `<div style="font-size:11px;color:var(--accent);font-weight:600;margin:12px 0 6px;padding-top:8px;border-top:1px solid var(--border)">Iteration ${currentIter}</div>`;
        }

        const time = `<span style="color:var(--text-dim);font-size:11px;margin-right:6px">${escHtml(h.timestamp)}</span>`;

        if (h.role === 'supervisor') {
            html += `<div style="margin:4px 0;padding:8px 10px;background:var(--bg-secondary);border-radius:6px;border-left:3px solid var(--purple);font-size:12px">
                ${time}<span style="color:var(--purple);font-weight:500">Supervisor &#8594; CLI</span>
                <div style="margin-top:4px;white-space:pre-wrap;color:var(--text);max-height:200px;overflow-y:auto;font-family:monospace;font-size:11px">${escapeHtml(h.content.substring(0, 500))}${h.content.length > 500 ? '...' : ''}</div>
            </div>`;
        } else if (h.role === 'cli_result') {
            html += `<div style="margin:4px 0;padding:8px 10px;background:var(--bg-tertiary);border-radius:6px;border-left:3px solid var(--green);font-size:12px">
                ${time}<span style="color:var(--green);font-weight:500">CLI &#8594; Supervisor</span>
                <details style="margin-top:4px"><summary style="cursor:pointer;color:var(--text-dim);font-size:11px">결과 보기 (${h.content.length}자)</summary>
                <div style="margin-top:4px;white-space:pre-wrap;color:var(--text);max-height:300px;overflow-y:auto;font-family:monospace;font-size:11px">${escapeHtml(h.content)}</div>
                </details>
            </div>`;
        } else if (h.role === 'system') {
            html += `<div style="margin:4px 0;font-size:11px;color:var(--text-dim);font-style:italic">${time}${escapeHtml(h.content)}</div>`;
        } else if (h.role === 'error') {
            html += `<div style="margin:4px 0;padding:6px 10px;background:rgba(248,81,73,0.1);border-radius:4px;font-size:12px;color:var(--red)">${time}${escapeHtml(h.content)}</div>`;
        }
    }

    el.innerHTML = html || '<div style="text-align:center;padding:40px;color:var(--text-dim)"><p>파이프라인을 시작하면 여기에 진행 내용이 표시됩니다</p></div>';
    el.scrollTop = el.scrollHeight;
}

function escapeHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,'&#39;').replace(/"/g,'&quot;');
}

// ─── Plan Phase (계획 수립) ──────────────────────────────────────
let activePlanId = null;
let planPollTimer = null;

async function startPlanPhase() {
    if (!activeSessionId) {
        alert('먼저 세션을 선택하세요');
        return;
    }
    const goal = document.getElementById('pipelineGoal').value.trim();
    if (!goal) { alert('목표를 입력하세요'); return; }

    const mode = document.getElementById('pipelineMode').value;
    const body = {
        session_id: activeSessionId,
        goal: goal,
        mode: mode,
        supervisor_model: document.getElementById('pipelineSupervisorModel').value,
    };

    try {
        const res = await api('POST', '/plan-phases', body);
        if (res.error) { alert(res.error); return; }
        activePlanId = res.plan_id;
        document.getElementById('planPhaseContainer').style.display = '';
        document.getElementById('planPhaseContent').innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-dim)"><div class="spinner" style="margin:0 auto 12px"></div>질문 생성 중...</div>';
        startPlanPolling();
    } catch (e) {
        alert('계획 수립 시작 실패: ' + e.message);
    }
}

function startPlanPolling() {
    if (planPollTimer) clearInterval(planPollTimer);
    planPollTimer = setInterval(pollPlanPhase, 1500);
    pollPlanPhase();
}

async function pollPlanPhase() {
    if (!activePlanId) return;
    try {
        const data = await api('GET', `/plan-phases/${activePlanId}`);
        if (data.error) {
            clearInterval(planPollTimer);
            planPollTimer = null;
            return;
        }

        if (data.status === 'questions_generating') {
            document.getElementById('planPhaseContent').innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-dim)"><div class="spinner" style="margin:0 auto 12px"></div>질문 생성 중...</div>';
        } else if (data.status === 'questions_ready') {
            clearInterval(planPollTimer);
            planPollTimer = null;
            renderPlanQuestions(data.questions);
        } else if (data.status === 'plan_generating') {
            document.getElementById('planPhaseContent').innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-dim)"><div class="spinner" style="margin:0 auto 12px"></div>실행 계획 생성 중...</div>';
        } else if (data.status === 'plan_ready') {
            clearInterval(planPollTimer);
            planPollTimer = null;
            renderPlanReview(data.plan_text);
        } else if (data.status === 'approved') {
            clearInterval(planPollTimer);
            planPollTimer = null;
            closePlanPhase();
        } else if (data.status === 'error') {
            clearInterval(planPollTimer);
            planPollTimer = null;
            document.getElementById('planPhaseContent').innerHTML = `
                <div style="padding:16px;color:var(--red)">
                    <div style="font-weight:600;margin-bottom:8px">오류 발생</div>
                    <div style="font-size:12px;margin-bottom:12px">${escapeHtml(data.error)}</div>
                    <button class="btn btn-small" onclick="retryPlanPhase()" style="background:var(--orange);color:white">재시도</button>
                    <button class="btn btn-small" onclick="closePlanPhase()" style="margin-left:6px">닫기</button>
                </div>`;
        }
    } catch (e) { console.error('Plan poll error:', e); }
}

function renderPlanQuestions(questions) {
    const el = document.getElementById('planPhaseContent');
    let html = '<div style="font-size:13px;color:var(--purple);font-weight:600;margin-bottom:12px">&#128203; 계획 수립 — 아래 질문에 답변해주세요</div>';

    for (const q of questions) {
        const qid = q.id || 'q0';
        html += `<div style="margin-bottom:16px;padding:12px;background:var(--bg-secondary);border-radius:8px;border-left:3px solid var(--purple)">`;
        html += `<div style="font-size:13px;font-weight:500;color:var(--text);margin-bottom:4px">${escapeHtml(q.question)}</div>`;
        if (q.why) {
            html += `<div style="font-size:11px;color:var(--text-dim);margin-bottom:8px">${escapeHtml(q.why)}</div>`;
        }
        html += `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px">`;
        for (const opt of (q.options || [])) {
            const label = opt.label || '';
            const desc = opt.description || '';
            html += `<button onclick="selectPlanOption('${qid}', this, '${escapeHtml(label).replace(/'/g, "\\'")}')"
                class="plan-opt-btn" data-qid="${qid}"
                style="padding:6px 12px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);cursor:pointer;font-size:12px;text-align:left;transition:all 0.15s;max-width:280px"
                onmouseover="this.style.borderColor='var(--purple)'"
                onmouseout="if(!this.classList.contains('plan-selected'))this.style.borderColor='var(--border)'">
                <div style="font-weight:500">${escapeHtml(label)}</div>
                ${desc ? `<div style="font-size:11px;color:var(--text-dim);margin-top:2px">${escapeHtml(desc)}</div>` : ''}
            </button>`;
        }
        html += `</div>`;
        html += `<input type="text" placeholder="직접 입력..." data-qid="${qid}" class="plan-custom-input"
            oninput="onPlanCustomInput('${qid}', this)"
            style="width:100%;padding:6px 8px;background:var(--bg);border:1px dashed var(--border);border-radius:4px;color:var(--text);font-size:12px;box-sizing:border-box">`;
        html += `</div>`;
    }

    html += `<div style="display:flex;gap:8px;margin-top:12px">
        <button class="btn btn-primary btn-small" onclick="submitPlanAnswers()">답변 제출</button>
        <button class="btn btn-small" onclick="closePlanPhase()">취소</button>
    </div>`;

    el.innerHTML = html;
}

// 질문별 선택 상태 저장
const planSelectedAnswers = {};

function selectPlanOption(qid, btnEl, label) {
    // 같은 질문의 다른 버튼 선택 해제
    document.querySelectorAll(`button.plan-opt-btn[data-qid="${qid}"]`).forEach(b => {
        b.classList.remove('plan-selected');
        b.style.borderColor = 'var(--border)';
        b.style.background = 'var(--bg)';
    });
    // 선택 하이라이트
    btnEl.classList.add('plan-selected');
    btnEl.style.borderColor = 'var(--purple)';
    btnEl.style.background = 'rgba(137,87,229,0.1)';
    planSelectedAnswers[qid] = label;
    // 직접 입력 필드 초기화
    const input = document.querySelector(`input.plan-custom-input[data-qid="${qid}"]`);
    if (input) input.value = '';
}

function onPlanCustomInput(qid, inputEl) {
    if (inputEl.value.trim()) {
        planSelectedAnswers[qid] = inputEl.value.trim();
        // 옵션 버튼 선택 해제
        document.querySelectorAll(`button.plan-opt-btn[data-qid="${qid}"]`).forEach(b => {
            b.classList.remove('plan-selected');
            b.style.borderColor = 'var(--border)';
            b.style.background = 'var(--bg)';
        });
    }
}

async function submitPlanAnswers() {
    if (!activePlanId) return;
    if (Object.keys(planSelectedAnswers).length === 0) {
        alert('최소 하나의 질문에 답변해주세요');
        return;
    }

    try {
        const res = await api('POST', `/plan-phases/${activePlanId}/answers`, { answers: planSelectedAnswers });
        if (res.error) { alert(res.error); return; }
        document.getElementById('planPhaseContent').innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-dim)"><div class="spinner" style="margin:0 auto 12px"></div>실행 계획 생성 중...</div>';
        startPlanPolling();
    } catch (e) {
        alert('답변 제출 실패: ' + e.message);
    }
}

function renderPlanReview(planText) {
    const el = document.getElementById('planPhaseContent');
    // simple markdown → HTML (headers, bold, lists)
    let rendered = escapeHtml(planText)
        .replace(/^### (.+)$/gm, '<h4 style="color:var(--accent);margin:12px 0 6px;font-size:13px">$1</h4>')
        .replace(/^## (.+)$/gm, '<h3 style="color:var(--text);margin:14px 0 8px;font-size:14px">$1</h3>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^- (.+)$/gm, '<div style="padding-left:12px;margin:2px 0">&#8226; $1</div>')
        .replace(/^(\d+)\. (.+)$/gm, '<div style="padding-left:12px;margin:4px 0"><strong>$1.</strong> $2</div>')
        .replace(/\n/g, '<br>');

    let html = `<div style="font-size:13px;color:var(--purple);font-weight:600;margin-bottom:12px">&#128203; 실행 계획 검토</div>`;
    html += `<div id="planReviewDisplay" style="font-size:12px;line-height:1.6;padding:12px;background:var(--bg-secondary);border-radius:8px;border-left:3px solid var(--green);margin-bottom:8px">${rendered}</div>`;
    html += `<div style="margin-bottom:12px">
        <label style="font-size:11px;color:var(--text-dim);display:block;margin-bottom:4px">계획 편집 (선택사항)</label>
        <textarea id="planEditArea" rows="6" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:8px;font-size:12px;resize:vertical;font-family:monospace;box-sizing:border-box;display:none">${escapeHtml(planText)}</textarea>
        <button class="btn btn-small" onclick="togglePlanEdit()" style="font-size:11px;margin-top:4px">편집 모드</button>
    </div>`;
    html += `<div style="display:flex;gap:8px">
        <button class="btn btn-primary btn-small" onclick="approvePlan()">승인 및 실행</button>
        <button class="btn btn-small" onclick="regeneratePlan()" style="background:var(--orange);color:white">재생성</button>
        <button class="btn btn-small" onclick="closePlanPhase()">취소</button>
    </div>`;

    el.innerHTML = html;
}

function togglePlanEdit() {
    const area = document.getElementById('planEditArea');
    const display = document.getElementById('planReviewDisplay');
    if (area.style.display === 'none') {
        area.style.display = '';
        display.style.display = 'none';
    } else {
        area.style.display = 'none';
        display.style.display = '';
    }
}

async function approvePlan() {
    if (!activePlanId) return;
    const editArea = document.getElementById('planEditArea');
    const edited = editArea && editArea.style.display !== 'none' ? editArea.value : null;

    const body = {
        plan_text: edited,
        max_iterations: parseInt(document.getElementById('pipelineMaxIter').value) || 20,
        max_cycles: parseInt(document.getElementById('pipelineMaxCycles').value) || 100,
    };

    try {
        const res = await api('POST', `/plan-phases/${activePlanId}/approve`, body);
        if (res.error) { alert(res.error); return; }

        closePlanPhase();

        // 파이프라인 시작됨 → 파이프라인 UI로 전환
        if (res.pipeline_id) {
            setActivePipelineForSession(res.pipeline_id);
            document.getElementById('pipelineStartBtn').style.display = 'none';
            document.getElementById('pipelineStopBtn').style.display = '';
            document.getElementById('pipelineStatusBar').style.display = '';
            document.getElementById('pipelineSummary').style.display = 'none';
            document.getElementById('pipelineHistory').innerHTML = '';
            startPipelinePolling();
            if (res.worker_session_id) {
                try { await refreshSessions(); } catch (_) {}
                selectSession(res.worker_session_id);
            }
        }
    } catch (e) {
        alert('계획 승인 실패: ' + e.message);
    }
}

async function regeneratePlan() {
    if (!activePlanId) return;
    try {
        await api('POST', `/plan-phases/${activePlanId}/regenerate`);
        document.getElementById('planPhaseContent').innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-dim)"><div class="spinner" style="margin:0 auto 12px"></div>실행 계획 재생성 중...</div>';
        startPlanPolling();
    } catch (e) {
        alert('재생성 실패: ' + e.message);
    }
}

async function retryPlanPhase() {
    closePlanPhase();
    // 선택 상태 초기화 후 다시 시작
    Object.keys(planSelectedAnswers).forEach(k => delete planSelectedAnswers[k]);
    startPlanPhase();
}

function closePlanPhase() {
    if (planPollTimer) { clearInterval(planPollTimer); planPollTimer = null; }
    document.getElementById('planPhaseContainer').style.display = 'none';
    document.getElementById('planPhaseContent').innerHTML = '';
    activePlanId = null;
    Object.keys(planSelectedAnswers).forEach(k => delete planSelectedAnswers[k]);
}

// ─── Shell Terminal (xterm.js) ────────────────────────────────
let shellTerm = null;
let shellWs = null;
let activeShellId = null;
let shellWsConnectId = 0;  // Shell WS stale 메시지 차단용

function onTerminalModeChange() {
    const mode = document.getElementById('terminalMode').value;
    const claudeEl = document.getElementById('claudeTerminal');
    const shellEl = document.getElementById('shellContainer');
    const shellTypeGroup = document.getElementById('shellTypeGroup');
    const shellActions = document.getElementById('shellActions');

    if (mode === 'claude') {
        claudeEl.style.display = '';
        shellEl.classList.remove('active');
        shellTypeGroup.style.display = 'none';
        shellActions.style.display = 'none';
    } else {
        claudeEl.style.display = 'none';
        shellEl.classList.add('active');
        shellTypeGroup.style.display = '';
        shellActions.style.display = 'flex';
        // 이미 연결된 shell이 없으면 빈 상태
        if (!shellTerm) initShellTerminal();
    }
}

function initShellTerminal() {
    if (shellTerm) return;
    const container = document.getElementById('shellTerminal');
    shellTerm = new Terminal({
        cursorBlink: true,
        cursorStyle: 'block',
        fontSize: 13,
        fontFamily: "'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace",
        theme: {
            background: '#0d1117',
            foreground: '#e6edf3',
            cursor: '#58a6ff',
            selectionBackground: '#264f78',
            black: '#0d1117',
            red: '#f85149',
            green: '#3fb950',
            yellow: '#d29922',
            blue: '#58a6ff',
            magenta: '#bc8cff',
            cyan: '#39d353',
            white: '#e6edf3',
        },
        allowProposedApi: true,
    });

    const fitAddon = new FitAddon.FitAddon();
    shellTerm.loadAddon(fitAddon);

    try {
        const webLinksAddon = new WebLinksAddon.WebLinksAddon();
        shellTerm.loadAddon(webLinksAddon);
    } catch(e) {}

    shellTerm.open(container);
    fitAddon.fit();

    shellTerm.writeln('\x1b[90m[ Shell Terminal — Connect 버튼을 눌러 시작하세요 ]\x1b[0m');

    // 키 입력 → WebSocket
    shellTerm.onData((data) => {
        if (shellWs && shellWs.readyState === WebSocket.OPEN) {
            shellWs.send(data);
        }
    });

    // 리사이즈 감지
    const resizeObserver = new ResizeObserver(() => {
        try {
            fitAddon.fit();
            if (shellWs && shellWs.readyState === WebSocket.OPEN) {
                shellWs.send(JSON.stringify({ type: 'resize', rows: shellTerm.rows, cols: shellTerm.cols }));
            }
        } catch(e) {}
    });
    resizeObserver.observe(container);

    // 전역 저장
    window._shellFitAddon = fitAddon;
}

async function createShellSession() {
    const shellType = document.getElementById('shellTypeSelect').value;
    // 작업 디렉토리: 활성 Claude 세션의 work_dir 사용
    let workDir = '.';
    if (activeSessionId) {
        try {
            const allSessions = await api('GET', '/sessions');
            if (Array.isArray(allSessions)) {
                const s = allSessions.find(s => s.id === activeSessionId);
                if (s) workDir = s.work_dir;
            }
        } catch(e) {}
    }

    if (!shellTerm) initShellTerminal();

    // 기존 shell 종료
    if (activeShellId) {
        try { await api('DELETE', `/shell/${activeShellId}`); } catch(e) {}
        if (shellWs) { shellWs.onmessage = null; shellWs.onclose = null; shellWs.close(); shellWs = null; }
        activeShellId = null;
    }

    const cols = shellTerm.cols || 120;
    const rows = shellTerm.rows || 30;

    try {
        const res = await api('POST', '/shell/create', {
            shell_type: shellType,
            work_dir: workDir,
            cols, rows
        });
        if (res.error) { alert('Shell 생성 실패: ' + res.error); return; }
        activeShellId = res.id;
        shellTerm.clear();
        shellTerm.writeln(`\x1b[90m[ ${shellType.toUpperCase()} connected — ${workDir} ]\x1b[0m\r\n`);
        connectShellWebSocket(res.id);
        document.getElementById('shellKillBtn').style.display = '';
    } catch(e) {
        alert('Shell 생성 실패: ' + e.message);
    }
}

function connectShellWebSocket(shellId) {
    shellWsConnectId++;  // 새 연결 ID — 이전 Shell WS 메시지 무시
    if (shellWs) {
        shellWs.onmessage = null;  // 즉시 메시지 수신 차단
        shellWs.onclose = null;    // 자동 종료 핸들러 차단
        shellWs.close();
        shellWs = null;
    }

    const myShellConnectId = shellWsConnectId;  // 클로저에 캡처
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsBase = window.location.port === '8006' ? '' : '/svc/claude';
    shellWs = new WebSocket(`${proto}//${location.host}${wsBase}/ws/shell/${shellId}`);

    shellWs.onopen = () => {
        if (myShellConnectId !== shellWsConnectId) return;
        // fit 후 resize 전달
        if (window._shellFitAddon) {
            try { window._shellFitAddon.fit(); } catch(e) {}
        }
        if (shellTerm && shellWs && shellWs.readyState === WebSocket.OPEN) {
            shellWs.send(JSON.stringify({ type: 'resize', rows: shellTerm.rows, cols: shellTerm.cols }));
        }
    };

    shellWs.onmessage = (e) => {
        if (myShellConnectId !== shellWsConnectId) return;  // stale guard
        if (shellTerm) shellTerm.write(e.data);
    };

    shellWs.onclose = () => {
        if (myShellConnectId !== shellWsConnectId) return;  // stale guard
        shellWs = null;
        if (shellTerm) {
            shellTerm.writeln('\r\n\x1b[90m[ 연결 종료됨 ]\x1b[0m');
        }
        document.getElementById('shellKillBtn').style.display = 'none';
    };

    shellWs.onerror = () => {};
}

async function killShellSession() {
    if (!activeShellId) return;
    try { await api('DELETE', `/shell/${activeShellId}`); } catch(e) {}
    if (shellWs) { shellWs.onmessage = null; shellWs.onclose = null; shellWs.close(); shellWs = null; }
    activeShellId = null;
    document.getElementById('shellKillBtn').style.display = 'none';
    if (shellTerm) shellTerm.writeln('\r\n\x1b[90m[ Shell 종료됨 ]\x1b[0m');
}

// 환경변수에 API Key가 있는지 확인
(async () => {
    try {
        const res = await api('GET', '/../health');
    } catch(e) {}
})();

// ─── Admin Panel ────────────────────────────────────────────────────
// /admin/* 엔드포인트는 API_BASE(/api)와 별도 경로
const ADMIN_BASE = window.location.port === '8006' ? '/admin' : '/api/claude/admin';

async function adminFetch(method, path, body = null) {
    try {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(`${ADMIN_BASE}${path}`, opts);
        return res.ok ? await res.json() : null;
    } catch (e) {
        console.error('[admin]', e);
        return null;
    }
}

async function pollAdminStatus() {
    const data = await adminFetch('GET', '/status');
    if (!data) return;

    const active = data.active_pipelines ?? 0;
    const resumable = data.resumable_runs ?? [];

    // 통계 배지 갱신
    const activeBadge = document.getElementById('adminActiveBadge');
    activeBadge.textContent = `실행 중: ${active}개`;
    activeBadge.className = 'admin-badge' + (active > 0 ? ' warn' : '');

    const statsEl = document.getElementById('adminStats');
    // 기존 복구 배지 제거 후 재렌더
    const oldResumeBadge = document.getElementById('adminResumableBadge');
    if (oldResumeBadge) oldResumeBadge.remove();
    if (resumable.length > 0) {
        const badge = document.createElement('span');
        badge.id = 'adminResumableBadge';
        badge.className = 'admin-badge warn';
        badge.textContent = `복구 가능: ${resumable.length}개`;
        statsEl.appendChild(badge);
    }

    // 재시작 버튼 활성/비활성
    const btn = document.getElementById('adminRestartBtn');
    if (data.safe_to_restart) {
        btn.disabled = false;
        btn.classList.add('safe');
    } else {
        btn.disabled = true;
        btn.classList.remove('safe');
    }

    // 복구 가능 목록
    const listEl = document.getElementById('resumableList');
    if (resumable.length === 0) {
        listEl.style.display = 'none';
        listEl.innerHTML = '';
    } else {
        listEl.style.display = 'flex';
        listEl.innerHTML = resumable.map(r => {
            const ts = (r.updated_at || r.created_at || '').replace('T', ' ').slice(0, 16);
            return `<div class="resumable-item">
                <span class="resumable-item-info" title="${r.id} | ${r.session_id}">
                    ${r.id} · S${r.current_stage} · ${ts}
                </span>
                <button class="btn btn-small" onclick="resumeRun('${r.id}')">재개</button>
            </div>`;
        }).join('');
    }
}

async function adminRestart() {
    if (!confirm('파이프라인이 없습니다. 서버를 재시작하시겠습니까?')) return;
    const btn = document.getElementById('adminRestartBtn');
    btn.disabled = true;
    btn.textContent = '재시작 중...';
    await adminFetch('POST', '/restart');
    setTimeout(() => location.reload(), 3000);
}

async function resumeRun(runId) {
    const data = await adminFetch('POST', `/resume/${runId}`);
    if (data) alert(`재개 요청: ${runId}\n(현재 미구현 — DB 체크포인트만 조회됩니다)`);
}

// 초기 로드 + 5초 폴링
pollAdminStatus();
setInterval(pollAdminStatus, 5000);

</script>

</body>
</html>"""


# ─── 엔트리포인트 ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("SERVICE_PORT", "8006"))
    print("=" * 60)
    print("  Claude Session Manager")
    print(f"  http://localhost:{port}")
    print("  Ctrl+C to stop")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port)
