"""
app/routes_api.py — /api/* REST endpoints.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Query, UploadFile, File, Depends, Header
from fastapi.responses import JSONResponse, FileResponse

import app.state as _state
from app.state import sessions, shell_sessions, pipelines, plan_phases
from app.models import (
    APP_DIR, DATA_DIR, LOGS_DIR, SESSIONS_DIR, UPLOADS_DIR, SCREENSHOTS_DIR,
    PROJECTS_FILE, TEMPLATES_FILE, TEMPLATES_DIR,
    load_projects, save_projects, _load_template,
    CreateSessionRequest, SendCommandRequest, GitExecRequest, GitCloneRequest,
    ProjectRequest, PipelineStartRequest, PipelineStopRequest, ShellCreateRequest,
    RenameSessionRequest, ChangeModelRequest, ForkSessionRequest, PromptTemplate,
    ClaudeMdRequest, CompareRequest, PlanPhaseStartRequest, PlanPhaseAnswerRequest,
    PlanPhaseApproveRequest, PlanPhaseRejectRequest,
    DismissSessionsRequest, CleanupPipelinesRequest,
    MEDIA_TOKEN_TTL, TASK_TIMEOUTS,
)
from app.session import ClaudeSession, _check_rate_limit
from app.shell import ShellSession, HAS_WINPTY
from app.screen import ScreenMonitor
from app.pipeline import PipelineRunner, PlanPhase
from app.auth import verify_admin_key, _is_browse_allowed, _ALLOWED_BROWSE_ROOTS
from app.pipeline_store import (
    get_resumable_runs, cleanup_old_runs, cleanup_interrupted_runs,
)

router = APIRouter(prefix="/api", tags=["api"])
screen_monitor = ScreenMonitor()

logger = logging.getLogger(__name__)


# ─── Media signed-token helpers ───────────────────────────────────────────────

def _media_secret() -> str:
    return os.environ.get("ADMIN_API_KEY", "")

def _generate_media_token(expires: int) -> str:
    """HMAC-SHA256(secret, expires_str) — 토큰은 secret 없이는 위조 불가."""
    secret = _media_secret()
    if not secret:
        return ""
    return hmac.new(secret.encode(), str(expires).encode(), hashlib.sha256).hexdigest()

def _verify_media_token(token: str, expires: int) -> bool:
    """토큰 서명 + 만료 시간 검증."""
    if time.time() > expires:
        return False
    expected = _generate_media_token(expires)
    return hmac.compare_digest(expected, token)

def _media_auth_enabled() -> bool:
    return bool(_media_secret())

@router.get("/stats")
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
        "claude_cli": _state.CLAUDE_EXE is not None,
        "shell_available": HAS_WINPTY,
    }


@router.get("/sessions")
async def list_sessions():
    return [s.to_dict() for s in list(sessions.values())]


@router.get("/sessions/pending-restore")
async def pending_restore_sessions():
    """모든 세션의 미리보기 정보 반환 (복원 여부 판단용).

    각 세션의 대화 미리보기, 라인 수, 파일 크기를 포함하여
    유저가 유지/삭제를 판단할 수 있게 한다.
    """
    result = []
    for s in sessions.values():
        preview_lines = []
        for entry in s.output_lines[:30]:
            text = entry.get("text", "").strip()
            if text and len(text) > 10:
                preview_lines.append(text[:200])
            if len(preview_lines) >= 5:
                break
        state_path = s._save_path
        result.append({
            **s.to_dict(),
            "preview": preview_lines,
            "output_line_count": len(s.output_lines),
            "size_bytes": state_path.stat().st_size if state_path.exists() else 0,
        })
    return result


@router.post("/sessions/dismiss")
async def dismiss_sessions(body: DismissSessionsRequest):
    """선택한 세션들을 일괄 영구 삭제 (프로세스 종료 + 파일 삭제)."""
    dismissed = []
    not_found = []
    for sid in body.session_ids:
        if sid not in sessions:
            not_found.append(sid)
            continue
        session = sessions[sid]
        await session.kill()
        session.delete_state()
        del sessions[sid]
        dismissed.append(sid)
    return {"dismissed": dismissed, "not_found": not_found}


@router.post("/sessions")
async def create_session(body: CreateSessionRequest, request: Request):
    if not _state.CLAUDE_EXE:
        raise HTTPException(status_code=503, detail="Claude CLI not available")

    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    session_id = str(uuid.uuid4())[:8]
    session = ClaudeSession(session_id, body.work_dir, body.model,
                            skip_permissions=body.skip_permissions,
                            mcp_config=body.mcp_config,
                            ephemeral=body.ephemeral)
    if body.ephemeral:
        session.name = f"tmp-{session_id}"
    session.start_worker()
    sessions[session_id] = session
    session.save_state()  # ephemeral이면 no-op

    if body.prompt:
        await session.send_prompt(body.prompt)

    return {"id": session_id, "name": session.name, "status": "created",
            "ephemeral": body.ephemeral}


@router.delete("/sessions/{session_id}")
async def kill_session(session_id: str, remove: bool = Query(True)):
    """세션 종료 및 제거. remove=false면 상태 파일 유지(재시작 시 복원 가능)"""
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


@router.post("/sessions/{session_id}/send")
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
    # task_type에 따라 idle_timeout 적용 (image_gen 등 장시간 작업 지원)
    from app.models import TASK_TIMEOUTS
    task_type = body.task_type if body.task_type in TASK_TIMEOUTS else "default"
    session.idle_timeout = TASK_TIMEOUTS[task_type]
    await session.send_prompt(prompt)
    return {"status": "queued", "queue_size": session._queue.qsize(), "idle_timeout": session.idle_timeout}


# ─── Media security endpoints ─────────────────────────────────────────────────

@router.get("/media-token")
async def get_media_token():
    """단기 미디어 액세스 토큰 발급.
    ADMIN_API_KEY 미설정 시: 빈 토큰 반환 (인증 불필요 모드).
    프론트엔드는 이 토큰을 /api/media/... 요청에 ?mkey=... 로 첨부.
    """
    if not _media_auth_enabled():
        return {"token": "", "expires": 0, "auth_required": False}
    expires = int(time.time()) + MEDIA_TOKEN_TTL
    token = _generate_media_token(expires)
    return {"token": f"{token}:{expires}", "expires": expires, "auth_required": True}


@router.get("/media/{full_path:path}")
async def serve_media(request: Request, full_path: str, mkey: Optional[str] = Query(default=None)):
    """인증된 미디어 파일 서빙.
    full_path 예: uploads/session_id/file.jpg | screenshots/screen_xxx.jpg
    인증 활성 시 ?mkey={token}:{expires} 필수. 만료 또는 서명 불일치 → 403.
    인증 실패/경로 이탈 시도는 WARNING 레벨 로그로 기록.
    """
    client_ip = request.client.host if request.client else "unknown"

    if _media_auth_enabled():
        if not mkey:
            logger.warning("media auth: 토큰 없음 — ip=%s path=%s", client_ip, full_path)
            raise HTTPException(status_code=401, detail="미디어 토큰 필요 (mkey)")
        parts = mkey.split(":", 1)
        if len(parts) != 2:
            logger.warning("media auth: 토큰 형식 오류 — ip=%s path=%s", client_ip, full_path)
            raise HTTPException(status_code=403, detail="토큰 형식 오류")
        token_sig, expires_str = parts
        try:
            expires = int(expires_str)
        except ValueError:
            logger.warning("media auth: 만료시간 파싱 실패 — ip=%s path=%s", client_ip, full_path)
            raise HTTPException(status_code=403, detail="토큰 형식 오류")
        if not _verify_media_token(token_sig, expires):
            logger.warning("media auth: 토큰 검증 실패 (만료 또는 서명 불일치) — ip=%s path=%s", client_ip, full_path)
            raise HTTPException(status_code=403, detail="토큰 만료 또는 서명 불일치")

    # 파일 경로 결정 및 경로 이탈 방지
    if full_path.startswith("uploads/"):
        base_dir = UPLOADS_DIR
        rel = full_path[len("uploads/"):]
    elif full_path.startswith("screenshots/"):
        base_dir = SCREENSHOTS_DIR
        rel = full_path[len("screenshots/"):]
    else:
        raise HTTPException(status_code=404, detail="지원하지 않는 미디어 경로")

    try:
        filepath = (base_dir / rel).resolve()
        if not filepath.is_relative_to(base_dir.resolve()):
            logger.warning("media security: 경로 이탈 시도 (path traversal) — ip=%s path=%s", client_ip, full_path)
            raise HTTPException(status_code=403, detail="경로 이탈 거부")
    except HTTPException:
        raise
    except Exception:
        logger.warning("media security: 경로 처리 오류 — ip=%s path=%s", client_ip, full_path)
        raise HTTPException(status_code=403, detail="경로 오류")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="파일 없음")

    return FileResponse(filepath)


@router.post("/sessions/{session_id}/upload")
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
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{ts}_{base_name}"
    filepath = session_dir / safe_name

    # resolved path가 upload 디렉토리 밖이면 거부 (심볼릭 링크 등 우회 방지)
    if not filepath.resolve().is_relative_to(session_dir.resolve()):
        raise HTTPException(status_code=400, detail="잘못된 파일 경로")

    filepath.write_bytes(content)

    # 파일 저장 후 카운트 재확인 — 동시 업로드로 한도 초과 시 롤백 (TOCTOU 방지)
    if len(list(session_dir.iterdir())) > 50:
        filepath.unlink(missing_ok=True)
        raise HTTPException(status_code=429, detail="업로드 파일 수 한도 초과 (최대 50개)")

    return {
        "filename": safe_name,
        "path": str(filepath.resolve()),
        "url": f"/uploads/{session_id}/{safe_name}",
        "size": len(content),
    }


@router.post("/sessions/{session_id}/interrupt")
async def interrupt_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    await sessions[session_id].interrupt()
    return {"status": "interrupted"}


@router.get("/sessions/{session_id}/output")
async def get_output(session_id: str, lines: int = Query(200, ge=1, le=5000)):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    output = sessions[session_id].get_formatted_output(lines)
    return {"output": output}


@router.patch("/sessions/{session_id}/rename")
async def rename_session(session_id: str, body: RenameSessionRequest):
    """세션 이름 변경"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    sessions[session_id].name = body.name.strip()
    sessions[session_id].save_state()
    return {"status": "renamed", "name": body.name.strip()}


