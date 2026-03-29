"""
tests/test_pipeline_report.py

Pipeline Final Report, Pending Items, Stop 기능 테스트.

Coverage:
  - app/pipeline.py: PipelineRunner._log_step, _collect_pending_question,
    _record_auto_decision, _generate_report, _generate_text_summary
  - app/pipeline.py: stop(stop_type="hard"|"soft"), _soft_stop_flag
  - app/pipeline.py: started_at / ended_at 필드
  - app/routes_api.py: POST /pipelines/{id}/stop (stop_type body)
  - app/models.py: PipelineStopRequest

실행:
    .venv/Scripts/pytest tests/test_pipeline_report.py -v
"""
import asyncio
import time
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import sessions, pipelines
from app.models import PipelineStopRequest, LOGS_DIR
from app.pipeline import PipelineRunner
from app.session import ClaudeSession

client = TestClient(app=main_module.app, raise_server_exceptions=True)


# ════════════════════════════════════════════════════════════════════════════════
# 공통 픽스처
# ════════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def reset_state():
    main_module._session_create_log.clear()
    sessions.clear()
    pipelines.clear()
    yield
    main_module._session_create_log.clear()
    sessions.clear()
    pipelines.clear()


def _make_session(sid="s1") -> ClaudeSession:
    s = ClaudeSession(sid, ".", "sonnet")
    return s


def _make_runner(sid="s1", goal="test goal") -> tuple[PipelineRunner, ClaudeSession]:
    s = _make_session(sid)
    r = PipelineRunner(s, goal, supervisor_model="sonnet",
                       max_iterations=5, mode="api", max_cycles=3)
    return r, s


# ════════════════════════════════════════════════════════════════════════════════
# PipelineStopRequest 모델
# ════════════════════════════════════════════════════════════════════════════════

class TestPipelineStopRequest:
    def test_default_stop_type_is_hard(self):
        req = PipelineStopRequest()
        assert req.stop_type == "hard"

    def test_soft_accepted(self):
        req = PipelineStopRequest(stop_type="soft")
        assert req.stop_type == "soft"

    def test_invalid_stop_type_rejected(self):
        with pytest.raises(Exception):
            PipelineStopRequest(stop_type="force")


# ════════════════════════════════════════════════════════════════════════════════
# PipelineRunner 초기화 필드
# ════════════════════════════════════════════════════════════════════════════════

class TestPipelineRunnerNewFields:
    def test_initial_fields_present(self):
        r, _ = _make_runner()
        assert r.started_at == ""
        assert r.ended_at is None
        assert r.stop_type is None
        assert r._soft_stop_flag is False
        assert r._step_log == []
        assert r.report is None
        assert "questions" in r.pending_items
        assert "auto_decisions" in r.pending_items
        assert "suggestions" in r.pending_items

    def test_pending_items_empty_initially(self):
        r, _ = _make_runner()
        assert r.pending_items["questions"] == []
        assert r.pending_items["auto_decisions"] == []
        assert r.pending_items["suggestions"] == []


# ════════════════════════════════════════════════════════════════════════════════
# _log_step
# ════════════════════════════════════════════════════════════════════════════════

