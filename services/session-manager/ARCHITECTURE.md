# Session Manager — Architecture & Operations Spec

## Overview
Claude CLI 세션을 관리하는 FastAPI 서버. 세션 생성/삭제/복원, 파이프라인 구동, WebSocket 출력 스트리밍을 제공한다.

## Module Structure
```
app/
├── main.py          # FastAPI 앱, lifespan(시작/종료), 로깅 설정
├── session.py       # ClaudeSession — CLI 프로세스 관리, PTY I/O, 출력 파싱
├── shell.py         # ShellSession — 범용 PTY 셸 (xterm.js 연동)
├── pipeline.py      # PipelineRunner — supervisor→worker 반복 루프
├── pipeline_store.py# SQLite 기반 파이프라인 상태 영속화
├── routes_api.py    # /api/* REST endpoints
├── routes_ws.py     # WebSocket endpoints (세션 출력, 셸 PTY)
├── routes_admin.py  # /admin/* 관리 endpoints
├── models.py        # Pydantic 모델, 경로 상수, 유틸
├── state.py         # 글로벌 상태 (sessions dict, pipelines dict)
├── auth.py          # ADMIN_API_KEY 인증
├── screen.py        # ScreenMonitor (스크린샷 모니터링)
└── templates/
    └── index.html   # 웹 UI (인라인 CSS, check.js 참조)
data/
├── check.js         # 프론트엔드 JS (세션 목록, WS 연결, 출력 렌더링)
├── sessions/        # 세션 상태 JSON 파일 (재시작 시 복원)
├── logs/            # 세션별 로그 파일
└── pipeline_state.db# 파이프라인 실행 기록 (SQLite)
```

## Session Lifecycle
```
[생성] POST /api/sessions
  → ClaudeSession(id, work_dir, model) 생성
  → save_state() → data/sessions/{id}.json 저장
  → start_worker() → Claude CLI 프로세스 spawn (ConPTY)

[실행] POST /api/sessions/{id}/send
  → send_prompt(text) → PTY stdin에 텍스트 전달
  → _read_output_loop() → stdout 파싱 → output_lines[] 축적

[모니터링] WS /ws/{session_id}
  → _output_version 변경 감지 → output + output_lines JSON 전송
  → pending_question 있으면 함께 전송

[종료] DELETE /api/sessions/{id}
  → kill() → 프로세스 종료
  → remove=true(기본): delete_state() + dict에서 제거
  → remove=false: save_state()만 (재시작 시 복원 가능)
```

## Pipeline Flow
```
[시작] POST /api/pipelines
  → PipelineRunner(session, goal, supervisor_model)
  → start() → asyncio.Task 생성

[루프] _run_loop()
  1. supervisor에게 goal + last_output 전달
  2. supervisor 응답에 PIPELINE_DONE: 있으면 완료
  3. supervisor 응답을 worker CLI에 전달
  4. worker 완료 대기 (busy=False)
  5. worker 출력 수집 → supervisor에게 전달 → 반복

[종료]
  - PIPELINE_DONE → status=completed
  - 에러 → status=failed
  - 사용자 중단 → status=stopped
  - finally: supervisor 세션 정리, worker 바인딩 해제
```

## Ephemeral Session
- `ephemeral=true`로 생성 시 `save_state()` no-op, 로그 미생성
- 서버 재시작 시 복원되지 않음
- 이름 prefix: `tmp-`

## Output Rendering (Frontend)
```
Backend (routes_ws.py)
  → output: string (flat text, 하위호환)
  → output_lines: [{type, text, time}, ...] (구조화 데이터)

Frontend (check.js: renderStructuredOutput)
  → type별 HTML 블록 생성:
     system  → 파란 테두리 + ⚙ 아이콘
     tool    → 접기 가능한 details 블록 + 🔧
     error   → 빨간 테두리 + ❌
     assistant/result → [ToolName] 패턴 감지 → 인라인 하이라이트
```

## Watchdog
- `watchdog.bat` — CMD 루프로 python 프로세스 재시작
- `launcher.bat` — 전체 서비스 통합 시작 (SM + ImageGen + Docker)
- 외부 `taskkill //F //IM python.exe` 대응: watchdog이 5초 내 재시작

## Known Patterns & Gotchas
1. **외부 kill 대응**: `taskkill //F //IM python.exe`가 모든 Python 죽임 → watchdog 필수
2. **pyc 캐시**: 코드 수정 후 `__pycache__` 삭제 필요 (안 하면 이전 코드 실행)
3. **eval 잔해**: 파이프라인 대량 실행 시 DB에 interrupted 레코드, logs/에 대량 로그 축적 → 주기적 정리 필요
4. **ConPTY 특성**: Windows PTY는 ANSI escape 코드를 포함하여 출력 → 파싱 시 strip 필요
5. **WS reconnect**: 프론트엔드에서 exponential backoff (최대 5초, 10회 시도)
6. **session_uuid**: Claude CLI의 `--resume` 용 UUID. 세션 복원 시 이전 대화 이어감