@router.patch("/sessions/{session_id}/model")
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


@router.get("/sessions/{session_id}/export")
async def export_session(session_id: str):
    """세션 대화를 Markdown으로 내보내기"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    md = sessions[session_id].export_markdown()
    return {"markdown": md, "name": sessions[session_id].name}


@router.post("/sessions/{session_id}/fork")
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


@router.get("/templates")
async def list_templates():
    return _load_templates()


@router.post("/templates")
async def create_template(body: PromptTemplate):
    templates = _load_templates()
    entry = {"id": str(uuid.uuid4())[:8], "name": body.name,
             "prompt": body.prompt, "category": body.category,
             "created_at": datetime.now().isoformat()}
    templates.append(entry)
    _save_templates(templates)
    return entry


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    templates = _load_templates()
    templates = [t for t in templates if t.get("id") != template_id]
    _save_templates(templates)
    return {"status": "deleted"}


# ─── CLAUDE.md 편집 ──────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/claude-md")
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
            logger.error("[get_claude_md] %s", e)
            raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다")
    return {"content": content, "path": str(claude_md)}


@router.put("/sessions/{session_id}/claude-md")
async def update_claude_md(session_id: str, body: ClaudeMdRequest):
    """세션 작업 디렉토리의 CLAUDE.md 저장"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션 없음")
    work_dir = sessions[session_id].work_dir
    claude_md = Path(work_dir) / "CLAUDE.md"
    try:
        claude_md.write_text(body.content, encoding="utf-8")
    except Exception as e:
        logger.error("[update_claude_md] %s", e)
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다")
    return {"status": "saved", "path": str(claude_md)}


