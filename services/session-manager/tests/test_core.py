"""
tests/test_core.py

session-manager 핵심 로직 단위 테스트:
  1. git_clone 경로 검증 (P1-B 보안 버그 회귀 방지)
  2. git status --porcelain 파싱 (P2-B off-by-one 회귀 방지)
  3. _check_rate_limit (분당 생성 수 / 활성 세션 수 제한)
  4. PlanPhase._parse_questions_json (LLM 응답 JSON 파싱)
  5. work_dir "~" 확장 회귀 (Bug 2)
  6. CLAUDE_EXE None 가드 회귀 (Bug 3)
  7. git_clone 빈 repo_name 회귀 (Bug 4)
  8. ShellSession get_running_loop 회귀 (Bug 1)
  9. ClaudeSession 기본 동작 경계값
  10. load_projects / save_projects 유틸리티
  11. PipelineRunner.start() supervisor 실패 시 롤백 (Bug B)
  12. PlanPhase.approve() runner.start() 실패 시 pipelines 고아 방지 (Bug A)

실행:
    .venv/Scripts/pytest tests/test_core.py -v
"""
import asyncio
import json
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import (
    _check_rate_limit,
    MAX_SESSION_CREATES_PER_MINUTE,
    MAX_SESSIONS_PER_CLIENT,
    PlanPhase,
    PipelineRunner,
    ClaudeSession,
    ShellSession,
    load_projects,
    save_projects,
)

# ── TestClient (lifespan 미실행 — startup/shutdown 훅 없이 엔드포인트 직접 호출) ──
client = TestClient(app=main_module.app, raise_server_exceptions=True)


# ════════════════════════════════════════════════════════════════════════════════
# 공통 픽스처
# ════════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def reset_global_state():
    """각 테스트 전후 모든 전역 상태 초기화 (순서 독립성 보장)"""
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


# ════════════════════════════════════════════════════════════════════════════════
# 1. git_clone 경로 검증 (P1-B)
#
# 검증 순서 (main.py git_clone):
#   1) URL 프로토콜 체크 → 400
#   2) 셸 메타문자 체크 → 400
#   3) dest Path.resolve() + is_relative_to(allowed_roots) → 400
# 검증 오류는 subprocess 실행 전에 발생하므로 mock 불필요.
# ════════════════════════════════════════════════════════════════════════════════

class TestGitCloneUrlValidation:

    def test_http_protocol_is_blocked(self):
        """http:// URL은 차단되어야 한다 (https만 허용)"""
        r = client.post("/api/git/clone", json={"url": "http://github.com/foo/bar"})
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert "URL 프로토콜" in r.json()["detail"], r.json()

    def test_file_protocol_is_blocked(self):
        """file:// URL은 차단되어야 한다"""
        r = client.post("/api/git/clone", json={"url": "file:///etc/passwd"})
        assert r.status_code == 400
        assert "URL 프로토콜" in r.json()["detail"]

    def test_ftp_protocol_is_blocked(self):
        """ftp:// URL은 차단되어야 한다"""
        r = client.post("/api/git/clone", json={"url": "ftp://example.com/repo"})
        assert r.status_code == 400
        assert "URL 프로토콜" in r.json()["detail"]

    def test_shell_semicolon_in_url_is_blocked(self):
        """URL에 세미콜론 포함 시 command injection 차단"""
        r = client.post("/api/git/clone", json={
            "url": "https://github.com/foo/bar;rm -rf /"
        })
        assert r.status_code == 400
        assert "허용되지 않은 문자" in r.json()["detail"]

    def test_shell_pipe_in_url_is_blocked(self):
        """URL에 파이프(|) 포함 시 차단"""
        r = client.post("/api/git/clone", json={
            "url": "https://github.com/foo/bar|evil_cmd"
        })
        assert r.status_code == 400
        assert "허용되지 않은 문자" in r.json()["detail"]

    def test_shell_ampersand_in_url_is_blocked(self):
        """URL에 & 포함 시 차단"""
        r = client.post("/api/git/clone", json={
            "url": "https://github.com/foo/bar&background_cmd"
        })
        assert r.status_code == 400
        assert "허용되지 않은 문자" in r.json()["detail"]

    def test_shell_backtick_in_url_is_blocked(self):
        """URL에 백틱(`) 포함 시 차단"""
        r = client.post("/api/git/clone", json={
            "url": "https://github.com/foo/bar`id`"
        })
        assert r.status_code == 400
        assert "허용되지 않은 문자" in r.json()["detail"]

    def test_newline_in_url_is_blocked(self):
        """URL에 개행 포함 시 차단"""
        r = client.post("/api/git/clone", json={
            "url": "https://github.com/foo/bar\nmalicious"
        })
        assert r.status_code == 400
        assert "허용되지 않은 문자" in r.json()["detail"]

    def test_git_at_url_passes_protocol_check(self):
        """git@ URL은 프로토콜 검증을 통과해야 한다 — 메타문자 없는 경우"""
        # dest를 forbidden 경로로 줘서 subprocess 전에 종료 (path 검증 에러 기대)
        # 프로토콜 에러가 아닌 다른 에러(path 또는 subprocess 실패)가 나야 함
        forbidden_dest = str(Path.home().parent / "test_git_at")
        r = client.post("/api/git/clone", json={
            "url": "git@github.com:user/repo.git",
            "dest": forbidden_dest,
        })
        # 프로토콜 오류가 아님을 확인 (path 오류 또는 subprocess 오류여야 함)
        detail = r.json().get("detail", "")
        assert "URL 프로토콜" not in detail, \
            "git@ URL should pass protocol check, but got protocol error"

    def test_https_url_passes_protocol_check(self):
        """https:// URL은 프로토콜 검증을 통과해야 한다"""
        forbidden_dest = str(Path.home().parent / "test_https_check")
        r = client.post("/api/git/clone", json={
            "url": "https://github.com/foo/bar",
            "dest": forbidden_dest,
        })
        detail = r.json().get("detail", "")
        assert "URL 프로토콜" not in detail, \
            "https:// URL should pass protocol check"


