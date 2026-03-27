# Session Manager — Architecture & API Reference

## 개요

Claude CLI 세션을 웹 UI에서 관리하는 FastAPI 서버.
Windows 네이티브 (asyncio.subprocess + pywinpty ConPTY).

- **포트**: 8006
- **DB**: SQLite (파이프라인 체크포인트용) — `data/pipeline_state.db`
- **세션 상태**: JSON 파일 — `data/sessions/{session_id}.json`
- **로그**: `data/logs/{session_name}_{timestamp}.log`

---

## 모듈 구조 (Phase 2 분리 후)

원래 6,800줄 단일 `main.py`를 목적별 모듈로 분리:

| 모듈 | 역할 | 주요 클래스/함수 |
|------|------|----------------|
| `main.py` (~400줄) | 앱 팩토리, lifespan, 미들웨어, `/`, `/health`, WebSocket 라우트 | `lifespan`, `health`, `websocket_output`, `websocket_shell` |
| `models.py` | 경로 상수, 환경변수 기반 설정, Pydantic 모델 | `APP_DIR`, `DATA_DIR`, `LOGS_DIR`, 모든 Request 모델 |
| `state.py` | 공유 가변 상태 (프로세스 전체) | `sessions`, `pipelines`, `shell_sessions`, `plan_phases`, `CLAUDE_EXE` |
| `auth.py` | Admin 키 인증, 브라우즈 루트 허용 목록 | `verify_admin_key`, `_is_browse_allowed` |
| `session.py` (~670줄) | Claude CLI 프로세스 래퍼 + 큐 기반 실행 | `ClaudeSession`, `_check_rate_limit`, `_cleanup_dead_sessions` |
| `shell.py` | ConPTY 터미널 세션 (pywinpty) | `ShellSession`, `HAS_WINPTY` |
| `screen.py` | Windows 스크린 캡처 | `ScreenMonitor` |
| `pipeline.py` (~500줄) | 감독자-작업자 파이프라인 엔진 + 계획 수립 | `PipelineRunner`, `PlanPhase` |
| `pipeline_store.py` | SQLite 파이프라인 체크포인트 영속화 | `create_run`, `update_stage`, `save_checkpoint`, `get_resumable_runs` |
| `routes_admin.py` | `/admin/*` 엔드포인트 (인증 필요) | `admin_status`, `admin_restart`, `admin_resume` |
| `routes_api.py` (~1200줄) | `/api/*` REST 엔드포인트 전체 (62개) | 세션/파이프라인/git/shell/templates 등 |

**상태 공유 패턴**: 뮤터블 dict는 `from app.state import sessions` 방식으로 참조를 공유 (mutation은 전파됨). `bool`/`str` 같은 scalar는 `import app.state as _state`로 접근해야 live value를 읽음.

---

## 핵심 컴포넌트

### 1. ClaudeSession (`app/session.py`)

Claude CLI 프로세스를 래핑하는 세션 객체.

| 필드 | 설명 |
|------|------|
| `id` | 8자 UUID (세션 식별자) |
| `name` | 사용자 지정 이름 (기본: `claude-{id}`) |
| `work_dir` | Claude CLI 작업 디렉토리 |
| `model` | `opus` / `sonnet` / 빈 문자열(CLI 기본값) |
| `alive` | 세션 활성 여부 |
| `busy` | 현재 프롬프트 실행 중 여부 |
| `session_uuid` | Claude CLI `--continue` 용 세션 UUID |
| `pipeline_id` | 바인딩된 파이프라인 ID (없으면 None) |

**내부 동작:**
- `start_worker()` → asyncio Task로 큐 소비 루프 시작
- `send_prompt(text)` → 큐에 프롬프트 추가 → worker가 순차 처리
- worker는 `claude -p --output-format stream-json --continue {uuid}` 실행
- 출력은 `output_lines` (최대 5000줄)에 누적, WebSocket으로 실시간 전달
- `save_state()` / `load_state()` → JSON 직렬화/역직렬화

**라이프사이클:**
```
생성 → start_worker() → [send_prompt → CLI 실행 → 출력 수집]* → kill() → delete_state()
  ↕                                                                    ↕
save_state() ←──────── 서버 재시작 ────────→ load_state() → start_worker()
```

### 2. PipelineRunner (`app/pipeline.py`)

supervisor(LLM)가 worker(ClaudeSession)를 반복 구동하는 파이프라인 엔진.

| 모드 | supervisor | 특징 |
|------|-----------|------|
| `api` | Anthropic API (AsyncAnthropic) | API Key 필요, 빠름 |
| `cli` | 별도 Claude CLI (no-tools) | API Key 불필요, 로컬 전용 |

**흐름:**
```
POST /api/pipelines
    → PipelineRunner 생성
    → 기존 세션을 worker로 바인딩 (별도 pw- 세션 미생성)
    → _run_loop() 시작:
        1. supervisor에 goal + 이전 출력 전달 → 다음 프롬프트 생성
        2. PIPELINE_DONE 체크 → 있으면 완료 종료
        3. worker 세션에 프롬프트 전달
        4. worker 출력 수집 → supervisor에 피드백
        5. max_iterations 도달 시 자동 사이클 전환
    → 종료 시 supervisor 세션 kill + 파이프라인 바인딩 해제
```