# ─── 멀티 모델 비교 ──────────────────────────────────────────────────────────

@router.post("/compare")
async def compare_models(body: CompareRequest, request: Request):
    """같은 프롬프트를 여러 모델에 보내고 결과 비교"""
    if not _state.CLAUDE_EXE:
        raise HTTPException(status_code=503, detail="Claude CLI not available")
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)
    model_count = len(body.models[:4])
    # 생성할 세션 수만큼 여유가 있는지 사전 확인 (rate limit 통과 후 N개 세션 동시 생성 우회 방지)
    active_count = sum(1 for s in sessions.values() if s.alive)
    if active_count + model_count > MAX_SESSIONS_PER_CLIENT:
        raise HTTPException(
            status_code=429,
            detail=f"세션 한도 초과: 현재 {active_count}개 활성, {model_count}개 추가 시 한도({MAX_SESSIONS_PER_CLIENT}) 초과"
        )

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


# ─── 로그 관리 ───────────────────────────────────────────────────────────────────

@router.get("/logs")
async def list_logs():
    logs = []
    all_files = list(LOGS_DIR.glob("*.log")) + list(LOGS_DIR.glob("*.txt"))
    for f in sorted(all_files, key=lambda x: x.stat().st_mtime, reverse=True):
        stat = f.stat()
        logs.append({
            "filename": f.name,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return logs


@router.get("/logs/{filename}")
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

# 탐색 허용 루트 디렉토리 — 홈 또는 프로젝트 루트 하위만 허용


@router.get("/browse")
async def browse_folder(path: str = Query("")):
    """폴더 탐색 - 허용된 루트(홈/프로젝트) 하위 디렉토리 목록 반환"""
    if not path:
        # 기본: 드라이브 목록 (Windows) — 경로 검증 불필요
        if sys.platform == "win32":
            drives = []
            for letter in string.ascii_uppercase:
                dp = Path(f"{letter}:\\")
                if dp.exists():
                    drives.append({"name": f"{letter}:\\", "path": f"{letter}:\\", "type": "drive"})
            return {"current": "", "parent": "", "items": drives}
        else:
            path = str(Path.home())  # 루트(/) 대신 홈 디렉토리를 기본값으로

    folder = Path(path)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="유효하지 않은 경로")

    # 보안: 허용 루트 하위인지 검증 (path traversal, 시스템 디렉토리 접근 차단)
    if not _is_browse_allowed(folder):
        raise HTTPException(
            status_code=403,
            detail="접근 거부: 홈 디렉토리 또는 프로젝트 루트 하위 경로만 탐색 가능합니다"
        )

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


@router.get("/projects")
async def get_projects():
    """저장된 프로젝트 목록"""
    return load_projects()


@router.post("/projects")
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


@router.delete("/projects")
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


@router.get("/git/status")
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


@router.get("/git/log")
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


@router.get("/git/branches")
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


@router.get("/git/diff")
async def git_diff(path: str = Query(...), cached: bool = Query(False)):
    """git diff (staged or unstaged)"""
    if not Path(path).exists():
        raise HTTPException(status_code=400, detail="경로 없음")

    args = ["diff", "--stat"]
    if cached:
        args.append("--cached")
    res = await run_git(args, path)
    return {"diff": res["stdout"] if res["ok"] else res["stderr"]}


@router.post("/git/exec")
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


@router.get("/git/prs")
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


@router.get("/git/issues")
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


@router.get("/git/remote")
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


@router.get("/git/gh-auth")
async def gh_auth_status():
    """gh CLI 인증 상태 확인"""
    res = await run_gh(["auth", "status"], ".")
    # gh auth status는 stderr에 출력함
    output = res["stderr"] or res["stdout"]
    logged_in = "Logged in" in output
    return {"ok": logged_in, "output": output}


@router.post("/git/clone")
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
            not_empty = next(dest_path.iterdir(), None) is not None
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


@router.get("/git/gh-repos")
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

@router.post("/pipelines")
async def start_pipeline(body: PipelineStartRequest):
    """파이프라인 시작 — 감독자(API 또는 CLI)가 작업자 CLI를 반복 구동"""
    if _state._shutting_down:
        raise HTTPException(status_code=503, detail="서버 종료 준비 중 — 신규 파이프라인 생성 불가")
    if body.session_id not in sessions:
        raise HTTPException(status_code=400, detail="유효한 세션 ID 필요")
    if body.mode == "api":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=400, detail="API 모드에서는 ANTHROPIC_API_KEY 환경변수 필요")
    if body.mode == "cli" and not _state.CLAUDE_EXE:
        raise HTTPException(status_code=400, detail="CLI 모드에서는 Claude CLI 필요")

    session = sessions[body.session_id]

    # 세션이 이미 파이프라인에 바인딩되어 있으면 충돌 방지
    if session.pipeline_id:
        raise HTTPException(
            status_code=409,
            detail=f"Session already bound to pipeline {session.pipeline_id}")

    runner = PipelineRunner(
        session, body.goal, body.supervisor_model,
        body.max_iterations, body.mode, body.max_cycles,
        cycle_phases=body.cycle_phases,
        cycle_reflection=body.cycle_reflection,
        cycle_checkpoint=body.cycle_checkpoint,
    )
    pipelines[runner.id] = runner
    try:
        runner.start()
    except Exception as e:
        pipelines.pop(runner.id, None)
        raise HTTPException(status_code=500, detail=f"파이프라인 시작 실패: {str(e)}")

    return {
        "pipeline_id": runner.id,
        "session_id": session.id,
        "status": runner.status,
        "mode": body.mode,
        "cycle_reflection": runner.cycle_reflection,
        "cycle_checkpoint": runner.cycle_checkpoint,
        "cycle_phases": runner.cycle_phases,
    }


