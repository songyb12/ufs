# VIBE 2.0 — SOXL Investment Intelligence

SOXL 레버리지 ETF 투자 브리핑 서비스. 신호등(GREEN/YELLOW/RED) 기반 일일 투자 판단 보조 엔진.

## Architecture

```
Collector (yfinance, CNN F&G)
    ↓
Engine (Technical + Leverage + Macro → Signal)
    ↓
Briefing (LLM 한국어 브리핑 or Fallback 템플릿)
    ↓
FastAPI REST API ← React Dashboard
```

3레이어 파이프라인: **데이터 수집 → 시그널 엔진 → 브리핑 생성**

- 백엔드: FastAPI + SQLite(WAL) + APScheduler
- 프론트엔드: React 19 + TypeScript + Tailwind 4 + Recharts

## Features

- **실시간 신호등**: SOXL 매수/관망/매도 신호 (GREEN/YELLOW/RED)
- **LLM 한국어 브리핑**: Anthropic Claude API로 구조화된 투자 분석 생성, API key 없으면 룰 기반 fallback
- **3축 분석 엔진**:
  - Technical (40%): RSI, MACD, 볼린저밴드, 이평선
  - Leverage (30%): 괴리율(3x tracking), VIX 변동성, 일일변동성
  - Macro (30%): VIX, 금리 방향, DXY, Fear & Greed (역발상)
- **자동 스케줄링**: 장중 30분 간격 수집, 장 마감 후 일일 브리핑, 장 외 매크로 모니터링

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Python 3.12, FastAPI, SQLite (WAL mode), APScheduler |
| Data | yfinance, httpx (CNN Fear & Greed), pandas, numpy |
| AI | Anthropic Claude API (tool_use structured output) |
| Auth | JWT (python-jose + bcrypt) |
| Frontend | React 19, TypeScript, Tailwind 4, Vite, Recharts |
| Infra | Docker, nginx (reverse proxy) |

## Quick Start

### Backend

```bash
cd services/vibe2
pip install -r requirements.txt
uvicorn app.main:app --port 8010
```

### Frontend

```bash
cd services/vibe2/dashboard
npm install
npm run dev
```

### Docker

```bash
docker compose up vibe2 vibe2-dashboard
```

- Backend: http://localhost:8010
- Dashboard: http://localhost:3002

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| POST | `/auth/login` | No | JWT 토큰 발급 (dev/dev1234) |
| GET | `/signal/current` | Yes | 최신 시그널 (5분 캐시) |
| GET | `/briefing/latest` | Yes | 최신 브리핑 (없으면 자동 생성) |
| GET | `/briefing/history?days=N` | Yes | 브리핑 이력 조회 |
| POST | `/briefing/refresh` | Yes | 강제 파이프라인 재실행 |
| GET | `/data/price?symbol=SOXL&days=90` | Yes | 가격 데이터 |
| GET | `/data/macro` | Yes | 최신 매크로 지표 |

## Signal Engine Weights

```
Final Score = Technical × 0.4 + Leverage × 0.3 + Macro × 0.3

Score >= +0.3  → GREEN  (매수/홀드 유리)
-0.3 ~ +0.3   → YELLOW (관망)
Score <= -0.3  → RED    (회피 권장)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (empty) | Claude API key. 비어있으면 fallback 모드 |
| `JWT_SECRET` | `vibe2-dev-secret` | JWT 서명 키 |
| `DATABASE_URL` | `sqlite:///./vibe2.db` | SQLite DB 경로 |
| `UPDATE_INTERVAL_MINUTES` | `30` | 장중 수집 주기 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |

## Testing

```bash
cd services/vibe2
python -m pytest tests/ -v
```

42+ tests — 외부 API mock으로 네트워크 없이 실행.

## Relationship to VIBE 1.0

VIBE 2.0은 기존 VIBE 1.0(`:8001`)과 **완전 독립** 서비스.

- VIBE 1.0: 다종목 한/미 투자 파이프라인 (7단계, 2398 tests)
- VIBE 2.0: SOXL 단일 종목 특화 브리핑 엔진 (3레이어)
- DB/코드/포트 모두 분리, 병행 운영