**사이클 시스템:**
- `max_iterations`: 1사이클 내 최대 반복
- `max_cycles`: 최대 사이클 수
- 사이클 전환 시 iteration 리셋, supervisor retry 카운터 리셋

**영속화 (`pipeline_store.py`):**
- `create_run()` → `update_stage()` → `save_checkpoint()` → `mark_complete()`
- 서버 재시작 시 `get_resumable_runs()`로 interrupted run 감지
- `POST /admin/resume/{run_id}`로 체크포인트 기반 재개 힌트 제공

### 3. ShellSession (`app/shell.py`)

ConPTY (pywinpty) 기반 터미널 세션. cmd/powershell 지원.

### 4. PlanPhase (`app/pipeline.py`)

LLM 기반 계획 수립 엔진. 질문→답변→계획 생성→승인 흐름.

상태 머신: `questions_generating` → `questions_ready` → `plan_generating` → `plan_ready` → `approved` / `error`

### 5. ScreenMonitor (`app/screen.py`)

주기적 스크린 캡처 (mss 라이브러리). 모니터링 대시보드용.

---

## 환경변수

| 변수 | 설명 | 기본값 | 필수 |
|------|------|--------|------|
| `ADMIN_API_KEY` | `/admin/*` 엔드포인트용 비밀 키 (`X-Admin-Key` 헤더) | `""` (admin 비활성) | 권장 |
| `SERVICE_PORT` | HTTP 리슨 포트 (`__main__` 실행 시) | `8006` | — |
| `LOG_LEVEL` | 로그 레벨 (`DEBUG`/`INFO`/`WARNING`/`ERROR`) | `INFO` | — |
| `ANTHROPIC_API_KEY` | Anthropic API 키 (파이프라인 `mode=api` 시) | — | API 모드 파이프라인 |
| `LLM_API_KEY` | `ANTHROPIC_API_KEY` 폴백 별칭 | — | — |
| `MAX_SESSIONS_PER_CLIENT` | 클라이언트 IP당 최대 동시 활성 세션 수 | `10` | — |
| `ALLOW_GIT_WRITE` | `/api/git/exec`에서 쓰기 git 명령 허용 여부 | `true` | — |

---

## API 엔드포인트

### 세션 관리

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/sessions` | 전체 세션 목록 |
| GET | `/api/sessions/pending-restore` | 세션 미리보기 (복원 판단용, preview/line_count/size 포함) |
| POST | `/api/sessions` | 세션 생성 (`work_dir`, `model`, `name` 등) |
| POST | `/api/sessions/dismiss` | 세션 일괄 영구 삭제 (`session_ids[]`) |
| DELETE | `/api/sessions/{id}` | 세션 종료 (`?remove=true`면 상태 파일도 삭제) |
| POST | `/api/sessions/{id}/send` | 프롬프트 전송 |
| POST | `/api/sessions/{id}/interrupt` | 실행 중단 (SIGINT) |
| GET | `/api/sessions/{id}/output` | 출력 조회 (`?lines=200`) |
| PATCH | `/api/sessions/{id}/rename` | 세션 이름 변경 |
| PATCH | `/api/sessions/{id}/model` | 모델 변경 |
| GET | `/api/sessions/{id}/export` | 대화 내보내기 (전체 output_lines) |
| POST | `/api/sessions/{id}/fork` | 세션 복제 (대화 이어서) |
| POST | `/api/sessions/{id}/upload` | 파일 업로드 (work_dir에 저장) |
| GET | `/api/sessions/{id}/claude-md` | CLAUDE.md 읽기 |
| PUT | `/api/sessions/{id}/claude-md` | CLAUDE.md 쓰기 |

### 파이프라인

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/pipelines` | 파이프라인 시작 |
| GET | `/api/pipelines` | 전체 파이프라인 목록 |
| GET | `/api/pipelines/{id}` | 파이프라인 상태/히스토리 |
| POST | `/api/pipelines/{id}/stop` | 파이프라인 중단 |
| DELETE | `/api/pipelines/{id}` | 파이프라인 제거 (메모리에서) |
| POST | `/api/pipelines/cleanup` | 완료/실패 파이프라인 일괄 정리 |

### 계획 수립 (Plan Phase)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/plan-phases` | 계획 수립 시작 |
| GET | `/api/plan-phases` | 전체 플랜 목록 |
| GET | `/api/plan-phases/{id}` | 플랜 상태/질문/계획 |
| POST | `/api/plan-phases/{id}/answers` | 질문 답변 제출 |
| POST | `/api/plan-phases/{id}/approve` | 계획 승인 (파이프라인으로 전환) |
| POST | `/api/plan-phases/{id}/regenerate` | 계획 재생성 |
| DELETE | `/api/plan-phases/{id}` | 플랜 삭제 |

