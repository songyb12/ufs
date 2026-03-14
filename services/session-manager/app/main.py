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
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# ─── 설정 ───────────────────────────────────────────────────────────────────────

APP_DIR = Path(__file__).parent.parent  # services/session-manager/
LOGS_DIR = APP_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
PROJECTS_FILE = DATA_DIR / "projects.json"

# 호스트 실행 시 .env 파일 로드 (Docker 외부)
_env_file = APP_DIR.parent.parent / ".env"  # ../../.env = 프로젝트 루트
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

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


@asynccontextmanager
async def lifespan(app):
    global CLAUDE_EXE
    CLAUDE_EXE = find_claude_exe()
    if CLAUDE_EXE:
        print(f"  Claude CLI: {CLAUDE_EXE}")
    else:
        print("  ⚠ Claude CLI not found — session creation disabled")
    yield
    for session in sessions.values():
        await session.kill()


app = FastAPI(title="Claude Session Manager", lifespan=lifespan)

# 활성 세션 관리
sessions: dict = {}


# ─── 세션 클래스 ─────────────────────────────────────────────────────────────────

class ClaudeSession:
    """Claude CLI 세션 관리 (print 모드 + stream-json)

    각 세션은 작업 큐를 가지며, 프롬프트를 보내면 Claude CLI를
    -p --output-format stream-json 모드로 실행하여 결과를 스트리밍합니다.
    여러 프롬프트를 보내면 순차적으로 처리됩니다.
    --continue 옵션으로 이전 대화를 이어갑니다.
    """

    def __init__(self, session_id: str, work_dir: str, model: str = ""):
        self.id = session_id
        self.name = f"claude-{session_id}"
        self.work_dir = work_dir
        self.model = model  # e.g. "claude-sonnet-4-5-20250514", "" = CLI default
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

        cmd = [CLAUDE_EXE, "-p", "--output-format", "stream-json",
               "--verbose", "--dangerously-skip-permissions"]

        if use_model:
            cmd.extend(["--model", use_model])

        # 이전 세션 이어가기
        if self.session_uuid:
            cmd.extend(["--resume", self.session_uuid])

        cmd.append(prompt)

        stderr_lines = []

        try:
            # 중첩 세션 감지 방지: CLAUDECODE 환경변수 제거
            # LLM_API_KEY → ANTHROPIC_API_KEY 매핑 (Claude CLI 인증)
            env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
            if "ANTHROPIC_API_KEY" not in env and os.environ.get("LLM_API_KEY"):
                env["ANTHROPIC_API_KEY"] = os.environ["LLM_API_KEY"]
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
                    f"모델 '{use_model}' 사용 불가 → 기본 모델로 자동 재시도합니다...")
                self.process = None
                await self._run_claude(prompt, _retry_without_model=True)
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
            if result_text and not any(l["text"] == result_text for l in self.output_lines[-5:]):
                self._append_output("result", result_text)
            self._append_output("system", "--- Done ---")
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


@app.get("/api/sessions")
async def list_sessions():
    return [s.to_dict() for s in sessions.values()]


@app.post("/api/sessions")
async def create_session(body: dict = None):
    if not CLAUDE_EXE:
        return JSONResponse(status_code=503, content={"error": "Claude CLI not available"})
    body = body or {}
    session_id = str(uuid.uuid4())[:8]
    work_dir = body.get("work_dir", ".")
    model = body.get("model", "")

    session = ClaudeSession(session_id, work_dir, model)
    session.start_worker()
    sessions[session_id] = session

    # 초기 프롬프트가 있으면 바로 전송
    prompt = body.get("prompt", "")
    if prompt:
        await session.send_prompt(prompt)

    return {"id": session_id, "name": session.name, "status": "created"}


@app.delete("/api/sessions/{session_id}")
async def kill_session(session_id: str):
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "세션 없음"})
    await sessions[session_id].kill()
    return {"status": "killed"}


@app.delete("/api/sessions/{session_id}/remove")
async def remove_session(session_id: str):
    """세션을 종료하고 목록에서 완전 제거"""
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "세션 없음"})
    await sessions[session_id].kill()
    del sessions[session_id]
    return {"status": "removed"}


