# Session Manager — Bug & Code Quality Audit

**날짜**: 2026-03-27
**기준 커밋**: `70aa149`
**테스트 상태**: 209 passed (기준선)
**수정 완료**: 2026-03-27 — CRITICAL 2건 + HIGH 4건 수정, 209 passed 유지

---

## CRITICAL (런타임 크래시 가능)

### C-1 · `session.py:290` — `APP_DIR` NameError (MCP config 경로 검증) ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/session.py:290` |
| **심각도** | CRITICAL |
| **문제** | `_run_claude()` 내 MCP config 경로 검증 코드가 `APP_DIR`를 참조하지만, `session.py`의 import 목록에 `APP_DIR`가 없다. `mcp_config`가 설정된 세션을 실행하는 즉시 `NameError: name 'APP_DIR' is not defined` 발생. |
| **코드** | `_allowed_mcp = (APP_DIR, Path.home() / ".claude")` |
| **수정 방향** | `from app.models import (..., APP_DIR)` 추가. 또는 이미 import된 `SESSIONS_DIR`와 동일한 방법으로 `app.auth._ALLOWED_BROWSE_ROOTS` 재사용 검토. |
| **수정 내용** | `from app.models import (APP_DIR, LOGS_DIR, SESSIONS_DIR, ...)` — APP_DIR을 models import 목록에 추가. |

---

### C-2 · `session.py:581` — `signal` NameError (Unix interrupt) ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/session.py:581` |
| **심각도** | CRITICAL |
| **문제** | `interrupt()` 메서드의 `else` 분기(비-Windows)에서 `signal.SIGINT`를 참조하지만, `session.py` 최상단에 `import signal`이 없다. Linux/macOS 환경(또는 Docker 컨테이너)에서 `interrupt()` 호출 시 즉시 `NameError`. |
| **코드** | `self.process.send_signal(signal.SIGINT)` |
| **수정 방향** | `session.py` import 섹션에 `import signal` 추가. |
| **수정 내용** | stdlib import 목록에 `import signal` 추가 (C-1과 동시 수정). |

---

## HIGH (기능 버그 / 잠재적 보안 문제)

### H-1 · `routes_api.py:205` — 업로드 파일 수 TOCTOU 레이스 ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/routes_api.py:205` |
| **심각도** | HIGH |
| **문제** | 업로드 수 제한 검사(`len(list(session_dir.iterdir())) >= 50`)가 실제 파일 쓰기 전에 발생한다. 동시 요청 N개가 동시에 검사를 통과하면 50개를 초과하는 파일이 쓰일 수 있다. |
| **코드** | `if session_dir.exists() and len(list(session_dir.iterdir())) >= 50:` |
| **수정 방향** | 파일 저장 후 카운트 재확인 + 초과 시 파일 삭제, 또는 per-session lock 사용. |
| **수정 내용** | 사전 검사 제거 → 파일 쓰기 후 `len(iterdir()) > 50`이면 `filepath.unlink()`로 롤백 후 429. |

---

### H-2 · `session.py:402-408` — UUID 만료 재시도 무한루프 가능성 ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/session.py:402–408` |
| **심각도** | HIGH |
| **문제** | UUID 만료 감지 조건 `not all_output and not _retry_without_model`이 참이면 `session_uuid = None`으로 리셋 후 `await self._run_claude(prompt)`를 재귀 호출한다. Claude CLI가 새 UUID 없이도 빈 출력을 반환하는 엣지케이스(네트워크 단절, API 제한 등)에서 무한 재귀 발생 가능. |
| **코드** | `await self._run_claude(prompt)` — 인자 없이 재귀 |
| **수정 방향** | 재시도 횟수 카운터(`_uuid_retry_count`)를 추가하거나, 이미 있는 `_retry_without_model=True`를 사용해 재귀 깊이 1로 제한. |
| **수정 내용** | `_run_claude()`에 `_uuid_reset: bool = False` 파라미터 추가. 재귀 호출 시 `_uuid_reset=True` 전달, 조건에 `and not _uuid_reset` 추가로 재귀 깊이 1로 제한. |

---

### H-3 · `shell.py:72` — `asyncio.get_running_loop()` 비동기 컨텍스트 미보장 ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/shell.py:72` |
| **심각도** | HIGH |
| **문제** | `ShellSession.start()`가 `asyncio.get_running_loop()`를 호출하는데, 이 메서드가 동기 컨텍스트에서 호출되면 `RuntimeError: no running event loop` 발생. 현재 엔드포인트에서는 항상 async 컨텍스트이지만, 테스트나 유지보수 과정에서 동기 호출 시 조용히 실패할 수 있다. |
| **코드** | `self._loop = asyncio.get_running_loop()` |
| **수정 방향** | `start()`를 `async def`로 선언하거나, 호출부에서 `asyncio.get_event_loop()`로 폴백하는 guard 추가. |
| **수정 내용** | `try/except RuntimeError` 추가 — 루프 없는 환경에서 `self._loop = None` 폴백. `_push_data`가 이미 `if self._loop and self._loop.is_running()` 가드를 갖고 있어 안전. 기존 회귀 테스트도 새 동작에 맞게 업데이트. |

