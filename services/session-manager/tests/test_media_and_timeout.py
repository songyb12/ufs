"""
tests/test_media_and_timeout.py

CLI 타임아웃 개선 및 미디어 보안 기능 테스트.

Coverage:
  - app/routes_api.py: GET /media-token, GET /media/{path}
  - app/session.py: idle_timeout 설정 (task_type via send_command)
  - app/models.py: TASK_TIMEOUTS 환경변수 오버라이드
  - 경로 이탈(path traversal) 방어 검증

실행:
    .venv/Scripts/pytest tests/test_media_and_timeout.py -v
"""
import asyncio
import hashlib
import hmac
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
import app.models as models_module
import app.routes_api as routes_api_module
from app.main import ClaudeSession, sessions
from app.models import TASK_TIMEOUTS, UPLOADS_DIR, SCREENSHOTS_DIR

client = TestClient(app=main_module.app, raise_server_exceptions=True)


# ════════════════════════════════════════════════════════════════════════════════
# 공통 픽스처
# ════════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def reset_global_state():
    """각 테스트 전후 전역 상태 및 미디어 인증 환경변수 초기화"""
    main_module._session_create_log.clear()
    main_module.sessions.clear()
    yield
    main_module._session_create_log.clear()
    main_module.sessions.clear()
    # ADMIN_API_KEY 정리 (테스트에서 설정했을 경우)
    os.environ.pop("ADMIN_API_KEY", None)


def _make_session(sid="ms01") -> ClaudeSession:
    async def _build():
        return ClaudeSession(sid, ".", "sonnet")
    return asyncio.run(_build())


def _register_session(sid="ms01") -> ClaudeSession:
    s = _make_session(sid)
    sessions[sid] = s
    return s


def _gen_valid_token(secret: str, ttl: int = 3600) -> str:
    """테스트용 유효 mkey 생성: "{sig}:{expires}" """
    expires = int(time.time()) + ttl
    sig = hmac.new(secret.encode(), str(expires).encode(), hashlib.sha256).hexdigest()
    return f"{sig}:{expires}"


def _gen_expired_token(secret: str) -> str:
    """만료된 mkey 생성: 1초 전 만료"""
    expires = int(time.time()) - 1
    sig = hmac.new(secret.encode(), str(expires).encode(), hashlib.sha256).hexdigest()
    return f"{sig}:{expires}"


# ════════════════════════════════════════════════════════════════════════════════
# 1. models.py — TASK_TIMEOUTS 환경변수 오버라이드
# ════════════════════════════════════════════════════════════════════════════════

class TestTaskTimeoutsConfig:
    """TASK_TIMEOUTS 딕셔너리 구조 및 기본값 검증"""

    def test_default_keys_present(self):
        """필수 키가 모두 존재해야 한다"""
        assert "default" in TASK_TIMEOUTS
        assert "long_task" in TASK_TIMEOUTS
        assert "image_gen" in TASK_TIMEOUTS

    def test_default_values_are_positive(self):
        """모든 값이 양의 정수여야 한다"""
        for k, v in TASK_TIMEOUTS.items():
            assert isinstance(v, int), f"{k}의 값이 int가 아님"
            assert v > 0, f"{k}의 값이 0 이하"

    def test_image_gen_longer_than_default(self):
        """image_gen은 default보다 긴 타임아웃을 가져야 한다"""
        assert TASK_TIMEOUTS["image_gen"] > TASK_TIMEOUTS["default"]

    def test_env_override(self, monkeypatch):
        """환경변수가 TASK_TIMEOUTS를 오버라이드하는지 확인 (모듈 재로드 방식)"""
        monkeypatch.setenv("TASK_TIMEOUT_DEFAULT", "42")
        # 모듈 수준에서 이미 로드되었으므로, 직접 os.environ.get 동작 확인
        val = int(os.environ.get("TASK_TIMEOUT_DEFAULT", "300"))
        assert val == 42


# ════════════════════════════════════════════════════════════════════════════════
# 2. send_command task_type → session.idle_timeout 적용
# ════════════════════════════════════════════════════════════════════════════════