@app.post("/api/sessions/{session_id}/send")
async def send_command(session_id: str, body: dict):
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "세션 없음"})

    command = body.get("command", "")
    if not command:
        return JSONResponse(status_code=400, content={"error": "프롬프트 필요"})

    session = sessions[session_id]
    await session.send_prompt(command)
    return {"status": "queued", "queue_size": session._queue.qsize()}


@app.post("/api/sessions/{session_id}/interrupt")
async def interrupt_session(session_id: str):
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "세션 없음"})
    await sessions[session_id].interrupt()
    return {"status": "interrupted"}


@app.get("/api/sessions/{session_id}/output")
async def get_output(session_id: str, lines: int = 200):
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "세션 없음"})
    output = sessions[session_id].get_formatted_output(lines)
    return {"output": output}


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
                    await asyncio.wait_for(
                        websocket.send_json({
                            "output": output,
                            "alive": session.alive,
                            "busy": session.busy,
                            "queue_size": session._queue.qsize(),
                        }),
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
    log_path = LOGS_DIR / filename
    if not log_path.exists():
        return JSONResponse(status_code=404, content={"error": "로그 없음"})

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
        return JSONResponse(status_code=400, content={"error": "유효하지 않은 경로"})

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
async def add_project(body: dict):
    """프로젝트 즐겨찾기 추가"""
    path = body.get("path", "")
    name = body.get("name", "") or Path(path).name

    if not path or not Path(path).exists():
        return JSONResponse(status_code=400, content={"error": "유효하지 않은 경로"})

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
async def remove_project(body: dict):
    """프로젝트 즐겨찾기 삭제"""
    path = body.get("path", "")
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
        return JSONResponse(status_code=400, content={"error": "경로 없음"})

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
        return JSONResponse(status_code=400, content={"error": "경로 없음"})

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
        return JSONResponse(status_code=400, content={"error": "경로 없음"})

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
        return JSONResponse(status_code=400, content={"error": "경로 없음"})

    args = ["diff", "--stat"]
    if cached:
        args.append("--cached")
    res = await run_git(args, path)
    return {"diff": res["stdout"] if res["ok"] else res["stderr"]}


@app.post("/api/git/exec")
async def git_exec(body: dict):
    """git 명령 실행 (commit, push, pull, checkout 등)"""
    path = body.get("path", "")
    command = body.get("command", "")  # e.g. "commit -m 'msg'", "push", "pull"

    if not path or not Path(path).exists():
        return JSONResponse(status_code=400, content={"error": "경로 없음"})
    if not command:
        return JSONResponse(status_code=400, content={"error": "명령어 필요"})

    # 보안: 위험한 명령어 차단
    blocked = ["reset --hard", "clean -f", "push --force", "push -f"]
    for b in blocked:
        if b in command:
            return JSONResponse(status_code=403, content={"error": f"차단된 명령어: {b}"})

    # command를 쉘로 넘겨 실행 (따옴표 등 처리)
    try:
        proc = await asyncio.create_subprocess_shell(
            f"git {command}",
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
        return JSONResponse(status_code=400, content={"error": "경로 없음"})

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
        return JSONResponse(status_code=400, content={"error": "경로 없음"})

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
        return JSONResponse(status_code=400, content={"error": "경로 없음"})

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
async def git_clone(body: dict):
    """GitHub repo 클론"""
    url = body.get("url", "").strip()
    dest = body.get("dest", "").strip()

    if not url:
        return JSONResponse(status_code=400, content={"error": "URL 필요"})

    # dest가 없으면 현재 디렉토리에 repo 이름으로
    if dest:
        dest_path = Path(dest)
    else:
        # URL에서 repo 이름 추출
        repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
        dest_path = Path(".") / repo_name

    if dest_path.exists() and any(dest_path.iterdir()):
        return JSONResponse(status_code=400, content={"error": f"디렉토리가 이미 존재함: {dest_path}"})

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


# ─── 프론트엔드 ──────────────────────────────────────────────────────────────────

FRONTEND_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Session Manager</title>
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
    align-items: center;
}

.terminal-input-bar input {
    flex: 1;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 12px;
    color: var(--text);
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 13px;
    outline: none;
}

.terminal-input-bar input:focus { border-color: var(--accent); }

.logs-container { flex: 1; overflow: hidden; display: none; flex-direction: column; }
.logs-container.active { display: flex; }
.terminal-container.hidden { display: none; }

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
        <h1><span class="icon">&#9654;</span> Claude Session Manager</h1>
        <div class="header-actions">
            <button class="btn" onclick="refreshSessions()">&#8635; Refresh</button>
        </div>
    </div>

    <div class="sidebar">
        <div class="sidebar-header">
            <h2>Sessions</h2>
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
        </div>

        <div class="session-actions" id="sessionActions" style="display:none">
            <button class="btn btn-small btn-danger" onclick="killSession()">&#10005; Kill</button>
            <button class="btn btn-small btn-danger" onclick="removeSession()" style="background:var(--bg-tertiary);color:var(--text-dim);border-color:var(--border)" title="Kill and remove from list">&#128465; Remove</button>
            <button class="btn btn-small" onclick="interruptSession()">Stop</button>
            <span class="status-badge" id="statusBadge">Idle</span>
        </div>

        <div class="terminal-container" id="terminalView">
            <div class="terminal-output" id="terminalOutput">
                <div class="empty-state">
                    <span class="icon">&#9000;</span>
                    <p>Select or create a session to start</p>
                </div>
            </div>
            <div class="terminal-input-bar">
                <input type="text" id="commandInput" placeholder="Enter prompt for Claude..."
                       onkeydown="if(event.key==='Enter')sendCommand()">
                <button class="btn btn-primary btn-small" onclick="sendCommand()">Send</button>
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
            <option value="opus">Opus (latest)</option>
            <option value="haiku">Haiku (latest)</option>
            <option value="claude-sonnet-4-5-20250514">Sonnet 4.5</option>
            <option value="claude-opus-4-5-20250414">Opus 4.5</option>
        </select>

        <label>Initial Prompt (optional)</label>
        <textarea id="newPrompt" placeholder="e.g. Help me fix the login bug"></textarea>
        <div class="modal-actions">
            <button class="btn" onclick="hideNewSessionModal()">Cancel</button>
            <button class="btn btn-primary" onclick="createSession()">Create</button>
        </div>
    </div>
</div>

<script>
let activeSessionId = null;
let ws = null;
let autoScroll = true;

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
            </div>
        </div>`;
    }).join('');
}

function selectSession(id) {
    activeSessionId = id;
    document.getElementById('sessionActions').style.display = 'flex';
    refreshSessions();
    connectWebSocket(id);
}

let wsReconnectTimer = null;
let wsReconnectAttempts = 0;

function connectWebSocket(sessionId) {
    if (ws) { ws.close(); ws = null; }
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
    wsReconnectAttempts = 0;

    _doConnect(sessionId);
}

function _doConnect(sessionId) {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsBase = window.location.port === '8006' ? '' : '/svc/claude';
    ws = new WebSocket(`${proto}//${location.host}${wsBase}/ws/${sessionId}`);

    ws.onopen = () => { wsReconnectAttempts = 0; };

    ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.error) {
            // 세션 제거됨 등
            ws.close();
            ws = null;
            return;
        }
        if (data.output !== undefined) {
            const el = document.getElementById('terminalOutput');
            el.textContent = data.output;
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
    };

    ws.onclose = () => {
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
    const result = await api('POST', '/sessions', { work_dir, prompt, model });

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
    await api('DELETE', `/sessions/${activeSessionId}/remove`);
    activeSessionId = null;
    document.getElementById('sessionActions').style.display = 'none';
    document.getElementById('terminalOutput').innerHTML = '<div class="empty-state"><span class="icon">&#9000;</span><p>Select or create a session to start</p></div>';
    if (ws) { ws.close(); ws = null; }
    refreshSessions();
}

async function sendCommand() {
    if (!activeSessionId) return;
    const input = document.getElementById('commandInput');
    const command = input.value.trim();
    if (!command) return;
    await api('POST', `/sessions/${activeSessionId}/send`, { command });
    input.value = '';
}

async function interruptSession() {
    if (!activeSessionId) return;
    await api('POST', `/sessions/${activeSessionId}/interrupt`);
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

    if (tab === 'terminal') {
        document.getElementById('terminalView').classList.remove('hidden');
    } else if (tab === 'git') {
        document.getElementById('gitView').classList.add('active');
        autoFillGitPath();
        loadGitProjects();
    } else if (tab === 'logs') {
        document.getElementById('logsView').classList.add('active');
        loadLogs();
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

refreshSessions();
setInterval(refreshSessions, 5000);
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
