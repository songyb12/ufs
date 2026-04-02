# Session Manager — 함정 & 작업 규칙

AI 보조 개발 시 반복되는 실수 패턴과 예방 규칙을 기록한다.
버그를 수정하거나 새 기능을 추가할 때 **먼저 이 파일을 읽고**, 작업 후 **새로운 교훈이 생기면 추가**한다.

---

## 1. 임포트 누락 (NameError at runtime)

**사례**: `routes_api.py`에서 `string.ascii_uppercase`를 사용했지만 `import string`이 없어 `/api/browse?path=` 가 500.
테스트는 있었지만 빈 path 케이스(드라이브 목록 코드경로)만 커버가 안 됐다.

**패턴**: 표준 라이브러리 모듈(`string`, `math`, `textwrap` 등)은 흔히 쓰이기 때문에 다른 파일에서 이미 임포트됐다고 착각하기 쉽다.

**예방**:
- 새 stdlib 함수 사용 시 해당 파일 맨 위 import 블록을 직접 확인
- 새 엔드포인트/함수 추가 후 해당 코드경로를 직접 호출하는 테스트가 있는지 확인
- `python -c "from app.routes_api import router"` 로 임포트 에러 조기 발견 가능

---

## 2. 테스트 코드경로 커버리지 공백

**사례**: `/api/browse?path=` (빈 path, Windows 드라이브 열거) 코드경로는 테스트 없음 → 버그가 490 테스트를 통과.

**패턴**: 조건 분기(`if not path`, `if sys.platform == "win32"`)로 나뉘는 코드경로 중 한쪽이 누락되는 경우.

**예방**:
- 분기가 있는 엔드포인트는 각 분기마다 테스트 케이스 1개 이상
- 새 엔드포인트 추가 시 해당 파일에 테스트 추가 (PR 단위가 아니더라도 같은 커밋에)

---

## 3. 유령 세션 (Ghost Session)

**사례**: `s1`, `sess-p-resume` — 과거 작업에서 고정 ID로 세션을 생성하고 `data/sessions/`에 persist됨. 서버 재시작마다 복원돼 UI에 표시.

**패턴**: 테스트 또는 일회성 스크립트에서 고정 ID(`"s1"`, `"test-session"`)로 실제 세션을 만들면 JSON persist 파일이 남는다.

**예방**:
- 테스트에서 `ClaudeSession` 생성 시 `ephemeral=True` 또는 UUID 기반 ID 사용
- `lifespan` 좀비 세션 필터에 테스트 ID 패턴(`^test-`, `^s\d+$`) 추가 고려
- 직접 삭제: `DELETE /api/sessions/{id}` 또는 `data/sessions/{id}.json` 삭제

---

## 4. `textContent` → `innerHTML` 전환 시 XSS

**사례**: 세션 채팅 출력을 `el.textContent`에서 `el.innerHTML`로 바꿀 때 이미지 인라인 렌더를 위해 전환.

**패턴**: 성능/기능을 위해 `textContent`를 `innerHTML`로 교체할 때 escaping이 누락되면 XSS 취약점.

**규칙**:
- `innerHTML`에 삽입되는 모든 사용자/CLI 데이터는 반드시 `escapeHtml()` 통과
- 이미지 URL은 `/uploads/` 또는 `/screenshots/` prefix 화이트리스트로만 허용
- `renderTextWithImages()` 패턴: "escape 먼저, img 태그만 후처리"

---

## 5. `supervisor_model` 기본값 drift

**사례**: `sonnet`이 여러 곳에 기본값으로 하드코딩 → `opus`로 일괄 변경 시 누락 발생 가능.

**위치 목록** (변경 시 전부 확인):
- `models.py`: `PipelineStartRequest.supervisor_model`, `PlanPhaseStartRequest.supervisor_model`
- `pipeline.py`: `PlanPhase.__init__`, `_validate_recommended` setdefault
- `pipeline_configs.py`: 4개 builtin 프리셋
- `index.html`: 감독자 모델 드롭다운 첫 번째 옵션

---

## 6. index.html 단일 파일 SPA 작업 규칙

파일이 ~4000줄이라 구조 파악이 중요.

**주요 섹션 위치** (줄 번호는 대략적):
- CSS 변수 (`:root`): 14~27번
- 탭 정의 (`tab-bar`): ~1030번
- 모달 HTML: ~1343~1460번
- WS 메시지 핸들러: ~1760번
- `switchTab()`: ~2530번
- Pipeline 함수들: ~3000번
- `renderPipelineHistory()`: ~3420번
- `escapeHtml()`, `renderTextWithImages()`: ~3500번

