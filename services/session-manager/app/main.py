"""
Claude Session Manager
Windows 네이티브 - Claude CLI 세션을 웹 UI로 관리하는 프로그램
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
import uvicorn

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
        return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    return []


def save_projects(projects: list[dict]):
    """프로젝트 목록 저장"""
    PROJECTS_FILE.write_text(json.dumps(projects, ensure_ascii=False, indent=2), encoding="utf-8")


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
            versions = sorted(claude_code_dir.iterdir(), reverse=True)
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

            if not session.alive and not session.busy:
                # created_at으로부터 TTL 초과 확인
                try:
                    created = datetime.fromisoformat(session.created_at)
                    if (now - created).total_seconds() > SESSION_TTL_SECONDS:
                        to_remove.append(sid)
                except Exception:
                    pass
        for sid in to_remove:
            try:
                sessions[sid].delete_state()
                await sessions[sid].kill()
            except Exception:
                pass
            sessions.pop(sid, None)
        if to_remove:
            print(f"  [cleanup] {len(to_remove)} dead session(s) removed")

        # 완료된 파이프라인도 정리
        pipe_remove = []
        for pid, pipe in pipelines.items():
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
            shell_sessions[sid].kill()
            shell_sessions.pop(sid, None)
        if shell_remove:
            print(f"  [cleanup] {len(shell_remove)} dead shell(s) removed")


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

            session = ClaudeSession.load_state(sid)

            # pw-* (고아 worker) → 파이프라인 바인딩 해제, 일반 세션으로 전환
            if sid.startswith("pw-"):
                session.pipeline_id = None
                session.pipeline_role = None
                pw_converted += 1

            # 저장된 opus 모델 → 기본 모델로 전환 (구독 미지원 방지)
            if session.model == "opus":
                session.model = ""

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
        print(f"  Converted {pw_converted} orphan worker(s) to normal session(s)")

    # 자동 정리 태스크 시작
    cleanup_task = asyncio.create_task(_cleanup_dead_sessions())
    print(f"  Session cleanup: every {CLEANUP_INTERVAL}s, TTL {SESSION_TTL_SECONDS}s")

    yield

    # 정리 태스크 중단
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    for session in sessions.values():
        await session.kill()
    for shell in list(shell_sessions.values()):
        shell.kill()


app = FastAPI(title="Claude Session Manager", lifespan=lifespan)

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
    mode: str = Field(default="cli", pattern="^(api|cli)$")

class ShellCreateRequest(BaseModel):
    shell_type: str = Field(default="cmd", pattern="^(cmd|powershell)$")
    work_dir: str = "."
    cols: int = Field(default=120, ge=40, le=400)
    rows: int = Field(default=30, ge=10, le=200)

class RenameSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)

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
        use_model = self.model if not _retry_without_model else ""

        cmd = [CLAUDE_EXE, "-p", "--output-format", "stream-json", "--verbose"]
        if self.skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        if self.no_tools:
            cmd.extend(["--tools", ""])

        if use_model:
            cmd.extend(["--model", use_model])

        if self.mcp_config:
            cmd.extend(["--mcp-config", self.mcp_config])

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
                cwd=self.work_dir if self.work_dir not in (".", "~") else None,
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
                    self._handle_stream_event(event)
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

        # 로그 파일 기록 (에러 시 무시 - 이벤트 루프 차단 방지)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"[{entry['time']}] [{otype}] {text}\n")
        except Exception:
            pass  # 로그 실패가 메인 동작을 방해하지 않도록

    async def send_prompt(self, prompt: str):
        """프롬프트를 큐에 추가"""
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
        self._buffer: list[str] = []  # 최근 출력 버퍼
        self._buffer_lock = threading.Lock()
        self._max_buffer = 50000  # 최대 버퍼 문자 수
        self._subscribers: list[asyncio.Queue] = []  # WebSocket 구독자 큐

    def start(self):
        """PTY 프로세스 시작"""
        if not HAS_WINPTY:
            raise RuntimeError("pywinpty not installed")

        if self.shell_type == "powershell":
            exe = shutil.which("powershell.exe") or "powershell.exe"
        else:
            exe = os.environ.get("COMSPEC", "cmd.exe")

        cwd = self.work_dir if self.work_dir not in (".", "~") else None

        self.pty = PtyProcess.spawn(
            exe,
            dimensions=(self.rows, self.cols),
            cwd=cwd,
        )
        self.alive = True

        # stdout 읽기 스레드 시작
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()

    def _push_data(self, data: str):
        """버퍼에 저장 + 구독자에게 전달"""
        with self._buffer_lock:
            self._buffer.append(data)
            total = sum(len(s) for s in self._buffer)
            while total > self._max_buffer and len(self._buffer) > 1:
                removed = self._buffer.pop(0)
                total -= len(removed)
        for q in self._subscribers[:]:
            try:
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
            except Exception:
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
        for q in self._subscribers[:]:
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
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """WebSocket 구독자 해제"""
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
- 목표가 완전히 달성되었으면: PIPELINE_DONE: [완료 요약]

## 현재 상태
- 반복: {iteration}/{max_iterations}
- 작업자 CLI 작업 디렉토리: {work_dir}"""


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
                 mode: str = "api"):
        self.id = str(uuid.uuid4())[:8]
        self._source_session = source_session  # 참조용 원본 세션 (설정 복사 목적)
        self.session: Optional[ClaudeSession] = None  # 전용 worker 세션 (start()에서 생성)
        self.goal = goal
        self.supervisor_model = supervisor_model
        self.max_iterations = max_iterations
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
        """파이프라인 전용 worker 세션 생성 — 원본 세션의 설정을 복사"""
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
        # sessions dict에 등록 (UI에서 확인 가능)
        sessions[wid] = worker
        worker.save_state()
        return worker

    def start(self):
        self.status = "running"
        self.session = self._create_worker_session()
        # 원본 세션에 파이프라인 바인딩 마킹
        self._source_session.pipeline_id = self.id
        self._source_session.save_state()
        if self.mode == "cli":
            self._create_supervisor_session()
        self._task = asyncio.create_task(self._run_loop())

    def _create_supervisor_session(self):
        """감독자용 CLI 세션 생성 (도구 차단 — 텍스트만 출력)

        감독자 세션은 sessions dict에 등록하지 않고, save_state를 no-op으로
        오버라이드하여 좀비 파일을 방지한다.
        """
        sid = f"sv-{self.id}"
        sv = ClaudeSession(sid, self.session.work_dir, self.supervisor_model,
                           no_tools=True,
                           skip_permissions=self.session.skip_permissions)
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
        # 감독자 세션도 종료
        if self._supervisor_session:
            await self._supervisor_session.kill()

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
            if session.busy or session._output_version != version_before:
                break
            await asyncio.sleep(0.5)

        # Phase 2: busy=False가 될 때까지 대기
        while session.busy:
            if self._stop_flag:
                return "[파이프라인 중단됨]"
            if time.time() - start > timeout:
                self._add_history("system", f"세션 실행 시간 초과 ({timeout}초)")
                return "[시간 초과]"
            await asyncio.sleep(1)

        return session.get_formatted_output(100)

    # ─── 메인 루프 ─────────────────────────────────────

    async def _run_loop(self):
        """메인 파이프라인 루프 — mode에 따라 감독자 방식 분기"""
        last_output = ""
        try:
            while self.iteration < self.max_iterations and not self._stop_flag:
                self.iteration += 1

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
                    return

                # 성공 시 재시도 카운터 리셋
                self._supervisor_retries = 0
                self._add_history("supervisor", supervisor_response)

                # 2. DONE 체크
                if "PIPELINE_DONE:" in supervisor_response:
                    idx = supervisor_response.index("PIPELINE_DONE:")
                    self.summary = supervisor_response[idx + len("PIPELINE_DONE:"):].strip()
                    self.status = "completed"
                    self._add_history("system", f"파이프라인 완료: {self.summary}")
                    return

                # 3. 작업자 CLI에 프롬프트 전달
                await self.session.send_prompt(supervisor_response)

                # 4. 작업자 CLI 완료 대기
                last_output = await self._wait_for_session(self.session)
                self._add_history("cli_result", last_output)

            # 최대 반복 도달
            if self.iteration >= self.max_iterations and not self._stop_flag:
                self.status = "completed"
                self.summary = f"최대 반복 횟수({self.max_iterations})에 도달하여 종료"
                self._add_history("system", self.summary)

        except Exception as e:
            self.status = "failed"
            self._add_history("error", f"파이프라인 오류: {str(e)}")
        finally:
            # 감독자 CLI 세션 정리 (kill + 디스크에서 삭제)
            if self._supervisor_session:
                await self._supervisor_session.kill()
                self._supervisor_session.delete_state()

            # worker 세션의 파이프라인 바인딩 해제 (세션 자체는 살려둠)
            if self.session:
                self.session.pipeline_id = None
                self.session.pipeline_role = None
                self.session.save_state()

            # 원본 세션의 파이프라인 바인딩도 해제
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
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            work_dir=self.session.work_dir,
        )

        messages = self._build_messages(last_output)

        response = await client.messages.create(
            model=self.supervisor_model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        )

        return response.content[0].text.strip()

    async def _call_supervisor_cli(self, last_output: str) -> str:
        """감독자 CLI 세션에 프롬프트 전달 → 결과 파싱"""
        sv = self._supervisor_session
        if not sv or not sv.alive:
            raise RuntimeError("감독자 CLI 세션이 종료됨")

        # 감독자에게 보낼 메시지 구성
        system_context = _SUPERVISOR_SYSTEM.format(
            goal=self.goal,
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            work_dir=self.session.work_dir,
        )

        if last_output:
            prompt = (
                f"{system_context}\n\n"
                f"---\n[반복 {self.iteration}/{self.max_iterations}]\n"
                f"작업자 CLI 실행 결과 (최근):\n"
                f"{last_output[-3000:]}\n\n"
                f"위 결과를 분석하고, 다음에 작업자 CLI에 보낼 프롬프트를 생성하세요. "
                f"프롬프트 본문만 출력하세요."
            )
        else:
            prompt = (
                f"{system_context}\n\n"
                f"---\n[반복 {self.iteration}/{self.max_iterations}]\n"
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
        import re
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
            user_msg = f"[반복 {self.iteration}/{self.max_iterations}]\nCLI 실행 결과:\n{last_output[-3000:]}"
        else:
            user_msg = f"[반복 {self.iteration}/{self.max_iterations}]\n목표를 달성하기 위한 첫 번째 프롬프트를 생성하세요."
        messages.append({"role": "user", "content": user_msg})
        return messages

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session.id if self.session else None,
            "source_session_id": self._source_session.id if self._source_session else None,
            "goal": self.goal,
            "supervisor_model": self.supervisor_model,
            "mode": self.mode,
            "status": self.status,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "summary": self.summary,
            "created_at": self.created_at,
            "history": self.history[-50:],
            "supervisor_retries": self._supervisor_retries,
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
    return [s.to_dict() for s in sessions.values()]


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

    session = sessions[session_id]
    await session.send_prompt(body.command)
    return {"status": "queued", "queue_size": session._queue.qsize()}


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


@app.get("/api/sessions/{session_id}/export")
async def export_session(session_id: str):
    """세션 대화를 Markdown으로 내보내기"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    md = sessions[session_id].export_markdown()
    return {"markdown": md, "name": sessions[session_id].name}


@app.post("/api/sessions/{session_id}/fork")
async def fork_session(session_id: str, body: ForkSessionRequest):
    """세션 복제 — 대화 기록과 session_uuid를 복사하여 분기"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
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
        return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
    return []


def _save_templates(templates: list[dict]):
    TEMPLATES_FILE.write_text(json.dumps(templates, ensure_ascii=False, indent=2),
                              encoding="utf-8")


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
            raise HTTPException(status_code=500, detail=str(e))
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
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "saved", "path": str(claude_md)}