# 하위호환: 기존 /api/pipeline/start 경로 유지
@router.post("/pipeline/start")
async def start_pipeline_compat(body: PipelineStartRequest):
    return await start_pipeline(body)


@router.get("/pipelines")
async def list_pipelines():
    return [p.to_dict() for p in pipelines.values()]


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    if pipeline_id not in pipelines:
        raise HTTPException(status_code=404, detail="파이프라인 없음")
    return pipelines[pipeline_id].to_dict()


# 하위호환
@router.get("/pipeline/{pipeline_id}")
async def get_pipeline_compat(pipeline_id: str):
    return await get_pipeline(pipeline_id)


@router.get("/pipelines/{pipeline_id}/report")
async def get_pipeline_report(pipeline_id: str):
    """파이프라인 최종 리포트 조회.

    완료/실패/중단 후 생성된 report + pending_items를 반환.
    실행 중이거나 시작 전이면 report=null + 현재 pending_items 반환.

    응답 필드:
    - pipeline_id, status, stop_type
    - report: 완료 후 생성된 구조화 리포트 (null이면 아직 실행 중)
      - pipeline_config: supervisor_model, mode, max_iterations, max_cycles 등
      - steps: [{step_idx, cycle, iteration, status, duration_seconds, output_preview, error}]
      - total/completed/failed/aborted_steps 카운트
      - errors: 오류 메시지 목록
      - text_summary: 사람이 읽기 쉬운 마크다운 리포트
    - pending_items: {questions, auto_decisions, suggestions} (실행 중에도 조회 가능)
    - pending_items_count: 항목별 개수
    """
    if pipeline_id not in pipelines:
        raise HTTPException(status_code=404, detail="파이프라인 없음")
    p = pipelines[pipeline_id]
    counts = {
        "questions": len(p.pending_items.get("questions", [])),
        "auto_decisions": len(p.pending_items.get("auto_decisions", [])),
        "suggestions": len(p.pending_items.get("suggestions", [])),
    }
    return {
        "pipeline_id": pipeline_id,
        "status": p.status,
        "stop_type": p.stop_type,
        "started_at": p.started_at,
        "ended_at": p.ended_at,
        "report": p.report,
        "pending_items": p.pending_items,
        "pending_items_count": counts,
        "message": (
            None if p.report
            else "파이프라인이 실행 중입니다. 완료/중단 후 report가 생성됩니다."
        ),
    }