**규칙**:
- 새 탭 추가 시: tab-bar HTML + 컨테이너 div + `switchTab()` 분기 + hide 로직 (4곳 모두)
- `innerHTML` 사용 시 항상 `escapeHtml()` 또는 `renderTextWithImages()` 경유
- 새 JS 함수는 관련 섹션 주석(`// ─── ...`) 아래에 배치

---

## 7. 이미지 인라인 표시 — 경로 형식

**사례**: Claude가 파일을 생성 후 경로를 출력할 때 Windows 백슬래시(`data\uploads\sid\file.png`)를 사용하면 프론트엔드 정규식이 파일명 직전에서 끊겨 이미지가 렌더되지 않음. 포워드슬래시 경로(`/uploads/sid/file.png`)는 항상 정상 동작.

**수정 내용** (2026-03-30): `_IMG_PATH_RE`에서 `data[/\]uploads[/\]...` 이후 `\\` 제외 제거, `_extractImgUrl` 내부에서 백슬래시→포워드슬래시 정규화 추가. 이제 두 형식 모두 처리 가능.

**Claude에게**: 이미지 파일 생성 후 경로를 언급할 때는 `/uploads/{session_id}/{filename}` 형식을 사용하면 바로 인라인 표시됨.

---

## 8. 비원자적 파일 쓰기 (세션 손상)

**사례**: `save_state()`에서 `write_text()`를 직접 사용 → 서버 강제 종료/크래시 시 JSON 파일이 절반만 쓰여서 재시작 시 `load_state` 실패 → 세션 유실.

**패턴**: Python `Path.write_text()` / `open().write()`는 원자적이지 않음. 쓰기 도중 프로세스가 종료되면 파일이 깨진 채로 남음.

**규칙**:
- 상태 파일 저장 시 항상 `tmp → os.replace` 패턴 사용:
  ```python
  tmp = save_path.with_suffix(".json.tmp")
  tmp.write_text(json.dumps(data), encoding="utf-8")
  os.replace(tmp, save_path)
  ```
- `save_projects()`, `save_state()` 등 영속 상태 쓰기 함수에 적용

---

## 9. async 미들웨어 안에서 동기 I/O

**사례**: `add_security_headers` 미들웨어에서 `open().write()`로 access log 쓰기 → GET `/` 요청마다 이벤트 루프 블로킹.

**패턴**: FastAPI/Starlette async 미들웨어는 이벤트 루프에서 실행됨. 동기 I/O(파일, DB 등)를 직접 호출하면 모든 요청 처리가 block됨.

**규칙**:
- async 미들웨어/핸들러 안에서 동기 I/O → `asyncio.to_thread(fn, *args)` 사용
- SQLite, 파일 쓰기 등 짧지만 blocking 가능한 작업도 포함

---

## 10. git/browse 엔드포인트 경로 검증 누락

**사례**: `git_status`, `git_log`, `git_diff`, `git_branches`, `git_exec`에서 `Path(path).exists()` 만 체크하고 `_is_browse_allowed()` 미호출 → 허용 루트 밖 디렉토리(예: `C:\Windows`)에서 git 명령 실행 가능.

**패턴**: 새 경로 파라미터를 받는 엔드포인트를 추가할 때 "경로가 존재하는지"만 확인하고 "허용된 루트인지"를 빠뜨리는 경우.

**규칙**:
- 경로 파라미터를 받는 모든 엔드포인트: `_is_browse_allowed()` 필수
- git 엔드포인트는 `_check_git_path(path)` 헬퍼 함수로 통일 (존재 여부 + allowlist 검증)
- 새 경로 파라미터 엔드포인트 추가 시 체크리스트 항목 확인

---

## 11. OAuth 토큰 미상속 (독립 실행 시 인증 실패)

**사례**: 세션 매니저가 watchdog.bat으로 독립 실행됨 → Claude Desktop의 직계 자식이 아니므로 `CLAUDE_CODE_OAUTH_TOKEN` 환경변수 미상속 → CLI 실행 시 "Your organization does not have access" 에러.

**패턴**: `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1`은 Desktop IPC를 통한 토큰 주입을 의미하는데, Desktop 자식이 아닌 프로세스에서는 IPC 채널이 없어 실패. 재부팅 시마다 토큰이 갱신되므로 환경변수 고정값도 무효.