### Git 연동

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/git/status` | git status (`?path=`) |
| GET | `/api/git/log` | git log (`?path=&limit=20`) |
| GET | `/api/git/branches` | 브랜치 목록 |
| GET | `/api/git/diff` | diff (`?cached=true` for staged) |
| POST | `/api/git/exec` | git 명령 실행 (화이트리스트 검증, `ALLOW_GIT_WRITE` 제어) |
| POST | `/api/git/clone` | 저장소 클론 |
| GET | `/api/git/prs` | GitHub PR 목록 (`gh pr list`) |
| GET | `/api/git/issues` | GitHub Issue 목록 |
| GET | `/api/git/remote` | 리모트 정보 |
| GET | `/api/git/gh-auth` | GitHub CLI 인증 상태 |
| GET | `/api/git/gh-repos` | GitHub 저장소 검색 |

### Shell 터미널

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/shells` | 셸 생성 (cmd/powershell) |
| GET | `/api/shells` | 셸 목록 |
| DELETE | `/api/shells/{id}` | 셸 종료 |
| WS | `/ws/shell/{id}` | 셸 WebSocket (stdin/stdout 스트리밍) |

### 기타

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스체크 (`status`, `sessions`, `claude_cli`, `db_ok`) |
| GET | `/api/stats` | 서버 통계 |
| GET | `/api/browse` | 디렉토리 탐색 |
| GET/POST/DELETE | `/api/projects` | 프로젝트 관리 (즐겨찾기) |
| GET/POST/DELETE | `/api/templates` | 프롬프트 템플릿 CRUD |
| POST | `/api/compare` | 멀티 모델 비교 |
| WS | `/ws/{id}` | 세션 WebSocket (실시간 출력 스트리밍) |

### Admin (`X-Admin-Key` 헤더 필요)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/admin/status` | 서버 상태 + 재개 가능 파이프라인 목록 |
| POST | `/admin/restart` | 파이프라인 drain 후 `os.execv` 재시작 |
| POST | `/admin/resume/{run_id}` | 중단된 파이프라인 재개 힌트 |

### 스크린 모니터링

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/monitor/start` | 모니터링 시작 (`?interval=30`) |
| POST | `/api/monitor/stop` | 모니터링 중단 |
| GET | `/api/monitor/capture` | 즉시 캡처 |
| GET | `/api/monitor/latest` | 최근 캡처 이미지 |

---

## 서버 시작/종료 흐름

### Startup (`lifespan`)
1. Claude CLI 경로 탐색 (`find_claude_exe`) → `app.state.CLAUDE_EXE` 설정
2. `data/sessions/*.json`에서 세션 복원
   - `sv-/pw-/ev-/src-/cmp-` 접두사 = 좀비 → 자동 삭제
   - 정상 세션: `load_state()` → `start_worker()` → `sessions` dict에 등록
   - 파이프라인 바인딩 해제 (파이프라인은 메모리 전용)
3. `_cleanup_dead_sessions()` 태스크 시작 (주기적 TTL 기반 정리)
4. `get_resumable_runs()`로 중단된 파이프라인 감지 → `mark_interrupted()`

### Shutdown
1. `_state._shutting_down = True` → 신규 생성 차단
2. 모든 파이프라인 stop
3. 감독자 세션 kill
4. 작업자 세션 kill (상태 파일 유지 → 재시작 시 복원)
5. 셸 세션 kill

---

## 데이터 디렉토리 구조

```
data/
  sessions/           # 세션 상태 JSON
    {session_id}.json
  logs/               # 세션별 대화 로그 (E-3: DATA_DIR/logs로 통합)
    {session_name}_{timestamp}.log
  uploads/            # 파일 업로드 임시 저장
  screenshots/        # ScreenMonitor 캡처 이미지
  pipeline_state.db   # SQLite — 파이프라인 체크포인트
  projects.json       # 즐겨찾기 프로젝트 목록
  templates.json      # 프롬프트 템플릿
```

Docker 볼륨 마운트: `-v $(pwd)/data:/app/data` 하나로 전체 영속 데이터 커버.

---

## 패치 시 참고사항

1. **세션 상태 필드 추가 시**: `save_state()`와 `load_state()` 양쪽에 반영 필요.
   `load_state()`에서 `.get(key, default)`로 하위 호환 유지.
2. **새 API 엔드포인트 추가 시**: `routes_api.py`에 추가 + 이 문서의 해당 섹션에 업데이트.
   compat 엔드포인트(`/api/pipeline/*` → `/api/pipelines/*`)는 더 이상 추가하지 않음.
3. **파이프라인 로직 변경 시**: `pipeline_store.py` 상단 docstring의 흐름도도 업데이트.
4. **좀비 접두사 추가 시**: `lifespan`의 접두사 리스트에 반영 (`sv-`, `pw-`, `ev-`, `src-`, `cmp-`).
5. **프론트엔드 연동**: 프론트엔드는 `static/` 디렉토리에서 서빙. API 응답 스키마 변경 시 프론트 동시 수정.
6. **상태 변수 패치 시**: 테스트에서 `monkeypatch.setattr(state_module, ...)` 사용. bool/str scalar는 반드시 module reference로 접근해야 live value가 반영됨.