@router.post("/pipelines/{pipeline_id}/cycle-confirm")
async def confirm_pipeline_cycle(pipeline_id: str):
    """Cycle checkpoint 대기 중인 파이프라인의 다음 사이클 실행을 승인.

    cycle_checkpoint=True로 시작된 파이프라인이 사이클 전환 시 status='paused'로
    대기할 때 이 엔드포인트로 승인하면 다음 사이클이 시작됩니다.

    응답:
    - confirmed=True: 승인 성공, 파이프라인 재개
    - confirmed=False: 파이프라인이 checkpoint 대기 상태가 아님
    """
    if pipeline_id not in pipelines:
        raise HTTPException(status_code=404, detail="파이프라인 없음")
    p = pipelines[pipeline_id]
    confirmed = p.confirm_cycle()
    return {
        "pipeline_id": pipeline_id,
        "confirmed": confirmed,
        "status": p.status,
        "current_cycle": p.current_cycle,
        "current_phase": p._get_cycle_phase(),
        "message": (
            f"사이클 {p.current_cycle} ({p._get_cycle_phase()}) 승인됨"
            if confirmed else
            "파이프라인이 checkpoint 대기 상태가 아닙니다"
        ),
    }


@router.get("/pipelines/{pipeline_id}/cycle-summaries")
async def get_cycle_summaries(pipeline_id: str):
    """파이프라인의 사이클별 반성 요약 전체 조회."""
    if pipeline_id not in pipelines:
        raise HTTPException(status_code=404, detail="파이프라인 없음")
    p = pipelines[pipeline_id]
    return {
        "pipeline_id": pipeline_id,
        "cycle_summaries": p.cycle_summaries,
        "count": len(p.cycle_summaries),
    }