**규칙**:
- `_ENV_BLOCKLIST`에 `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST` 반드시 포함 (IPC 차단)
- `CLAUDE_CODE_OAUTH_TOKEN`이 env에 없으면 `~/.claude/.credentials.json`에서 런타임 주입
- Desktop이 꺼져 있으면 토큰 갱신 안 됨 → 장기 무인 운영 시 주의

---

## 12. "출력 없음" 에러 오분류 (UUID 만료 vs 인증 vs 네트워크)

**사례**: CLI가 인증 오류/네트워크 오류로 stdout 없이 종료 → "세션 UUID 만료 감지"로 오판 → UUID 리셋 → 재시도도 같은 이유로 실패 → "--- Done ---" 미표시 → 세션 stuck.

**패턴**: `not all_output`만으로 UUID 만료를 판단하면 인증/네트워크/기타 에러와 구분 불가.

**규칙**:
- 에러 분류 우선순위: 인증 에러 > 모델 에러 > UUID 만료 > 기타
- stderr/combined에서 인증 관련 키워드 먼저 체크 후 UUID 만료 판정
- `_run_claude` 완료 후 반드시 "--- Done ---" 보장 (정상/에러 모든 경로)
- `_process_queue`의 finally 블록에서도 "--- Done ---" 최종 보장

---

## 13. 포트 번호 하드코딩 분산 (8000 vs 8006)

**사례**: 세션 매니저 포트가 8006인데, UFS Shell의 `vite.config.ts`, `appRegistry.ts`, `ClaudeApp.tsx`, `index.html` 4곳에 8000으로 하드코딩 → iframe에서 master-core JSON이 보이거나 세션 목록이 빈 화면.

**패턴**: 포트 번호가 여러 파일에 분산 하드코딩되어 있으면 한 곳만 바꾸고 나머지를 누락.

**위치 목록** (변경 시 전부 확인):
- `frontend/ufs-shell/vite.config.ts`: `/api/claude`, `/svc/claude` 프록시 target
- `frontend/ufs-shell/src/apps/claude/ClaudeApp.tsx`: `SESSION_MANAGER_DIRECT`, 포트 표시
- `frontend/ufs-shell/src/shared/appRegistry.ts`: `port` 필드
- `services/session-manager/app/templates/index.html`: `_isDirectAccess` 포트 목록
- `frontend/ufs-shell/nginx.conf`: prod 프록시 (이건 이미 8006으로 되어있었음)

---

## 14. 인증 에러 키워드 오탐 (Claude 응답 텍스트 매칭)

**사례**: Claude가 SSH 인증, GitHub 로그인 등을 논의하면 응답에 "authentication", "login again" 등이 포함 → 인증 에러로 오판 → 불필요한 재시도 발생. 정상 응답 후 "--- Done ---" 바로 다음에 "인증 오류 감지 → 토큰 갱신 후 재시도합니다..." 가 뜨는 패턴.

**패턴**: `combined = stderr + all_output` 전체에서 키워드 검색하면 Claude 응답 내용까지 매칭됨.

**규칙**:
- 인증 에러 키워드는 **stderr만** 검사 (Claude 응답인 stdout 제외)
- 키워드를 좁게: `"authentication"` → `"authentication required"` 등 CLI 에러 메시지에만 매칭되도록
- 모든 에러 분류에서 stdout(Claude 응답)과 stderr(CLI 에러)를 구분하여 검사

---

## 작업 전 체크리스트

새 기능 추가 또는 버그 수정 전:

```
[ ] 관련 파일의 import 블록 확인 (누락된 stdlib 없는지)
[ ] 수정하는 코드경로에 테스트가 있는지 확인
[ ] index.html 수정 시: 탭/모달/switchTab 4곳 일관성 확인
[ ] innerHTML 사용 시: escapeHtml 경유 여부 확인
[ ] 모델명 기본값 변경 시: 위 5번 목록 전체 확인
[ ] 경로 파라미터 추가 시: _is_browse_allowed() 검증 포함됐는지 확인
[ ] 상태 파일 저장 시: tmp → os.replace 원자적 쓰기 사용했는지 확인
[ ] async 핸들러/미들웨어에서 동기 I/O: asyncio.to_thread 사용했는지 확인
[ ] CLI 서브프로세스 에러 처리: 인증/모델/UUID/네트워크 분류 순서 확인
[ ] _run_claude 모든 경로에서 "--- Done ---" 표시 보장 여부 확인
[ ] 포트 번호 변경 시: 위 13번 목록 전체 확인
[ ] 수정 후: python -m pytest tests/ -q 통과 확인
```
