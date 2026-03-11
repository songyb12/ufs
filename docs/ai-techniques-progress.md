# UFS AI 테크닉 적용 — 진행상황 로그

## 프로젝트 개요
- **목표**: UFS 에코시스템에 5가지 AI 테크닉 도입
- **시작일**: 2026-03-11
- **브랜치**: `claude/analyze-repository-6OTUo`

## 테크닉 목록 및 상태

| # | 테크닉 | 상태 | 예상 공수 | 완료일 |
|---|--------|------|----------|--------|
| 1 | Structured Output (tool_use) | ✅ 완료 | 1-2일 | 2026-03-11 |
| 2 | MCP Server | ✅ 완료 | 2-3일 | 2026-03-11 |
| 3 | SQL-RAG | ✅ 완료 | 3-4일 | 2026-03-11 |
| 4 | Agentic Portfolio Review | ✅ 완료 | 4-5일 | 2026-03-11 |
| 5 | Embedding 유사도 | ✅ 완료 | 3-4일 | 2026-03-11 |

---

## 2026-03-11 (Day 1)

### 세션1 — 전체 5가지 테크닉 구현

#### #1 Structured Output (tool_use) — VIBE 파이프라인 안정화
기존 `json.loads(response.content[0].text)` 패턴 → Anthropic `tool_use` API로 교체. JSON 파싱 실패 시 silent degradation 문제 해결.

- [x] `s7_red_team.py` — `_call_anthropic()` → tool_use 패턴 적용
  - 스키마: `concern_level` (enum), `risk_flags` (array), `reasoning`, `recommended_action` (enum)
  - `tool_choice={"type": "tool", "name": "red_team_result"}` 로 스키마 보장
- [x] `s8_explanation.py` — `_call_anthropic()` → tool_use 패턴 적용
  - 동적 종목코드 키 문제 → `explanations: [{symbol, explanation}]` array로 해결, dict 변환
- [x] `s9_portfolio_scenarios.py` — `_call_anthropic()` → tool_use 패턴 적용
  - `held: [{symbol, scenario}]`, `entry: [{symbol, scenario}]` 구조
- guru.py, ai_analysis.py는 자유 텍스트 반환 → 변경 불필요로 판단

#### #2 MCP Server — master-core를 MCP 진입점으로
Claude Desktop/Agent에서 UFS 전체 서비스를 tool로 호출 가능하도록 구현.

- [x] `master-core/app/mcp_server.py` 신규 생성
  - 12개 MCP tool 정의 (VIBE 7개, Life-Master 3개, Eng-Ops 1개, System 1개)
  - stdio + SSE 듀얼 transport 지원
- [x] `master-core/mcp-config.example.json` — Claude Desktop 설정 예시
- [x] `master-core/requirements.txt`에 `mcp[cli]>=1.0.0` 추가

#### #3 SQL-RAG — VIBE 자연어 쿼리
"삼성전자 최근 RSI 추이는?" → SQL 생성 → 실행 → 한국어 답변.

- [x] `services/vibe/app/briefing/rag_query.py` 신규 생성
  - 3단계 파이프라인: generate_sql → execute_safe_sql → synthesize_answer
  - 30+ 테이블 스키마 설명을 LLM 프롬프트에 주입
  - SQL 생성 시 tool_use (`execute_sql` tool)로 구조화된 출력 보장
  - 보안: SELECT only, 28개 테이블 allowlist, LIMIT 100, users/runtime_config 접근 차단
- [x] `services/vibe/app/routers/briefing.py`에 `POST /briefing/query` 엔드포인트 추가
- [x] MCP Server에 `vibe_rag_query` tool 추가 (13개로 확장)

#### #4 Agentic Portfolio Review — 멀티스텝 자율 분석
LLM이 tool을 반복 호출(max 5회)하며 포트폴리오를 자율 분석 → 한국어 리포트.

- [x] `services/vibe/app/briefing/agent_review.py` 신규 생성
  - 8개 tool: portfolio_positions, signals_for_symbol, all_latest_signals, macro_snapshot, performance_summary, upcoming_events, exit_history, sentiment
  - Max 5 iteration agent loop (Anthropic Messages API tool_use 루프)
  - 한국어 리포트 (포트폴리오 현황, 종목 분석, 매크로, 리스크, 액션 아이템)
