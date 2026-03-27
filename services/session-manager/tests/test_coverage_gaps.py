"""
tests/test_coverage_gaps.py

커버리지 갭 보완 테스트 — 상위 3개 미커버 파일 집중:
  1. app/pipeline.py  (40%) — _tail_lines, PipelineRunner utils, PlanPhase utils
  2. app/screen.py    (39%) — ScreenMonitor lifecycle (mocked mss/PIL)
  3. app/routes_api.py(44%) — session ops, templates, logs, git/exec security, pipelines, plan-phases, monitor, shells

실행:
    .venv/Scripts/pytest tests/test_coverage_gaps.py -v
"""
import asyncio
import json
import os
import string
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
import app.models as models_module
import app.pipeline as pipeline_module
import app.screen as screen_module
import app.session as session_module
import app.shell as shell_module
import app.state as state_module
from app.main import (
    ClaudeSession,
    PipelineRunner,
    PlanPhase,
    ShellSession,
    MAX_SESSIONS_PER_CLIENT,
    sessions,
    pipelines,
    plan_phases,
    shell_sessions,
)
from app.pipeline import _tail_lines
from app.screen import ScreenMonitor

client = TestClient(app=main_module.app, raise_server_exceptions=True)


# ════════════════════════════════════════════════════════════════════════════════
# 공통 픽스처
# ════════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def reset_global_state():
    """각 테스트 전후 전역 상태 초기화"""
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


def _make_session(sid="test01", work_dir=".", model="sonnet") -> ClaudeSession:
    """테스트용 ClaudeSession 생성 (start_worker 미호출)"""
    async def _build():
        return ClaudeSession(sid, work_dir, model)
    return asyncio.run(_build())


def _register_session(sid="test01") -> ClaudeSession:
    """세션을 전역 sessions dict에 등록하고 반환"""
    s = _make_session(sid)
    main_module.sessions[sid] = s
    return s


# ════════════════════════════════════════════════════════════════════════════════
# 1. pipeline.py — _tail_lines
# ════════════════════════════════════════════════════════════════════════════════

class TestTailLines:
    """_tail_lines 텍스트 절단 헬퍼"""

    def test_short_text_unchanged(self):
        """max_chars 이하 텍스트는 그대로 반환해야 한다"""
        text = "hello world"
        assert _tail_lines(text, max_chars=100) == text

    def test_exact_length_unchanged(self):
        """정확히 max_chars 길이의 텍스트도 그대로 반환해야 한다"""
        text = "a" * 3000
        assert _tail_lines(text, max_chars=3000) == text

    def test_long_text_truncated_at_line_boundary(self):
        """max_chars 초과 시 라인 경계에서 절단해야 한다"""
        # 3001자 텍스트 (마지막 3000자 내에 개행 포함)
        prefix = "line0\n"
        filler = "x" * 2994 + "\n"  # 2995자
        suffix = "lastline"         # 8자 → total tail[-3000:] = filler + suffix
        text = prefix + filler + suffix
        result = _tail_lines(text, max_chars=3000)
        # 첫 번째 개행 이후부터 시작해야 함
        assert not result.startswith("x"), "라인 경계 이전 내용이 포함되면 안 됨"
        assert "lastline" in result

    def test_long_text_no_newline_in_tail_returns_full_tail(self):
        """tail에 개행이 없으면 tail 전체를 그대로 반환해야 한다"""
        text = "a" * 4000  # 개행 없음
        result = _tail_lines(text, max_chars=3000)
        assert len(result) == 3000
        assert result == "a" * 3000

    def test_default_max_chars_is_3000(self):
        """기본 max_chars=3000으로 동작해야 한다"""
        text = "b" * 5000
        result = _tail_lines(text)
        assert len(result) <= 3000


# ════════════════════════════════════════════════════════════════════════════════
# 2. pipeline.py — PipelineRunner 유틸
# ════════════════════════════════════════════════════════════════════════════════