class TestLogStep:
    def test_completed_step_recorded(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        start = time.time()
        r._log_step(1, "completed", "output text", start=start)
        assert len(r._step_log) == 1
        step = r._step_log[0]
        assert step["step_idx"] == 1
        assert step["status"] == "completed"
        assert step["cycle"] == 1
        assert step["iteration"] == 1
        assert step["duration_seconds"] >= 0
        assert step["output_preview"] == "output text"
        assert step["error"] is None

    def test_failed_step_records_error(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 2
        start = time.time()
        r._log_step(2, "failed", "", start=start, error="something went wrong")
        step = r._step_log[0]
        assert step["status"] == "failed"
        assert step["error"] == "something went wrong"

    def test_aborted_step_recorded(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._log_step(1, "aborted", "[파이프라인 중단됨]", start=time.time())
        assert r._step_log[0]["status"] == "aborted"

    def test_output_preview_truncated_at_200(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        long_output = "x" * 500
        r._log_step(1, "completed", long_output, start=time.time())
        assert len(r._step_log[0]["output_preview"]) <= 200

    def test_multiple_steps_accumulate(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        for i in range(1, 4):
            r.iteration = i
            r._log_step(i, "completed", f"output {i}", start=time.time())
        assert len(r._step_log) == 3
        assert [s["step_idx"] for s in r._step_log] == [1, 2, 3]

    def test_started_at_and_ended_at_iso_format(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        start = time.time()
        r._log_step(1, "completed", "ok", start=start)
        step = r._step_log[0]
        # Should be parseable ISO timestamps
        datetime.fromisoformat(step["started_at"])
        datetime.fromisoformat(step["ended_at"])


# ════════════════════════════════════════════════════════════════════════════════
# _collect_pending_question
# ════════════════════════════════════════════════════════════════════════════════

class TestCollectPendingQuestion:
    def test_no_pending_question_noop(self):
        r, s = _make_runner()
        s.pending_question = None
        r.current_cycle = 1
        r.iteration = 1
        r._collect_pending_question(1)
        assert r.pending_items["questions"] == []

    def test_pending_question_collected(self):
        r, s = _make_runner()
        s.pending_question = {
            "questions": [
                {"question": "테스트 질문?", "options": [{"label": "예"}, {"label": "아니오"}]}
            ]
        }
        r.current_cycle = 1
        r.iteration = 2
        r._collect_pending_question(2)
        assert len(r.pending_items["questions"]) == 1
        q = r.pending_items["questions"][0]
        assert q["step"] == 2
        assert q["cycle"] == 1
        assert q["iteration"] == 2
        assert q["content"] == "테스트 질문?"
        assert len(q["options"]) == 2
        assert q["severity"] == "medium"
        assert "note" in q

    def test_multiple_questions_all_collected(self):
        r, s = _make_runner()
        s.pending_question = {
            "questions": [
                {"question": "Q1?", "options": []},
                {"question": "Q2?", "options": []},
            ]
        }
        r.current_cycle = 1
        r.iteration = 1
        r._collect_pending_question(1)
        assert len(r.pending_items["questions"]) == 2

    def test_empty_questions_list_noop(self):
        r, s = _make_runner()
        s.pending_question = {"questions": []}
        r.current_cycle = 1
        r.iteration = 1
        r._collect_pending_question(1)
        assert r.pending_items["questions"] == []


# ════════════════════════════════════════════════════════════════════════════════
# _record_auto_decision
# ════════════════════════════════════════════════════════════════════════════════

class TestRecordAutoDecision:
    def test_decision_recorded(self):
        r, _ = _make_runner()
        r.current_cycle = 2
        r.iteration = 3
        r._record_auto_decision(3, "사이클 1 최대 반복 도달", "사이클 2 자동 시작",
                                 severity="low")
        assert len(r.pending_items["auto_decisions"]) == 1
        d = r.pending_items["auto_decisions"][0]
        assert d["step"] == 3
        assert d["cycle"] == 2
        assert d["iteration"] == 3
        assert d["description"] == "사이클 1 최대 반복 도달"
        assert d["choice"] == "사이클 2 자동 시작"
        assert d["severity"] == "low"
        assert d["alternatives"] == []

    def test_alternatives_stored(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._record_auto_decision(1, "모델 선택", "sonnet", alternatives=["opus", "haiku"])
        d = r.pending_items["auto_decisions"][0]
        assert d["alternatives"] == ["opus", "haiku"]

    def test_medium_severity(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._record_auto_decision(1, "감독자 오류", "재생성", severity="medium")
        assert r.pending_items["auto_decisions"][0]["severity"] == "medium"


# ════════════════════════════════════════════════════════════════════════════════
# _generate_report
# ════════════════════════════════════════════════════════════════════════════════

class TestGenerateReport:
    def _build_runner_with_steps(self, status="completed") -> PipelineRunner:
        r, s = _make_runner(goal="테스트 목표")
        r.started_at = "2026-01-01T10:00:00"
        r.ended_at = "2026-01-01T10:05:00"
        r.status = status
        r.summary = "작업 완료"
        r.current_cycle = 1
        r.iteration = 2
        r._log_step(1, "completed", "첫 번째 단계 결과", start=time.time() - 10)
        r._log_step(2, "completed", "두 번째 단계 결과", start=time.time() - 5)
        return r

    def test_report_basic_structure(self):
        r = self._build_runner_with_steps()
        report = r._generate_report()
        assert report["pipeline_id"] == r.id
        assert report["session_id"] == r.session.id
        assert report["goal"] == "테스트 목표"
        assert report["status"] == "completed"
        assert report["stop_type"] is None
        assert report["started_at"] == "2026-01-01T10:00:00"
        assert report["ended_at"] == "2026-01-01T10:05:00"

    def test_report_duration_calculated(self):
        r = self._build_runner_with_steps()
        report = r._generate_report()
        assert report["duration_seconds"] == 300.0  # 5분

    def test_report_step_counts(self):
        r = self._build_runner_with_steps()
        report = r._generate_report()
        assert report["total_steps"] == 2
        assert report["completed_steps"] == 2
        assert report["failed_steps"] == 0
        assert report["aborted_steps"] == 0

    def test_report_with_failed_step(self):
        r, _ = _make_runner()
        r.started_at = datetime.now().isoformat()
        r.ended_at = datetime.now().isoformat()
        r.status = "failed"
        r.current_cycle = 1
        r.iteration = 1
        r._log_step(1, "completed", "ok", start=time.time())
        r._log_step(2, "failed", "error output", start=time.time(), error="처리 오류")
        report = r._generate_report()
        assert report["completed_steps"] == 1
        assert report["failed_steps"] == 1
        assert "처리 오류" in report["errors"]

    def test_report_with_aborted_step(self):
        r, _ = _make_runner()
        r.started_at = datetime.now().isoformat()
        r.ended_at = datetime.now().isoformat()
        r.status = "stopped"
        r.stop_type = "hard"
        r.current_cycle = 1
        r.iteration = 1
        r._log_step(1, "aborted", "[파이프라인 중단됨]", start=time.time())
        report = r._generate_report()
        assert report["aborted_steps"] == 1
        assert report["stop_type"] == "hard"

    def test_report_includes_pending_items(self):
        r = self._build_runner_with_steps()
        r.pending_items["questions"].append({
            "step": 1, "content": "확인 필요", "severity": "medium"
        })
        r.pending_items["auto_decisions"].append({
            "step": 1, "description": "자동 선택", "choice": "A"
        })
        report = r._generate_report()
        assert len(report["pending_items"]["questions"]) == 1
        assert len(report["pending_items"]["auto_decisions"]) == 1

    def test_report_includes_text_summary(self):
        r = self._build_runner_with_steps()
        report = r._generate_report()
        assert "text_summary" in report
        assert isinstance(report["text_summary"], str)
        assert len(report["text_summary"]) > 0

    def test_report_invalid_timestamps_graceful(self):
        r, _ = _make_runner()
        r.started_at = "invalid"
        r.ended_at = "also-invalid"
        r.status = "completed"
        report = r._generate_report()
        assert report["duration_seconds"] == 0.0

    def test_report_no_timestamps_graceful(self):
        r, _ = _make_runner()
        r.started_at = ""
        r.ended_at = None
        r.status = "failed"
        report = r._generate_report()
        assert report["duration_seconds"] == 0.0


# ════════════════════════════════════════════════════════════════════════════════
# _generate_text_summary
# ════════════════════════════════════════════════════════════════════════════════

class TestGenerateTextSummary:
    def test_text_summary_contains_key_info(self):
        r, _ = _make_runner(goal="테스트 목표")
        r.started_at = "2026-01-01T10:00:00"
        r.ended_at = "2026-01-01T10:02:00"
        r.status = "completed"
        r.current_cycle = 1
        r.iteration = 1
        start = time.time()
        r._log_step(1, "completed", "결과", start=start)
        text = r._generate_text_summary(r._step_log, 120.0, [])
        assert r.id in text
        assert "completed" in text
        assert "테스트 목표" in text
        assert "120" in text  # duration in seconds always present in _fmt_duration output

    def test_text_summary_stopped_with_stop_type(self):
        r, _ = _make_runner()
        r.status = "stopped"
        r.stop_type = "soft"
        text = r._generate_text_summary([], 0.0, [])
        assert "soft stop" in text

    def test_text_summary_errors_shown(self):
        r, _ = _make_runner()
        r.status = "failed"
        text = r._generate_text_summary([], 0.0, ["치명적 오류 발생"])
        assert "치명적 오류 발생" in text

    def test_text_summary_pending_items_section(self):
        r, _ = _make_runner()
        r.status = "completed"
        r.pending_items["questions"].append({
            "step": 1, "content": "확인 필요한 질문", "severity": "high", "options": []
        })
        r.pending_items["auto_decisions"].append({
            "step": 1, "description": "자동 결정", "choice": "B", "severity": "low"
        })
        text = r._generate_text_summary([], 0.0, [])
        assert "후속 조치" in text
        assert "확인 필요한 질문" in text
        assert "자동 결정" in text

    def test_text_summary_step_details(self):
        r, _ = _make_runner()
        r.status = "completed"
        r.current_cycle = 1
        r.iteration = 1
        r._log_step(1, "completed", "첫 단계 결과입니다", start=time.time())
        text = r._generate_text_summary(r._step_log, 0.0, [])
        assert "Step 1" in text
        assert "첫 단계 결과입니다" in text

    def test_long_goal_truncated_in_summary(self):
        long_goal = "A" * 200
        r, _ = _make_runner(goal=long_goal)
        r.status = "completed"
        text = r._generate_text_summary([], 0.0, [])
        # Goal is truncated to 120 chars + "..."
        assert "..." in text


# ════════════════════════════════════════════════════════════════════════════════
# stop() 메서드 동작
# ════════════════════════════════════════════════════════════════════════════════

class TestStopMethod:
    def test_hard_stop_sets_stop_flag(self):
        r, _ = _make_runner()
        asyncio.run(r.stop("hard"))
        assert r._stop_flag is True
        assert r._soft_stop_flag is False
        assert r.status == "stopped"
        assert r.stop_type == "hard"

    def test_soft_stop_sets_soft_flag_only(self):
        r, _ = _make_runner()
        asyncio.run(r.stop("soft"))
        assert r._stop_flag is False
        assert r._soft_stop_flag is True
        assert r.status != "stopped"  # status not changed by soft stop
        assert r.stop_type == "soft"

    def test_hard_stop_history_message(self):
        r, _ = _make_runner()
        asyncio.run(r.stop("hard"))
        messages = [h["content"] for h in r.history]
        assert any("Hard stop" in m or "즉시 중단" in m for m in messages)

    def test_soft_stop_history_message(self):
        r, _ = _make_runner()
        asyncio.run(r.stop("soft"))
        messages = [h["content"] for h in r.history]
        assert any("Soft stop" in m or "현재 단계 완료" in m for m in messages)

    def test_default_stop_is_hard(self):
        r, _ = _make_runner()
        asyncio.run(r.stop())
        assert r.stop_type == "hard"
        assert r._stop_flag is True


# ════════════════════════════════════════════════════════════════════════════════
# to_dict() 새 필드 포함 확인
# ════════════════════════════════════════════════════════════════════════════════

class TestToDict:
    def test_new_fields_present(self):
        r, _ = _make_runner()
        d = r.to_dict()
        assert "started_at" in d
        assert "ended_at" in d
        assert "stop_type" in d
        assert "pending_items_count" in d
        assert "report" in d

    def test_pending_items_count_structure(self):
        r, _ = _make_runner()
        r.pending_items["questions"].append({"content": "q1"})
        r.pending_items["auto_decisions"].append({"content": "d1"})
        d = r.to_dict()
        assert d["pending_items_count"]["questions"] == 1
        assert d["pending_items_count"]["auto_decisions"] == 1
        assert d["pending_items_count"]["suggestions"] == 0

    def test_report_none_before_completion(self):
        r, _ = _make_runner()
        d = r.to_dict()
        assert d["report"] is None

    def test_report_populated_after_generate(self):
        r, _ = _make_runner()
        r.started_at = datetime.now().isoformat()
        r.ended_at = datetime.now().isoformat()
        r.status = "completed"
        r.report = r._generate_report()
        d = r.to_dict()
        assert d["report"] is not None
        assert d["report"]["pipeline_id"] == r.id


# ════════════════════════════════════════════════════════════════════════════════
# HTTP 엔드포인트: POST /pipelines/{id}/stop
# ════════════════════════════════════════════════════════════════════════════════

class TestStopEndpoint:
    def _register_running_pipeline(self, pid="p1") -> PipelineRunner:
        s = _make_session(f"sess-{pid}")
        sessions[s.id] = s
        r = PipelineRunner(s, "goal", "sonnet", 5)
        r.status = "running"
        pipelines[pid] = r
        return r

    def test_hard_stop_default_no_body(self):
        r = self._register_running_pipeline()
        pid = list(pipelines.keys())[0]
        resp = client.post(f"/api/pipelines/{pid}/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"
        assert data["stop_type"] == "hard"

    def test_explicit_hard_stop(self):
        r = self._register_running_pipeline()
        pid = list(pipelines.keys())[0]
        resp = client.post(f"/api/pipelines/{pid}/stop",
                           json={"stop_type": "hard"})
        assert resp.status_code == 200
        assert resp.json()["stop_type"] == "hard"
        assert resp.json()["status"] == "stopped"

    def test_soft_stop_returns_stopping(self):
        r = self._register_running_pipeline()
        pid = list(pipelines.keys())[0]
        resp = client.post(f"/api/pipelines/{pid}/stop",
                           json={"stop_type": "soft"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["stop_type"] == "soft"
        assert data["status"] == "stopping"

    def test_soft_stop_sets_soft_flag(self):
        r = self._register_running_pipeline()
        pid = list(pipelines.keys())[0]
        client.post(f"/api/pipelines/{pid}/stop", json={"stop_type": "soft"})
        assert pipelines[pid]._soft_stop_flag is True
        assert pipelines[pid]._stop_flag is False

    def test_hard_stop_sets_hard_flag(self):
        r = self._register_running_pipeline()
        pid = list(pipelines.keys())[0]
        client.post(f"/api/pipelines/{pid}/stop", json={"stop_type": "hard"})
        assert pipelines[pid]._stop_flag is True

    def test_stop_404_for_unknown_pipeline(self):
        resp = client.post("/api/pipelines/nonexistent/stop")
        assert resp.status_code == 404

    def test_invalid_stop_type_422(self):
        r = self._register_running_pipeline()
        pid = list(pipelines.keys())[0]
        resp = client.post(f"/api/pipelines/{pid}/stop",
                           json={"stop_type": "force"})
        assert resp.status_code == 422

    def test_compat_endpoint_also_works(self):
        r = self._register_running_pipeline()
        pid = list(pipelines.keys())[0]
        resp = client.post(f"/api/pipeline/{pid}/stop",
                           json={"stop_type": "soft"})
        assert resp.status_code == 200
        assert resp.json()["stop_type"] == "soft"


# ════════════════════════════════════════════════════════════════════════════════
# report 구조 — stop 시나리오별
# ════════════════════════════════════════════════════════════════════════════════

class TestReportScenarios:
    def test_report_after_hard_stop(self):
        r, _ = _make_runner(goal="hard stop 목표")
        r.started_at = datetime.now().isoformat()
        r.current_cycle = 1
        r.iteration = 2
        r._log_step(1, "completed", "step 1 ok", start=time.time() - 5)
        r._log_step(2, "aborted", "[파이프라인 중단됨]", start=time.time())
        r.status = "stopped"
        r.stop_type = "hard"
        r.ended_at = datetime.now().isoformat()
        r.report = r._generate_report()

        assert r.report["status"] == "stopped"
        assert r.report["stop_type"] == "hard"
        assert r.report["completed_steps"] == 1
        assert r.report["aborted_steps"] == 1
        assert "text_summary" in r.report
        assert "⏹" in r.report["text_summary"]  # status icon for stopped

    def test_report_after_soft_stop(self):
        r, _ = _make_runner(goal="soft stop 목표")
        r.started_at = datetime.now().isoformat()
        r.current_cycle = 1
        r.iteration = 3
        for i in range(1, 4):
            r._log_step(i, "completed", f"step {i}", start=time.time())
        r.status = "stopped"
        r.stop_type = "soft"
        r.ended_at = datetime.now().isoformat()
        r.report = r._generate_report()

        assert r.report["completed_steps"] == 3
        assert r.report["aborted_steps"] == 0
        assert r.report["stop_type"] == "soft"
        assert "soft stop" in r.report["text_summary"]

    def test_report_after_completion(self):
        r, _ = _make_runner(goal="완료 목표")
        r.started_at = "2026-01-01T09:00:00"
        r.ended_at = "2026-01-01T09:10:00"
        r.status = "completed"
        r.summary = "모든 작업이 성공적으로 완료되었습니다"
        r.current_cycle = 1
        r.iteration = 5
        for i in range(1, 6):
            r._log_step(i, "completed", f"step {i} output", start=time.time())
        r.report = r._generate_report()

        assert r.report["status"] == "completed"
        assert r.report["completed_steps"] == 5
        assert r.report["duration_seconds"] == 600.0
        assert "완료" in r.report["text_summary"]
        assert "✅" in r.report["text_summary"]

    def test_report_after_failure(self):
        r, _ = _make_runner(goal="실패 목표")
        r.started_at = datetime.now().isoformat()
        r.ended_at = datetime.now().isoformat()
        r.status = "failed"
        r.current_cycle = 1
        r.iteration = 2
        r._log_step(1, "completed", "ok", start=time.time())
        r._log_step(2, "failed", "err", start=time.time(), error="critical error")
        r.report = r._generate_report()

        assert r.report["status"] == "failed"
        assert r.report["failed_steps"] == 1
        assert "critical error" in r.report["errors"]
        assert "❌" in r.report["text_summary"]

    def test_report_with_auto_decisions_and_questions(self):
        r, s = _make_runner(goal="복합 시나리오")
        r.started_at = datetime.now().isoformat()
        r.ended_at = datetime.now().isoformat()
        r.status = "completed"
        r.current_cycle = 2
        r.iteration = 1
        # Simulate cycle advance auto_decision
        r._record_auto_decision(5, "사이클 1 최대 반복 도달", "사이클 2 자동 시작")
        # Simulate a pending question that was collected
        s.pending_question = {
            "questions": [{"question": "어떤 파일을 삭제할까요?", "options": []}]
        }
        r._collect_pending_question(6)
        r.report = r._generate_report()

        assert len(r.report["pending_items"]["auto_decisions"]) == 1
        assert len(r.report["pending_items"]["questions"]) == 1
        assert "후속 조치" in r.report["text_summary"]
        assert "어떤 파일을 삭제할까요?" in r.report["text_summary"]


# ════════════════════════════════════════════════════════════════════════════════
# _parse_auto_decisions_from_output
# ════════════════════════════════════════════════════════════════════════════════

class TestParseAutoDecisions:
    def test_bracket_format_detected(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_auto_decisions_from_output(1, "[결정] A 방안 사용 → 파일 덮어쓰기")
        assert len(r.pending_items["auto_decisions"]) == 1
        d = r.pending_items["auto_decisions"][0]
        assert d["description"] == "A 방안 사용"
        assert d["choice"] == "파일 덮어쓰기"
        assert d["source"] == "text_pattern"

    def test_prefix_format_detected(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_auto_decisions_from_output(1, "결정: 기존 파일 삭제 후 재생성")
        assert len(r.pending_items["auto_decisions"]) == 1
        d = r.pending_items["auto_decisions"][0]
        assert "기존 파일 삭제 후 재생성" in d["description"]
        assert d["choice"] == ""

    def test_auto_selection_format(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_auto_decisions_from_output(1, "자동 선택: 최신 버전 사용")
        assert len(r.pending_items["auto_decisions"]) == 1

    def test_english_decision_format(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_auto_decisions_from_output(1, "Decision: use approach B → skip validation")
        assert len(r.pending_items["auto_decisions"]) == 1
        d = r.pending_items["auto_decisions"][0]
        assert "approach B" in d["description"]
        assert "skip validation" in d["choice"]

    def test_no_match_normal_text(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_auto_decisions_from_output(1, "일반적인 텍스트입니다. 아무 패턴도 없어요.")
        assert len(r.pending_items["auto_decisions"]) == 0

    def test_too_short_content_ignored(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_auto_decisions_from_output(1, "결정: AB")
        assert len(r.pending_items["auto_decisions"]) == 0

    def test_duplicate_not_added_twice(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        text = "[결정] 파일 삭제 → 덮어쓰기"
        r._parse_auto_decisions_from_output(1, text)
        r._parse_auto_decisions_from_output(1, text)
        assert len(r.pending_items["auto_decisions"]) == 1

    def test_multiline_text_all_parsed(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        text = "결정: 방안 A 선택\n일반 텍스트\n[결정] 버전 업그레이드 → v2.0 사용"
        r._parse_auto_decisions_from_output(1, text)
        assert len(r.pending_items["auto_decisions"]) == 2

    def test_empty_text_noop(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_auto_decisions_from_output(1, "")
        assert len(r.pending_items["auto_decisions"]) == 0


# ════════════════════════════════════════════════════════════════════════════════
# _parse_questions_from_output
# ════════════════════════════════════════════════════════════════════════════════

class TestParseQuestionsFromOutput:
    def test_confirm_needed_pattern(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_questions_from_output(1, "확인 필요: 기존 파일을 삭제할까요?")
        assert len(r.pending_items["questions"]) == 1
        q = r.pending_items["questions"][0]
        assert "기존 파일을 삭제할까요?" in q["content"]
        assert q["source"] == "text_pattern"

    def test_select_pattern(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_questions_from_output(1, "선택해 주세요: A 또는 B")
        assert len(r.pending_items["questions"]) == 1

    def test_bracket_question_format(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_questions_from_output(1, "[질문] 어떤 방식으로 진행할까요?")
        assert len(r.pending_items["questions"]) == 1

    def test_english_confirm_pattern(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_questions_from_output(1, "Please confirm: delete the old files?")
        assert len(r.pending_items["questions"]) == 1

    def test_no_match_normal_text(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_questions_from_output(1, "파일을 처리했습니다. 결과가 출력됩니다.")
        assert len(r.pending_items["questions"]) == 0

    def test_duplicate_not_added_twice(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        text = "확인 필요: 덮어쓸까요?"
        r._parse_questions_from_output(1, text)
        r._parse_questions_from_output(1, text)
        assert len(r.pending_items["questions"]) == 1

    def test_source_stored_in_note(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_questions_from_output(1, "확인 필요: 삭제할까요?", source="worker")
        assert r.pending_items["questions"][0]["source"] == "text_pattern"
        assert "worker" in r.pending_items["questions"][0]["note"]

    def test_empty_text_noop(self):
        r, _ = _make_runner()
        r.current_cycle = 1
        r.iteration = 1
        r._parse_questions_from_output(1, "")
        assert len(r.pending_items["questions"]) == 0


# ════════════════════════════════════════════════════════════════════════════════
# resume()
# ════════════════════════════════════════════════════════════════════════════════

class TestResume:
    def _make_soft_stopped(self) -> tuple:
        r, s = _make_runner()
        r.status = "stopped"
        r._soft_stop_flag = True
        r.stop_type = "soft"
        r.started_at = "2026-01-01T10:00:00"
        r.ended_at = "2026-01-01T10:05:00"
        r.current_cycle = 1
        r.iteration = 2
        r._log_step(1, "completed", "step 1", start=time.time() - 5)
        r._log_step(2, "completed", "step 2", start=time.time() - 2)
        r.report = r._generate_report()
        return r, s

    def test_resume_resets_flags(self):
        r, _ = self._make_soft_stopped()
        with patch("asyncio.create_task", side_effect=lambda coro: coro.close()):
            r.resume()
        assert r._stop_flag is False
        assert r._soft_stop_flag is False
        assert r.stop_type is None

    def test_resume_sets_running(self):
        r, _ = self._make_soft_stopped()
        with patch("asyncio.create_task", side_effect=lambda coro: coro.close()):
            r.resume()
        assert r.status == "running"

    def test_resume_clears_ended_at_and_report(self):
        r, _ = self._make_soft_stopped()
        with patch("asyncio.create_task", side_effect=lambda coro: coro.close()):
            r.resume()
        assert r.ended_at is None
        assert r.report is None

    def test_resume_preserves_step_log(self):
        r, _ = self._make_soft_stopped()
        steps_before = len(r._step_log)
        with patch("asyncio.create_task", side_effect=lambda coro: coro.close()):
            r.resume()
        assert len(r._step_log) == steps_before

    def test_resume_preserves_cycle_and_iteration(self):
        r, _ = self._make_soft_stopped()
        with patch("asyncio.create_task", side_effect=lambda coro: coro.close()):
            r.resume()
        assert r.current_cycle == 1
        assert r.iteration == 2

    def test_resume_adds_history_message(self):
        r, _ = self._make_soft_stopped()
        history_before = len(r.history)
        with patch("asyncio.create_task", side_effect=lambda coro: coro.close()):
            r.resume()
        assert len(r.history) > history_before
        assert "재개" in r.history[-1]["content"]

    def test_resume_spawns_asyncio_task(self):
        r, _ = self._make_soft_stopped()
        with patch("asyncio.create_task", side_effect=lambda coro: coro.close()) as mock_task:
            r.resume()
        mock_task.assert_called_once()

    def test_resume_fails_if_not_stopped(self):
        r, _ = _make_runner()
        r.status = "running"
        r._soft_stop_flag = True
        with pytest.raises(RuntimeError, match="stopped 상태"):
            r.resume()

    def test_resume_fails_if_hard_stop(self):
        r, _ = _make_runner()
        r.status = "stopped"
        r._soft_stop_flag = False
        with pytest.raises(RuntimeError, match="hard stop"):
            r.resume()

    def test_resume_fails_if_session_dead(self):
        r, s = self._make_soft_stopped()
        s.alive = False
        with pytest.raises(RuntimeError, match="세션이 종료"):
            r.resume()

    def test_resume_rollback_on_supervisor_failure(self):
        r, _ = self._make_soft_stopped()
        r.mode = "cli"
        with patch.object(r, "_create_supervisor_session",
                          side_effect=RuntimeError("sv fail")):
            with pytest.raises(RuntimeError, match="sv fail"):
                r.resume()
        assert r.status == "stopped"
        assert r._soft_stop_flag is True


# ════════════════════════════════════════════════════════════════════════════════
# HTTP: POST /pipelines/{id}/resume
# ════════════════════════════════════════════════════════════════════════════════

class TestResumeEndpoint:
    def _register_soft_stopped(self, pid="p-resume") -> PipelineRunner:
        s = _make_session(f"sess-{pid}")
        sessions[s.id] = s
        r = PipelineRunner(s, "goal", "sonnet", 5)
        r.status = "stopped"
        r._soft_stop_flag = True
        r.stop_type = "soft"
        r.current_cycle = 1
        r.iteration = 2
        pipelines[pid] = r
        return r

    def test_resume_success(self):
        r = self._register_soft_stopped()
        pid = list(pipelines.keys())[-1]
        with patch("asyncio.create_task", side_effect=lambda coro: coro.close()):
            resp = client.post(f"/api/pipelines/{pid}/resume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["pipeline_id"] == pid
        assert "current_cycle" in data
        assert "resumed_from_step" in data

    def test_resume_404_unknown_pipeline(self):
        resp = client.post("/api/pipelines/unknown/resume")
        assert resp.status_code == 404

    def test_resume_400_if_running(self):
        r = self._register_soft_stopped()
        pid = list(pipelines.keys())[-1]
        r.status = "running"
        resp = client.post(f"/api/pipelines/{pid}/resume")
        assert resp.status_code == 400
        assert "stopped" in resp.json()["detail"]

    def test_resume_400_if_hard_stopped(self):
        r = self._register_soft_stopped()
        pid = list(pipelines.keys())[-1]
        r._soft_stop_flag = False
        resp = client.post(f"/api/pipelines/{pid}/resume")
        assert resp.status_code == 400
        assert "hard stop" in resp.json()["detail"]

    def test_resume_400_if_session_dead(self):
        r = self._register_soft_stopped()
        pid = list(pipelines.keys())[-1]
        r.session.alive = False
        resp = client.post(f"/api/pipelines/{pid}/resume")
        assert resp.status_code == 400
        assert "세션" in resp.json()["detail"]

    def test_resume_step_log_preserved_in_response(self):
        r = self._register_soft_stopped()
        pid = list(pipelines.keys())[-1]
        r._log_step(1, "completed", "step 1", start=time.time())
        r._log_step(2, "completed", "step 2", start=time.time())
        with patch("asyncio.create_task", side_effect=lambda coro: coro.close()):
            resp = client.post(f"/api/pipelines/{pid}/resume")
        assert resp.json()["resumed_from_step"] == 2
        assert len(pipelines[pid]._step_log) == 2


# ════════════════════════════════════════════════════════════════════════════════
# 리포트 로그 파일 저장 (_save_report_log / GET /logs)
# ════════════════════════════════════════════════════════════════════════════════

class TestSaveReportLog:
    def test_save_creates_txt_file(self, tmp_path):
        r, _ = _make_runner()
        r.status = "completed"
        r.started_at = datetime.now().isoformat()
        r.ended_at = datetime.now().isoformat()
        with patch("app.pipeline.LOGS_DIR", tmp_path):
            r._save_report_log("## 테스트 리포트\n내용입니다.")
        files = list(tmp_path.glob("pipeline_*.txt"))
        assert len(files) == 1

    def test_save_filename_format(self, tmp_path):
        r, _ = _make_runner()
        r.status = "completed"
        with patch("app.pipeline.LOGS_DIR", tmp_path):
            r._save_report_log("content")
        f = next(tmp_path.glob("pipeline_*.txt"))
        assert f.name.startswith(f"pipeline_{r.id}_")
        assert f.name.endswith(".txt")

    def test_save_file_content(self, tmp_path):
        r, _ = _make_runner()
        r.status = "completed"
        expected = "## 리포트\n- 항목 1\n- 항목 2"
        with patch("app.pipeline.LOGS_DIR", tmp_path):
            r._save_report_log(expected)
        f = next(tmp_path.glob("pipeline_*.txt"))
        assert f.read_text(encoding="utf-8") == expected

    def test_save_creates_logs_dir_if_missing(self, tmp_path):
        r, _ = _make_runner()
        missing_dir = tmp_path / "new_logs"
        assert not missing_dir.exists()
        with patch("app.pipeline.LOGS_DIR", missing_dir):
            r._save_report_log("test")
        assert missing_dir.exists()

    def test_save_error_does_not_raise(self, tmp_path):
        r, _ = _make_runner()
        # 저장 실패 시 예외가 전파되지 않아야 함
        with patch("app.pipeline.LOGS_DIR", Path("/nonexistent/readonly/path")):
            r._save_report_log("content")  # no exception

    def test_generate_report_triggers_save(self, tmp_path):
        r, _ = _make_runner()
        r.status = "completed"
        r.started_at = datetime.now().isoformat()
        r.ended_at = datetime.now().isoformat()
        with patch("app.pipeline.LOGS_DIR", tmp_path):
            r._generate_report()
        assert len(list(tmp_path.glob("pipeline_*.txt"))) == 1


class TestLogsEndpointIncludesTxt:
    def test_list_logs_includes_txt_files(self, tmp_path):
        (tmp_path / "pipeline_abc_20260329_120000.txt").write_text("report", encoding="utf-8")
        (tmp_path / "session.log").write_text("log", encoding="utf-8")
        with patch("app.routes_api.LOGS_DIR", tmp_path):
            resp = client.get("/api/logs")
        assert resp.status_code == 200
        names = [e["filename"] for e in resp.json()]
        assert "pipeline_abc_20260329_120000.txt" in names
        assert "session.log" in names

    def test_get_log_serves_txt_file(self, tmp_path):
        content = "# Pipeline 리포트\n**목표:** 테스트"
        (tmp_path / "pipeline_abc_20260329_120000.txt").write_text(content, encoding="utf-8")
        with patch("app.routes_api.LOGS_DIR", tmp_path):
            resp = client.get("/api/logs/pipeline_abc_20260329_120000.txt")
        assert resp.status_code == 200
        assert resp.json()["content"] == content
