"""
app/models.py — Path constants, rate-limit constants, utility functions, Pydantic request models.

No mutable global state here; all runtime state lives in app/state.py.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# ─── Path constants ────────────────────────────────────────────────────────────

APP_DIR = Path(__file__).parent.parent          # services/session-manager/
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
SESSIONS_DIR = DATA_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)
IMAGEGEN_OUTPUT_DIR = Path(os.environ.get(
    "IMAGEGEN_OUTPUT_DIR",
    str(APP_DIR.parent.parent.parent / "04_ImageGen" / "output"),
))
PROJECTS_FILE = DATA_DIR / "projects.json"
TEMPLATES_FILE = DATA_DIR / "templates.json"
TEMPLATES_DIR = Path(__file__).parent / "templates"

# ─── .env loading (host execution outside Docker) ─────────────────────────────
# Uses os.environ.setdefault — never overrides vars already set by Docker/CI/tests.
# For tests: monkeypatch.setenv works for code that reads os.environ at call time.
# For module-level constants (e.g. MAX_SESSIONS_PER_CLIENT), use monkeypatch.setattr.

_env_file = APP_DIR.parent.parent / ".env"   # ../../.env = project root
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _value = _line.partition("=")
            _value = _value.strip()
            if len(_value) >= 2 and _value[0] == _value[-1] and _value[0] in ('"', "'"):
                _value = _value[1:-1]
            os.environ.setdefault(_key.strip(), _value)

# ─── TTL / rate-limit constants ───────────────────────────────────────────────

SESSION_TTL_SECONDS = 3600          # 1h idle session auto-cleanup
CLEANUP_INTERVAL = 300              # run cleanup every 5 min
CMP_SESSION_TTL_SECONDS = 600       # cmp-* sessions: 10 min TTL after completion
MAX_SESSIONS_PER_CLIENT = int(os.environ.get("MAX_SESSIONS_PER_CLIENT", "20"))
MAX_SESSION_CREATES_PER_MINUTE = 10

# ─── Task timeout config (seconds) ────────────────────────────────────────────
# 세션 idle_timeout 기본값. SendCommandRequest.task_type으로 오버라이드 가능.
TASK_TIMEOUTS: dict[str, int] = {
    "default":   int(os.environ.get("TASK_TIMEOUT_DEFAULT",   "300")),   # 5분
    "long_task": int(os.environ.get("TASK_TIMEOUT_LONG",      "900")),   # 15분
    "image_gen": int(os.environ.get("TASK_TIMEOUT_IMAGE_GEN", "1800")),  # 30분
}
HEARTBEAT_INTERVAL = 60  # heartbeat 주기 (초) — idle 상태 메시지 업데이트

# ─── Media signed-token config ────────────────────────────────────────────────
# ADMIN_API_KEY 설정 시 /uploads, /screenshots 는 signed token 필수.
# 토큰 없으면 /api/media/... 로 403 반환. 미설정 시 StaticFiles 직접 서빙(개발 모드).
MEDIA_TOKEN_TTL = int(os.environ.get("MEDIA_TOKEN_TTL", "3600"))  # 1시간

# ─── Utility functions ────────────────────────────────────────────────────────


def find_claude_exe() -> Optional[str]:
    """Search for the Claude CLI executable."""
    found = shutil.which("claude")
    if found:
        return found

    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")

    if appdata:
        claude_code_dir = Path(appdata) / "Claude" / "claude-code"
        if claude_code_dir.exists():
            try:
                versions = sorted(claude_code_dir.iterdir(), reverse=True)
            except (PermissionError, OSError):
                versions = []
            for v in versions:
                exe = v / "claude.exe"
                if exe.exists():
                    return str(exe)

    if localappdata:
        npm_exe = Path(localappdata) / "npm" / "claude.cmd"
        if npm_exe.exists():
            return str(npm_exe)

    return None


def _load_template(name: str, **kwargs: str) -> str:
    """Load an HTML template from app/templates/ and substitute named placeholders."""
    template = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    if kwargs:
        template = template.format_map(kwargs)
    return template


def load_projects() -> list[dict]:
    """Load saved project list."""
    if PROJECTS_FILE.exists():
        try:
            return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            PROJECTS_FILE.replace(PROJECTS_FILE.with_suffix(".json.bak"))
            return []
    return []


def save_projects(projects: list[dict]) -> None:
    """Save project list (atomic write — prevents partial writes)."""
    tmp = Path(str(PROJECTS_FILE) + ".tmp")
    tmp.write_text(json.dumps(projects, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, PROJECTS_FILE)


# ─── Pydantic request models ──────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    work_dir: str = "."
    model: str = ""
    prompt: str = ""
    skip_permissions: bool = False
    mcp_config: str = ""
    ephemeral: bool = False  # True면 디스크 저장/로그 기록 없는 임시 세션


class SendCommandRequest(BaseModel):
    command: str = Field(..., min_length=1, description="Prompt to execute")
    attachments: list[str] = Field(default=[], description="Attached file paths")
    task_type: str = Field(default="default", description="작업 유형: default|long_task|image_gen")


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
    supervisor_model: str = "opus"
    max_iterations: int = Field(default=20, ge=1, le=100)
    max_cycles: int = Field(default=100, ge=1, le=200)
    mode: str = Field(default="cli", pattern="^(api|cli)$")
    # Cycle 고급 기능
    cycle_phases: Optional[list[str]] = Field(
        default=None,
        description="사이클별 페이즈 이름 목록 (미지정 시 기본 4단계 순환 적용)")
    cycle_reflection: bool = Field(
        default=True,
        description="사이클 종료 시 반성/재계획 실행 여부")
    cycle_checkpoint: bool = Field(
        default=False,
        description="사이클 시작 전 사용자 확인 대기 여부 (POST /cycle-confirm으로 승인)")


class PipelineStopRequest(BaseModel):
    stop_type: str = Field(default="hard", pattern="^(hard|soft)$")


class ShellCreateRequest(BaseModel):
    shell_type: str = Field(default="cmd", pattern="^(cmd|powershell)$")
    work_dir: str = "."
    cols: int = Field(default=120, ge=40, le=400)
    rows: int = Field(default=30, ge=10, le=200)


class RenameSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class ReorderSessionsRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1, description="세션 ID 목록 (표시 순서대로)")


class ChangeModelRequest(BaseModel):
    model: str = Field(..., max_length=80, description="Model name (e.g. sonnet, opus, haiku; empty = CLI default)")


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
    supervisor_model: str = "opus"


class PlanPhaseAnswerRequest(BaseModel):
    answers: dict[str, str]


class PlanPhaseApproveRequest(BaseModel):
    plan_text: str | None = None
    max_iterations: int = Field(default=20, ge=1, le=100)
    max_cycles: int = Field(default=100, ge=1, le=200)
    cycle_phases: list[str] | None = None
    cycle_reflection: bool = True
    cycle_checkpoint: bool = False


class PlanPhaseRejectRequest(BaseModel):
    feedback: str = Field(..., min_length=1)


class DismissSessionsRequest(BaseModel):
    session_ids: list[str] = Field(..., min_length=1)


class CleanupPipelinesRequest(BaseModel):
    run_ids: list[str] | None = None


class PipelineRecommendRequest(BaseModel):
    goal: str = Field(..., min_length=1, description="파이프라인 목표 텍스트")
    mode: str = Field(default="cli", pattern="^(api|cli)$")


class PipelineConfigSaveRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=60,
                      pattern=r"^[a-zA-Z0-9_\-가-힣]+$",
                      description="설정 식별자 (영문/한글/숫자/_- 조합)")
    label: str = Field(..., min_length=1, max_length=40, description="표시 이름")
    description: str = Field(default="", max_length=200)
    config: dict = Field(..., description="PipelineStartRequest 호환 파라미터 dict")
