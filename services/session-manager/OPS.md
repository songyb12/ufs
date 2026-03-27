# Session Manager — 운영 가이드

## 시작/종료

```bash
# 권장: watchdog 경유 (자동 재시작)
watchdog.bat              # 콘솔 모드
watchdog.bat --headless   # 백그라운드 모드 (start-headless.bat과 동일)

# 직접 실행 (watchdog 없이, 죽으면 수동 재시작 필요)
start.bat
```

## watchdog 동작

- 서버 crash 또는 외부 kill 시 **5초 후 자동 재시작**
- `exit code 0` (정상 종료) → watchdog도 같이 종료
- 60초 내 5번 연속 crash → rapid restart 감지 → 포기
- 로그: `data/logs/watchdog.log` (headless 모드)

## 알려진 위험: `taskkill //F //IM python.exe`

세션에서 다른 Python 서비스(ImageGen 등)를 재시작할 때 이 명령을 사용하면
**모든 Python 프로세스가 죽음** — session-manager 포함.

### 안전한 대안
```bash
# ImageGen만 죽이기 (gui.py 프로세스만 대상)
wmic process where "CommandLine like '%%gui.py%%'" call terminate 2>nul

# 또는 포트 기반 (ImageGen이 특정 포트를 사용하는 경우)
for /f "tokens=5" %a in ('netstat -ano ^| findstr :7860') do taskkill /F /PID %a
```

watchdog이 활성화되어 있으면 전체 kill 후에도 session-manager가 자동 복구되지만,
**세션 내 진행 중인 작업은 중단됨** (파이프라인 interrupted 처리).

## 포트

| 서비스 | 포트 |
|--------|------|
| Session Manager | 8006 |

## 데이터 디렉토리 구조

```
data/
├── sessions/          # 세션 상태 파일 (*.json) — 서버 재시작 시 복원
├── logs/              # CLI 실행 로그 + watchdog.log
├── uploads/           # 파일 첨부
├── screenshots/       # 스크린샷
├── pipeline_state.db  # 파이프라인 체크포인트 (SQLite)
├── projects.json      # 프로젝트 목록
└── templates.json     # 프롬프트 템플릿
```

## 세션 타입

| 타입 | 접두사 | 디스크 저장 | 복원 | 용도 |
|------|--------|-------------|------|------|
| 일반 | `claude-*` | ✅ | ✅ | 기본 세션 |
| 임시 (ephemeral) | `tmp-*` | ❌ | ❌ | 일회성 작업 |
| 비교 | `cmp-*` | ✅ | ✅ | 멀티모델 비교 (10분 TTL) |
| 감독자 | `sv-*` | ❌ | ❌ (좀비 자동삭제) | 파이프라인 supervisor |
| 작업자 | `pw-*` | ❌ | ❌ (좀비 자동삭제) | 파이프라인 worker (legacy) |

## 세션 라이프사이클

```
POST /api/sessions → ClaudeSession 생성 → worker_task 시작 → save_state()
  ↓
POST /sessions/{id}/send → 큐에 프롬프트 추가 → Claude CLI 실행 → 출력 스트리밍
  ↓
서버 종료 → lifespan shutdown → 모든 세션 kill (상태 파일 유지)
  ↓
서버 재시작 → *.json에서 세션 복원 → start_worker()
  ↓
DELETE /api/sessions/{id} → kill + 상태 파일 삭제 (remove=true, 기본값)
```

## 파이프라인 라이프사이클

```
POST /api/pipelines → PipelineRunner 생성 → 기존 세션을 worker로 바인딩
  ↓
supervisor(API/CLI)가 goal 기반 프롬프트 생성 → worker에 전달 → 출력 수집 → 피드백
  ↓
PIPELINE_DONE 또는 max_iterations 도달 → 종료
  ↓
서버 crash 시 → DB에 interrupted로 기록 → 재시작 후 수동 재개 가능
```

## 자동 정리

| 대상 | 조건 | 주기 |
|------|------|------|
| 죽은 세션 | alive=false, TTL(1h) 초과 | 5분마다 |
| cmp-* 세션 | 완료 후 10분 초과 | 5분마다 |
| 완료된 파이프라인 | completed/failed/stopped, 1h 초과 | 5분마다 |
| 좀비 세션 파일 | sv-/pw-/ev-/src-/cmp-/plan-sv- 접두사 | 서버 시작 시 |
| DB 오래된 run | completed/failed, 30일 초과 | 서버 시작 시 |

## API 인증

- 일반 API (`/api/*`): 인증 없음 (로컬 전용)
- Admin API (`/admin/*`): `X-Admin-Key` 헤더 필요 (`ADMIN_API_KEY` 환경변수)
- WebSocket: `ADMIN_API_KEY` 미설정 시 인증 비활성화

## 트러블슈팅

### 서버가 자꾸 죽음
→ `taskkill //F //IM python.exe`가 실행되고 있지 않은지 확인
→ watchdog.bat으로 시작하면 자동 복구

### 세션이 "입력 즉시 Done" 반환
→ session_uuid 만료. 코드에서 자동 감지/리셋 로직이 있음 (all_output이 비면 uuid 리셋 후 재시도)

### 좀비 세션 파일이 남음
→ 서버 시작 시 sv-/pw-/ev- 등 자동 삭제됨
→ DELETE API는 remove=true(기본값)로 상태 파일도 삭제

### 파이프라인 interrupted 레코드 대량 발생
→ `python -c "from app.pipeline_store import cleanup_interrupted_runs; cleanup_interrupted_runs()"`
→ 또는 서버 관리 UI에서 정리