class TestGitCloneDestValidation:

    # 허용 루트 계산 (테스트 클래스 레벨에서 한 번만 계산)
    _home = Path.home()
    _project_root = main_module.APP_DIR.parent.parent

    def _is_forbidden(self, path: Path) -> bool:
        """path가 허용 루트 밖인지 확인 (검증 로직과 동일)"""
        return not (
            path.is_relative_to(self._home) or
            path.is_relative_to(self._project_root)
        )

    def test_dest_above_home_is_blocked(self):
        """홈 디렉토리 상위 경로는 차단되어야 한다"""
        candidate = self._home.parent / "injected_repo"
        if not self._is_forbidden(candidate):
            pytest.skip("test environment: home.parent is inside an allowed root")

        r = client.post("/api/git/clone", json={
            "url": "https://github.com/foo/bar",
            "dest": str(candidate),
        })
        assert r.status_code == 400, \
            f"path {candidate} should be blocked, got {r.status_code}: {r.text}"
        assert "허용되지 않는 대상 경로" in r.json()["detail"]

    def test_dest_dotdot_traversal_is_blocked(self):
        """../../ traversal로 홈 상위 탈출 시도는 차단되어야 한다"""
        # C:\Users\saos3\..\..\etc\shadow → C:\etc\shadow
        traversal = str(self._home / ".." / ".." / "etc" / "shadow")
        resolved = Path(traversal).resolve()

        if not self._is_forbidden(resolved):
            pytest.skip("traversal resolves inside an allowed root in this environment")

        r = client.post("/api/git/clone", json={
            "url": "https://github.com/foo/bar",
            "dest": traversal,
        })
        assert r.status_code == 400
        assert "허용되지 않는 대상 경로" in r.json()["detail"]

    def test_dest_under_home_passes_path_check(self):
        """홈 하위 경로는 경로 검증을 통과해야 한다 (subprocess mock)"""
        allowed_dest = str(self._home / "test_clone_allowed_path")

        # subprocess를 mock하여 실제 git 실행 방지
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"Cloning into..."))
        mock_proc.returncode = 0
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            r = client.post("/api/git/clone", json={
                "url": "https://github.com/foo/bar",
                "dest": allowed_dest,
            })

        # 경로 검증 오류가 아님을 확인
        detail = r.json().get("detail", "")
        assert "허용되지 않는 대상 경로" not in detail, \
            f"path under home should pass, but got: {detail}"
        assert r.status_code in (200, 400), r.text  # 200 또는 "이미 존재" 400은 허용

    def test_dest_under_project_root_passes_path_check(self):
        """프로젝트 루트 하위 경로는 경로 검증을 통과해야 한다 (subprocess mock)"""
        allowed_dest = str(self._project_root / "test_clone_proj_path")

        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            r = client.post("/api/git/clone", json={
                "url": "https://github.com/foo/bar",
                "dest": allowed_dest,
            })

        detail = r.json().get("detail", "")
        assert "허용되지 않는 대상 경로" not in detail, \
            f"path under project root should pass, but got: {detail}"


# ════════════════════════════════════════════════════════════════════════════════
# 2. git status --porcelain 파싱 (P2-B)
#
# 실제 엔드포인트는 asyncio.gather로 git 실행 — 여기서는 파싱 로직만 분리 테스트.
# main.py의 파싱 로직을 그대로 복제하여 off-by-one 조건(len >= 4)을 검증한다.
# ════════════════════════════════════════════════════════════════════════════════

def _parse_porcelain(stdout: str) -> list[dict]:
    """main.py git_status()의 파싱 로직 (테스트용 복제)"""
    files = []
    if stdout:
        for line in stdout.splitlines():
            if len(line) >= 4:          # P2-B: 이전에는 >= 3 이었음
                xy = line[:2]
                fname = line[3:]
                files.append({"status": xy.strip(), "file": fname})
    return files


class TestGitStatusParsing:

    def test_modified_file(self):
        """ M file.py → status='M', file='file.py'"""
        result = _parse_porcelain(" M file.py")
        assert len(result) == 1
        assert result[0] == {"status": "M", "file": "file.py"}

    def test_staged_new_file(self):
        """A  new.py → status='A', file='new.py'"""
        result = _parse_porcelain("A  new.py")
        assert len(result) == 1
        assert result[0]["status"] == "A"
        assert result[0]["file"] == "new.py"

    def test_deleted_file(self):
        """D  deleted.py"""
        result = _parse_porcelain("D  deleted.py")
        assert result[0]["status"] == "D"

    def test_untracked_file(self):
        """?? untracked.py"""
        result = _parse_porcelain("?? untracked.py")
        assert result[0]["status"] == "??"
        assert result[0]["file"] == "untracked.py"

    def test_file_with_spaces_in_name(self):
        """파일명에 공백이 포함된 경우"""
        result = _parse_porcelain(" M my file with spaces.py")
        assert len(result) == 1
        assert result[0]["file"] == "my file with spaces.py"

    def test_empty_output(self):
        """빈 출력 — 파일 없음"""
        assert _parse_porcelain("") == []

    def test_empty_lines_ignored(self):
        """빈 줄은 무시되어야 한다 (len < 4)"""
        stdout = " M file.py\n\n?? other.py\n"
        result = _parse_porcelain(stdout)
        assert len(result) == 2, f"empty lines should be ignored, got {result}"

    def test_line_of_exactly_3_chars_is_ignored(self):
        """len == 3인 줄은 무시 (P2-B 핵심: 이전 버그에서 파싱됐던 케이스)"""
        # "XY\n" → split 후 "XY " (3자) — 파일명이 공백이 되는 버그
        line_3 = "XY "   # exactly 3 chars, no filename
        result = _parse_porcelain(line_3)
        assert result == [], \
            f"line with len==3 should be ignored, but got: {result}"

    def test_line_of_exactly_4_chars_is_parsed(self):
        """len == 4인 줄은 파싱 (경계값: 파일명 1글자)"""
        line_4 = "XY f"  # xy="XY", sep=" ", fname="f"
        result = _parse_porcelain(line_4)
        assert len(result) == 1
        assert result[0]["file"] == "f"

    def test_multiple_files(self):
        """여러 파일 동시 파싱"""
        stdout = " M src/main.py\nA  tests/test_foo.py\n?? docs/README.md"
        result = _parse_porcelain(stdout)
        assert len(result) == 3
        assert result[0]["file"] == "src/main.py"
        assert result[1]["file"] == "tests/test_foo.py"
        assert result[2]["file"] == "docs/README.md"

    def test_rename_with_arrow(self):
        """이름 변경: R  old.py -> new.py"""
        result = _parse_porcelain("R  old.py -> new.py")
        assert len(result) == 1
        assert result[0]["file"] == "old.py -> new.py"
        assert result[0]["status"] == "R"


# ════════════════════════════════════════════════════════════════════════════════
# 3. _check_rate_limit
#
# _session_create_log 및 sessions 전역 딕셔너리를 직접 조작.
# time.time을 monkeypatch로 제어하여 시간 의존 로직 검증.
# ════════════════════════════════════════════════════════════════════════════════