# ─── 멀티 모델 비교 ──────────────────────────────────────────────────────────

@app.post("/api/compare")
async def compare_models(body: CompareRequest):
    """같은 프롬프트를 여러 모델에 보내고 결과 비교"""
    if not CLAUDE_EXE:
        raise HTTPException(status_code=503, detail="Claude CLI not available")

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
    dead_count = 0  # 죽은 세션 감지 카운터

    try:
        while True:
            # 세션이 목록에서 제거되었으면 종료
            if session_id not in sessions:
                await websocket.send_json({"error": "세션 제거됨"})
                break

            if session._output_version != last_version:
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

            # 죽은 세션이면 간격을 늘림 (리소스 절약)
            if not session.alive and not session.busy:
                dead_count += 1
                if dead_count > 150:  # 30초(0.2s*150) 이상 죽은 상태 → 연결 종료
                    break
                await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


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
            import string
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
    except (asyncio.TimeoutError, FileNotFoundError, Exception) as e:
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
            if len(line) >= 3:
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
    import shlex
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

    # dest가 없으면 현재 디렉토리에 repo 이름으로
    if dest:
        dest_path = Path(dest)
    else:
        # URL에서 repo 이름 추출
        repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
        dest_path = Path(".") / repo_name

    if dest_path.exists() and any(dest_path.iterdir()):
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
                            body.max_iterations, body.mode)
    pipelines[runner.id] = runner
    runner.start()

    return {
        "pipeline_id": runner.id,
        "worker_session_id": runner.session.id if runner.session else None,
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
        raise HTTPException(status_code=500, detail=str(e))
    shell_sessions[shell_id] = shell
    return shell.to_dict()


# 하위호환
@app.post("/api/shell/create")
async def create_shell_compat(body: ShellCreateRequest):
    return await create_shell(body)


@app.get("/api/shells")
async def list_shells():
    return [s.to_dict() for s in shell_sessions.values()]


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
                # resize 명령 감지
                if text.startswith("\x1b[8;"):
                    # xterm.js resize: ESC[8;rows;colst
                    try:
                        parts = text[4:-1].split(";")
                        rows, cols = int(parts[0]), int(parts[1])
                        shell.resize(cols, rows)
                    except Exception:
                        pass
                else:
                    shell.write(text)
            elif "bytes" in msg:
                shell.write(msg["bytes"].decode("utf-8", errors="replace"))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
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
                    <textarea id="commandInput" rows="1" placeholder="Enter prompt for Claude... (Shift+Enter = 줄바꿈)"
                              onkeydown="handleInputKeydown(event)"></textarea>
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
                    <div style="width:90px">
                        <label style="font-size:11px;color:var(--text-dim);display:block;margin-bottom:3px">최대 반복</label>
                        <input type="number" id="pipelineMaxIter" value="20" min="1" max="100" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:6px 8px;font-size:12px">
                    </div>
                    <div id="pipelineApiKeyGroup" style="flex:1;min-width:180px;display:none">
                        <label style="font-size:11px;color:var(--text-dim);display:block;margin-bottom:3px">API Key</label>
                        <span style="font-size:11px;color:var(--text-dim)">서버 환경변수(ANTHROPIC_API_KEY) 사용</span>
                    </div>
                    <button class="btn btn-primary btn-small" onclick="startPipeline()" id="pipelineStartBtn">&#9654; Start</button>
                    <button class="btn btn-small btn-danger" onclick="stopPipeline()" id="pipelineStopBtn" style="display:none">&#9632; Stop</button>
                </div>
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

async function api(method, path, body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API_BASE}${path}`, opts);
    return res.json();
}

async function refreshSessions() {
    const list = await api('GET', '/sessions');
    const el = document.getElementById('sessionList');

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
            <div class="session-name">${s.name}</div>
            <div class="session-meta">
                <span class="status-dot ${statusClass}"></span>
                ${statusText}${queueInfo}
                &middot; ${s.work_dir}
                ${s.model ? `&middot; <span style="color:var(--purple)">${s.model.replace('claude-','').split('-202')[0]}</span>` : ''}
                ${s.skip_permissions ? '&middot; <span style="color:var(--green);font-size:10px" title="권한 자동 승인">&#9989;</span>' : ''}
                ${(s.total_input_tokens + s.total_output_tokens) > 0 ? `&middot; <span style="font-size:10px;color:var(--text-dim)" title="토큰: ${s.total_input_tokens} in / ${s.total_output_tokens} out">${formatTokens(s.total_input_tokens + s.total_output_tokens)}</span>` : ''}
            </div>
        </div>`;
    }).join('');
}