---

### H-4 · `routes_api.py:387-393` — 세션 수 검사와 rate limit 순서 역전 ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/routes_api.py:387–393` |
| **심각도** | HIGH |
| **문제** | `/compare` 엔드포인트는 `active_count + model_count > MAX_SESSIONS_PER_CLIENT` 검사를 먼저 하고 `_check_rate_limit()`를 나중에 호출한다. Rate limit를 우회한 공격자가 세션 한도 검사도 동시에 통과하면 의도보다 많은 세션을 생성할 수 있다. 일반 세션 생성(`/api/sessions`)은 반대 순서(rate limit → 세션 한도)로 되어 있어 불일치. |
| **수정 방향** | `_check_rate_limit()` 호출을 세션 수 검사 앞으로 이동. |
| **수정 내용** | `_check_rate_limit(client_ip)` 호출을 `model_count` 계산 바로 다음으로 이동, 세션 한도 검사보다 먼저 실행되도록 순서 변경. |

---

## MEDIUM (코드 품질 / 유지보수성)

### M-1 · `routes_api.py:23-24` — 중복 import ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/routes_api.py:23–24` |
| **심각도** | MEDIUM |
| **문제** | `import app.state as _state`가 연속으로 두 번 선언되어 있다. 런타임에는 무해하지만 코드 관리 실수를 나타낸다. |
| **수정 방향** | 중복 행 제거. |
| **수정 내용** | 중복 import 행 제거. 동시에 `import logging` 추가 (M-2 묶음 처리). |

---

### M-2 · `routes_api.py:48` — 비정상 logger 초기화 패턴 ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/routes_api.py:48` |
| **심각도** | MEDIUM |
| **문제** | `logger = __import__('logging').getLogger("session-manager")`는 동작하지만 비관용적(non-idiomatic) 패턴이다. `logging`은 이미 표준 import 방식이 있으며, 다른 모듈은 모두 `import logging` 후 `logging.getLogger()`를 사용한다. |
| **수정 방향** | 최상단에 `import logging` 추가 후 `logger = logging.getLogger("session-manager")` 로 교체. |
| **수정 내용** | `import logging` 추가 + `logger = logging.getLogger(__name__)` 로 교체. routes_ws.py도 동일하게 정상화. |

---

### M-3 · `main.py` — 사용하지 않는 stale import 다수 ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/main.py` (전반) |
| **심각도** | MEDIUM |
| **문제** | 모노리스 분리 후 `main.py`에 `shlex`, `shutil`, `string`, `subprocess`, `threading`, `uuid`, `collections.deque`, `FastAPI.WebSocket`, `FastAPI.Query`, `FastAPI.UploadFile` 등 이제 사용하지 않는 import들이 남아 있다. re-export 목적의 import와 실제 stale import가 혼재하여 가독성 저하. |
| **수정 방향** | 실제 `main.py` 내부에서 사용하는 것만 남기고 re-export 필요 항목은 명시적 주석으로 구분. |
| **수정 내용** | stdlib 12개 (`shlex`, `shutil`, `signal`, `string`, `subprocess`, `sys`, `threading`, `time`(유지), `uuid`, `deque`, `datetime`, `Path`, `Optional`) + FastAPI 8개 + pydantic 2개 + 사용 안 하는 app.models Pydantic 모델 전체 제거. Re-export 항목은 `# re-exported for tests` 주석으로 명시. |

---

### M-4 · `models.py` — 모듈 import 시 환경 부작용 ✅ ADDRESSED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/models.py:33–42` (추정) |
| **심각도** | MEDIUM |
| **문제** | `.env` 파일 로드 및 `os.environ.setdefault()` 호출이 모듈 레벨(import 시)에 실행된다. 테스트에서 환경 변수를 `monkeypatch.setenv`로 설정하더라도 이미 module import가 일어났다면 효과가 없을 수 있다. |
| **수정 방향** | 환경 변수 로딩을 `lifespan` 또는 별도 `config.py`로 이동. 또는 `_load_env()` 함수로 래핑해 명시적 호출. |
| **수정 내용** | `.env` 로딩은 `setdefault`를 사용하므로 이미 설정된 env var를 덮지 않는다 — by design. 모듈 레벨 상수(`MAX_SESSIONS_PER_CLIENT` 등)는 `monkeypatch.setattr`로 패치 가능. 설계 의도를 명확히 하는 주석 추가. |

---

### M-5 · `pipeline_store.py` — 매 DB 작업마다 새 커넥션 생성 ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/pipeline_store.py` (전반) |
| **심각도** | MEDIUM |
| **문제** | `create_run`, `update_stage`, `save_checkpoint` 등 모든 함수가 `sqlite3.connect()` → 작업 → `conn.close()` 패턴을 반복한다. 파이프라인이 고빈도로 체크포인트를 저장할 때 커넥션 생성 오버헤드가 누적된다. |
| **수정 방향** | 모듈 레벨 커넥션 풀 또는 `contextlib.contextmanager` 기반 `_get_conn()` 헬퍼로 통합. WAL 모드는 이미 설정되어 있으므로 read/write 동시성은 충분. |
| **수정 내용** | `@contextmanager _get_conn()` 추가. 모든 함수의 `conn = _connect(); try: ...; finally: conn.close()` 패턴을 `with _lock, _get_conn() as conn:` 단일 with 구문으로 통합. try/finally boilerplate 8개 제거. |