class TestCheckRateLimit:
    """_check_rate_limit(client_ip) 테스트

    제한 조건:
      1) 분당 MAX_SESSION_CREATES_PER_MINUTE(=10)회 이상 생성 시 429
      2) 활성 세션(alive=True) 수 >= MAX_SESSIONS_PER_CLIENT(=10) 시 429
    """

    def test_first_call_succeeds(self):
        """첫 번째 호출은 통과해야 한다"""
        _check_rate_limit("1.2.3.4")  # 예외 없으면 통과
        assert "1.2.3.4" in main_module._session_create_log

    def test_timestamp_recorded_after_call(self):
        """성공적인 호출 후 타임스탬프가 기록되어야 한다"""
        before = time.time()
        _check_rate_limit("1.2.3.4")
        after = time.time()
        ts_list = main_module._session_create_log["1.2.3.4"]
        assert len(ts_list) == 1
        assert before <= ts_list[0] <= after

    def test_under_per_minute_limit_succeeds(self, monkeypatch):
        """분당 제한 미만 호출은 모두 통과해야 한다"""
        t = time.time()
        monkeypatch.setattr(main_module.time, "time", lambda: t)
        for i in range(MAX_SESSION_CREATES_PER_MINUTE - 1):
            _check_rate_limit("1.2.3.4")  # 9번 — 모두 통과

    def test_at_per_minute_limit_raises(self, monkeypatch):
        """분당 제한 도달 시 HTTPException(429) 발생"""
        t = time.time()
        monkeypatch.setattr(main_module.time, "time", lambda: t)
        # 제한치만큼 미리 채우기
        main_module._session_create_log["1.2.3.4"] = [t] * MAX_SESSION_CREATES_PER_MINUTE
        with pytest.raises(HTTPException) as exc:
            _check_rate_limit("1.2.3.4")
        assert exc.value.status_code == 429
        assert "분당" in exc.value.detail

    def test_window_expiry_resets_count(self, monkeypatch):
        """1분 윈도우 만료 후 카운트가 리셋되어 호출이 통과해야 한다"""
        now = time.time()
        # 61초 전 타임스탬프 — 모두 만료됨
        old_timestamps = [now - 61] * MAX_SESSION_CREATES_PER_MINUTE
        main_module._session_create_log["1.2.3.4"] = old_timestamps

        monkeypatch.setattr(main_module.time, "time", lambda: now)
        _check_rate_limit("1.2.3.4")  # 예외 없이 통과해야 함

        # 만료된 타임스탬프는 제거되고 현재 타임스탬프 1개만 남아야 한다
        remaining = main_module._session_create_log["1.2.3.4"]
        assert len(remaining) == 1, f"expired timestamps should be purged, got {remaining}"

    def test_different_ips_are_independent(self, monkeypatch):
        """IP별로 독립적인 카운터를 가진다"""
        t = time.time()
        monkeypatch.setattr(main_module.time, "time", lambda: t)
        # IP A를 제한치까지 채우기
        main_module._session_create_log["10.0.0.1"] = [t] * MAX_SESSION_CREATES_PER_MINUTE
        # IP B는 별도 카운터 — 통과해야 한다
        _check_rate_limit("10.0.0.2")  # 예외 없으면 통과

    def test_active_session_limit_raises(self):
        """활성 세션 수 >= MAX 시 HTTPException(429) 발생"""
        # 살아있는 세션 MAX개 생성
        for i in range(MAX_SESSIONS_PER_CLIENT):
            mock_session = MagicMock()
            mock_session.alive = True
            main_module.sessions[f"s{i}"] = mock_session

        with pytest.raises(HTTPException) as exc:
            _check_rate_limit("1.2.3.4")
        assert exc.value.status_code == 429
        assert "활성 세션" in exc.value.detail

    def test_dead_sessions_not_counted(self):
        """alive=False 세션은 활성 카운트에 포함되지 않는다"""
        # MAX개의 죽은 세션
        for i in range(MAX_SESSIONS_PER_CLIENT):
            mock_session = MagicMock()
            mock_session.alive = False
            main_module.sessions[f"dead{i}"] = mock_session

        _check_rate_limit("1.2.3.4")  # 예외 없이 통과해야 한다

    def test_mixed_sessions_counted_correctly(self):
        """alive=True인 세션만 카운트 — MAX - 1개 alive이면 통과"""
        for i in range(MAX_SESSIONS_PER_CLIENT - 1):
            mock_session = MagicMock()
            mock_session.alive = True
            main_module.sessions[f"alive{i}"] = mock_session
        # 죽은 세션 다수 추가 — 카운트에 영향 없어야 함
        for i in range(5):
            mock_session = MagicMock()
            mock_session.alive = False
            main_module.sessions[f"dead{i}"] = mock_session

        _check_rate_limit("1.2.3.4")  # MAX - 1 alive → 통과해야 함


# ════════════════════════════════════════════════════════════════════════════════
# 4. PlanPhase._parse_questions_json
#
# self를 사용하지 않는 메서드이므로 object.__new__(PlanPhase)로 인스턴스 생성.
# ════════════════════════════════════════════════════════════════════════════════

def _make_phase() -> PlanPhase:
    """PlanPhase 인스턴스를 __init__ 없이 생성 (source_session 불필요)"""
    phase = object.__new__(PlanPhase)
    return phase


def _make_questions_payload(questions: list[dict]) -> str:
    """테스트용 질문 JSON 페이로드 생성"""
    return json.dumps({"questions": questions})


class TestParseQuestionsJson:

    def setup_method(self):
        self.phase = _make_phase()

    def test_valid_json_parsed_correctly(self):
        """정상 JSON에서 질문 목록을 파싱해야 한다"""
        payload = _make_questions_payload([
            {"id": "q1", "question": "어떤 언어?", "why": "기술 선택", "options": []},
            {"id": "q2", "question": "테스트 필요?", "why": "품질", "options": []},
        ])
        result = self.phase._parse_questions_json(payload)
        assert len(result) == 2
        assert result[0]["id"] == "q1"
        assert result[0]["question"] == "어떤 언어?"
        assert result[1]["id"] == "q2"

    def test_code_fence_json_is_unwrapped(self):
        """```json ... ``` 코드 펜스로 감싸진 JSON도 파싱해야 한다"""
        inner = _make_questions_payload([
            {"id": "q1", "question": "테스트 질문", "why": "이유", "options": []}
        ])
        fenced = f"```json\n{inner}\n```"
        result = self.phase._parse_questions_json(fenced)
        assert len(result) == 1
        assert result[0]["question"] == "테스트 질문"

    def test_plain_code_fence_without_language_tag(self):
        """``` (언어 태그 없는) 코드 펜스도 처리해야 한다"""
        inner = _make_questions_payload([
            {"id": "q1", "question": "Q1", "why": "", "options": []}
        ])
        fenced = f"```\n{inner}\n```"
        result = self.phase._parse_questions_json(fenced)
        assert len(result) == 1

    def test_default_fields_set_when_missing(self):
        """id, why, options 필드 누락 시 기본값으로 채워져야 한다"""
        payload = json.dumps({"questions": [
            {"question": "필드 없는 질문"}  # id, why, options 누락
        ]})
        result = self.phase._parse_questions_json(payload)
        assert result[0]["id"] == "q1"    # 자동 생성
        assert result[0]["why"] == ""     # 기본값
        assert result[0]["options"] == [] # 기본값

    def test_question_field_defaults_to_empty_string(self):
        """question 필드 누락 시 빈 문자열로 채워져야 한다"""
        payload = json.dumps({"questions": [{"id": "q1"}]})
        result = self.phase._parse_questions_json(payload)
        assert result[0]["question"] == ""

    def test_id_auto_increments(self):
        """id 누락 시 q1, q2, q3 ... 순서로 자동 생성"""
        payload = json.dumps({"questions": [
            {"question": "첫 번째"},
            {"question": "두 번째"},
            {"question": "세 번째"},
        ]})
        result = self.phase._parse_questions_json(payload)
        assert result[0]["id"] == "q1"
        assert result[1]["id"] == "q2"
        assert result[2]["id"] == "q3"

    def test_empty_questions_list(self):
        """questions 배열이 비어있으면 빈 리스트 반환"""
        payload = json.dumps({"questions": []})
        result = self.phase._parse_questions_json(payload)
        assert result == []

    def test_json_embedded_in_prose(self):
        """앞뒤 산문 텍스트 안에 JSON이 있는 경우도 파싱 (fallback 경로)"""
        inner = _make_questions_payload([
            {"id": "q1", "question": "임베디드 질문", "why": "", "options": []}
        ])
        prose_wrapped = f"네, 다음 JSON을 제공합니다:\n{inner}\n감사합니다."
        result = self.phase._parse_questions_json(prose_wrapped)
        assert len(result) == 1
        assert result[0]["question"] == "임베디드 질문"

    def test_invalid_json_raises_runtime_error(self):
        """유효하지 않은 JSON은 RuntimeError를 발생시켜야 한다"""
        with pytest.raises((RuntimeError, Exception)):
            self.phase._parse_questions_json("이것은 JSON이 아닙니다")

    def test_empty_string_raises(self):
        """빈 문자열 입력 시 예외 발생"""
        with pytest.raises((RuntimeError, Exception)):
            self.phase._parse_questions_json("")

    def test_options_list_preserved(self):
        """options 목록이 있으면 원본 그대로 보존되어야 한다"""
        payload = json.dumps({"questions": [
            {
                "id": "q1",
                "question": "선택지 테스트",
                "why": "이유",
                "options": [
                    {"label": "A", "description": "옵션 A"},
                    {"label": "B", "description": "옵션 B"},
                ]
            }
        ]})
        result = self.phase._parse_questions_json(payload)
        assert len(result[0]["options"]) == 2
        assert result[0]["options"][0]["label"] == "A"