function selectSession(id) {
    activeSessionId = id;
    localStorage.setItem('sm_activeSessionId', id);
    document.getElementById('sessionActions').style.display = 'flex';
    refreshSessions();
    connectWebSocket(id);
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
    const myConnectId = wsConnectId;  // 클로저에 캡처
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsBase = window.location.port === '8006' ? '' : '/svc/claude';
    ws = new WebSocket(`${proto}//${location.host}${wsBase}/ws/${sessionId}`);

    ws.onopen = () => { wsReconnectAttempts = 0; };

    ws.onmessage = (e) => {
        // 세션 전환 후 도착한 stale 메시지 차단
        if (myConnectId !== wsConnectId) return;
        const data = JSON.parse(e.data);
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
    if (ws) { ws.close(); ws = null; }
    refreshSessions();
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

async function sendCommand() {
    if (!activeSessionId) return;
    const input = document.getElementById('commandInput');
    const command = input.value.trim();
    if (!command) return;
    await api('POST', `/sessions/${activeSessionId}/send`, { command });
    input.value = '';
    input.style.height = '38px';  // 리셋
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

async function loadTemplateList() {
    const templates = await api('GET', '/templates');
    const el = document.getElementById('templateList');
    if (!templates.length) {
        el.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:20px;font-size:13px">저장된 템플릿이 없습니다</div>';
        return;
    }
    // 카테고리별 그룹핑
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
            html += `<div style="display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:4px;cursor:pointer;margin-bottom:4px;background:var(--bg-secondary)" onmouseover="this.style.background='var(--bg-tertiary)'" onmouseout="this.style.background='var(--bg-secondary)'">
                <div style="flex:1;min-width:0" onclick="useTemplate('${escapeHtml(t.prompt.replace(/'/g, "\\'").replace(/\n/g, "\\n"))}')">
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
        const s = sessions.find(s => s.id === activeSessionId);
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
    for (const [model, sid] of Object.entries(compareSessionIds)) {
        try {
            const data = await api('GET', `/sessions/${sid}/output`);
            const el = document.getElementById(`cmpResult_${model}`);
            if (el) el.textContent = data.output || '(대기 중...)';
        } catch (e) {}
        // 아직 busy인지 확인
        try {
            const sessions = await api('GET', '/sessions');
            const s = sessions.find(s => s.id === sid);
            if (s && s.busy) allDone = false;
        } catch (e) { allDone = false; }
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
    starredPaths = new Set(projects.map(p => p.path));

    // 빵 부스러기 네비게이션
    const bc = document.getElementById('browserBreadcrumb');
    if (data.current) {
        let parts = data.current.replace(/\\/g, '/').split('/').filter(Boolean);
        let accumulated = '';
        let crumbs = '<span onclick="browseTo(\'\')">Drives</span>';
        for (let i = 0; i < parts.length; i++) {
            accumulated += parts[i] + (i === 0 && parts[i].endsWith(':') ? '\\' : '\\');
            crumbs += ` / <span onclick="browseTo('${accumulated.replace(/\\/g, '\\\\')}')">${parts[i]}</span>`;
        }
        bc.innerHTML = crumbs;
    } else {
        bc.innerHTML = '<span>Drives</span>';
    }

    // 아이템 목록
    const el = document.getElementById('browserItems');
    if (data.parent) {
        el.innerHTML = `<div class="browser-item" onclick="browseTo('${data.parent.replace(/\\/g, '\\\\')}')">
            <span class="icon">&#8592;</span><span class="name">..</span></div>`;
    } else {
        el.innerHTML = '';
    }

    el.innerHTML += data.items.map(item => {
        let icon = item.type === 'drive' ? '&#128430;' : item.type === 'project' ? '&#128193;' : '&#128194;';
        let isStarred = starredPaths.has(item.path);
        return `<div class="browser-item">
            <span class="icon">${icon}</span>
            <span class="name" onclick="onBrowserItemClick('${item.path.replace(/\\/g, '\\\\')}', '${item.type}')">${item.name}${item.type === 'project' ? ' (git)' : ''}</span>
            <span class="actions">
                ${item.type !== 'drive' ? `<span class="star-btn ${isStarred ? 'starred' : ''}" onclick="toggleStar('${item.path.replace(/\\/g, '\\\\')}', '${item.name}')">&#9733;</span>` : ''}
                <button class="btn btn-small" onclick="selectFolder('${item.path.replace(/\\/g, '\\\\')}')">Select</button>
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

    if (projects.length === 0) {
        el.innerHTML = '';
        return;
    }

    el.innerHTML = `<h4>Saved Projects</h4>` +
        projects.map(p => `
            <span class="project-chip" onclick="selectFolder('${p.path.replace(/\\/g, '\\\\')}')">
                &#128193; ${p.name}
                <span class="remove" onclick="event.stopPropagation(); removeProject('${p.path.replace(/\\/g, '\\\\')}')">&#10005;</span>
            </span>
        `).join('');
}

async function removeProject(path) {
    await api('DELETE', '/projects', { path });
    loadProjects();
}

function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');

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
                const wd = parts[parts.length - 1].trim();
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

    if (projects.length === 0) {
        el.style.display = 'none';
        return;
    }

    el.style.display = 'flex';
    el.innerHTML = projects.map(p =>
        `<span class="project-chip" onclick="selectGitRepo('${p.path.replace(/\\/g, '\\\\')}')">&#128193; ${p.name}</span>`
    ).join('');
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
            return `<li class="git-file-item"><span class="git-file-status ${cls}">${f.status}</span><span>${f.file}</span></li>`;
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
            <span class="git-commit-meta">${c.author} · ${c.date}</span>
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
            ${pr.headRefName ? `<span class="pr-branch">${pr.headRefName}</span>` : ''}
            <a href="${pr.url}" target="_blank">Open</a>
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
            <a href="${issue.url}" target="_blank">Open</a>
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
            <a href="${gh.url}" target="_blank" style="color:var(--accent);font-weight:600;text-decoration:none">${escHtml(gh.owner?.login || '')}/${escHtml(gh.name)}</a>
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
        // Put it in the URL field ready for clone
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
        return `<li class="gh-repo-item" onclick="selectGhRepo('${escHtml(url)}')">
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
        el.innerHTML = `<li style="padding:12px 14px;color:var(--text-dim);font-size:12px">${data.error || 'No repos found'}</li>`;
        return;
    }

    el.innerHTML = data.repos.map(r => {
        const name = r.fullName || `${r.owner?.login || ''}/${r.name}`;
        const url = r.url || '';
        const desc = r.description || '';
        const vis = r.isPrivate ? '<span class="gh-repo-badge private">Private</span>' : '<span class="gh-repo-badge public">Public</span>';
        return `<li class="gh-repo-item" onclick="selectGhRepo('${escHtml(url)}')">
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

async function loadLogs() {
    const logs = await api('GET', '/logs');
    const el = document.getElementById('logsList');
    document.getElementById('logViewer').style.display = 'none';
    el.style.display = 'block';

    if (logs.length === 0) {
        el.innerHTML = '<div class="empty-state"><p>No logs yet</p></div>';
        return;
    }

    el.innerHTML = logs.map(l => `
        <div class="log-item" onclick="viewLog('${l.filename}')">
            <span class="log-name">${l.filename}</span>
            <span class="log-meta">${formatSize(l.size)} &middot; ${formatDate(l.modified)}</span>
        </div>
    `).join('');
}

async function viewLog(filename) {
    const data = await api('GET', `/logs/${filename}`);
    document.getElementById('logsList').style.display = 'none';
    const viewer = document.getElementById('logViewer');
    viewer.style.display = 'block';
    viewer.textContent = data.content || 'Empty log';
}

async function searchLogs() {
    const query = document.getElementById('logSearchInput').value;
    if (!query) { loadLogs(); return; }

    const logs = await api('GET', '/logs');
    const viewer = document.getElementById('logViewer');
    const listEl = document.getElementById('logsList');
    listEl.style.display = 'none';
    viewer.style.display = 'block';

    let results = [];
    for (const log of logs) {
        const data = await api('GET', `/logs/${log.filename}?search=${encodeURIComponent(query)}`);
        if (data.matches > 0) {
            results.push(`=== ${log.filename} (${data.matches} matches) ===\n${data.content}`);
        }
    }

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
setInterval(refreshSessions, 5000);

// ─── Pipeline ──────────────────────────────────────────────────────
let activePipelineId = localStorage.getItem('sm_activePipelineId') || null;
let pipelinePollTimer = null;

function onPipelineModeChange() {
    const mode = document.getElementById('pipelineMode').value;
    document.getElementById('pipelineApiKeyGroup').style.display = mode === 'api' ? '' : 'none';
}

async function loadPipelinesForSession() {
    /* Pipeline 탭 진입 시 현재 세션의 파이프라인 목록 로드 */
    try {
        const all = await api('GET', '/pipelines');
        // 현재 세션의 파이프라인만 필터
        const mine = activeSessionId ? all.filter(p => p.session_id === activeSessionId) : all;

        if (mine.length === 0 && !activePipelineId) {
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
            localStorage.setItem('sm_activePipelineId', activePipelineId);
        }

        // 파이프라인 목록이 여러개면 선택 UI 표시
        if (mine.length > 1) {
            let listHtml = '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">';
            for (const p of mine) {
                const active = p.id === activePipelineId;
                const color = { running:'var(--orange)', completed:'var(--green)', failed:'var(--red)', stopped:'var(--text-dim)' }[p.status] || 'var(--text-dim)';
                listHtml += `<button onclick="selectPipeline('${p.id}')" class="btn btn-small" style="font-size:11px;${active?'border-color:var(--accent);color:var(--accent)':''}">` +
                    `<span style="color:${color}">&#9679;</span> #${p.id.substring(0,6)} (iter ${p.iteration}/${p.max_iterations})</button>`;
            }
            listHtml += '</div>';
            const el = document.getElementById('pipelineListBar');
            if (el) el.innerHTML = listHtml;
        }

        if (activePipelineId) {
            // 현재 파이프라인 상태 복원
            pollPipeline();
            const ap = mine.find(p => p.id === activePipelineId);
            if (ap && ap.status === 'running') {
                document.getElementById('pipelineStartBtn').style.display = 'none';
                document.getElementById('pipelineStopBtn').style.display = '';
                document.getElementById('pipelineStatusBar').style.display = '';
                startPipelinePolling();
            }
        }
    } catch (e) { console.error('loadPipelinesForSession error:', e); }
}

function selectPipeline(id) {
    activePipelineId = id;
    localStorage.setItem('sm_activePipelineId', id);
    pollPipeline();
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
    };

    try {
        const res = await api('POST', '/pipelines', body);
        if (res.error) { alert(res.error); return; }
        activePipelineId = res.pipeline_id;
        localStorage.setItem('sm_activePipelineId', activePipelineId);
        document.getElementById('pipelineStartBtn').style.display = 'none';
        document.getElementById('pipelineStopBtn').style.display = '';
        document.getElementById('pipelineStatusBar').style.display = '';
        document.getElementById('pipelineSummary').style.display = 'none';
        document.getElementById('pipelineHistory').innerHTML = '';
        startPipelinePolling();
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
        if (data.error) return;

        // 상태 업데이트
        const pct = data.max_iterations > 0 ? Math.round((data.iteration / data.max_iterations) * 100) : 0;
        document.getElementById('pipelineProgressBar').style.width = pct + '%';
        document.getElementById('pipelineIterText').textContent = `${data.iteration}/${data.max_iterations}`;

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

        const time = `<span style="color:var(--text-dim);font-size:11px;margin-right:6px">${h.timestamp}</span>`;

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
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ─── Shell Terminal (xterm.js) ────────────────────────────────
let shellTerm = null;
let shellWs = null;
let activeShellId = null;

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
                shellWs.send(`\x1b[8;${shellTerm.rows};${shellTerm.cols}t`);
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
    if (activeSessionId && sessionList) {
        const s = sessionList.find(s => s.id === activeSessionId);
        if (s) workDir = s.work_dir;
    }

    if (!shellTerm) initShellTerminal();

    // 기존 shell 종료
    if (activeShellId) {
        try { await api('DELETE', `/shell/${activeShellId}`); } catch(e) {}
        if (shellWs) { shellWs.close(); shellWs = null; }
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
    if (shellWs) { shellWs.close(); shellWs = null; }

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsBase = window.location.port === '8006' ? '' : '/svc/claude';
    shellWs = new WebSocket(`${proto}//${location.host}${wsBase}/ws/shell/${shellId}`);

    shellWs.onopen = () => {
        // fit 후 resize 전달
        if (window._shellFitAddon) {
            try { window._shellFitAddon.fit(); } catch(e) {}
        }
        if (shellTerm && shellWs.readyState === WebSocket.OPEN) {
            shellWs.send(`\x1b[8;${shellTerm.rows};${shellTerm.cols}t`);
        }
    };

    shellWs.onmessage = (e) => {
        if (shellTerm) shellTerm.write(e.data);
    };

    shellWs.onclose = () => {
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
    if (shellWs) { shellWs.close(); shellWs = null; }
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
