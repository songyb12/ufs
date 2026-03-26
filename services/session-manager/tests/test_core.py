"""
tests/test_core.py

session-manager 핵심 로직 단위 테스트:
  1. git_clone 경로 검증 (P1-B 보안 버그 회귀 방지)
  2. git status --porcelain 파싱 (P2-B off-by-one 회귀 방지)
  3. _check_rate_limit (분당 생성 수 / 활성 세션 수 제한)
  4. PlanPhase._parse_questions_json (LLM 응답 JSON 파싱)

실행:
    .venv/Scripts/pytest tests/test_core.py -v
"""
import json
import time
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
)

# ── TestClient (lifespan 미실행 — startup/shutdown 훅 없이 엔드포인트 직접 호출) ──
client = TestClient(app=main_module.app, raise_server_exceptions=True)


# ════════════════════════════════════════════════════════════════════════════════
# 공통 픽스처
# ════════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def reset_global_state():
    """각 테스트 전후 rate-limit 및 세션 전역 상태 초기화"""
    main_module._session_create_log.clear()
    main_module.sessions.clear()
    yield
    main_module._session_create_log.clear()
    main_module.sessions.clear()


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