# ════════════════════════════════════════════════════════════════════════════════
# 5. work_dir "~" 확장 회귀 (Bug 2)
#
# 수정 전: work_dir="~" → cwd=None (서버 프로세스 cwd 사용)
# 수정 후: work_dir="~" → cwd=Path("~").expanduser() (홈 디렉토리)
# ════════════════════════════════════════════════════════════════════════════════

class TestWorkdirTildeExpansion:
    """_run_claude work_dir='~' 처리 회귀 테스트"""

    @staticmethod
    def _capture_cwd(work_dir: str, monkeypatch) -> dict:
        """_run_claude 실행 시 create_subprocess_exec에 전달된 cwd를 캡처한다."""
        captured: dict = {}

        async def _run():
            async def fake_exec(*args, **kwargs):
                captured["cwd"] = kwargs.get("cwd")
                raise RuntimeError("mock — subprocess 실행 불필요")

            monkeypatch.setattr(main_module, "CLAUDE_EXE", "claude")
            session = ClaudeSession(f"td{uuid.uuid4().hex[:4]}", work_dir, "")
            with patch("asyncio.create_subprocess_exec",
                       AsyncMock(side_effect=fake_exec)):
                await session._run_claude("dummy prompt")

        asyncio.run(_run())
        return captured

    def test_tilde_expands_to_home_directory(self, monkeypatch):
        """work_dir='~' → cwd가 홈 디렉토리여야 한다 (cwd=None이면 안 됨)"""
        captured = self._capture_cwd("~", monkeypatch)
        expected = str(Path("~").expanduser())
        assert captured.get("cwd") == expected, (
            f"'~' should expand to '{expected}', got '{captured.get('cwd')}'"
        )
        assert captured.get("cwd") is not None, (
            "'~' must not become cwd=None (regression: would use server process cwd)"
        )

    def test_dot_yields_none_cwd(self, monkeypatch):
        """work_dir='.' → cwd=None (서버 프로세스 현재 디렉토리 그대로 유지)"""
        captured = self._capture_cwd(".", monkeypatch)
        assert captured.get("cwd") is None, (
            f"work_dir='.' should yield cwd=None, got '{captured.get('cwd')}'"
        )

    def test_absolute_path_passed_unchanged(self, monkeypatch, tmp_path):
        """절대 경로는 그대로 cwd로 전달되어야 한다"""
        captured = self._capture_cwd(str(tmp_path), monkeypatch)
        assert captured.get("cwd") == str(tmp_path), (
            f"Absolute path should pass through unchanged, got '{captured.get('cwd')}'"
        )


# ════════════════════════════════════════════════════════════════════════════════
# 6. CLAUDE_EXE None 가드 회귀 (Bug 3)
#
# 수정 전: CLAUDE_EXE=None → cmd=[None, ...] → TypeError (미처리 예외)
# 수정 후: CLAUDE_EXE=None → error 출력 후 조용히 반환
# ════════════════════════════════════════════════════════════════════════════════

class TestClaudeExeNoneGuard:
    """_run_claude CLAUDE_EXE=None 처리 회귀 테스트"""

    def test_none_exe_appends_error_message(self, monkeypatch):
        """CLAUDE_EXE=None이면 output_lines에 error 타입 항목이 추가되어야 한다"""
        monkeypatch.setattr(main_module, "CLAUDE_EXE", None)

        async def _run():
            session = ClaudeSession("ne01", ".", "")
            await session._run_claude("test prompt")
            return session

        session = asyncio.run(_run())
        error_lines = [l for l in session.output_lines if l["type"] == "error"]
        assert len(error_lines) >= 1, "CLAUDE_EXE=None 시 에러 메시지가 출력되어야 함"
        joined = " ".join(l["text"] for l in error_lines)
        assert "Claude CLI" in joined or "CLAUDE_EXE" in joined, (
            f"에러 메시지에 'Claude CLI' 또는 'CLAUDE_EXE'가 포함되어야 함: {joined}"
        )

    def test_none_exe_does_not_raise(self, monkeypatch):
        """CLAUDE_EXE=None이면 예외 없이 정상 종료해야 한다 (TypeError 회귀 방지)"""
        monkeypatch.setattr(main_module, "CLAUDE_EXE", None)

        async def _run():
            session = ClaudeSession("ne02", ".", "")
            await session._run_claude("test prompt")  # 예외 없이 반환되면 통과

        asyncio.run(_run())  # 예외 발생 시 asyncio.run이 re-raise하여 테스트 실패

    def test_none_exe_does_not_change_busy_state(self, monkeypatch):
        """CLAUDE_EXE=None 경로는 busy 상태를 변경하지 않아야 한다
        (busy 전환은 _process_queue 레벨에서 관리)"""
        monkeypatch.setattr(main_module, "CLAUDE_EXE", None)

        async def _run():
            session = ClaudeSession("ne03", ".", "")
            assert session.busy is False
            await session._run_claude("test")
            # _run_claude 자체는 busy를 변경하지 않음 — _process_queue가 관리
            assert session.busy is False

        asyncio.run(_run())


# ════════════════════════════════════════════════════════════════════════════════
# 7. git_clone 빈 repo_name 회귀 (Bug 4)
#
# 수정 전: URL 마지막 세그먼트가 ".git"만이면 repo_name="" → dest_path=cwd (혼란)
# 수정 후: repo_name="" → HTTPException(400)
# ════════════════════════════════════════════════════════════════════════════════

