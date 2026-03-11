# UFS AI 테크닉 적용 — 진행상황 로그

## 프로젝트 개요
- **목표**: UFS 에코시스템에 5가지 AI 테크닉 도입
- **시작일**: 2026-03-11
- **플랜 파일**: `/root/.claude/plans/cheeky-wobbling-feigenbaum.md`
- **브랜치**: `claude/analyze-repository-6OTUo`

## 테크닉 목록 및 상태

| # | 테크닉 | 상태 | 예상 공수 | 시작일 | 완료일 |
|---|--------|------|----------|--------|--------|
| 1 | Structured Output (tool_use) | ✅ 완료 | 1-2일 | 2026-03-11 | 2026-03-11 |
| 2 | MCP Server | ✅ 완료 | 2-3일 | 2026-03-11 | 2026-03-11 |
| 3 | SQL-RAG | ✅ 완료 | 3-4일 | 2026-03-11 | 2026-03-11 |
| 4 | Agentic Portfolio Review | ✅ 완료 | 4-5일 | 2026-03-11 | 2026-03-11 |
| 5 | Embedding 유사도 | ✅ 완료 | 3-4일 | 2026-03-11 | 2026-03-11 |

---

## Day 1 — 2026-03-11

### 전체 5가지 테크닉 구현 완료

#### #1 Structured Output (tool_use) — VIBE 파이프라인 안정화
- [x] `s7_red_team.py` — `_call_anthropic()` → tool_use 패턴 적용
  - 스키마: `concern_level` (enum), `risk_flags` (array), `reasoning`, `recommended_action` (enum)
  - `json.loads()` 제거, `tool_choice={"type": "tool"}` 로 스키마 보장
- [x] `s8_explanation.py` — `_call_anthropic()` → tool_use 패턴 적용
  - 동적 종목코드 키 → `explanations: [{symbol, explanation}]` array로 변환
- [x] `s9_portfolio_scenarios.py` — `_call_anthropic()` → tool_use 패턴 적용
  - `held: [{symbol, scenario}]`, `entry: [{symbol, scenario}]` 구조
- guru.py, ai_analysis.py는 자유 텍스트 반환 → 변경 불필요

#### #2 MCP Server — master-core를 MCP 서버로
- [x] `master-core/app/mcp_server.py` 신규 생성
  - 12개 MCP tool 정의 (VIBE 8개, Life-Master 3개, System 1개)
  - stdio + SSE 듀얼 transport 지원
  - `master-core/mcp-config.example.json` 예시 설정
  - `master-core/requirements.txt`에 `mcp[cli]>=1.0.0` 추가

#### #3 SQL-RAG — VIBE 자연어 쿼리
- [x] `services/vibe/app/briefing/rag_query.py` 신규 생성
  - 30+ 테이블 스키마 설명을 LLM 프롬프트에 주입
  - SQL 생성 시 tool_use로 구조화된 출력 보장
  - 보안: SELECT only, 테이블 allowlist, LIMIT 100, users 테이블 접근 차단
  - 3단계 파이프라인: generate_sql → execute_safe_sql → synthesize_answer
- [x] `services/vibe/app/routers/briefing.py`에 `POST /briefing/query` 엔드포인트 추가
- [x] MCP Server에 `vibe_rag_query` tool 추가

#### #4 Agentic Portfolio Review — 멀티스텝 분석
- [x] `services/vibe/app/briefing/agent_review.py` 신규 생성
  - 8개 tool 정의 (portfolio, signals, macro, performance, events, exits, sentiment)
  - Max 5 iteration agent loop
  - Anthropic Messages API tool_use 루프 구현
  - 한국어 리포트 생성 (포트폴리오 현황, 종목 분석, 매크로, 리스크, 액션 아이템)
- [x] `services/vibe/app/routers/briefing.py`에 `POST /briefing/agent-review` 엔드포인트 추가

#### #5 Embedding 유사도 — 종목 클러스터링 + 단어 그룹핑
- [x] **VIBE**: `services/vibe/app/indicators/similarity.py` 신규 생성
  - Feature vector: RSI, disparity, technical_score, macro_score, raw_score, confidence + sector one-hot
  - Cosine similarity (순수 Python, 외부 의존성 없음)
  - `GET /signals/similar/{symbol}` 엔드포인트 추가
- [x] **Life-Master**: `services/life-master/app/services/vocab_similarity.py` 신규 생성
  - Feature-based: JLPT level, part of speech, tags, 한자 공유도
  - Embedding-based (optional): sentence-transformers 설치 시 활성화
  - 테마별 단어 그룹핑 기능
  - 3개 엔드포인트 추가: `/vocab/{id}/similar`, `/vocab/{id}/similar-semantic`, `/vocab/groups/thematic`

### 테스트 결과
- VIBE: 1752 passed, 2 failed (기존 실패), 86 errors (numpy/pandas 미설치 환경)
- 새 코드에 의한 regression 없음

### 파일 변경 목록
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

