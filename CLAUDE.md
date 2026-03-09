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
- VIBE 백엔드: `services/vibe/app/` (FastAPI, 30 모듈)
- VIBE 대시보드: `services/vibe/dashboard/src/` (React, 15 페이지)
- VIBE 테스트: `services/vibe/tests/`
- Bocchi-master: `frontend/bocchi-master/src/` (React 19 + TypeScript 5.9 + Tailwind 4 + Vite 7)

## Architecture Decisions
- DB: SQLite per service (PostgreSQL 마이그레이션 경로 확보)
- Bocchi: React (Web Audio API + WebMIDI API)
- Network: 로컬 전용, REST only
- Docker Compose: master-core:8000, vibe:8001, lab-studio:8002, eng-ops:8003, life-master:8004, bocchi-frontend:3000

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