class TestGitCloneEmptyRepoName:
    """git_clone 빈 repo_name 처리 회귀 테스트"""

    def test_dotgit_only_segment_returns_400(self):
        """https URL의 마지막 세그먼트가 '.git'만이면 400을 반환해야 한다"""
        r = client.post("/api/git/clone", json={
            "url": "https://github.com/user/.git",
        })
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert "repo 이름" in r.json()["detail"]

    def test_git_at_dotgit_only_returns_400(self):
        """git@ URL도 마지막 세그먼트가 '.git'만이면 400을 반환해야 한다"""
        r = client.post("/api/git/clone", json={
            "url": "git@github.com:user/.git",
        })
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert "repo 이름" in r.json()["detail"]

    def test_normal_repo_url_no_repo_name_error(self):
        """정상 repo URL (dest 없음)은 repo_name 추출 오류가 발생하면 안 된다"""
        # dest를 forbidden 경로로 줘서 path 검증에서 400 반환되게 함
        # "repo 이름" 에러가 아닌 다른 에러여야 함
        forbidden_dest = str(Path.home().parent / "test_repo_name_check")
        r = client.post("/api/git/clone", json={
            "url": "https://github.com/user/myrepo.git",
            "dest": forbidden_dest,
        })
        detail = r.json().get("detail", "")
        assert "repo 이름" not in detail, (
            f"정상 URL에서 repo_name 추출 오류가 발생하면 안 됨: {detail}"
        )

    def test_whitespace_only_name_returns_400(self):
        """공백만으로 된 repo_name도 차단되어야 한다 (.git → strip → '')"""
        # "https://github.com/user/%20.git" 같은 경우 방어적 확인
        r = client.post("/api/git/clone", json={
            "url": "https://github.com/user/ .git",
        })
        # 셸 메타문자(공백) 차단 전에 URL 메타문자 검사에서 걸릴 수도 있음
        # 어떤 이유든 400이 되어야 한다
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"


# ════════════════════════════════════════════════════════════════════════════════
# 8. ShellSession get_running_loop 회귀 (Bug 1)
#
# 수정 전: asyncio.get_event_loop() — Python 3.10+ deprecated
# 수정 후: asyncio.get_running_loop() — 실행 중인 루프 직접 참조
# ════════════════════════════════════════════════════════════════════════════════

class TestShellSessionRunningLoop:
    """ShellSession.start() get_running_loop() 회귀 테스트"""

    def _setup_pty_mock(self, monkeypatch) -> MagicMock:
        """PtyProcess mock 설정 (HAS_WINPTY 여부 무관)"""
        mock_pty = MagicMock()
        mock_pty.isalive.return_value = False  # _read_loop 즉시 종료
        mock_pty_cls = MagicMock()
        mock_pty_cls.spawn.return_value = mock_pty
        monkeypatch.setattr(main_module, "HAS_WINPTY", True)
        monkeypatch.setattr(main_module, "PtyProcess", mock_pty_cls, raising=False)
        return mock_pty

    def test_start_assigns_running_loop(self, monkeypatch):
        """start() 후 shell._loop가 asyncio.get_running_loop() 결과와 일치해야 한다"""
        self._setup_pty_mock(monkeypatch)

        async def _test():
            running = asyncio.get_running_loop()
            shell = ShellSession("sh01", ".", "cmd", 80, 24)
            shell.start()
            try:
                assert shell._loop is running, (
                    f"shell._loop should be the running event loop; "
                    f"expected {running!r}, got {shell._loop!r}"
                )
            finally:
                shell.kill()

        asyncio.run(_test())

    def test_start_outside_async_context_raises(self, monkeypatch):
        """start()를 async 컨텍스트 밖에서 호출하면 RuntimeError가 발생해야 한다.

        get_running_loop()는 실행 중인 루프가 없으면 RuntimeError를 발생시킨다.
        get_event_loop() 방식에서는 경고만 발생했음 — 이 테스트가 회귀 방지.
        """
        self._setup_pty_mock(monkeypatch)
        shell = ShellSession("sh02", ".", "cmd", 80, 24)
        with pytest.raises(RuntimeError, match="no running event loop"):
            shell.start()


# ════════════════════════════════════════════════════════════════════════════════
# 9. ClaudeSession 기본 동작 경계값
# ════════════════════════════════════════════════════════════════════════════════

class TestClaudeSessionEdgeCases:
    """ClaudeSession 기본 동작 및 경계값 테스트"""

    def test_to_dict_has_required_keys(self):
        """to_dict()가 필수 키를 포함해야 한다"""
        async def _run():
            return ClaudeSession("d01", ".", "").to_dict()

        d = asyncio.run(_run())
        required = {
            "id", "name", "work_dir", "model", "alive", "busy",
            "pipeline_id", "pipeline_role",
            "total_input_tokens", "total_output_tokens",
        }
        missing = required - set(d.keys())
        assert not missing, f"Missing keys in to_dict(): {missing}"

    def test_initial_alive_is_true(self):
        """생성 직후 alive=True여야 한다"""
        async def _run():
            return ClaudeSession("a01", ".", "").alive

        assert asyncio.run(_run()) is True

    def test_initial_busy_is_false(self):
        """생성 직후 busy=False여야 한다"""
        async def _run():
            return ClaudeSession("b01", ".", "").busy

        assert asyncio.run(_run()) is False

    def test_append_output_increments_version_by_one(self):
        """_append_output 호출 한 번 → _output_version이 정확히 1 증가해야 한다"""
        async def _run():
            session = ClaudeSession("v01", ".", "")
            before = session._output_version
            session._append_output("system", "test")
            return session._output_version - before

        assert asyncio.run(_run()) == 1

    def test_output_lines_capped_at_max_lines(self):
        """output_lines이 max_lines 초과 시 오래된 항목이 제거되어야 한다"""
        async def _run():
            session = ClaudeSession("m01", ".", "")
            session.max_lines = 5
            for i in range(10):
                session._append_output("system", f"line {i}")
            return session.output_lines

        lines = asyncio.run(_run())
        assert len(lines) == 5, f"max_lines=5 초과 시 잘라내야 함, got {len(lines)}"
        assert lines[0]["text"] == "line 5", "가장 오래된 항목이 제거되어야 함"
        assert lines[-1]["text"] == "line 9", "가장 최신 항목이 보존되어야 함"

    def test_session_id_reflected_in_name(self):
        """session_id가 name 필드에 포함되어야 한다"""
        async def _run():
            return ClaudeSession("abc123", ".", "").name

        assert "abc123" in asyncio.run(_run())

    def test_export_markdown_contains_session_name(self):
        """export_markdown()에 세션 이름이 포함되어야 한다"""
        async def _run():
            session = ClaudeSession("exp01", ".", "sonnet")
            session._append_output("assistant", "Hello world")
            return session.export_markdown()

        md = asyncio.run(_run())
        assert "claude-exp01" in md
        assert "Hello world" in md

    def test_get_formatted_output_empty(self):
        """output_lines가 비어있을 때 get_formatted_output은 빈 문자열을 반환해야 한다"""
        async def _run():
            return ClaudeSession("f01", ".", "").get_formatted_output()

        assert asyncio.run(_run()) == ""


# ════════════════════════════════════════════════════════════════════════════════
# 10. load_projects / save_projects 유틸리티
# ════════════════════════════════════════════════════════════════════════════════

