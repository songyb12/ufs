# UFS Master Core Ecosystem

## Project Overview
- Personal AI OS: MSA 설계 (각 모듈 독립 SaaS spin-off 가능)
- Core: FastAPI + Docker 마이크로서비스, 로컬 홈 서버
- Level 0 = API Gateway (master-core:8000), Level 1 = Sub-Projects

## Sub-Projects
1. **VIBE** (Investment Intelligence) — 파이프라인 구현 완료, 401 tests passing
2. **Lab-Studio / Bocchi-master** — 기타/베이스 연습 웹앱 (사업화 1순위)
3. **Engineering-Ops** — C언어 HW 검증 로그 분석 (프로토타입)
4. **Life-Master** — 루틴/일정 최적화 (기획 단계)

## Key Paths
- **UFS Shell**: `frontend/ufs-shell/src/` (React 19 + TypeScript 5.9 + Tailwind 4 + Vite 7 + React Router 7)
- VIBE 백엔드: `services/vibe/app/` (FastAPI, 30 모듈)
- VIBE 대시보드: `services/vibe/dashboard/src/` (React, 15 페이지)
- VIBE 테스트: `services/vibe/tests/`
- Bocchi-master: `frontend/bocchi-master/src/` (React 19 + TypeScript 5.9 + Tailwind 4 + Vite 7)

## Architecture Decisions
- **UFS Shell**: 통합 프론트엔드 셸 — 모노레포 라우팅 방식, 서브앱을 lazy-loaded routes로 로딩
  - Shell 구조: `shell/` (공통 레이아웃), `apps/` (서브앱별 디렉토리), `shared/` (공통 유틸)
  - 서브앱 마이그레이션 경로: placeholder → 코드 이동 → 완전 통합
- DB: SQLite per service (PostgreSQL 마이그레이션 경로 확보)
- Bocchi: React (Web Audio API + WebMIDI API)
- Network: 로컬 전용, REST only
- Docker Compose: ufs-shell:3000, bocchi-frontend:3001, master-core:8000, mcp-server:8005(SSE), vibe:8001, lab-studio:8002, eng-ops:8003, life-master:8004

## AI Techniques (구현 완료)
- **MCP Server**: `master-core/app/mcp_server.py` — Claude Desktop/Agent에서 UFS 전체 서비스 접근 (12 tools, stdio+SSE)
- **SQL-RAG**: `services/vibe/app/briefing/rag_query.py` — 자연어 → SQL → 한국어 답변 (POST /briefing/query)
- **Agentic Review**: `services/vibe/app/briefing/agent_review.py` — LLM 자율 포트폴리오 분석 (POST /briefing/agent-review)
- **Structured Output**: s7/s8/s9 _call_anthropic()에 tool_use 적용 (json.loads 제거)
- **Stock Similarity**: `services/vibe/app/indicators/similarity.py` — feature-vector cosine similarity (GET /signals/similar/{symbol})
- **Vocab Grouping**: `services/life-master/app/services/vocab_similarity.py` — 일본어 단어 유사도/테마 그룹핑
- 진행상황 로그: `docs/ai-techniques-progress.md`

## VIBE Auth
- ID/PW 로그인 (bcrypt + JWT), dev 계정: dev/dev1234

## User Preferences
- Engineering mindset: 추상적 비유 배제, 아키텍처/로직 중심
- Fact-check first: 모르면 모른다고 명시
- Proactive: 다음 스텝 선제시
- 한국어 소통

## Bocchi-master Current Features (Batch 30 기준)
- Fretboard: SVG 렌더링, 다중 오버레이 (scale/voicing/pattern/chord-tone), auto-zoom, ghost mode, left-hand mirror
- Audio: Web Audio 메트로놈 (accent patterns, subdivision, swing, pendulum), 코드/스케일 재생
- Theory: Circle of Fifths, scale library, chord voicing DB (guitar+bass)
- Practice: 프렛보드 퀴즈, 코드 전환 타이머, 연습 기록 (export/import)
- Progression: Markov-chain 랜덤 생성, 프리셋, voicing comparison
- Rhythm: 스트럼 패턴 (arrow + notation view)
- MIDI: WebMIDI input 연동
- Settings: 튜닝 quick-switch, 다크 UI, localStorage 자동 저장