---

### M-6 · `main.py` — docstring 줄번호 stale ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/main.py:8–28` |
| **심각도** | MEDIUM |
| **문제** | 파일 상단 docstring의 "모듈 구조 맵" 줄번호(L44, L213 등)가 분리 리팩터링 이후 실제 위치와 일치하지 않는다. 코드 탐색 시 혼란 유발. |
| **수정 방향** | 분리된 모듈을 나열하는 방식으로 docstring 갱신. |
| **수정 내용** | 줄번호 기반 지도를 모듈명 기반 지도로 전면 교체. 각 모듈 파일명과 역할 설명으로 재작성. |

---

## LOW (스타일 / 마이너 개선)

### L-1 · `screen.py` — 지연 import (mss, PIL) ✅ ADDRESSED (by design)

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/screen.py` (`capture()` 메서드 내부) |
| **심각도** | LOW |
| **문제** | `mss`와 `PIL` import가 메서드 바디 내에 위치한다. 첫 캡처 호출 때까지 의존성 누락을 감지하지 못한다. |
| **수정 방향** | 파일 최상단으로 이동 (설치 안 된 경우 `ImportError`를 즉시 확인 가능). |
| **수정 내용** | `mss`/`PIL`은 optional 의존성 — 스크린 캡처 미사용 서버에 불필요한 ImportError를 막기 위해 lazy import가 의도적 설계임. 설계 의도를 명확히 하는 주석 추가. |

---

### L-2 · 로그 메시지 언어 혼재 ✅ FIXED (partial)

| 항목 | 내용 |
|------|------|
| **파일:라인** | 전체 `app/` (session.py, pipeline.py, routes_api.py 등) |
| **심각도** | LOW |
| **문제** | 로그 메시지와 주석이 한국어/영어 혼재. 프로덕션 로그 분석 도구(grep, ELK 등) 사용 시 일관성 저하. |
| **수정 방향** | 신규 코드는 영어로 통일 권장. 기존 코드는 점진적 정리. |
| **수정 내용** | `routes_api.py`, `routes_ws.py`, `pipeline.py`의 `getLogger()` 이름을 `__name__` 패턴으로 통일. 신규 추가 코드(`_tail_lines`, `_get_conn` 등)는 영어 주석으로 작성. User-facing HTTP 오류 메시지는 건드리지 않음. |

---

### L-3 · `pipeline.py:429,508` — 출력 트렁케이션 시맨틱 경계 없음 ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/pipeline.py:429`, `app/pipeline.py:508` |
| **심각도** | LOW |
| **문제** | `last_output[-3000:]`로 단순 문자 수 기준 잘라내기를 한다. 멀티바이트 문자(한국어)나 JSON 구조 중간에서 잘릴 경우 supervisor가 불완전한 컨텍스트를 받는다. |
| **수정 방향** | 줄 단위(`splitlines()`)로 잘라내기, 또는 최소 시맨틱 단위(완전한 마지막 문장) 보장. |
| **수정 내용** | `_tail_lines(text, max_chars=3000)` 헬퍼 추가. `[-3000:]` 후 첫 `\n` 위치에서 시작해 줄 경계를 보장. 두 곳(`_generate_supervisor_prompt_cli`, `_build_messages`) 모두 교체. |

---

### L-4 · `routes_api.py:881` — `any(dest_path.iterdir())` 제너레이터 누수 가능 ✅ FIXED

| 항목 | 내용 |
|------|------|
| **파일:라인** | `app/routes_api.py:881` |
| **심각도** | LOW |
| **문제** | `any(dest_path.iterdir())`는 첫 항목에서 중단하지만 제너레이터(OS 디렉터리 핸들)가 즉시 닫히지 않을 수 있다. Windows에서 디렉터리 핸들 누수 가능. |
| **수정 방향** | `next(dest_path.iterdir(), None) is not None` 또는 `bool(list(itertools.islice(dest_path.iterdir(), 1)))` 사용. |
| **수정 내용** | `any(dest_path.iterdir())` → `next(dest_path.iterdir(), None) is not None` 으로 교체. |

---

## 요약

| 심각도 | 건수 |
|--------|------|
| CRITICAL | 2 |
| HIGH | 4 |
| MEDIUM | 6 |
| LOW | 4 |
| **합계** | **16** |

### 즉시 수정 권장 (CRITICAL)
1. `session.py` — `APP_DIR` import 누락 (MCP 기능 완전 불동작)
2. `session.py` — `signal` import 누락 (Unix 환경 interrupt 불동작)

### 다음 스프린트 권장 (HIGH)
3. `routes_api.py` — 업로드 TOCTOU 레이스
4. `session.py` — UUID 재시도 무한루프 가능성
5. `shell.py` — `get_running_loop()` 가드 부재
6. `routes_api.py` — `/compare` 검사 순서 역전