class TestProjectsPersistence:
    """load_projects / save_projects 유틸리티 테스트"""

    def test_load_returns_empty_when_file_missing(self, monkeypatch, tmp_path):
        """projects.json이 없으면 빈 리스트를 반환해야 한다"""
        monkeypatch.setattr(main_module, "PROJECTS_FILE", tmp_path / "projects.json")
        assert load_projects() == []

    def test_load_handles_corrupt_json_and_creates_backup(self, monkeypatch, tmp_path):
        """손상된 JSON 파일은 .bak으로 백업 후 빈 리스트를 반환해야 한다"""
        fake_path = tmp_path / "projects.json"
        fake_path.write_text("{invalid json content", encoding="utf-8")
        monkeypatch.setattr(main_module, "PROJECTS_FILE", fake_path)

        result = load_projects()

        assert result == [], f"손상된 파일 시 빈 리스트 반환 기대, got {result}"
        bak = fake_path.with_suffix(".json.bak")
        assert bak.exists(), "손상된 파일의 백업(.bak)이 생성되어야 함"

    def test_save_and_load_roundtrip(self, monkeypatch, tmp_path):
        """save_projects 후 load_projects로 동일한 데이터를 복원해야 한다"""
        fake_path = tmp_path / "projects.json"
        monkeypatch.setattr(main_module, "PROJECTS_FILE", fake_path)

        projects = [
            {"name": "TestProject", "path": "/test/path", "added_at": "2026-01-01T00:00:00"}
        ]
        save_projects(projects)
        loaded = load_projects()

        assert loaded == projects

    def test_save_uses_atomic_write(self, monkeypatch, tmp_path):
        """save_projects가 원자적 쓰기를 사용하는지 검증 (.tmp 파일이 최종 교체됨)"""
        fake_path = tmp_path / "projects.json"
        monkeypatch.setattr(main_module, "PROJECTS_FILE", fake_path)

        save_projects([{"name": "Test", "path": "/test"}])

        # tmp 파일이 남아있으면 원자적 쓰기 실패
        assert not (tmp_path / "projects.json.tmp").exists(), (
            ".tmp 파일이 남아있으면 안 됨 (원자적 쓰기 실패)"
        )
        assert fake_path.exists(), "최종 projects.json이 존재해야 함"

    def test_save_preserves_unicode(self, monkeypatch, tmp_path):
        """한국어/유니코드 프로젝트 이름이 손실 없이 저장/복원되어야 한다"""
        fake_path = tmp_path / "projects.json"
        monkeypatch.setattr(main_module, "PROJECTS_FILE", fake_path)

        projects = [{"name": "한국어 프로젝트", "path": "/경로/테스트"}]
        save_projects(projects)
        loaded = load_projects()

        assert loaded[0]["name"] == "한국어 프로젝트"
        assert loaded[0]["path"] == "/경로/테스트"


# ════════════════════════════════════════════════════════════════════════════════
# 11. PipelineRunner.start() supervisor 실패 시 롤백 (Bug B)
#
# _create_supervisor_session() 실패 → sessions["pw-*"] 제거 +
# _source_session.pipeline_id = None 로 원상 복구되어야 한다.
# ════════════════════════════════════════════════════════════════════════════════

class TestPipelineRunnerStartRollback:

    def _make_source_session(self) -> ClaudeSession:
        sid = f"src-{uuid.uuid4().hex[:6]}"
        s = ClaudeSession(sid, ".", "claude-opus-4-6")
        main_module.sessions[sid] = s
        return s

    def test_supervisor_failure_removes_worker_from_sessions(self, monkeypatch):
        """supervisor 생성 실패 시 sessions에서 pw-* 항목이 제거되어야 한다"""
        src = self._make_source_session()
        runner = PipelineRunner(src, "goal", "claude-opus-4-6", 3, "cli", 1)

        def _fake_create_worker():
            wid = f"pw-{runner.id}"
            worker = ClaudeSession(wid, ".", "claude-opus-4-6")
            worker.start_worker = lambda: None
            worker.save_state = lambda: None
            main_module.sessions[wid] = worker
            return worker

        monkeypatch.setattr(runner, "_create_worker_session", _fake_create_worker)
        monkeypatch.setattr(runner, "_create_supervisor_session",
                            lambda: (_ for _ in ()).throw(RuntimeError("mock supervisor fail")))

        with pytest.raises(RuntimeError, match="mock supervisor fail"):
            runner.start()

        assert f"pw-{runner.id}" not in main_module.sessions, (
            "supervisor 생성 실패 후 pw-* 세션이 sessions에 남아있으면 안 됨"
        )

    def test_supervisor_failure_resets_source_pipeline_id(self, monkeypatch):
        """supervisor 생성 실패 시 source 세션의 pipeline_id가 None으로 초기화되어야 한다"""
        src = self._make_source_session()
        runner = PipelineRunner(src, "goal", "claude-opus-4-6", 3, "cli", 1)

        def _fake_create_worker():
            wid = f"pw-{runner.id}"
            worker = ClaudeSession(wid, ".", "claude-opus-4-6")
            worker.start_worker = lambda: None
            worker.save_state = lambda: None
            main_module.sessions[wid] = worker
            return worker

        monkeypatch.setattr(runner, "_create_worker_session", _fake_create_worker)
        monkeypatch.setattr(runner, "_create_supervisor_session",
                            lambda: (_ for _ in ()).throw(RuntimeError("mock supervisor fail")))
        monkeypatch.setattr(src, "save_state", lambda: None)

        with pytest.raises(RuntimeError):
            runner.start()

        assert src.pipeline_id is None, (
            "supervisor 생성 실패 후 source.pipeline_id가 None이어야 함"
        )

    def test_api_mode_no_supervisor_succeeds(self, monkeypatch):
        """mode='api'이면 supervisor 없이 태스크만 생성되어야 한다 (정상 경로)"""
        async def _run():
            src = self._make_source_session()
            runner = PipelineRunner(src, "goal", "claude-opus-4-6", 3, "api", 1)

            def _fake_create_worker():
                wid = f"pw-{runner.id}"
                worker = ClaudeSession(wid, ".", "claude-opus-4-6")
                worker.start_worker = lambda: None
                worker.save_state = lambda: None
                main_module.sessions[wid] = worker
                return worker

            monkeypatch.setattr(runner, "_create_worker_session", _fake_create_worker)
            monkeypatch.setattr(src, "save_state", lambda: None)

            # _run_loop을 즉시 반환하는 코루틴으로 대체
            async def _fake_run_loop():
                return
            monkeypatch.setattr(runner, "_run_loop", _fake_run_loop)

            runner.start()  # 예외 없어야 함
            assert runner._task is not None
            runner._task.cancel()
            try:
                await runner._task
            except asyncio.CancelledError:
                pass

        asyncio.run(_run())


# ════════════════════════════════════════════════════════════════════════════════
# 12. PlanPhase.approve() runner.start() 실패 시 pipelines 고아 방지 (Bug A)
#
# runner.start() 예외 → pipelines dict에서 해당 runner 제거되어야 한다.
# ════════════════════════════════════════════════════════════════════════════════