@router.post("/pipelines/{pipeline_id}/resume")
async def resume_pipeline(pipeline_id: str):
    """soft_stop으로 중단된 파이프라인을 재개.

    재개 조건:
    - status == "stopped" AND soft_stop으로 중단된 것
    - worker 세션이 여전히 alive (세션 바인딩 보존 중)

    재개 시 _step_log / pending_items / current_cycle / iteration을 유지하여 이어서 실행.
    """
    if pipeline_id not in pipelines:
        raise HTTPException(status_code=404, detail="파이프라인 없음")
    p = pipelines[pipeline_id]
    if p.status != "stopped":
        raise HTTPException(
            status_code=400,
            detail=f"재개 불가: status={p.status!r} — stopped 상태여야 합니다")
    if not p._soft_stop_flag:
        raise HTTPException(
            status_code=400,
            detail="hard stop으로 중단된 파이프라인은 재개할 수 없습니다")
    if not p.session or not p.session.alive:
        raise HTTPException(
            status_code=400,
            detail="worker 세션이 종료되어 재개할 수 없습니다")
    try:
        p.resume()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "status": "running",
        "pipeline_id": pipeline_id,
        "current_cycle": p.current_cycle,
        "iteration": p.iteration,
        "resumed_from_step": len(p._step_log),
    }