- [x] `services/vibe/app/routers/briefing.py`에 `POST /briefing/agent-review` 엔드포인트 추가

#### #5 Embedding 유사도 — 종목 클러스터링 + 단어 그룹핑

**VIBE** (외부 의존성 없음, 순수 Python):
- [x] `services/vibe/app/indicators/similarity.py` 신규 생성
  - Feature vector: RSI, disparity, technical_score, macro_score, raw_score, confidence + sector one-hot (23개 섹터)
  - Cosine similarity 순수 Python 구현
- [x] `services/vibe/app/routers/signals.py`에 `GET /signals/similar/{symbol}` 엔드포인트 추가

**Life-Master** (feature-based 기본 + embedding optional):
- [x] `services/life-master/app/services/vocab_similarity.py` 신규 생성
  - Feature-based: JLPT level, part of speech, tags Jaccard, 한자 문자 공유도
  - Embedding-based (optional): `paraphrase-multilingual-MiniLM-L12-v2` lazy-load
  - 테마별 단어 그룹핑 (POS + tag 기반 클러스터)
- [x] `services/life-master/app/routers/japanese.py`에 3개 엔드포인트 추가
  - `GET /vocab/{id}/similar`, `GET /vocab/{id}/similar-semantic`, `GET /vocab/groups/thematic`

#### 테스트 결과
- VIBE 기존 테스트: 1752 passed, 2 failed (기존 실패), 86 errors (numpy/pandas 미설치 환경)
- 새 코드에 의한 regression 없음

#### 파일 변경
```
수정:
  services/vibe/app/pipeline/stages/s7_red_team.py
  services/vibe/app/pipeline/stages/s8_explanation.py
  services/vibe/app/pipeline/stages/s9_portfolio_scenarios.py
  services/vibe/app/routers/briefing.py
  services/vibe/app/routers/signals.py
  services/life-master/app/routers/japanese.py
  master-core/requirements.txt

신규:
  master-core/app/mcp_server.py
  master-core/mcp-config.example.json
  services/vibe/app/briefing/rag_query.py
  services/vibe/app/briefing/agent_review.py
  services/vibe/app/indicators/similarity.py
  services/life-master/app/services/vocab_similarity.py
  docs/ai-techniques-progress.md
```

---

### 세션2 — Docker Compose + 테스트 44개

- [x] Docker Compose에 `mcp-server` 서비스 추가 (port 8005, SSE transport)
- [x] CLAUDE.md에 AI Techniques 섹션 추가
- [x] VIBE 테스트 44개 작성 및 통과
  - `test_rag_query.py`: SQL 검증/보안 테스트 23개
  - `test_similarity.py`: cosine similarity, normalize, feature vector 테스트 21개

#### 파일 변경
```
수정: docker-compose.yml, CLAUDE.md
신규: services/vibe/tests/test_rag_query.py, services/vibe/tests/test_similarity.py
```

---

### 세션3 — 프롬프트 튜닝 + 테스트 41개

#### RAG 쿼리 프롬프트 튜닝
- [x] `rag_query.py` SQL_GENERATION_SYSTEM_PROMPT에 5개 few-shot 예시 추가
  - 한국 주식 (005930 삼성전자), 미국 주식, 매크로, 포트폴리오, JOIN 쿼리

#### Agent Review 프롬프트 최적화
- [x] `agent_review.py` AGENT_SYSTEM_PROMPT 강화
  - 5단계 명시적 작업 순서 (portfolio → macro/sentiment → signals → performance → report)
  - 상세 리포트 템플릿

#### 테스트 스위트 작성 (41개)
- [x] `services/vibe/tests/test_structured_output.py` — 7개
  - S7/S8/S9 tool_use 요청 형식, 폴백, API 에러 처리
  - `patch.dict("sys.modules")` 방식으로 lazy import 모킹
- [x] `master-core/tests/test_mcp_server.py` — 16개
  - Tool definitions 검증 (필수 필드, 유니크 이름, 유효 메서드, 서비스 매핑)
  - _call_service HTTP 라우팅 (GET/POST, 파라미터 필터링, 게이트웨이 URL, 에러)