class TestPlanPhaseApproveRollback:

    def _make_plan_phase(self) -> tuple:
        sid = f"src-{uuid.uuid4().hex[:6]}"
        src = ClaudeSession(sid, ".", "claude-opus-4-6")
        main_module.sessions[sid] = src
        phase = PlanPhase(src, "test goal", "claude-opus-4-6", "api")
        phase.status = "plan_ready"
        phase.plan_text = "1단계: 테스트"
        return phase, src

    def test_start_failure_removes_runner_from_pipelines(self, monkeypatch):
        """runner.start() 실패 시 pipelines에 고아 항목이 남으면 안 된다"""
        phase, src = self._make_plan_phase()

        monkeypatch.setattr(main_module, "PipelineRunner",
                            lambda *a, **kw: _FailingRunner())

        async def _run():
            with pytest.raises(RuntimeError, match="mock start fail"):
                await phase.approve(None, 3, 1)
            assert len(main_module.pipelines) == 0, (
                "start() 실패 후 pipelines에 항목이 남아있으면 안 됨"
            )

        asyncio.run(_run())

    def test_start_failure_does_not_set_phase_pipeline_id(self, monkeypatch):
        """runner.start() 실패 시 PlanPhase.pipeline_id가 설정되면 안 된다"""
        phase, src = self._make_plan_phase()

        monkeypatch.setattr(main_module, "PipelineRunner",
                            lambda *a, **kw: _FailingRunner())

        async def _run():
            with pytest.raises(RuntimeError):
                await phase.approve(None, 3, 1)
            assert phase.pipeline_id is None, (
                "start() 실패 후 phase.pipeline_id가 설정되면 안 됨"
            )

        asyncio.run(_run())

    def test_start_success_registers_pipeline(self, monkeypatch):
        """runner.start() 성공 시 pipelines에 runner가 등록되어야 한다"""
        phase, src = self._make_plan_phase()

        async def _run():
            fake_runner = _SucceedingRunner()
            monkeypatch.setattr(main_module, "PipelineRunner",
                                lambda *a, **kw: fake_runner)
            result = await phase.approve(None, 3, 1)
            assert result == fake_runner.id
            assert fake_runner.id in main_module.pipelines

        asyncio.run(_run())


# ── _FailingRunner / _SucceedingRunner: approve() 테스트용 최소 스텁 ──

class _FailingRunner:
    id = f"fail-{uuid.uuid4().hex[:6]}"

    def start(self):
        raise RuntimeError("mock start fail")


class _SucceedingRunner:
    id = f"ok-{uuid.uuid4().hex[:6]}"

    def start(self):
        pass  # 성공


# ════════════════════════════════════════════════════════════════════════════════
# 13. ClaudeSession._handle_stream_event — stream-json 이벤트 파싱 (순수 함수)
# ════════════════════════════════════════════════════════════════════════════════

class TestHandleStreamEvent:

    def _make_session(self) -> ClaudeSession:
        sid = f"ev-{uuid.uuid4().hex[:6]}"
        return ClaudeSession(sid, ".", "")

    # ── system 이벤트 ─────────────────────────────────────────────────────────

    def test_system_event_sets_session_uuid(self):
        s = self._make_session()
        s._handle_stream_event({"type": "system", "session_id": "abc123"})
        assert s.session_uuid == "abc123"

    def test_system_event_no_session_id_keeps_none(self):
        s = self._make_session()
        s._handle_stream_event({"type": "system"})
        assert s.session_uuid is None

    # ── assistant 이벤트 (텍스트 블록) ────────────────────────────────────────

    def test_assistant_text_block_appended(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Hello"}]},
        })
        assert any(e["text"] == "Hello" for e in s.output_lines)

    # ── assistant 이벤트 (tool_use — 각 분기) ─────────────────────────────────

    def test_assistant_bash_tool_use(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use",
                                      "name": "Bash",
                                      "input": {"command": "ls -la"}}]},
        })
        assert any("[Bash] ls -la" in e["text"] for e in s.output_lines)

    def test_assistant_read_tool_use(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use",
                                      "name": "Read",
                                      "input": {"file_path": "/some/file.py"}}]},
        })
        assert any("[Read] /some/file.py" in e["text"] for e in s.output_lines)

    def test_assistant_glob_tool_use(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use",
                                      "name": "Glob",
                                      "input": {"pattern": "**/*.py"}}]},
        })
        assert any("[Glob] **/*.py" in e["text"] for e in s.output_lines)

    def test_assistant_grep_tool_use(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use",
                                      "name": "Grep",
                                      "input": {"pattern": "def main"}}]},
        })
        assert any("[Grep] def main" in e["text"] for e in s.output_lines)

    def test_assistant_agent_tool_use(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use",
                                      "name": "Agent",
                                      "input": {"description": "Explore codebase"}}]},
        })
        assert any("[Agent] Explore codebase" in e["text"] for e in s.output_lines)

    def test_assistant_todowrite_tool_use(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use",
                                      "name": "TodoWrite",
                                      "input": {"todos": [{"content": "Fix bug",
                                                           "status": "in_progress",
                                                           "activeForm": "Fixing bug"}]}}]},
        })
        assert any("[TodoWrite]" in e["text"] for e in s.output_lines)

    def test_assistant_unknown_tool_use(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use",
                                      "name": "UnknownTool",
                                      "input": {}}]},
        })
        assert any("[UnknownTool]" in e["text"] for e in s.output_lines)

    def test_assistant_ask_user_question_sets_pending_question(self):
        s = self._make_session()
        tool_input = {"questions": [{"question": "어느 버전?", "options": [
            {"label": "v1", "description": "버전 1"},
            {"label": "v2", "description": "버전 2"},
        ]}]}
        s._handle_stream_event({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use",
                                      "name": "AskUserQuestion",
                                      "input": tool_input}]},
        })
        assert s.pending_question is not None
        texts = [e["text"] for e in s.output_lines]
        assert any("어느 버전?" in t for t in texts)
        assert any("v1" in t for t in texts)

    # ── content_block_delta ───────────────────────────────────────────────────

    def test_content_block_delta_creates_streaming_line(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "Hello "},
        })
        last = s.output_lines[-1]
        assert last["text"] == "Hello "
        assert last["streaming"] is True

    def test_content_block_delta_appends_to_existing_streaming_line(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "Hello "},
        })
        s._handle_stream_event({
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "World"},
        })
        last = s.output_lines[-1]
        assert last["text"] == "Hello World"
        assert last["streaming"] is True

    # ── content_block_stop ────────────────────────────────────────────────────

    def test_content_block_stop_clears_streaming_flag(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "Hello"},
        })
        assert s.output_lines[-1]["streaming"] is True
        s._handle_stream_event({"type": "content_block_stop"})
        assert s.output_lines[-1]["streaming"] is False

    def test_content_block_stop_no_op_when_no_streaming_line(self):
        """스트리밍 라인 없이 stop 이벤트 → 예외 없이 통과"""
        s = self._make_session()
        s._handle_stream_event({"type": "content_block_stop"})
        assert s.output_lines == []

    # ── result 이벤트 ─────────────────────────────────────────────────────────

    def test_result_event_updates_tokens(self):
        s = self._make_session()
        s._handle_stream_event({
            "type": "result",
            "result": "완료",
            "session_id": "newuuid",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        })
        assert s.total_input_tokens == 100
        assert s.total_output_tokens == 50
        assert s.session_uuid == "newuuid"
        texts = [e["text"] for e in s.output_lines]
        assert any("완료" in t for t in texts)
        assert any("--- Done ---" in t for t in texts)

    def test_result_event_empty_result_no_extra_line(self):
        """result가 빈 문자열이면 result 라인이 추가되지 않고 Done만 추가"""
        s = self._make_session()
        initial_count = len(s.output_lines)
        s._handle_stream_event({
            "type": "result",
            "result": "",
            "session_id": None,
            "usage": {},
        })
        assert len(s.output_lines) == initial_count + 1
        assert s.output_lines[-1]["text"] == "--- Done ---"

    # ── 잘못된 이벤트 ─────────────────────────────────────────────────────────

    def test_non_dict_event_silently_ignored(self):
        s = self._make_session()
        s._handle_stream_event("not a dict")  # type: ignore
        assert s.output_lines == []

    def test_unknown_event_type_silently_ignored(self):
        s = self._make_session()
        s._handle_stream_event({"type": "unknown_event_type"})
        assert s.output_lines == []


