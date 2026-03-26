"""
tests/test_integration.py

httpx.AsyncClient + ASGITransport 기반 FastAPI 통합 테스트.
lifespan은 비활성화 — 외부 프로세스(Claude CLI, git, shell) 없이 실행.

커버 영역:
  - GET /health, /api/stats
  - GET /api/sessions, POST (503), DELETE 404, 세션 404 연산군
  - GET/POST/DELETE /api/templates
  - GET/POST/DELETE /api/projects
  - GET /api/browse
  - GET /api/logs, GET /api/logs/{filename} (404/400)
  - GET/POST/DELETE /api/pipelines (404/400)
  - GET/POST/DELETE /api/plan-phases (404/409)
  - GET/DELETE /api/shells (503 create, 404 kill)
  - POST /api/git/clone (URL 검증)

실행:
    .venv/Scripts/pytest tests/test_integration.py -v
"""
import json
import uuid
from pathlib import Path

import httpx
import pytest

import app.main as main_module
from app.main import app, ClaudeSession, PlanPhase


# ── 공통 픽스처 ───────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_state(monkeypatch, tmp_path):
    """전역 딕셔너리 초기화 + 파일 경로를 tmp_path로 격리"""
    sessions_dir = tmp_path / "sessions"
    logs_dir = tmp_path / "logs"
    sessions_dir.mkdir()
    logs_dir.mkdir()

    monkeypatch.setattr(main_module, "PROJECTS_FILE", tmp_path / "projects.json")
    monkeypatch.setattr(main_module, "TEMPLATES_FILE", tmp_path / "templates.json")
    monkeypatch.setattr(main_module, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(main_module, "LOGS_DIR", logs_dir)

    main_module._session_create_log.clear()
    main_module.sessions.clear()
    main_module.pipelines.clear()
    main_module.plan_phases.clear()
    main_module.shell_sessions.clear()
    yield
    main_module._session_create_log.clear()
    main_module.sessions.clear()
    main_module.pipelines.clear()
    main_module.plan_phases.clear()
    main_module.shell_sessions.clear()


@pytest.fixture
async def client():
    """lifespan 없이 앱에 직접 접근하는 비동기 HTTP 클라이언트"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ════════════════════════════════════════════════════════════════════════════════
# 1. Health / Stats
# ════════════════════════════════════════════════════════════════════════════════

class TestHealthAndStats:

    async def test_health_returns_200(self, client):
        r = await client.get("/health")
        assert r.status_code == 200

    async def test_health_has_required_keys(self, client):
        r = await client.get("/health")
        body = r.json()
        assert "status" in body
        assert "sessions" in body
        assert "claude_cli" in body

    async def test_health_status_degraded_when_no_claude_exe(self, client, monkeypatch):
        monkeypatch.setattr(main_module, "CLAUDE_EXE", None)
        r = await client.get("/health")
        assert r.json()["status"] == "degraded"
        assert r.json()["claude_cli"] is False

    async def test_stats_returns_200(self, client):
        r = await client.get("/api/stats")
        assert r.status_code == 200

    async def test_stats_has_required_keys(self, client):
        body = (await client.get("/api/stats")).json()
        assert "sessions" in body
        assert "pipelines" in body
        assert "shells" in body
        assert "claude_cli" in body
        assert "shell_available" in body

    async def test_stats_reflects_session_count(self, client):
        sid = f"t-{uuid.uuid4().hex[:4]}"
        main_module.sessions[sid] = ClaudeSession(sid, ".", "")
        body = (await client.get("/api/stats")).json()
        assert body["sessions"]["total"] == 1


# ════════════════════════════════════════════════════════════════════════════════
# 2. Sessions
# ════════════════════════════════════════════════════════════════════════════════

class TestSessions:

    async def test_list_sessions_empty(self, client):
        r = await client.get("/api/sessions")
        assert r.status_code == 200
        assert r.json() == []

    async def test_list_sessions_reflects_state(self, client):
        sid = f"s-{uuid.uuid4().hex[:4]}"
        main_module.sessions[sid] = ClaudeSession(sid, ".", "")
        r = await client.get("/api/sessions")
        ids = [s["id"] for s in r.json()]
        assert sid in ids

    async def test_create_session_returns_503_when_no_cli(self, client, monkeypatch):
        monkeypatch.setattr(main_module, "CLAUDE_EXE", None)
        r = await client.post("/api/sessions", json={"work_dir": "."})
        assert r.status_code == 503

    async def test_delete_session_404_for_unknown(self, client):
        r = await client.delete("/api/sessions/nonexistent")
        assert r.status_code == 404

    async def test_send_404_for_unknown_session(self, client):
        r = await client.post("/api/sessions/ghost/send", json={"command": "hello"})
        assert r.status_code == 404

    async def test_interrupt_404_for_unknown_session(self, client):
        r = await client.post("/api/sessions/ghost/interrupt")
        assert r.status_code == 404

    async def test_get_output_404_for_unknown_session(self, client):
        r = await client.get("/api/sessions/ghost/output")
        assert r.status_code == 404

    async def test_rename_404_for_unknown_session(self, client):
        r = await client.patch("/api/sessions/ghost/rename", json={"name": "x"})
        assert r.status_code == 404

    async def test_change_model_404_for_unknown_session(self, client):
        r = await client.patch("/api/sessions/ghost/model", json={"model": "sonnet"})
        assert r.status_code == 404

    async def test_export_404_for_unknown_session(self, client):
        r = await client.get("/api/sessions/ghost/export")
        assert r.status_code == 404

    async def test_fork_404_for_unknown_session(self, client):
        r = await client.post("/api/sessions/ghost/fork", json={})
        assert r.status_code == 404

    async def test_get_claude_md_404_for_unknown_session(self, client):
        r = await client.get("/api/sessions/ghost/claude-md")
        assert r.status_code == 404

    async def test_put_claude_md_404_for_unknown_session(self, client):
        r = await client.put("/api/sessions/ghost/claude-md", json={"content": ""})
        assert r.status_code == 404

    async def test_send_409_for_dead_session(self, client):
        """alive=False인 세션에 send → 409 Conflict"""
        sid = f"s-{uuid.uuid4().hex[:4]}"
        s = ClaudeSession(sid, ".", "")
        s.alive = False
        main_module.sessions[sid] = s
        r = await client.post(f"/api/sessions/{sid}/send", json={"command": "test"})
        assert r.status_code == 409


# ════════════════════════════════════════════════════════════════════════════════
# 3. Templates
# ════════════════════════════════════════════════════════════════════════════════

class TestTemplates:

    async def test_list_templates_empty(self, client):
        r = await client.get("/api/templates")
        assert r.status_code == 200
        assert r.json() == []

    async def test_create_template_returns_entry(self, client):
        payload = {"name": "기본 분석", "prompt": "이 코드를 분석하라", "category": "dev"}
        r = await client.post("/api/templates", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "기본 분석"
        assert body["prompt"] == "이 코드를 분석하라"
        assert body["category"] == "dev"
        assert "id" in body
        assert "created_at" in body

    async def test_create_and_list_template(self, client):
        await client.post("/api/templates", json={"name": "T1", "prompt": "p1", "category": ""})
        r = await client.get("/api/templates")
        names = [t["name"] for t in r.json()]
        assert "T1" in names

    async def test_delete_template_returns_deleted(self, client):
        created = (await client.post(
            "/api/templates", json={"name": "Del", "prompt": "p", "category": ""}
        )).json()
        tid = created["id"]
        r = await client.delete(f"/api/templates/{tid}")
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"

    async def test_delete_template_removes_from_list(self, client):
        created = (await client.post(
            "/api/templates", json={"name": "ToRemove", "prompt": "x", "category": ""}
        )).json()
        tid = created["id"]
        await client.delete(f"/api/templates/{tid}")
        names = [t["name"] for t in (await client.get("/api/templates")).json()]
        assert "ToRemove" not in names

    async def test_delete_nonexistent_template_returns_deleted(self, client):
        """존재하지 않는 template 삭제 — no-op이지만 에러 없이 'deleted' 반환"""
        r = await client.delete("/api/templates/no-such-id")
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"


# ════════════════════════════════════════════════════════════════════════════════
# 4. Projects
# ════════════════════════════════════════════════════════════════════════════════

class TestProjects:

    async def test_list_projects_empty(self, client):
        r = await client.get("/api/projects")
        assert r.status_code == 200
        assert r.json() == []

    async def test_add_project_invalid_path_returns_400(self, client):
        r = await client.post("/api/projects", json={"path": "/no/such/path/xyz", "name": ""})
        assert r.status_code == 400

    async def test_add_project_valid_path(self, client, tmp_path):
        r = await client.post("/api/projects", json={"path": str(tmp_path), "name": "MyProj"})
        assert r.status_code == 200
        assert r.json()["status"] == "added"

    async def test_add_project_duplicate_returns_already_exists(self, client, tmp_path):
        payload = {"path": str(tmp_path), "name": "X"}
        await client.post("/api/projects", json=payload)
        r = await client.post("/api/projects", json=payload)
        assert r.json()["status"] == "already_exists"

    async def test_add_project_appears_in_list(self, client, tmp_path):
        await client.post("/api/projects", json={"path": str(tmp_path), "name": "Visible"})
        projects = (await client.get("/api/projects")).json()
        names = [p["name"] for p in projects]
        assert "Visible" in names

    async def test_remove_project(self, client, tmp_path):
        await client.post("/api/projects", json={"path": str(tmp_path), "name": "R"})
        r = await client.request("DELETE", "/api/projects",
                                 json={"path": str(tmp_path), "name": ""})
        assert r.status_code == 200
        assert r.json()["status"] == "removed"
        projects = (await client.get("/api/projects")).json()
        assert not any(p["path"] == str(tmp_path) for p in projects)


# ════════════════════════════════════════════════════════════════════════════════
# 5. Folder Browse
# ════════════════════════════════════════════════════════════════════════════════

class TestBrowse:

    async def test_browse_valid_path_returns_200(self, client, tmp_path):
        r = await client.get("/api/browse", params={"path": str(tmp_path)})
        assert r.status_code == 200
        body = r.json()
        assert "current" in body
        assert "items" in body

    async def test_browse_invalid_path_returns_400(self, client):
        r = await client.get("/api/browse", params={"path": "/no/such/dir/zzz"})
        assert r.status_code == 400

    async def test_browse_lists_subdirs(self, client, tmp_path):
        (tmp_path / "subdir_a").mkdir()
        (tmp_path / "subdir_b").mkdir()
        r = await client.get("/api/browse", params={"path": str(tmp_path)})
        names = [i["name"] for i in r.json()["items"]]
        assert "subdir_a" in names
        assert "subdir_b" in names


# ════════════════════════════════════════════════════════════════════════════════
# 6. Logs
# ════════════════════════════════════════════════════════════════════════════════

class TestLogs:

    async def test_list_logs_empty(self, client):
        r = await client.get("/api/logs")
        assert r.status_code == 200
        assert r.json() == []

    async def test_list_logs_includes_log_files(self, client, tmp_path):
        (tmp_path / "logs" / "test.log").write_text("hello")
        r = await client.get("/api/logs")
        names = [f["filename"] for f in r.json()]
        assert "test.log" in names

    async def test_get_log_returns_content(self, client, tmp_path):
        (tmp_path / "logs" / "sample.log").write_text("log content")
        r = await client.get("/api/logs/sample.log")
        assert r.status_code == 200
        assert "log content" in r.json()["content"]

    async def test_get_log_404_for_missing(self, client):
        r = await client.get("/api/logs/nonexistent.log")
        assert r.status_code == 404

    async def test_get_log_400_for_dotdot_in_filename(self, client):
        """.. 포함 파일명은 path traversal 방어로 400을 반환해야 한다"""
        # httpx는 URL 경로의 /../를 정규화하므로 파일명 자체에 ..을 포함시킨다
        r = await client.get("/api/logs/test..evil.log")
        assert r.status_code == 400

    async def test_get_log_search_filters_lines(self, client, tmp_path):
        (tmp_path / "logs" / "app.log").write_text("ERROR something\nINFO ok\nERROR again")
        r = await client.get("/api/logs/app.log", params={"search": "ERROR"})
        assert r.status_code == 200
        body = r.json()
        assert body["matches"] == 2
        assert "INFO ok" not in body["content"]


# ════════════════════════════════════════════════════════════════════════════════
# 7. Pipelines
# ════════════════════════════════════════════════════════════════════════════════

class TestPipelines:

    async def test_list_pipelines_empty(self, client):
        r = await client.get("/api/pipelines")
        assert r.status_code == 200
        assert r.json() == []

    async def test_get_pipeline_404(self, client):
        r = await client.get("/api/pipelines/no-such-id")
        assert r.status_code == 404

    async def test_stop_pipeline_404(self, client):
        r = await client.post("/api/pipelines/no-such-id/stop")
        assert r.status_code == 404

    async def test_delete_pipeline_404(self, client):
        r = await client.delete("/api/pipelines/no-such-id")
        assert r.status_code == 404

    async def test_start_pipeline_400_for_unknown_session(self, client):
        r = await client.post("/api/pipelines", json={
            "session_id": "no-such-session",
            "goal": "do something",
        })
        assert r.status_code == 400

    async def test_start_pipeline_400_for_api_mode_no_key(self, client, monkeypatch):
        """API 모드인데 ANTHROPIC_API_KEY 없으면 400"""
        sid = f"s-{uuid.uuid4().hex[:4]}"
        main_module.sessions[sid] = ClaudeSession(sid, ".", "")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        r = await client.post("/api/pipelines", json={
            "session_id": sid,
            "goal": "goal",
            "mode": "api",
        })
        assert r.status_code == 400

    async def test_compat_get_pipeline_404(self, client):
        r = await client.get("/api/pipeline/no-such-id")
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════════════════
# 8. Plan Phases
# ════════════════════════════════════════════════════════════════════════════════

class TestPlanPhases:

    def _add_phase(self, status: str = "idle") -> PlanPhase:
        sid = f"src-{uuid.uuid4().hex[:4]}"
        src = ClaudeSession(sid, ".", "")
        main_module.sessions[sid] = src
        phase = PlanPhase(src, "goal", "cli", "sonnet")
        phase.status = status
        main_module.plan_phases[phase.id] = phase
        return phase

    async def test_list_plan_phases_empty(self, client):
        r = await client.get("/api/plan-phases")
        assert r.status_code == 200
        assert r.json() == []

    async def test_get_plan_phase_404(self, client):
        r = await client.get("/api/plan-phases/no-such-id")
        assert r.status_code == 404

    async def test_submit_answers_404_for_unknown(self, client):
        r = await client.post("/api/plan-phases/ghost/answers", json={"answers": {}})
        assert r.status_code == 404

    async def test_submit_answers_409_wrong_status(self, client):
        phase = self._add_phase(status="idle")  # questions_ready 아님
        r = await client.post(f"/api/plan-phases/{phase.id}/answers",
                              json={"answers": {"q1": "yes"}})
        assert r.status_code == 409

    async def test_submit_answers_success(self, client):
        phase = self._add_phase(status="questions_ready")
        r = await client.post(f"/api/plan-phases/{phase.id}/answers",
                              json={"answers": {"q1": "yes"}})
        assert r.status_code == 200

    async def test_approve_plan_phase_404(self, client):
        r = await client.post("/api/plan-phases/ghost/approve", json={})
        assert r.status_code == 404

    async def test_approve_plan_phase_409_wrong_status(self, client):
        phase = self._add_phase(status="questions_generating")
        r = await client.post(f"/api/plan-phases/{phase.id}/approve", json={})
        assert r.status_code == 409

    async def test_regenerate_plan_phase_404(self, client):
        r = await client.post("/api/plan-phases/ghost/regenerate")
        assert r.status_code == 404

    async def test_regenerate_409_wrong_status(self, client):
        phase = self._add_phase(status="idle")
        r = await client.post(f"/api/plan-phases/{phase.id}/regenerate")
        assert r.status_code == 409

    async def test_delete_plan_phase_404(self, client):
        r = await client.delete("/api/plan-phases/ghost")
        assert r.status_code == 404

    async def test_get_plan_phase_returns_to_dict(self, client):
        phase = self._add_phase(status="questions_ready")
        r = await client.get(f"/api/plan-phases/{phase.id}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == phase.id
        assert body["status"] == "questions_ready"

    async def test_create_plan_phase_400_for_unknown_session(self, client):
        r = await client.post("/api/plan-phases", json={
            "session_id": "no-such",
            "goal": "g",
            "mode": "cli",
        })
        assert r.status_code == 400


# ════════════════════════════════════════════════════════════════════════════════
# 9. Shells
# ════════════════════════════════════════════════════════════════════════════════

class TestShells:

    async def test_list_shells_empty(self, client):
        r = await client.get("/api/shells")
        assert r.status_code == 200
        assert r.json() == []

    async def test_create_shell_503_when_no_winpty(self, client, monkeypatch):
        monkeypatch.setattr(main_module, "HAS_WINPTY", False)
        r = await client.post("/api/shells", json={"shell_type": "cmd"})
        assert r.status_code == 503

    async def test_kill_shell_404_for_unknown(self, client):
        r = await client.delete("/api/shells/no-such-id")
        assert r.status_code == 404

    async def test_kill_shell_compat_404(self, client):
        r = await client.delete("/api/shell/no-such-id")
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════════════════
# 10. Git clone URL validation
# ════════════════════════════════════════════════════════════════════════════════

class TestGitCloneValidation:

    async def test_http_url_blocked(self, client):
        r = await client.post("/api/git/clone", json={"url": "http://github.com/x/y"})
        assert r.status_code == 400

    async def test_metachar_in_url_blocked(self, client):
        r = await client.post("/api/git/clone", json={"url": "https://github.com/x/y;rm -rf /"})
        assert r.status_code == 400

    async def test_dotgit_only_url_blocked(self, client):
        r = await client.post("/api/git/clone", json={"url": "https://github.com/user/.git"})
        assert r.status_code == 400

    async def test_valid_url_passes_validation(self, client, monkeypatch, tmp_path):
        """유효한 URL은 검증을 통과하고 git 실행 단계까지 진행 (git 실패 허용)"""
        import asyncio

        async def _fake_exec(*args, **kwargs):
            mock_proc = type("P", (), {
                "returncode": 1,
                "communicate": lambda self: asyncio.coroutine(
                    lambda: (b"", b"fake git error"))(),
            })()

            async def _comm():
                return b"", b"fake git error"

            mock_proc.communicate = _comm
            return mock_proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)
        # 유효한 https URL → 400이 아닌 다른 응답 (200 또는 git 실패로 200 ok:false)
        r = await client.post("/api/git/clone",
                              json={"url": "https://github.com/user/repo.git",
                                    "dest": str(tmp_path / "clone_target")})
        assert r.status_code != 400  # URL 검증은 통과


# ════════════════════════════════════════════════════════════════════════════════
# 11. Git status / log — 경로 검증
# ════════════════════════════════════════════════════════════════════════════════

class TestGitEndpoints:

    async def test_git_status_400_for_missing_path(self, client):
        r = await client.get("/api/git/status", params={"path": "/no/such/path"})
        assert r.status_code == 400

    async def test_git_log_400_for_missing_path(self, client):
        r = await client.get("/api/git/log", params={"path": "/no/such/path"})
        assert r.status_code == 400

    async def test_git_branches_400_for_missing_path(self, client):
        r = await client.get("/api/git/branches", params={"path": "/no/such/path"})
        assert r.status_code == 400

    async def test_git_diff_400_for_missing_path(self, client):
        r = await client.get("/api/git/diff", params={"path": "/no/such/path"})
        assert r.status_code == 400


# ════════════════════════════════════════════════════════════════════════════════
# 12. Admin API — /admin/status, /admin/restart, /admin/resume
# ════════════════════════════════════════════════════════════════════════════════

class TestAdminEndpoints:

    async def test_admin_status_returns_structure(self, client):
        """/admin/status 응답에 필수 키 + 타입 검증"""
        r = await client.get("/admin/status")
        assert r.status_code == 200
        data = r.json()
        assert "active_pipelines" in data
        assert "resumable_runs" in data
        assert "safe_to_restart" in data
        assert isinstance(data["active_pipelines"], int)
        assert isinstance(data["resumable_runs"], list)
        assert isinstance(data["safe_to_restart"], bool)

    async def test_admin_status_safe_to_restart_when_idle(self, client):
        """파이프라인 없는 idle 상태 → safe_to_restart == True"""
        r = await client.get("/admin/status")
        assert r.status_code == 200
        data = r.json()
        assert data["active_pipelines"] == 0
        assert data["safe_to_restart"] is True

    async def test_admin_resume_not_found(self, client):
        """존재하지 않는 run_id → 404"""
        r = await client.post("/admin/resume/nonexistent-id")
        assert r.status_code == 404

    async def test_admin_restart_returns_accepted(self, monkeypatch, client):
        """POST /admin/restart → 200 응답 (os.execv는 monkeypatch로 차단)"""
        import os
        monkeypatch.setattr(os, "execv", lambda *_: None)
        monkeypatch.setattr(main_module, "_shutting_down", False)
        r = await client.post("/admin/restart")
        assert r.status_code in (200, 202)
        data = r.json()
        assert "status" in data
        # 테스트 이후 _shutting_down 복원 (monkeypatch가 자동 처리)