@router.post("/pipelines/{pipeline_id}/stop")
async def stop_pipeline(pipeline_id: str, body: PipelineStopRequest = None):
    """파이프라인 중단.

    body.stop_type:
    - "hard" (기본): 즉시 중단, 진행 중인 작업 취소, 리포트 생성 후 세션 종료.
    - "soft": 현재 단계 완료 후 중단, 리포트 생성, 세션을 resumable 상태로 보존.
    """
    if pipeline_id not in pipelines:
        raise HTTPException(status_code=404, detail="파이프라인 없음")
    stop_type = (body.stop_type if body else None) or "hard"
    await pipelines[pipeline_id].stop(stop_type=stop_type)
    # soft stop은 현재 단계가 완료될 때까지 status="running" 유지
    result_status = "stopping" if stop_type == "soft" else "stopped"
    return {"status": result_status, "stop_type": stop_type}


# 하위호환
@router.post("/pipeline/{pipeline_id}/stop")
async def stop_pipeline_compat(pipeline_id: str, body: PipelineStopRequest = None):
    return await stop_pipeline(pipeline_id, body)


@router.delete("/pipelines/{pipeline_id}")
async def remove_pipeline(pipeline_id: str):
    if pipeline_id not in pipelines:
        raise HTTPException(status_code=404, detail="파이프라인 없음")
    p = pipelines[pipeline_id]
    if p.status == "running":
        await p.stop()
    del pipelines[pipeline_id]
    return {"status": "removed"}


@router.post("/pipelines/cleanup")
async def cleanup_pipelines(body: CleanupPipelinesRequest | None = None):
    """interrupted 상태 파이프라인 run을 DB에서 정리.

    body가 없거나 run_ids=null이면 모든 interrupted 삭제.
    run_ids가 있으면 해당 건만 삭제.
    """
    run_ids = body.run_ids if body else None
    before = get_resumable_runs()
    deleted = cleanup_interrupted_runs(run_ids)
    return {
        "deleted_count": deleted,
        "remaining_interrupted": len(get_resumable_runs()),
        "deleted_run_ids": [r["id"] for r in before if run_ids is None or r["id"] in (run_ids or [])],
    }


# ─── 계획 수립 API ─────────────────────────────────────────────────────────────────

@router.post("/plan-phases")
async def create_plan_phase(body: PlanPhaseStartRequest):
    """계획 수립 시작 — 질문 생성 개시"""
    if body.session_id not in sessions:
        raise HTTPException(status_code=400, detail="유효한 세션 ID 필요")
    if body.mode == "api":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=400, detail="API 모드에서는 ANTHROPIC_API_KEY 환경변수 필요")
    if body.mode == "cli" and not _state.CLAUDE_EXE:
        raise HTTPException(status_code=400, detail="CLI 모드에서는 Claude CLI 필요")

    session = sessions[body.session_id]
    phase = PlanPhase(session, body.goal, body.mode, body.supervisor_model)
    plan_phases[phase.id] = phase
    phase.start()

    return {"plan_id": phase.id, "status": phase.status}


@router.get("/plan-phases")
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


@router.get("/plan-phases/{plan_id}")
async def get_plan_phase(plan_id: str):
    """특정 plan phase 상태 조회 (폴링용)"""
    if plan_id not in plan_phases:
        raise HTTPException(status_code=404, detail="Plan phase 없음")
    return plan_phases[plan_id].to_dict()


@router.post("/plan-phases/{plan_id}/answers")
async def submit_plan_answers(plan_id: str, body: PlanPhaseAnswerRequest):
    """답변 제출 → 실행계획 생성 시작"""
    if plan_id not in plan_phases:
        raise HTTPException(status_code=404, detail="Plan phase 없음")
    phase = plan_phases[plan_id]
    if phase.status != "questions_ready":
        raise HTTPException(status_code=409, detail=f"현재 상태({phase.status})에서는 답변 제출 불가")
    await phase.submit_answers(body.answers)
    return {"status": phase.status}