- [x] `services/life-master/tests/test_vocab_similarity.py` — 18개
  - Jaccard similarity, 문자 오버랩, feature similarity 가중치 조합

#### 파일 변경
```
수정:
  services/vibe/app/briefing/rag_query.py (프롬프트 튜닝)
  services/vibe/app/briefing/agent_review.py (프롬프트 최적화)

신규:
  services/vibe/tests/test_structured_output.py
  master-core/tests/__init__.py
  master-core/tests/test_mcp_server.py
  services/life-master/tests/__init__.py
  services/life-master/tests/test_vocab_similarity.py
```

---

### 세션4 — 테스트 실행/수정 + 최종 정리

#### 테스트 수정 및 실행
- [x] `test_structured_output.py` patch 방식 수정
  - 문제: `patch("app.pipeline.stages.s7_red_team.anthropic")` → lazy import라 모듈에 `anthropic` 속성 없음
  - 해결: `patch.dict("sys.modules", {"anthropic": mock_mod})` 방식으로 교체
  - 결과: 7/7 passed
- [x] `test_mcp_server.py` 실행 — 16/16 passed
- [x] `test_vocab_similarity.py` assertion 수정
  - 문제: `_feature_similarity(a, a)` empty tags 시 0.75인데 1.0으로 단언, `None == None` True 미고려
  - 해결: 올바른 기대값으로 수정
  - 결과: 18/18 passed

#### 전체 테스트 결과 (신규 85개 전체 통과)
| 테스트 파일 | 개수 | 상태 |
|------------|------|------|
| `test_rag_query.py` | 23 | ✅ passed |
| `test_similarity.py` | 21 | ✅ passed |
| `test_structured_output.py` | 7 | ✅ passed |
| `test_mcp_server.py` | 16 | ✅ passed |
| `test_vocab_similarity.py` | 18 | ✅ passed |

#### 커밋
- `dcf3cf7` — `feat: add prompt tuning, test suites for AI techniques (41 tests)`

---

## 세션 간 공유 컨텍스트

### 현재 아키텍처 핵심
- VIBE LLM 통합: Anthropic/OpenAI 듀얼 프로바이더 지원
- 모든 LLM 기능은 config flag로 on/off (기본 off): `LLM_RED_TEAM_ENABLED`, `LLM_EXPLANATION_ENABLED`, `LLM_SCENARIO_ENABLED`
- DB: SQLite per service, 스키마 정의: `services/vibe/app/database/schema.py`
- 테스트: VIBE 기존 1752개 + 신규 85개 = 1837개

### 의존성 변경 추적
| 패키지 | 버전 | 대상 서비스 | 상태 |
|--------|------|------------|------|
| `mcp[cli]` | >=1.0.0 | master-core | requirements.txt에 추가됨 |
| `sentence-transformers` | >=2.2.0 | Life-Master | optional (없어도 feature-based fallback) |

### 신규 API 엔드포인트 요약
| 엔드포인트 | 메서드 | 서비스 | 설명 |
|-----------|--------|--------|------|
| `/briefing/query` | POST | VIBE | SQL-RAG 자연어 쿼리 |
| `/briefing/agent-review` | POST | VIBE | Agentic 포트폴리오 리뷰 |
| `/signals/similar/{symbol}` | GET | VIBE | 유사 종목 탐색 |
| `/vocab/{id}/similar` | GET | Life-Master | Feature 기반 유사 단어 |
| `/vocab/{id}/similar-semantic` | GET | Life-Master | Embedding 기반 유사 단어 |
| `/vocab/groups/thematic` | GET | Life-Master | 테마별 단어 그룹 |

### MCP Tool 목록 (13개)
`vibe_market_briefing`, `vibe_signals`, `vibe_portfolio`, `vibe_guru_insights`, `vibe_run_pipeline`, `vibe_ai_analysis`, `vibe_rag_query`, `vibe_watchlist`, `life_dashboard`, `life_schedule_today`, `life_japanese_stats`, `engops_status`, `ufs_health`

### 남은 작업 (로컬 환경 필요)
1. Claude Desktop 실제 MCP 연동 테스트
2. LLM API 키 설정 후 end-to-end 테스트