# ════════════════════════════════════════════════════════════════════════════════
# 14. ClaudeSession save_state / load_state / delete_state
# ════════════════════════════════════════════════════════════════════════════════

class TestClaudeSessionStatePersistence:

    def _make_session(self, monkeypatch, tmp_path) -> ClaudeSession:
        monkeypatch.setattr(main_module, "SESSIONS_DIR", tmp_path)
        monkeypatch.setattr(main_module, "LOGS_DIR", tmp_path)
        sid = f"st-{uuid.uuid4().hex[:6]}"
        s = ClaudeSession(sid, "/work", "opus")
        s.name = "test-session"
        s.session_uuid = "uuid-xyz"
        s.total_input_tokens = 42
        s.total_output_tokens = 7
        s.pipeline_id = "pipe-001"
        s.pipeline_role = "worker"
        s._append_output("assistant", "hello")
        return s

    def test_save_and_load_roundtrip(self, monkeypatch, tmp_path):
        s = self._make_session(monkeypatch, tmp_path)
        s.save_state()
        loaded = ClaudeSession.load_state(s.id)
        assert loaded.id == s.id
        assert loaded.name == "test-session"
        assert loaded.work_dir == "/work"
        assert loaded.model == "opus"
        assert loaded.session_uuid == "uuid-xyz"
        assert loaded.total_input_tokens == 42
        assert loaded.total_output_tokens == 7
        assert loaded.pipeline_id == "pipe-001"
        assert loaded.pipeline_role == "worker"
        assert len(loaded.output_lines) == 1
        assert loaded.output_lines[0]["text"] == "hello"

    def test_load_restores_output_version(self, monkeypatch, tmp_path):
        s = self._make_session(monkeypatch, tmp_path)
        s.save_state()
        loaded = ClaudeSession.load_state(s.id)
        assert loaded._output_version == len(loaded.output_lines)

    def test_delete_state_removes_file(self, monkeypatch, tmp_path):
        s = self._make_session(monkeypatch, tmp_path)
        s.save_state()
        save_file = tmp_path / f"{s.id}.json"
        assert save_file.exists()
        s.delete_state()
        assert not save_file.exists()

    def test_delete_state_no_op_when_file_missing(self, monkeypatch, tmp_path):
        """파일 없을 때 delete_state는 예외 없이 통과해야 한다"""
        s = self._make_session(monkeypatch, tmp_path)
        s.delete_state()  # 파일이 존재하지 않아도 예외 없음


# ════════════════════════════════════════════════════════════════════════════════
# 15. ClaudeSession.get_formatted_output — 출력 타입별 포맷 분기
# ════════════════════════════════════════════════════════════════════════════════

class TestGetFormattedOutputBranches:

    def _session_with_entries(self, types_and_texts: list) -> ClaudeSession:
        sid = f"fmt-{uuid.uuid4().hex[:6]}"
        s = ClaudeSession(sid, ".", "")
        for otype, text in types_and_texts:
            s._append_output(otype, text)
        return s

    def test_system_entry_wrapped_in_newlines(self):
        s = self._session_with_entries([("system", "--- Done ---")])
        out = s.get_formatted_output()
        assert "\n--- Done ---\n" in out

    def test_assistant_entry_plain_text(self):
        s = self._session_with_entries([("assistant", "안녕하세요")])
        out = s.get_formatted_output()
        assert "안녕하세요" in out

    def test_result_entry_plain_text(self):
        s = self._session_with_entries([("result", "작업 완료")])
        out = s.get_formatted_output()
        assert "작업 완료" in out

    def test_tool_entry_indented(self):
        s = self._session_with_entries([("tool", "[Bash] ls")])
        out = s.get_formatted_output()
        assert "  [Bash] ls" in out

    def test_error_entry_prefixed(self):
        s = self._session_with_entries([("error", "파일 없음")])
        out = s.get_formatted_output()
        assert "[ERROR] 파일 없음" in out

    def test_unknown_type_raw_text(self):
        s = self._session_with_entries([("unknown_type", "raw")])
        out = s.get_formatted_output()
        assert "raw" in out

    def test_lines_param_limits_output(self):
        # system 타입은 \n{text}\n 형태라 분리가 명확함
        s = self._session_with_entries([("system", f"line{i}") for i in range(100)])
        out = s.get_formatted_output(lines=5)
        assert "line99" in out      # 마지막 줄 포함
        assert "line95" in out      # 경계 포함 (100개 중 마지막 5 = 95~99)
        assert "line94" not in out  # 경계 밖 제외


# ════════════════════════════════════════════════════════════════════════════════
# 16. PlanPhase 헬퍼 — _find_question_text, to_dict
# ════════════════════════════════════════════════════════════════════════════════

class TestPlanPhaseHelpers:

    def _make_phase(self) -> PlanPhase:
        sid = f"ph-{uuid.uuid4().hex[:6]}"
        src = ClaudeSession(sid, ".", "")
        phase = PlanPhase(src, "목표", "cli", "sonnet")
        phase.questions = [
            {"id": "q1", "question": "어느 모드를 사용하시겠습니까?", "why": "", "options": []},
            {"id": "q2", "question": "최대 반복 횟수는?", "why": "", "options": []},
        ]
        return phase

    def test_find_question_text_returns_text_for_known_id(self):
        phase = self._make_phase()
        assert phase._find_question_text("q1") == "어느 모드를 사용하시겠습니까?"

    def test_find_question_text_returns_id_for_unknown(self):
        phase = self._make_phase()
        assert phase._find_question_text("q99") == "q99"

    def test_to_dict_has_required_keys(self):
        phase = self._make_phase()
        d = phase.to_dict()
        for key in ("id", "session_id", "goal", "mode", "supervisor_model",
                    "status", "questions", "answers", "plan_text", "error",
                    "pipeline_id", "created_at"):
            assert key in d, f"to_dict에 '{key}' 키가 없음"

    def test_to_dict_reflects_current_state(self):
        phase = self._make_phase()
        phase.status = "plan_ready"
        phase.plan_text = "1단계: 분석"
        phase.pipeline_id = "pipe-xyz"
        d = phase.to_dict()
        assert d["status"] == "plan_ready"
        assert d["plan_text"] == "1단계: 분석"
        assert d["pipeline_id"] == "pipe-xyz"
        assert d["goal"] == "목표"