@router.post("/plan-phases/{plan_id}/approve")
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
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파이프라인 시작 실패: {str(e)}")


@router.post("/plan-phases/{plan_id}/regenerate")
async def regenerate_plan(plan_id: str):
    """계획 재생성"""
    if plan_id not in plan_phases:
        raise HTTPException(status_code=404, detail="Plan phase 없음")
    phase = plan_phases[plan_id]
    if phase.status not in ("plan_ready", "error"):
        raise HTTPException(status_code=409, detail=f"현재 상태({phase.status})에서는 재생성 불가")
    await phase.regenerate()
    return {"status": phase.status}


@router.post("/plan-phases/{plan_id}/reject")
async def reject_plan_phase(plan_id: str, body: PlanPhaseRejectRequest):
    """플랜 거부 + 피드백 기반 추가 질의 (최대 1회)"""
    if plan_id not in plan_phases:
        raise HTTPException(status_code=404, detail="Plan phase 없음")
    phase = plan_phases[plan_id]
    if phase.status != "plan_ready":
        raise HTTPException(
            status_code=409,
            detail=f"현재 상태({phase.status})에서는 거부 불가 (plan_ready 상태 필요)",
        )
    try:
        await phase.reject_and_refine(body.feedback)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"status": phase.status}


@router.delete("/plan-phases/{plan_id}")
async def delete_plan_phase(plan_id: str):
    """Plan phase 삭제"""
    if plan_id not in plan_phases:
        raise HTTPException(status_code=404, detail="Plan phase 없음")
    phase = plan_phases[plan_id]
    await phase._cleanup_supervisor()
    del plan_phases[plan_id]
    return {"status": "removed"}




@router.post("/monitor/start")
async def monitor_start(interval: int = Query(30, ge=5, le=300)):
    await screen_monitor.start_periodic(interval)
    return {"status": "started", "interval": interval}


@router.post("/monitor/stop")
async def monitor_stop():
    await screen_monitor.stop()
    return {"status": "stopped"}


@router.get("/monitor/capture")
async def monitor_capture():
    try:
        path = await asyncio.to_thread(screen_monitor.capture)
        return {"path": str(path), "url": f"/screenshots/{path.name}",
                "timestamp": datetime.now().isoformat()}
    except ImportError:
        raise HTTPException(status_code=503, detail="mss/Pillow 미설치. pip install mss Pillow")
    except Exception as e:
        logger.error("[capture_screen] %s", e)
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다")


@router.get("/monitor/latest")
async def monitor_latest():
    if screen_monitor.latest and screen_monitor.latest.exists():
        return {"path": str(screen_monitor.latest), "url": f"/screenshots/{screen_monitor.latest.name}"}
    return {"path": None, "url": None}


# ─── Shell 터미널 API ────────────────────────────────────────────────────────────

@router.post("/shells")
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
        logger.error("[create_shell] %s", e)
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다")
    shell_sessions[shell_id] = shell
    return shell.to_dict()


# 하위호환
@router.post("/shell/create")
async def create_shell_compat(body: ShellCreateRequest, request: Request):
    return await create_shell(body, request)


@router.get("/shells")
async def list_shells():
    return [s.to_dict() for s in list(shell_sessions.values())]


@router.delete("/shells/{shell_id}")
async def kill_shell(shell_id: str):
    if shell_id not in shell_sessions:
        raise HTTPException(status_code=404, detail="Shell 세션 없음")
    shell_sessions[shell_id].kill()
    del shell_sessions[shell_id]
    return {"status": "killed"}


# 하위호환
@router.delete("/shell/{shell_id}")
async def kill_shell_compat(shell_id: str):
    return await kill_shell(shell_id)