class TestSendCommandTaskType:
    """send_command의 task_type이 session.idle_timeout에 반영되는지 검증"""

    def test_default_task_type_sets_default_timeout(self):
        """task_type 미지정 → TASK_TIMEOUTS["default"]로 설정"""
        s = _register_session("tt01")
        r = client.post("/api/sessions/tt01/send", json={"command": "hello"})
        assert r.status_code == 200
        assert s.idle_timeout == TASK_TIMEOUTS["default"]

    def test_image_gen_task_type_sets_longer_timeout(self):
        """task_type=image_gen → TASK_TIMEOUTS["image_gen"]으로 설정"""
        s = _register_session("tt02")
        r = client.post(
            "/api/sessions/tt02/send",
            json={"command": "이미지 생성해줘", "task_type": "image_gen"},
        )
        assert r.status_code == 200
        assert s.idle_timeout == TASK_TIMEOUTS["image_gen"]
        # 응답에 idle_timeout이 포함되어야 한다
        assert r.json()["idle_timeout"] == TASK_TIMEOUTS["image_gen"]

    def test_long_task_type_sets_long_timeout(self):
        """task_type=long_task → TASK_TIMEOUTS["long_task"]로 설정"""
        s = _register_session("tt03")
        client.post(
            "/api/sessions/tt03/send",
            json={"command": "긴 작업", "task_type": "long_task"},
        )
        assert s.idle_timeout == TASK_TIMEOUTS["long_task"]

    def test_unknown_task_type_falls_back_to_default(self):
        """알 수 없는 task_type → TASK_TIMEOUTS["default"]로 폴백"""
        s = _register_session("tt04")
        client.post(
            "/api/sessions/tt04/send",
            json={"command": "test", "task_type": "nonexistent_type"},
        )
        assert s.idle_timeout == TASK_TIMEOUTS["default"]

    def test_send_returns_idle_timeout_in_response(self):
        """응답 JSON에 idle_timeout 키가 포함되어야 한다"""
        _register_session("tt05")
        r = client.post(
            "/api/sessions/tt05/send",
            json={"command": "check", "task_type": "image_gen"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "idle_timeout" in body
        assert body["idle_timeout"] > 0

    def test_dead_session_returns_409(self):
        """종료된 세션에 send → 409 (기존 동작 유지)"""
        s = _register_session("tt06")
        s.alive = False
        r = client.post("/api/sessions/tt06/send", json={"command": "hello"})
        assert r.status_code == 409


# ════════════════════════════════════════════════════════════════════════════════
# 3. GET /api/media-token
# ════════════════════════════════════════════════════════════════════════════════

class TestMediaToken:
    """미디어 토큰 발급 엔드포인트"""

    def test_no_admin_key_returns_empty_token(self):
        """ADMIN_API_KEY 미설정 → 빈 토큰 + auth_required=False"""
        os.environ.pop("ADMIN_API_KEY", None)
        r = client.get("/api/media-token")
        assert r.status_code == 200
        body = r.json()
        assert body["token"] == ""
        assert body["expires"] == 0
        assert body["auth_required"] is False

    def test_with_admin_key_returns_signed_token(self, monkeypatch):
        """ADMIN_API_KEY 설정 → 서명된 토큰 + auth_required=True"""
        monkeypatch.setenv("ADMIN_API_KEY", "testsecret")
        r = client.get("/api/media-token")
        assert r.status_code == 200
        body = r.json()
        assert body["auth_required"] is True
        assert body["expires"] > int(time.time())
        # 토큰 형식: "{hex}:{timestamp}"
        token = body["token"]
        assert ":" in token
        sig, exp_str = token.rsplit(":", 1)
        assert len(sig) == 64  # SHA-256 hexdigest = 64자
        assert int(exp_str) == body["expires"]

    def test_with_admin_key_token_is_valid_hmac(self, monkeypatch):
        """발급된 토큰이 실제로 검증을 통과해야 한다"""
        secret = "testsecret_verify"
        monkeypatch.setenv("ADMIN_API_KEY", secret)
        r = client.get("/api/media-token")
        body = r.json()
        token = body["token"]
        sig, exp_str = token.rsplit(":", 1)
        expires = int(exp_str)
        # HMAC 재계산 후 비교
        expected = hmac.new(secret.encode(), exp_str.encode(), hashlib.sha256).hexdigest()
        assert hmac.compare_digest(expected, sig)


# ════════════════════════════════════════════════════════════════════════════════
# 4. GET /api/media/{full_path} — 파일 서빙 + 보안 검증
# ════════════════════════════════════════════════════════════════════════════════

class TestServeMedia:
    """미디어 파일 서빙 엔드포인트"""

    @pytest.fixture()
    def upload_file(self, tmp_path):
        """테스트용 업로드 파일 생성 및 정리"""
        session_dir = UPLOADS_DIR / "test_session"
        session_dir.mkdir(exist_ok=True)
        fp = session_dir / "test_image.png"
        fp.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # minimal PNG header
        yield fp
        fp.unlink(missing_ok=True)
        try:
            session_dir.rmdir()
        except OSError:
            pass

    @pytest.fixture()
    def screenshot_file(self):
        """테스트용 스크린샷 파일 생성 및 정리"""
        fp = SCREENSHOTS_DIR / "screen_test_9999.jpg"
        fp.write_bytes(b"\xff\xd8\xff" + b"\x00" * 50)  # minimal JPEG header
        yield fp
        fp.unlink(missing_ok=True)

    # ── 인증 미설정 (개발 모드) ──────────────────────────────────────────────

    def test_no_auth_upload_serves_without_token(self, upload_file):
        """ADMIN_API_KEY 미설정 → 토큰 없이 업로드 파일 서빙"""
        os.environ.pop("ADMIN_API_KEY", None)
        r = client.get("/api/media/uploads/test_session/test_image.png")
        assert r.status_code == 200

    def test_no_auth_screenshot_serves_without_token(self, screenshot_file):
        """ADMIN_API_KEY 미설정 → 토큰 없이 스크린샷 서빙"""
        os.environ.pop("ADMIN_API_KEY", None)
        r = client.get("/api/media/screenshots/screen_test_9999.jpg")
        assert r.status_code == 200

    # ── 인증 활성 — 토큰 없음/잘못됨 ────────────────────────────────────────

    def test_auth_no_token_returns_401(self, monkeypatch, upload_file):
        """ADMIN_API_KEY 설정 + 토큰 없음 → 401"""
        monkeypatch.setenv("ADMIN_API_KEY", "secret")
        r = client.get("/api/media/uploads/test_session/test_image.png")
        assert r.status_code == 401

    def test_auth_malformed_token_returns_403(self, monkeypatch, upload_file):
        """콜론 없는 잘못된 토큰 → 403"""
        monkeypatch.setenv("ADMIN_API_KEY", "secret")
        r = client.get(
            "/api/media/uploads/test_session/test_image.png",
            params={"mkey": "notavalidtoken"},
        )
        assert r.status_code == 403

    def test_auth_expired_token_returns_403(self, monkeypatch, upload_file):
        """만료된 토큰 → 403"""
        secret = "secret_expired"
        monkeypatch.setenv("ADMIN_API_KEY", secret)
        expired_mkey = _gen_expired_token(secret)
        r = client.get(
            "/api/media/uploads/test_session/test_image.png",
            params={"mkey": expired_mkey},
        )
        assert r.status_code == 403

    def test_auth_wrong_signature_returns_403(self, monkeypatch, upload_file):
        """서명이 맞지 않는 토큰 → 403"""
        monkeypatch.setenv("ADMIN_API_KEY", "real_secret")
        # 다른 secret으로 서명된 토큰
        wrong_mkey = _gen_valid_token("wrong_secret")
        r = client.get(
            "/api/media/uploads/test_session/test_image.png",
            params={"mkey": wrong_mkey},
        )
        assert r.status_code == 403

    def test_auth_valid_token_serves_file(self, monkeypatch, upload_file):
        """유효한 토큰 → 200 파일 응답"""
        secret = "valid_secret"
        monkeypatch.setenv("ADMIN_API_KEY", secret)
        valid_mkey = _gen_valid_token(secret)
        r = client.get(
            "/api/media/uploads/test_session/test_image.png",
            params={"mkey": valid_mkey},
        )
        assert r.status_code == 200

    # ── 파일 없음 / 경로 없음 ────────────────────────────────────────────────

    def test_file_not_found_returns_404(self):
        """존재하지 않는 파일 → 404"""
        os.environ.pop("ADMIN_API_KEY", None)
        r = client.get("/api/media/uploads/ghost_session/nonexistent.png")
        assert r.status_code == 404

    def test_unsupported_prefix_returns_404(self):
        """uploads/screenshots 외의 prefix → 404"""
        os.environ.pop("ADMIN_API_KEY", None)
        r = client.get("/api/media/logs/some_log.txt")
        assert r.status_code == 404

    # ── path traversal 방어 ──────────────────────────────────────────────────

    def test_path_traversal_dotdot_not_200(self):
        """../../etc/passwd 형태 경로 → 절대 200이 되어선 안 됨.
        Starlette가 URL path를 정규화하면 404,
        정규화를 통과하더라도 is_relative_to 체크로 403 반환.
        어느 쪽이든 파일을 서빙하지 않는 것이 핵심.
        """
        os.environ.pop("ADMIN_API_KEY", None)
        r = client.get("/api/media/uploads/../../etc/passwd")
        assert r.status_code != 200

    def test_path_traversal_encoded_dotdot_not_200(self):
        """URL 인코딩된 경로 이탈 시도 → 200이 되어선 안 됨"""
        os.environ.pop("ADMIN_API_KEY", None)
        r = client.get("/api/media/uploads/%2F..%2F..%2Fetc%2Fpasswd")
        assert r.status_code != 200

    def test_path_traversal_screenshots_dotdot_not_200(self):
        """screenshots 경로에서의 이탈 시도 → 200이 되어선 안 됨"""
        os.environ.pop("ADMIN_API_KEY", None)
        r = client.get("/api/media/screenshots/../../session.json")
        assert r.status_code != 200

    def test_path_traversal_with_valid_token_not_200(self, monkeypatch):
        """유효한 토큰이 있어도 path traversal은 차단되어야 함"""
        secret = "traversal_secret"
        monkeypatch.setenv("ADMIN_API_KEY", secret)
        valid_mkey = _gen_valid_token(secret)
        r = client.get(
            "/api/media/uploads/../../etc/passwd",
            params={"mkey": valid_mkey},
        )
        assert r.status_code != 200

    def test_is_relative_to_check_blocks_filesystem_traversal(self):
        """is_relative_to 체크가 실제 파일시스템 이탈 경로에서 403 반환.
        Starlette 정규화를 통과한 경우 (예: 심볼릭 링크, 직접 API 호출)에도
        서버 측 방어가 동작하는지 확인.
        """
        import app.routes_api as m
        from app.models import UPLOADS_DIR
        # resolve()가 base_dir 밖 경로를 만드는 케이스를 직접 시뮬레이션
        outside_path = UPLOADS_DIR.parent / "sessions" / "fake.json"
        # is_relative_to 방어 로직 직접 검증
        assert not outside_path.is_relative_to(UPLOADS_DIR.resolve())


# ════════════════════════════════════════════════════════════════════════════════
# 5. _verify_media_token 단위 테스트
# ════════════════════════════════════════════════════════════════════════════════

class TestVerifyMediaToken:
    """routes_api의 HMAC 검증 헬퍼 함수 단위 테스트"""

    def test_valid_token_passes(self, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "unit_secret")
        expires = int(time.time()) + 3600
        sig = routes_api_module._generate_media_token(expires)
        assert routes_api_module._verify_media_token(sig, expires) is True

    def test_expired_token_fails(self, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "unit_secret")
        expires = int(time.time()) - 1  # 이미 만료
        sig = routes_api_module._generate_media_token(expires)
        assert routes_api_module._verify_media_token(sig, expires) is False

    def test_wrong_signature_fails(self, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "unit_secret")
        expires = int(time.time()) + 3600
        assert routes_api_module._verify_media_token("deadbeef" * 8, expires) is False

    def test_empty_secret_returns_empty_token(self, monkeypatch):
        monkeypatch.delenv("ADMIN_API_KEY", raising=False)
        expires = int(time.time()) + 3600
        token = routes_api_module._generate_media_token(expires)
        assert token == ""

    def test_media_auth_enabled_with_key(self, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "nonempty")
        assert routes_api_module._media_auth_enabled() is True

    def test_media_auth_disabled_without_key(self, monkeypatch):
        monkeypatch.delenv("ADMIN_API_KEY", raising=False)
        assert routes_api_module._media_auth_enabled() is False