## 세션 간 공유 컨텍스트

### 현재 아키텍처 핵심
- VIBE LLM 통합: 5개 파일에서 Anthropic/OpenAI 듀얼 프로바이더 지원
- 모든 LLM 기능은 config flag로 on/off (기본 off): `LLM_RED_TEAM_ENABLED`, `LLM_EXPLANATION_ENABLED`, `LLM_SCENARIO_ENABLED`
- DB: SQLite (`services/vibe/vibe.db`), 스키마 정의: `services/vibe/app/database/schema.py`
- 테스트: 1752개 통과 중 (VIBE, numpy/pandas 제외 환경)

### 의존성 변경 추적
| 패키지 | 버전 | 추가 시점 | 대상 서비스 | 상태 |
|--------|------|----------|------------|------|
| `mcp[cli]` | >=1.0.0 | #2 MCP | master-core | requirements.txt에 추가됨 |
| `sentence-transformers` | >=2.2.0 | #5 Embedding | Life-Master | optional (없어도 feature-based fallback) |

### 다음 단계 (향후 세션)
1. ~~Docker Compose에 MCP SSE 서비스 추가 (port 8005)~~ ✅ 완료 (Day 1 세션2)
2. Claude Desktop 실제 연동 테스트
3. LLM API 키 설정 후 end-to-end 테스트
4. ~~RAG 쿼리 프롬프트 튜닝~~ ✅ 완료 (Day 1 세션3) — 5개 few-shot 예시 추가
5. ~~Agent review 프롬프트 최적화~~ ✅ 완료 (Day 1 세션3) — 5단계 작업 순서 + 리포트 템플릿
6. ~~테스트 작성 (Structured Output, MCP, Vocab Similarity)~~ ✅ 완료 (Day 1 세션3)

---

## Day 1 세션2 — 2026-03-11

### 추가 작업
- [x] Docker Compose에 `mcp-server` 서비스 추가 (port 8005, SSE transport)
- [x] VIBE 신규 테스트 44개 작성 및 통과
  - `test_rag_query.py`: SQL 검증/보안 테스트 23개
  - `test_similarity.py`: cosine similarity, normalize, feature vector 테스트 21개
- [x] CLAUDE.md에 AI Techniques 섹션 추가

### 추가 파일 변경
```
수정: docker-compose.yml, CLAUDE.md, docs/ai-techniques-progress.md
신규: services/vibe/tests/test_rag_query.py, services/vibe/tests/test_similarity.py
```

---

## Day 1 세션3 — 2026-03-11

### 프롬프트 튜닝 + 테스트 스위트 완성

#### RAG 쿼리 프롬프트 튜닝
- [x] `rag_query.py` SQL_GENERATION_SYSTEM_PROMPT에 5개 few-shot 예시 추가
  - 한국 주식 (005930 삼성전자), 미국 주식, 매크로, 포트폴리오, JOIN 쿼리 등

#### Agent Review 프롬프트 최적화
- [x] `agent_review.py` AGENT_SYSTEM_PROMPT 강화
  - 5단계 명시적 작업 순서 (portfolio → macro/sentiment → signals → performance → report)
  - 상세 리포트 템플릿 (포트폴리오 현황, 시장 환경, 종목 분석, 리스크 플래그, 액션 아이템)

#### 테스트 스위트 작성 (총 41개 신규 테스트)
- [x] `services/vibe/tests/test_structured_output.py` — 7개 테스트
  - S7: tool_use 요청 형식, no-tool-block 폴백, API 에러 처리
  - S8: array→dict 변환, tool schema name 검증
  - S9: held/entry dict 변환, tool schema name 검증
  - mock: `patch.dict("sys.modules")` 방식으로 lazy import 우회
- [x] `master-core/tests/test_mcp_server.py` — 16개 테스트
  - Tool definitions: 필수 필드, 유니크 이름, 유효 메서드, 서비스 매핑, 스키마 구조
  - _call_service: GET/POST 라우팅, 파라미터 필터링, 게이트웨이 URL, 에러 처리
- [x] `services/life-master/tests/test_vocab_similarity.py` — 18개 테스트
  - Jaccard: 동일/이질/부분 오버랩/빈 셋
  - Char overlap: 한자 공유, 빈 문자열
  - Feature similarity: JLPT/POS/태그/문자 가중치 조합 검증

### 테스트 결과
- test_structured_output.py: 7/7 passed
- test_mcp_server.py: 16/16 passed
- test_vocab_similarity.py: 18/18 passed

### 추가 파일 변경
```
수정:
  services/vibe/app/briefing/rag_query.py (프롬프트 튜닝)
  services/vibe/app/briefing/agent_review.py (프롬프트 최적화)
  docs/ai-techniques-progress.md

신규:
  services/vibe/tests/test_structured_output.py
  master-core/tests/__init__.py
  master-core/tests/test_mcp_server.py
  services/life-master/tests/__init__.py
  services/life-master/tests/test_vocab_similarity.py
```