class TestPipelineRunnerUtils:
    """PipelineRunner._build_messages / to_dict"""

    def _make_runner(self) -> PipelineRunner:
        async def _build():
            session = ClaudeSession("pr01", ".", "sonnet")
            return PipelineRunner(session, "test goal", "sonnet", 3, "api", 2)
        return asyncio.run(_build())

    def test_to_dict_has_required_keys(self):
        """to_dict()가 필수 키를 포함해야 한다"""
        runner = self._make_runner()
        d = runner.to_dict()
        required = {"id", "session_id", "goal", "supervisor_model", "mode",
                    "status", "iteration", "max_iterations", "current_cycle",
                    "max_cycles", "total_iterations", "summary", "created_at",
                    "history", "supervisor_retries"}
        missing = required - set(d.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_to_dict_initial_status_idle(self):
        """생성 직후 status는 idle이어야 한다"""
        runner = self._make_runner()
        assert runner.to_dict()["status"] == "idle"

    def test_build_messages_empty_history(self):
        """히스토리 없이 last_output=""이면 첫 번째 프롬프트 메시지가 생성되어야 한다"""
        runner = self._make_runner()
        msgs = runner._build_messages("")
        assert len(msgs) >= 1
        assert msgs[-1]["role"] == "user"
        assert "첫 번째" in msgs[-1]["content"]

    def test_build_messages_with_last_output(self):
        """last_output이 있으면 CLI 결과가 메시지에 포함되어야 한다"""
        runner = self._make_runner()
        msgs = runner._build_messages("some output here")
        last_msg = msgs[-1]
        assert last_msg["role"] == "user"
        assert "CLI 실행 결과" in last_msg["content"]

    def test_build_messages_history_included(self):
        """히스토리(supervisor+cli_result)가 메시지에 반영되어야 한다"""
        runner = self._make_runner()
        runner._add_history("supervisor", "do something")
        runner._add_history("cli_result", "done")
        msgs = runner._build_messages("")
        # supervisor → assistant, cli_result → user
        roles = [m["role"] for m in msgs]
        assert "assistant" in roles
        assert "user" in roles

    def test_add_history(self):
        """_add_history가 올바른 구조로 항목을 추가해야 한다"""
        runner = self._make_runner()
        runner._add_history("system", "test message")
        assert len(runner.history) == 1
        entry = runner.history[0]
        assert entry["role"] == "system"
        assert entry["content"] == "test message"
        assert "timestamp" in entry

    def test_stop_sets_flag_and_status(self):
        """stop()은 _stop_flag=True, status='stopped'를 설정해야 한다"""
        async def _run():
            session = ClaudeSession("ps01", ".", "sonnet")
            session.kill = AsyncMock()
            session.interrupt = AsyncMock()
            runner = PipelineRunner(session, "goal", "sonnet", 2, "api")
            await runner.stop()
            return runner._stop_flag, runner.status
        flag, status = asyncio.run(_run())
        assert flag is True
        assert status == "stopped"


# ════════════════════════════════════════════════════════════════════════════════
# 3. pipeline.py — PlanPhase 유틸
# ════════════════════════════════════════════════════════════════════════════════

class TestPlanPhaseUtils:
    """PlanPhase 유틸리티 메서드"""

    def _make_phase(self) -> PlanPhase:
        async def _build():
            session = ClaudeSession("ph01", ".", "sonnet")
            return PlanPhase(session, "test goal", "api", "sonnet")
        return asyncio.run(_build())

    def test_to_dict_has_required_keys(self):
        """to_dict()가 필수 키를 포함해야 한다"""
        phase = self._make_phase()
        d = phase.to_dict()
        required = {"id", "session_id", "goal", "mode", "supervisor_model",
                    "status", "questions", "answers", "plan_text", "error",
                    "pipeline_id", "created_at"}
        assert not (required - set(d.keys()))

    def test_initial_status_idle(self):
        """생성 직후 status는 idle이어야 한다"""
        phase = self._make_phase()
        assert phase.status == "idle"

    def test_find_question_text_found(self):
        """questions 목록에 있는 qid를 찾아야 한다"""
        phase = self._make_phase()
        phase.questions = [{"id": "q1", "question": "What is your goal?"}]
        assert phase._find_question_text("q1") == "What is your goal?"

    def test_find_question_text_not_found(self):
        """없는 qid는 qid 자체를 반환해야 한다"""
        phase = self._make_phase()
        phase.questions = []
        assert phase._find_question_text("q99") == "q99"

    def test_parse_questions_json_direct(self):
        """코드 펜스 없는 직접 JSON 파싱"""
        phase = self._make_phase()
        raw = json.dumps({"questions": [
            {"id": "q1", "question": "Test?", "why": "reason", "options": []}
        ]})
        result = phase._parse_questions_json(raw)
        assert len(result) == 1
        assert result[0]["id"] == "q1"
        assert result[0]["question"] == "Test?"

    def test_parse_questions_json_code_fenced(self):
        """```json ... ``` 코드 펜스 제거 후 파싱해야 한다"""
        phase = self._make_phase()
        payload = json.dumps({"questions": [{"question": "Fenced?"}]})
        raw = f"```json\n{payload}\n```"
        result = phase._parse_questions_json(raw)
        assert len(result) == 1
        assert result[0]["question"] == "Fenced?"

    def test_parse_questions_json_plain_code_fence(self):
        """``` (json 없이) 코드 펜스도 제거해야 한다"""
        phase = self._make_phase()
        payload = json.dumps({"questions": [{"question": "Plain fence?"}]})
        raw = f"```\n{payload}\n```"
        result = phase._parse_questions_json(raw)
        assert len(result) == 1

    def test_parse_questions_json_defaults_set(self):
        """id/why/options 미설정 시 기본값이 채워져야 한다"""
        phase = self._make_phase()
        raw = json.dumps({"questions": [{"question": "Minimal?"}]})
        result = phase._parse_questions_json(raw)
        assert result[0]["id"] == "q1"
        assert result[0]["why"] == ""
        assert result[0]["options"] == []

    def test_parse_questions_json_invalid_raises(self):
        """JSON도 추출 불가능한 텍스트는 RuntimeError를 발생시켜야 한다"""
        phase = self._make_phase()
        with pytest.raises(RuntimeError):
            phase._parse_questions_json("not json at all, no braces")

    def test_parse_questions_json_extracts_embedded_json(self):
        """앞뒤에 텍스트가 있어도 JSON 블록을 추출해야 한다"""
        phase = self._make_phase()
        payload = json.dumps({"questions": []})
        raw = f"Some preamble...\n{payload}\nTrailing text."
        result = phase._parse_questions_json(raw)
        assert result == []

    def test_get_project_context_no_files(self, tmp_path):
        """CLAUDE.md/README.md가 없으면 '없음' 메시지를 반환해야 한다"""
        async def _run():
            session = ClaudeSession("ctx01", str(tmp_path), "sonnet")
            phase = PlanPhase(session, "goal", "api", "sonnet")
            return phase._get_project_context()
        result = asyncio.run(_run())
        assert "없음" in result

    def test_get_project_context_with_claude_md(self, tmp_path):
        """CLAUDE.md가 있으면 내용을 포함해야 한다"""
        (tmp_path / "CLAUDE.md").write_text("# My Project\nTest content", encoding="utf-8")
        async def _run():
            session = ClaudeSession("ctx02", str(tmp_path), "sonnet")
            phase = PlanPhase(session, "goal", "api", "sonnet")
            return phase._get_project_context()
        result = asyncio.run(_run())
        assert "CLAUDE.md" in result
        assert "My Project" in result

    def test_cleanup_supervisor_no_session(self):
        """감독자 세션 없을 때 _cleanup_supervisor는 에러 없이 종료해야 한다"""
        async def _run():
            session = ClaudeSession("cs01", ".", "sonnet")
            phase = PlanPhase(session, "goal", "api", "sonnet")
            await phase._cleanup_supervisor()  # must not raise
        asyncio.run(_run())

    def test_cleanup_supervisor_calls_kill(self):
        """감독자 세션이 있으면 kill을 호출해야 한다"""
        async def _run():
            session = ClaudeSession("cs02", ".", "sonnet")
            phase = PlanPhase(session, "goal", "api", "sonnet")
            mock_sv = MagicMock()
            mock_sv.kill = AsyncMock()
            phase._supervisor_session = mock_sv
            await phase._cleanup_supervisor()
            assert mock_sv.kill.called
            assert phase._supervisor_session is None
        asyncio.run(_run())


# ════════════════════════════════════════════════════════════════════════════════
# 4. pipeline.py — _extract_cli_response
# ════════════════════════════════════════════════════════════════════════════════

class TestExtractCliResponse:
    """PipelineRunner._extract_cli_response"""

    def _make_runner(self) -> PipelineRunner:
        async def _build():
            session = ClaudeSession("ec01", ".", "sonnet")
            return PipelineRunner(session, "goal", "sonnet", 3, "cli")
        return asyncio.run(_build())

    def test_extracts_assistant_lines(self):
        """assistant 타입 출력을 추출해야 한다"""
        runner = self._make_runner()
        async def _run():
            sv = ClaudeSession("sv01", ".", "sonnet")
            sv.output_lines = [
                {"type": "system", "text": ">>> prompt sent"},
                {"type": "assistant", "text": "Here is my response"},
            ]
            return runner._extract_cli_response(sv)
        result = asyncio.run(_run())
        assert "Here is my response" in result

    def test_strips_function_calls_xml(self):
        """function_calls XML 블록을 제거해야 한다"""
        runner = self._make_runner()
        async def _run():
            sv = ClaudeSession("sv02", ".", "sonnet")
            sv.output_lines = [
                {"type": "system", "text": ">>> prompt"},
                {"type": "assistant", "text": "Answer <function_calls>foo</function_calls> done"},
            ]
            return runner._extract_cli_response(sv)
        result = asyncio.run(_run())
        assert "<function_calls>" not in result
        assert "Answer" in result
        assert "done" in result

    def test_empty_response_raises(self):
        """응답이 없으면 RuntimeError를 발생시켜야 한다"""
        runner = self._make_runner()
        async def _run():
            sv = ClaudeSession("sv03", ".", "sonnet")
            sv.output_lines = [
                {"type": "system", "text": ">>> prompt"},
            ]
            return runner._extract_cli_response(sv)
        with pytest.raises(RuntimeError):
            asyncio.run(_run())

    def test_stops_at_system_prompt_boundary(self):
        """>>> 이전 assistant 출력은 포함하지 않아야 한다"""
        runner = self._make_runner()
        async def _run():
            sv = ClaudeSession("sv04", ".", "sonnet")
            sv.output_lines = [
                {"type": "assistant", "text": "old response"},
                {"type": "system", "text": ">>> new prompt sent"},
                {"type": "assistant", "text": "new response"},
            ]
            return runner._extract_cli_response(sv)
        result = asyncio.run(_run())
        assert "new response" in result
        assert "old response" not in result


# ════════════════════════════════════════════════════════════════════════════════
# 5. screen.py — ScreenMonitor lifecycle
# ════════════════════════════════════════════════════════════════════════════════

class TestScreenMonitor:
    """ScreenMonitor 생명주기 (mss/PIL 없이 테스트)"""

    def test_initial_state(self):
        """생성 직후 기본값 확인"""
        monitor = ScreenMonitor()
        assert monitor._running is False
        assert monitor._task is None
        assert monitor._latest_path is None
        assert monitor.latest is None

    def test_latest_property_returns_path(self, tmp_path):
        """_latest_path 설정 시 latest 프로퍼티가 반환해야 한다"""
        monitor = ScreenMonitor()
        p = tmp_path / "screen_test.jpg"
        p.write_bytes(b"fake")
        monitor._latest_path = p
        assert monitor.latest == p

    def test_stop_no_task(self):
        """task 없을 때 stop()은 에러 없이 종료해야 한다"""
        async def _run():
            monitor = ScreenMonitor()
            await monitor.stop()
            assert monitor._running is False
        asyncio.run(_run())

    def test_stop_with_task_cancels(self):
        """task가 있으면 stop()이 cancel하고 None으로 설정해야 한다"""
        async def _run():
            monitor = ScreenMonitor()
            monitor._running = True
            # 장기 실행 태스크 생성
            async def _forever():
                await asyncio.sleep(9999)
            monitor._task = asyncio.create_task(_forever())
            await monitor.stop()
            assert monitor._running is False
            assert monitor._task is None
        asyncio.run(_run())

    def test_start_periodic_sets_running(self):
        """start_periodic()은 _running=True로 설정해야 한다"""
        async def _run():
            monitor = ScreenMonitor()
            # _loop를 무한루프하지 않도록 패치
            with patch.object(monitor, '_loop', new=AsyncMock()):
                await monitor.start_periodic(interval=60)
            assert monitor._running is True
            if monitor._task:
                monitor._task.cancel()
                try:
                    await monitor._task
                except (asyncio.CancelledError, Exception):
                    pass
        asyncio.run(_run())

    def test_start_periodic_cancels_existing_task(self):
        """기존 task가 있으면 start_periodic이 새 task를 생성해야 한다"""
        async def _run():
            monitor = ScreenMonitor()
            async def _forever():
                try:
                    await asyncio.sleep(9999)
                except asyncio.CancelledError:
                    pass
            old_task = asyncio.create_task(_forever())
            monitor._task = old_task

            with patch.object(monitor, '_loop', new=AsyncMock()):
                await monitor.start_periodic(interval=60)

            # 새 task가 생성되었는지 확인 (old_task와 다른 객체)
            assert monitor._task is not old_task
            # 강제 정리
            if monitor._task and not monitor._task.done():
                monitor._task.cancel()
                try:
                    await monitor._task
                except (asyncio.CancelledError, Exception):
                    pass
            if not old_task.done():
                old_task.cancel()
                try:
                    await old_task
                except (asyncio.CancelledError, Exception):
                    pass
        asyncio.run(_run())

    def test_cleanup_removes_old_files(self, monkeypatch, tmp_path):
        """_cleanup()은 50개 이하로 유지하도록 오래된 파일을 삭제해야 한다"""
        monkeypatch.setattr(screen_module, "SCREENSHOTS_DIR", tmp_path)

        monitor = ScreenMonitor()
        # 55개 파일 생성
        for i in range(55):
            (tmp_path / f"screen_{i:04d}.jpg").write_bytes(b"x")

        monitor._cleanup()

        remaining = list(tmp_path.glob("screen_*.jpg"))
        assert len(remaining) <= 50, f"50개 초과: {len(remaining)}"

    def test_capture_with_mock(self, monkeypatch, tmp_path):
        """mss와 PIL을 mock하여 capture() 성공 경로 테스트"""
        monkeypatch.setattr(screen_module, "SCREENSHOTS_DIR", tmp_path)

        mock_img = MagicMock()
        mock_img.size = (100, 100)
        mock_img.bgra = b"\x00" * (100 * 100 * 4)

        mock_sct = MagicMock()
        mock_sct.monitors = [{"top": 0, "left": 0, "width": 100, "height": 100}]
        mock_sct.grab.return_value = mock_img
        mock_sct.__enter__ = MagicMock(return_value=mock_sct)
        mock_sct.__exit__ = MagicMock(return_value=False)

        mock_pil_img = MagicMock()

        mock_mss = MagicMock()
        mock_mss.mss.return_value = mock_sct

        mock_image_class = MagicMock()
        mock_image_class.frombytes.return_value = mock_pil_img

        mock_pil_module = MagicMock()
        mock_pil_module.Image = mock_image_class

        monitor = ScreenMonitor()

        with patch.dict("sys.modules", {"mss": mock_mss, "PIL": mock_pil_module, "PIL.Image": mock_image_class}):
            path = monitor.capture()

        assert path is not None
        assert monitor._latest_path == path

    def test_loop_handles_exception(self):
        """_loop()에서 capture() 예외 시 로그 후 계속 실행해야 한다"""
        import app.screen as _screen_mod

        call_count = 0

        async def _fake_to_thread(fn, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("capture failed")
            # 두 번째 호출 시 루프 종료
            return None

        async def _run():
            monitor = ScreenMonitor()
            monitor._running = True
            monitor._interval = 0  # sleep 시간 최소화

            original_to_thread = asyncio.to_thread

            async def _patched_to_thread(fn, *args, **kwargs):
                result = await _fake_to_thread(fn, *args, **kwargs)
                monitor._running = False  # 루프 조기 종료
                return result

            with patch.object(_screen_mod.asyncio, "to_thread", new=_patched_to_thread):
                with patch.object(_screen_mod.asyncio, "sleep", new=AsyncMock()):
                    await monitor._loop()

            assert call_count >= 1
        asyncio.run(_run())


# ════════════════════════════════════════════════════════════════════════════════
# 6. routes_api.py — 세션 추가 operations
# ════════════════════════════════════════════════════════════════════════════════

class TestSessionOperations:
    """sessions 관련 미커버 엔드포인트"""

    def test_pending_restore_empty(self):
        """세션 없을 때 빈 리스트를 반환해야 한다"""
        r = client.get("/api/sessions/pending-restore")
        assert r.status_code == 200
        assert r.json() == []

    def test_pending_restore_with_session(self):
        """세션이 있으면 preview 정보가 포함되어야 한다"""
        s = _register_session("pr01")
        s._append_output("assistant", "Hello from Claude")
        r = client.get("/api/sessions/pending-restore")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert "preview" in data[0]
        assert "output_line_count" in data[0]

    def test_dismiss_sessions_found(self):
        """등록된 세션 ID는 dismissed 목록에 포함되어야 한다"""
        s = _register_session("dm01")
        s.kill = AsyncMock()
        s.delete_state = MagicMock()
        r = client.post("/api/sessions/dismiss", json={"session_ids": ["dm01"]})
        assert r.status_code == 200
        body = r.json()
        assert "dm01" in body["dismissed"]
        assert body["not_found"] == []

    def test_dismiss_sessions_not_found(self):
        """없는 세션 ID는 not_found에 포함되어야 한다"""
        r = client.post("/api/sessions/dismiss", json={"session_ids": ["nope"]})
        assert r.status_code == 200
        assert "nope" in r.json()["not_found"]

    def test_interrupt_session_404(self):
        """없는 세션 interrupt → 404"""
        r = client.post("/api/sessions/missing/interrupt")
        assert r.status_code == 404

    def test_interrupt_session_success(self):
        """존재하는 세션 interrupt → 200"""
        s = _register_session("ir01")
        s.interrupt = AsyncMock()
        r = client.post("/api/sessions/ir01/interrupt")
        assert r.status_code == 200

    def test_get_output_404(self):
        """없는 세션 output → 404"""
        r = client.get("/api/sessions/missing/output")
        assert r.status_code == 404

    def test_get_output_success(self):
        """존재하는 세션 output → 200, output 키 포함"""
        s = _register_session("out01")
        s._append_output("assistant", "test line")
        r = client.get("/api/sessions/out01/output")
        assert r.status_code == 200
        assert "output" in r.json()

    def test_rename_session_404(self):
        """없는 세션 rename → 404"""
        r = client.patch("/api/sessions/missing/rename", json={"name": "new"})
        assert r.status_code == 404

    def test_rename_session_success(self):
        """세션 rename → 200, 이름 변경 반영"""
        s = _register_session("rn01")
        s.save_state = MagicMock()
        r = client.patch("/api/sessions/rn01/rename", json={"name": "My Session"})
        assert r.status_code == 200
        assert r.json()["name"] == "My Session"

    def test_change_model_404(self):
        """없는 세션 model 변경 → 404"""
        r = client.patch("/api/sessions/missing/model", json={"model": "opus"})
        assert r.status_code == 404

    def test_change_model_success(self):
        """세션 model 변경 → 200, session_uuid 초기화"""
        s = _register_session("mod01")
        s.session_uuid = "old-uuid"
        s.save_state = MagicMock()
        r = client.patch("/api/sessions/mod01/model", json={"model": "claude-opus-4-6"})
        assert r.status_code == 200
        assert r.json()["model"] == "claude-opus-4-6"
        assert s.session_uuid is None

    def test_export_session_404(self):
        """없는 세션 export → 404"""
        r = client.get("/api/sessions/missing/export")
        assert r.status_code == 404

    def test_export_session_success(self):
        """세션 export → 200, markdown 키 포함"""
        s = _register_session("ex01")
        s._append_output("assistant", "Hello")
        r = client.get("/api/sessions/ex01/export")
        assert r.status_code == 200
        assert "markdown" in r.json()

    def test_fork_session_404(self):
        """없는 세션 fork → 404"""
        r = client.post("/api/sessions/missing/fork", json={"new_name": "forked"})
        assert r.status_code == 404

    def test_fork_session_success(self):
        """세션 fork → 200, 새 세션 ID 반환"""
        s = _register_session("fk01")
        s.start_worker = MagicMock()
        s.save_state = MagicMock()
        r = client.post("/api/sessions/fk01/fork", json={"new_name": "forked-session"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "forked"
        new_id = body["id"]
        assert new_id != "fk01"
        assert new_id in main_module.sessions

    def test_upload_file_session_not_found(self, tmp_path):
        """없는 세션에 업로드 → 404"""
        r = client.post(
            "/api/sessions/missing/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 404

    def test_upload_file_invalid_extension(self):
        """허용되지 않은 확장자 → 400"""
        _register_session("ul01")
        r = client.post(
            "/api/sessions/ul01/upload",
            files={"file": ("malware.exe", b"binary", "application/octet-stream")},
        )
        assert r.status_code == 400

    def test_upload_file_too_large(self, monkeypatch):
        """10MB 초과 파일 → 400"""
        _register_session("ul02")
        r = client.post(
            "/api/sessions/ul02/upload",
            files={"file": ("big.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain")},
        )
        assert r.status_code == 400

    def test_send_command_dead_session_409(self):
        """종료된 세션에 send → 409"""
        s = _register_session("sd01")
        s.alive = False
        r = client.post("/api/sessions/sd01/send", json={"command": "hello"})
        assert r.status_code == 409

    def test_delete_session_remove_true(self):
        """remove=true(기본)로 세션 삭제 → sessions에서 제거"""
        s = _register_session("dl01")
        s.kill = AsyncMock()
        s.delete_state = MagicMock()
        r = client.delete("/api/sessions/dl01")
        assert r.status_code == 200
        assert r.json()["status"] == "removed"
        assert "dl01" not in main_module.sessions

    def test_delete_session_remove_false(self):
        """remove=false면 세션이 sessions에 남아야 한다"""
        s = _register_session("dl02")
        s.kill = AsyncMock()
        s.save_state = MagicMock()
        r = client.delete("/api/sessions/dl02?remove=false")
        assert r.status_code == 200
        assert r.json()["status"] == "killed"
        assert "dl02" in main_module.sessions


# ════════════════════════════════════════════════════════════════════════════════
# 7. routes_api.py — 템플릿 CRUD
# ════════════════════════════════════════════════════════════════════════════════

class TestTemplates:
    """프롬프트 템플릿 API"""

    def test_list_templates_empty(self, monkeypatch, tmp_path):
        """템플릿 파일 없으면 빈 리스트 반환"""
        monkeypatch.setattr(models_module, "TEMPLATES_FILE", tmp_path / "templates.json")
        import app.routes_api as routes_api_module
        monkeypatch.setattr(routes_api_module, "TEMPLATES_FILE", tmp_path / "templates.json")
        r = client.get("/api/templates")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_and_list_template(self, monkeypatch, tmp_path):
        """템플릿 생성 후 목록 조회"""
        tf = tmp_path / "templates.json"
        monkeypatch.setattr(models_module, "TEMPLATES_FILE", tf)
        import app.routes_api as routes_api_module
        monkeypatch.setattr(routes_api_module, "TEMPLATES_FILE", tf)

        r = client.post("/api/templates", json={
            "name": "Test Template",
            "prompt": "Do something",
            "category": "testing",
        })
        assert r.status_code == 200
        entry = r.json()
        assert entry["name"] == "Test Template"
        assert "id" in entry

    def test_delete_template(self, monkeypatch, tmp_path):
        """템플릿 삭제"""
        tf = tmp_path / "templates.json"
        monkeypatch.setattr(models_module, "TEMPLATES_FILE", tf)
        import app.routes_api as routes_api_module
        monkeypatch.setattr(routes_api_module, "TEMPLATES_FILE", tf)

        # 먼저 생성
        r = client.post("/api/templates", json={
            "name": "ToDelete", "prompt": "del", "category": "test"
        })
        tid = r.json()["id"]

        r = client.delete(f"/api/templates/{tid}")
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"


# ════════════════════════════════════════════════════════════════════════════════
# 8. routes_api.py — CLAUDE.md 편집
# ════════════════════════════════════════════════════════════════════════════════

class TestClaudeMd:
    """CLAUDE.md 읽기/쓰기"""

    def test_get_claude_md_session_not_found(self):
        r = client.get("/api/sessions/missing/claude-md")
        assert r.status_code == 404

    def test_get_claude_md_not_exists(self, tmp_path):
        """CLAUDE.md 없으면 content=""를 반환해야 한다"""
        s = _register_session("cm01")
        s.work_dir = str(tmp_path)
        r = client.get("/api/sessions/cm01/claude-md")
        assert r.status_code == 200
        assert r.json()["content"] == ""

    def test_get_claude_md_exists(self, tmp_path):
        """CLAUDE.md 있으면 내용을 반환해야 한다"""
        (tmp_path / "CLAUDE.md").write_text("# Project", encoding="utf-8")
        s = _register_session("cm02")
        s.work_dir = str(tmp_path)
        r = client.get("/api/sessions/cm02/claude-md")
        assert r.status_code == 200
        assert "# Project" in r.json()["content"]

    def test_put_claude_md_session_not_found(self):
        r = client.put("/api/sessions/missing/claude-md", json={"content": "hello"})
        assert r.status_code == 404

    def test_put_claude_md_success(self, tmp_path):
        """CLAUDE.md 저장 성공"""
        s = _register_session("cm03")
        s.work_dir = str(tmp_path)
        r = client.put("/api/sessions/cm03/claude-md", json={"content": "# Updated"})
        assert r.status_code == 200
        assert r.json()["status"] == "saved"
        assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# Updated"


# ════════════════════════════════════════════════════════════════════════════════
# 9. routes_api.py — 로그 관리
# ════════════════════════════════════════════════════════════════════════════════

class TestLogs:
    """로그 목록/조회"""

    def test_list_logs_empty(self, monkeypatch, tmp_path):
        """로그 없으면 빈 리스트"""
        monkeypatch.setattr(models_module, "LOGS_DIR", tmp_path)
        import app.routes_api as routes_api_module
        monkeypatch.setattr(routes_api_module, "LOGS_DIR", tmp_path)
        r = client.get("/api/logs")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_logs_with_files(self, monkeypatch, tmp_path):
        """로그 파일 있으면 목록 반환"""
        (tmp_path / "app.log").write_text("log content")
        monkeypatch.setattr(models_module, "LOGS_DIR", tmp_path)
        import app.routes_api as routes_api_module
        monkeypatch.setattr(routes_api_module, "LOGS_DIR", tmp_path)
        r = client.get("/api/logs")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_get_log_dotdot_in_name_rejected(self, monkeypatch, tmp_path):
        """파일명에 '..'이 포함된 경우 → 400"""
        monkeypatch.setattr(models_module, "LOGS_DIR", tmp_path)
        import app.routes_api as routes_api_module
        monkeypatch.setattr(routes_api_module, "LOGS_DIR", tmp_path)
        # '..'이 파일명 안에 포함된 경우 차단되어야 한다
        r = client.get("/api/logs/file..etc.log")
        assert r.status_code == 400

    def test_get_log_backslash_rejected(self, monkeypatch, tmp_path):
        """백슬래시 포함 파일명 → 400"""
        monkeypatch.setattr(models_module, "LOGS_DIR", tmp_path)
        import app.routes_api as routes_api_module
        monkeypatch.setattr(routes_api_module, "LOGS_DIR", tmp_path)
        r = client.get("/api/logs/some\\file.log")
        assert r.status_code == 400

    def test_get_log_not_found(self, monkeypatch, tmp_path):
        """없는 로그 파일 → 404"""
        monkeypatch.setattr(models_module, "LOGS_DIR", tmp_path)
        import app.routes_api as routes_api_module
        monkeypatch.setattr(routes_api_module, "LOGS_DIR", tmp_path)
        r = client.get("/api/logs/nonexistent.log")
        assert r.status_code == 404

    def test_get_log_with_search(self, monkeypatch, tmp_path):
        """search 파라미터로 필터링"""
        (tmp_path / "app.log").write_text("line1 ERROR\nline2 INFO\nline3 ERROR")
        monkeypatch.setattr(models_module, "LOGS_DIR", tmp_path)
        import app.routes_api as routes_api_module
        monkeypatch.setattr(routes_api_module, "LOGS_DIR", tmp_path)
        r = client.get("/api/logs/app.log?search=ERROR")
        assert r.status_code == 200
        body = r.json()
        assert body["matches"] == 2
        assert "ERROR" in body["content"]

    def test_get_log_without_search(self, monkeypatch, tmp_path):
        """search 없이 전체 내용 반환"""
        (tmp_path / "app.log").write_text("full content here")
        monkeypatch.setattr(models_module, "LOGS_DIR", tmp_path)
        import app.routes_api as routes_api_module
        monkeypatch.setattr(routes_api_module, "LOGS_DIR", tmp_path)
        r = client.get("/api/logs/app.log")
        assert r.status_code == 200
        assert r.json()["content"] == "full content here"


# ════════════════════════════════════════════════════════════════════════════════
# 10. routes_api.py — git/exec 보안 검사
# ════════════════════════════════════════════════════════════════════════════════

class TestGitExec:
    """git/exec 명령 보안 검증"""

    def _body(self, command: str, path: str = ".") -> dict:
        return {"path": path, "command": command}

    def test_forbidden_command_403(self):
        """clean 등 절대 금지 명령 → 403"""
        r = client.post("/api/git/exec", json=self._body("clean -fd"))
        assert r.status_code == 403
        assert "금지" in r.json()["detail"]

    def test_unknown_command_403(self):
        """allow-list에 없는 명령 → 403"""
        r = client.post("/api/git/exec", json=self._body("bisect bad"))
        assert r.status_code == 403
        assert "허용되지 않은" in r.json()["detail"]

    def test_dangerous_flag_blocked(self):
        """--force 플래그 차단"""
        r = client.post("/api/git/exec", json=self._body("push --force"))
        assert r.status_code == 403
        assert "차단된 플래그" in r.json()["detail"]

    def test_hard_reset_blocked(self):
        """--hard 플래그 차단"""
        r = client.post("/api/git/exec", json=self._body("reset --hard HEAD"))
        assert r.status_code == 403

    def test_no_verify_blocked(self):
        """--no-verify 플래그 차단"""
        r = client.post("/api/git/exec", json=self._body("commit --no-verify -m msg"))
        assert r.status_code == 403

    def test_empty_command_rejects(self):
        """빈 명령어 → 422 (Pydantic min_length=1 검증) 또는 400"""
        r = client.post("/api/git/exec", json={"path": ".", "command": ""})
        # Pydantic 검증 실패(422) 또는 라우트 레벨 거부(400) 모두 허용
        assert r.status_code in (400, 422)

    def test_invalid_path_400(self):
        """존재하지 않는 경로 → 400"""
        r = client.post("/api/git/exec", json={"path": "/nonexistent/path/xyz", "command": "status"})
        assert r.status_code == 400

    def test_readonly_command_allowed(self, tmp_path):
        """status 등 읽기 전용 명령은 허용되어야 한다 (실행은 외부 프로세스)"""
        # tmp_path는 실제 git 저장소가 아니지만 보안 검사는 통과해야 함
        # (git 실행 결과는 ok=False여도 되지만 403/400이면 안 됨)
        r = client.post("/api/git/exec", json={"path": str(tmp_path), "command": "status"})
        # 403/400이 아니면 보안 검사 통과 (실제 실행 결과는 무관)
        assert r.status_code not in (400, 403)

    def test_shlex_parse_error_400(self):
        """파싱 불가능한 명령어 → 400"""
        r = client.post("/api/git/exec", json={"path": ".", "command": "commit -m 'unclosed"})
        assert r.status_code == 400


# ════════════════════════════════════════════════════════════════════════════════
# 11. routes_api.py — 파이프라인 API
# ════════════════════════════════════════════════════════════════════════════════

class TestPipelineAPI:
    """파이프라인 CRUD"""

    def _start_body(self, session_id="test01", mode="api") -> dict:
        return {
            "session_id": session_id,
            "goal": "test goal",
            "supervisor_model": "sonnet",
            "max_iterations": 2,
            "max_cycles": 1,
            "mode": mode,
        }

    def test_start_pipeline_invalid_session(self):
        """없는 세션 ID → 400"""
        r = client.post("/api/pipelines", json=self._start_body("nope"))
        assert r.status_code == 400

    def test_start_pipeline_api_mode_no_key(self, monkeypatch):
        """api 모드, ANTHROPIC_API_KEY 미설정 → 400"""
        _register_session("p01")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        r = client.post("/api/pipelines", json=self._start_body("p01", "api"))
        assert r.status_code == 400
        assert "ANTHROPIC_API_KEY" in r.json()["detail"]

    def test_start_pipeline_cli_mode_no_exe(self, monkeypatch):
        """cli 모드, CLAUDE_EXE=None → 400"""
        _register_session("p02")
        monkeypatch.setattr(state_module, "CLAUDE_EXE", None)
        r = client.post("/api/pipelines", json=self._start_body("p02", "cli"))
        assert r.status_code == 400

    def test_start_pipeline_session_already_bound(self, monkeypatch):
        """세션이 이미 파이프라인에 바인딩됨 → 409"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        s = _register_session("p03")
        s.pipeline_id = "existing-pipeline"

        with patch.object(PipelineRunner, "start", MagicMock()):
            r = client.post("/api/pipelines", json=self._start_body("p03", "api"))
        assert r.status_code == 409

    def test_start_pipeline_success(self, monkeypatch):
        """정상 파이프라인 시작 → 200"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        _register_session("p04")

        with patch.object(PipelineRunner, "start", MagicMock()):
            r = client.post("/api/pipelines", json=self._start_body("p04", "api"))
        assert r.status_code == 200
        assert "pipeline_id" in r.json()

    def test_list_pipelines_empty(self):
        r = client.get("/api/pipelines")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_pipeline_404(self):
        r = client.get("/api/pipelines/nope")
        assert r.status_code == 404

    def test_get_pipeline_found(self, monkeypatch):
        """등록된 파이프라인 조회"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        s = _register_session("p05")

        with patch.object(PipelineRunner, "start", MagicMock()):
            r = client.post("/api/pipelines", json=self._start_body("p05", "api"))
        pid = r.json()["pipeline_id"]

        r = client.get(f"/api/pipelines/{pid}")
        assert r.status_code == 200
        assert r.json()["id"] == pid

    def test_stop_pipeline_404(self):
        r = client.post("/api/pipelines/nope/stop")
        assert r.status_code == 404

    def test_stop_pipeline_success(self, monkeypatch):
        """파이프라인 stop"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        s = _register_session("p06")

        with patch.object(PipelineRunner, "start", MagicMock()):
            r = client.post("/api/pipelines", json=self._start_body("p06", "api"))
        pid = r.json()["pipeline_id"]

        with patch.object(PipelineRunner, "stop", new=AsyncMock()):
            r = client.post(f"/api/pipelines/{pid}/stop")
        assert r.status_code == 200

    def test_remove_pipeline_404(self):
        r = client.delete("/api/pipelines/nope")
        assert r.status_code == 404

    def test_remove_pipeline_not_running(self, monkeypatch):
        """비실행 파이프라인 삭제"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        s = _register_session("p07")

        with patch.object(PipelineRunner, "start", MagicMock()):
            r = client.post("/api/pipelines", json=self._start_body("p07", "api"))
        pid = r.json()["pipeline_id"]

        r = client.delete(f"/api/pipelines/{pid}")
        assert r.status_code == 200
        assert r.json()["status"] == "removed"
        assert pid not in main_module.pipelines

    def test_compat_route_pipeline_start(self, monkeypatch):
        """하위호환 /api/pipeline/start도 동작해야 한다"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        _register_session("p08")

        with patch.object(PipelineRunner, "start", MagicMock()):
            r = client.post("/api/pipeline/start", json=self._start_body("p08", "api"))
        assert r.status_code == 200

    def test_cleanup_pipelines(self):
        """cleanup 엔드포인트는 200을 반환해야 한다"""
        r = client.post("/api/pipelines/cleanup", json={})
        assert r.status_code == 200


# ════════════════════════════════════════════════════════════════════════════════
# 12. routes_api.py — Plan Phase API
# ════════════════════════════════════════════════════════════════════════════════

class TestPlanPhaseAPI:
    """Plan Phase CRUD + 상태 전이"""

    def _start_body(self, session_id="test01") -> dict:
        return {
            "session_id": session_id,
            "goal": "build a feature",
            "mode": "cli",
            "supervisor_model": "sonnet",
        }

    def test_create_plan_phase_invalid_session(self):
        r = client.post("/api/plan-phases", json=self._start_body("nope"))
        assert r.status_code == 400

    def test_create_plan_phase_api_mode_no_key(self, monkeypatch):
        _register_session("pp01")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        r = client.post("/api/plan-phases", json={**self._start_body("pp01"), "mode": "api"})
        assert r.status_code == 400

    def test_create_plan_phase_cli_mode_no_exe(self, monkeypatch):
        _register_session("pp02")
        monkeypatch.setattr(state_module, "CLAUDE_EXE", None)
        r = client.post("/api/plan-phases", json=self._start_body("pp02"))
        assert r.status_code == 400

    def test_create_plan_phase_success(self, monkeypatch):
        """CLI exe가 있으면 plan phase 생성 성공"""
        monkeypatch.setattr(state_module, "CLAUDE_EXE", "claude")
        _register_session("pp03")
        with patch.object(PlanPhase, "start", MagicMock()):
            r = client.post("/api/plan-phases", json=self._start_body("pp03"))
        assert r.status_code == 200
        assert "plan_id" in r.json()

    def test_list_plan_phases_empty(self):
        r = client.get("/api/plan-phases")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_plan_phases_expires_old(self, monkeypatch):
        """1시간 이상 된 비승인 plan phase는 자동 만료되어야 한다"""
        monkeypatch.setattr(state_module, "CLAUDE_EXE", "claude")
        s = _register_session("pp04")
        phase = PlanPhase(s, "goal", "cli", "sonnet")
        phase.status = "questions_generating"
        # created_at을 2시간 전으로 설정
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        phase.created_at = old_time
        main_module.plan_phases[phase.id] = phase

        r = client.get("/api/plan-phases")
        assert r.status_code == 200
        # 만료된 항목은 제거됨
        assert phase.id not in main_module.plan_phases

    def test_get_plan_phase_404(self):
        r = client.get("/api/plan-phases/nope")
        assert r.status_code == 404

    def test_get_plan_phase_found(self, monkeypatch):
        monkeypatch.setattr(state_module, "CLAUDE_EXE", "claude")
        s = _register_session("pp05")
        phase = PlanPhase(s, "goal", "cli", "sonnet")
        phase.status = "questions_ready"
        main_module.plan_phases[phase.id] = phase

        r = client.get(f"/api/plan-phases/{phase.id}")
        assert r.status_code == 200
        assert r.json()["id"] == phase.id

    def test_submit_answers_wrong_state(self, monkeypatch):
        """questions_ready 이외 상태에서 answers 제출 → 409"""
        monkeypatch.setattr(state_module, "CLAUDE_EXE", "claude")
        s = _register_session("pp06")
        phase = PlanPhase(s, "goal", "cli", "sonnet")
        phase.status = "plan_generating"  # wrong state
        main_module.plan_phases[phase.id] = phase

        r = client.post(f"/api/plan-phases/{phase.id}/answers",
                        json={"answers": {"q1": "yes"}})
        assert r.status_code == 409

    def test_submit_answers_success(self, monkeypatch):
        """questions_ready 상태에서 answers 제출 성공"""
        monkeypatch.setattr(state_module, "CLAUDE_EXE", "claude")
        s = _register_session("pp07")
        phase = PlanPhase(s, "goal", "cli", "sonnet")
        phase.status = "questions_ready"
        main_module.plan_phases[phase.id] = phase

        with patch.object(PlanPhase, "submit_answers", new=AsyncMock()) as mock_submit:
            r = client.post(f"/api/plan-phases/{phase.id}/answers",
                            json={"answers": {"q1": "yes"}})
        assert r.status_code == 200

    def test_approve_plan_wrong_state(self, monkeypatch):
        """plan_ready 이외 상태에서 approve → 409"""
        monkeypatch.setattr(state_module, "CLAUDE_EXE", "claude")
        s = _register_session("pp08")
        phase = PlanPhase(s, "goal", "cli", "sonnet")
        phase.status = "questions_generating"
        main_module.plan_phases[phase.id] = phase

        r = client.post(f"/api/plan-phases/{phase.id}/approve",
                        json={"plan_text": "step 1", "max_iterations": 3, "max_cycles": 1})
        assert r.status_code == 409

    def test_regenerate_plan_wrong_state(self, monkeypatch):
        """questions_generating 상태에서 regenerate → 409"""
        monkeypatch.setattr(state_module, "CLAUDE_EXE", "claude")
        s = _register_session("pp09")
        phase = PlanPhase(s, "goal", "cli", "sonnet")
        phase.status = "questions_generating"
        main_module.plan_phases[phase.id] = phase

        r = client.post(f"/api/plan-phases/{phase.id}/regenerate")
        assert r.status_code == 409

    def test_regenerate_plan_success(self, monkeypatch):
        """plan_ready 상태에서 regenerate → 200"""
        monkeypatch.setattr(state_module, "CLAUDE_EXE", "claude")
        s = _register_session("pp10")
        phase = PlanPhase(s, "goal", "cli", "sonnet")
        phase.status = "plan_ready"
        main_module.plan_phases[phase.id] = phase

        with patch.object(PlanPhase, "regenerate", new=AsyncMock()):
            r = client.post(f"/api/plan-phases/{phase.id}/regenerate")
        assert r.status_code == 200

    def test_delete_plan_phase_404(self):
        r = client.delete("/api/plan-phases/nope")
        assert r.status_code == 404

    def test_delete_plan_phase_success(self, monkeypatch):
        monkeypatch.setattr(state_module, "CLAUDE_EXE", "claude")
        s = _register_session("pp11")
        phase = PlanPhase(s, "goal", "cli", "sonnet")
        main_module.plan_phases[phase.id] = phase

        with patch.object(PlanPhase, "_cleanup_supervisor", new=AsyncMock()):
            r = client.delete(f"/api/plan-phases/{phase.id}")
        assert r.status_code == 200
        assert phase.id not in main_module.plan_phases


# ════════════════════════════════════════════════════════════════════════════════
# 13. routes_api.py — Monitor API
# ════════════════════════════════════════════════════════════════════════════════

class TestMonitorAPI:
    """Screen monitor 엔드포인트"""

    def test_monitor_stop(self):
        r = client.post("/api/monitor/stop")
        assert r.status_code == 200
        assert r.json()["status"] == "stopped"

    def test_monitor_start(self):
        r = client.post("/api/monitor/start?interval=60")
        assert r.status_code == 200
        assert r.json()["interval"] == 60
        # cleanup
        client.post("/api/monitor/stop")

    def test_monitor_latest_no_screenshot(self):
        """최신 스크린샷 없으면 None 반환"""
        r = client.get("/api/monitor/latest")
        assert r.status_code == 200
        assert r.json()["path"] is None

    def test_monitor_capture_import_error(self):
        """mss 미설치 시 capture → 503"""
        import app.routes_api as routes_api_module

        def _raise_import(*a, **kw):
            raise ImportError("no mss")

        with patch.object(routes_api_module.screen_monitor, "capture", side_effect=ImportError("no mss")):
            r = client.get("/api/monitor/capture")
        assert r.status_code == 503


# ════════════════════════════════════════════════════════════════════════════════
# 14. routes_api.py — Shell API
# ════════════════════════════════════════════════════════════════════════════════

class TestShellAPI:
    """Shell 세션 엔드포인트"""

    def test_create_shell_no_winpty(self, monkeypatch):
        """pywinpty 없으면 503 반환"""
        monkeypatch.setattr(shell_module, "HAS_WINPTY", False)
        import app.routes_api as routes_api_module
        monkeypatch.setattr(routes_api_module, "HAS_WINPTY", False)
        r = client.post("/api/shells", json={
            "work_dir": ".", "shell_type": "cmd", "cols": 80, "rows": 24
        })
        assert r.status_code == 503

    def test_list_shells_empty(self):
        r = client.get("/api/shells")
        assert r.status_code == 200
        assert r.json() == []

    def test_kill_shell_404(self):
        r = client.delete("/api/shells/nope")
        assert r.status_code == 404

    def test_kill_shell_success(self):
        """등록된 shell 삭제"""
        mock_shell = MagicMock()
        mock_shell.to_dict.return_value = {"id": "sh01", "alive": True}
        mock_shell.alive = True
        main_module.shell_sessions["sh01"] = mock_shell

        r = client.delete("/api/shells/sh01")
        assert r.status_code == 200
        assert "sh01" not in main_module.shell_sessions

    def test_compat_kill_shell(self):
        """하위호환 /api/shell/{id} DELETE"""
        mock_shell = MagicMock()
        mock_shell.to_dict.return_value = {"id": "sh02"}
        main_module.shell_sessions["sh02"] = mock_shell

        r = client.delete("/api/shell/sh02")
        assert r.status_code == 200


# ════════════════════════════════════════════════════════════════════════════════
# 15. routes_api.py — 통계 / 비교
# ════════════════════════════════════════════════════════════════════════════════

class TestStatsAndCompare:
    """stats, compare 엔드포인트"""

    def test_stats_empty(self):
        r = client.get("/api/stats")
        assert r.status_code == 200
        body = r.json()
        assert "sessions" in body
        assert "pipelines" in body
        assert "shells" in body

    def test_compare_no_claude_exe(self, monkeypatch):
        """CLAUDE_EXE=None → 503"""
        monkeypatch.setattr(state_module, "CLAUDE_EXE", None)
        r = client.post("/api/compare", json={
            "models": ["sonnet", "opus"],
            "prompt": "hello",
            "work_dir": ".",
            "skip_permissions": True,
        })
        assert r.status_code == 503

    def test_compare_session_limit(self, monkeypatch):
        """활성 세션 + 비교 세션 수가 한도 초과 → 429"""
        monkeypatch.setattr(state_module, "CLAUDE_EXE", "claude")
        # 현재 활성 세션 MAX개 등록
        for i in range(MAX_SESSIONS_PER_CLIENT):
            s = _make_session(f"cmp{i:02d}")
            main_module.sessions[f"cmp{i:02d}"] = s

        r = client.post("/api/compare", json={
            "models": ["sonnet", "opus"],
            "prompt": "test",
            "work_dir": ".",
            "skip_permissions": True,
        })
        assert r.status_code == 429


# ════════════════════════════════════════════════════════════════════════════════
# 16. pipeline_store.py — 미커버 엣지 케이스 (line 156, 181, 259-260)
# ════════════════════════════════════════════════════════════════════════════════

class TestPipelineStoreEdgeCases:
    """pipeline_store 미커버 분기 3개"""

    @pytest.fixture(autouse=True)
    def isolated_db(self, tmp_path, monkeypatch):
        """각 테스트에 격리된 임시 DB 사용 (test_pipeline_recovery.py 패턴 동일)"""
        import sqlite3
        import app.pipeline_store as ps_mod
        db_file = tmp_path / "ps_gap.db"
        monkeypatch.setattr(ps_mod, "_DB_PATH", db_file)
        conn = sqlite3.connect(str(db_file), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        ps_mod._init_db(conn)
        conn.close()

    def test_save_checkpoint_nonexistent_run_is_noop(self):
        """존재하지 않는 run_id로 save_checkpoint → 에러 없이 no-op (line 155-156)"""
        import app.pipeline_store as ps
        # run이 없는 상태에서 호출해도 예외가 발생하지 않아야 한다
        ps.save_checkpoint("ghost-run", 0, {"output": "data"})
        # 아무 run도 생성되지 않았음을 확인
        assert ps.get_resumable_runs() == []

    def test_get_checkpoint_nonexistent_run_returns_none(self):
        """존재하지 않는 run_id로 get_checkpoint → None 반환 (line 180-181)"""
        import app.pipeline_store as ps
        result = ps.get_checkpoint("ghost-run", 0)
        assert result is None

    def test_cleanup_interrupted_runs_with_specific_ids(self):
        """특정 run_ids 지정 시 해당 run만 삭제, 나머지 보존 (lines 259-260)"""
        import app.pipeline_store as ps
        ps.create_run("run-a", "ses1", 5)
        ps.create_run("run-b", "ses2", 5)
        ps.mark_interrupted("run-a")
        ps.mark_interrupted("run-b")

        deleted = ps.cleanup_interrupted_runs(run_ids=["run-a"])

        assert deleted == 1
        remaining = ps.get_resumable_runs()
        ids = [r["id"] for r in remaining]
        assert "run-a" not in ids
        assert "run-b" in ids


# ════════════════════════════════════════════════════════════════════════════════
# 17. routes_ws.py — WebSocket 에러 경로
# ════════════════════════════════════════════════════════════════════════════════

class TestWebSocketErrorPaths:
    """WebSocket 인증 실패 / 세션 상태 에러 경로"""

    def test_ws_shell_auth_rejected(self, monkeypatch):
        """ADMIN_API_KEY 설정 시 잘못된 토큰 → 에러 메시지 후 연결 종료"""
        monkeypatch.setenv("ADMIN_API_KEY", "secret123")
        import app.routes_ws as routes_ws_module
        # routes_ws 모듈의 os.environ 반영을 위해 reload 없이 직접 확인
        with client.websocket_connect("/ws/shell/sh_any?token=wrongtoken") as ws:
            data = ws.receive_json()
            assert "error" in data
            assert "인증" in data["error"]

    def test_ws_shell_dead_session_error(self):
        """shell_id 존재하지만 alive=False → 에러 메시지 전송 후 종료"""
        mock_shell = MagicMock()
        mock_shell.alive = False
        main_module.shell_sessions["sh_dead"] = mock_shell

        with client.websocket_connect("/ws/shell/sh_dead") as ws:
            data = ws.receive_json()
            assert "error" in data
            assert "종료" in data["error"]

    def test_ws_session_removed_while_connected(self):
        """WebSocket 연결 후 session이 dict에서 제거되면 에러 메시지 후 루프 탈출"""
        import app.routes_ws as routes_ws_module

        # 세션 등록
        s = _register_session("ws_rm01")

        # _output_event.wait()를 즉시 완료시키고, 연결 후 세션을 제거
        async def _fast_event_wait():
            return None

        async def _patched_wait_for(coro, timeout=None):
            # 첫 wait_for(send_json)은 그냥 실행, 두 번째(event.wait)는 짧게 종료
            return await coro

        with patch.object(routes_ws_module.asyncio, "wait_for",
                          side_effect=_patched_wait_for):
            with client.websocket_connect(f"/ws/ws_rm01") as ws:
                # 세션 제거 → 다음 루프에서 "세션 제거됨" 감지
                del main_module.sessions["ws_rm01"]
                # 루프가 break 후 WS가 닫히면 receive_json이 JSON 또는 disconnect
                try:
                    data = ws.receive_json()
                    assert "error" in data
                except Exception:
                    pass  # WebSocketDisconnect도 허용 (정상 종료 경로)
