# Song Chord System & UI Mode - Changelog

**작업 날짜**: 2026-03-28
**범위**: Bocchi-master 프론트엔드 + Master-Core 백엔드

---

## 변경 범위 요약

### Phase 1: Song Chord Search & Display
곡 코드 검색 시스템 (시드 데이터 + LLM 기반 AI 검색), 코드 시트 렌더링, localStorage 캐싱.

### Phase 2: Live Mode & Practice Integration
메트로놈 연동 자동 코드 진행 (Live Mode), 코드 클릭 → 프렛보드 보이싱 연결, 코드 목록 복사.

### Phase 3: Beginner/Advanced UI Mode
탭 필터링 + 페이지별 컨트롤 간소화. MetronomePanel, ScaleSelector, Fretboard 컨트롤에 beginnerMode prop 적용.

---

## 신규 생성 파일

### 프론트엔드 (8개)
| 파일 | 설명 |
|------|------|
| `src/types/song.ts` | Song, SongSection, ChordEntry 타입 정의 |
| `src/data/seedSongs.ts` | 15곡 시드 데이터 (검증된 코드 진행) |
| `src/data/songStore.ts` | localStorage CRUD (시드 + 유저 + LLM 곡 관리) |
| `src/components/song/SongChordPage.tsx` | 곡 검색/목록 메인 페이지, 삭제 기능 |
| `src/components/song/SongSearchBar.tsx` | 검색바 (추천곡 표시, 소스 아이콘) |
| `src/components/song/ChordSheet.tsx` | 코드 시트 렌더링 (섹션 컬러, transpose, 전체화면) |
| `src/components/song/LiveMode.tsx` | 메트로놈 연동 자동 코드 진행 모드 |
| `src/utils/transpose.ts` | transpose 유틸 + `parseChordName()` 코드 파서 |

### 백엔드 (1개)
| 파일 | 설명 |
|------|------|
| `master-core/app/routers/chord_search.py` | POST /api/chord-search — Anthropic tool_use로 코드 생성 |

---

## 수정된 기존 파일 (5개)

| 파일 | 변경 내용 |
|------|-----------|
| `src/App.tsx` | Song 탭 추가, beginnerMode 상수 + 프렛보드 컨트롤 조건부 렌더링 |
| `src/utils/panelConfig.ts` | 'song' 탭 + 'songChord' 패널 등록 (beginner/intermediate/advanced 레벨) |
| `src/hooks/useAppSettings.ts` | UiMode ('beginner'\|'advanced') 시스템, effectiveProfile 오버레이 |
| `src/components/metronome/MetronomePanel.tsx` | `beginnerMode` prop — 고급 옵션 조건부 숨김 |
| `src/components/scale/ScaleSelector.tsx` | `beginnerMode` prop — 스케일/코드 화이트리스트 필터링 |

---

## 주요 기능 상세

### 1. 곡 코드 검색
- **15곡 시드 데이터**: Let It Be, Wonderwall, Hotel California 등 기타 입문 필수곡
- **AI 검색**: Anthropic Claude API (tool_use structured output)로 코드 진행 생성
- **localStorage 캐싱**: 검색 결과 자동 저장, 오프라인 재사용
- **소스 구분**: seed(✓검증), llm(✨AI), user(✎사용자) 아이콘 표시
- **삭제**: LLM/사용자 곡 삭제 가능 (시드곡은 보호)

### 2. 코드 시트
- **섹션별 컬러 코딩**: Intro(cyan), Verse(blue), Chorus(amber), Bridge(purple) 등
- **Transpose**: ±반음 조옮김 (0~±11 범위)
- **전체화면 모드**: 연습 시 집중 뷰
- **LLM 면책 표시**: AI 생성 곡에 정확도 경고 문구

### 3. 라이브 모드 (Live Mode)
- **메트로놈 연동**: useMetronome 훅 재사용, BPM/박자 자동 설정
- **자동 코드 진행**: 비트 카운트 기반 섹션 순회
- **현재 코드 하이라이트**: 활성 코드 시각적 강조
- **수동 내비게이션**: 이전/다음 코드 버튼

### 4. 연습 연동
- **코드 클릭 → 프렛보드**: parseChordName()으로 코드 파싱 → CHORDS 배열 매칭 → 보이싱 표시
- **코드 목록 복사**: 곡의 고유 코드 → 클립보드 (Chord Transition 연습용)

### 5. 초보자/고급 모드
- **탭 필터링**: beginner 레벨에서 Song/Metronome/Scale/Fretboard만 표시
- **MetronomePanel 간소화**: accent cycling, pendulum, quick tempos, click sound, subdivision, swing, tempo trainer 숨김
- **ScaleSelector 간소화**: 5개 스케일 (Major, Minor, Penta Major/Minor, Blues) + 7개 코드만 표시
- **Fretboard 간소화**: Labels(name만), auto-zoom/Row2 확장/Ghost/Fingering/ChordTones/Capo/Strings/Compare overlay 숨김
- **원칙**: `beginnerMode?: boolean` optional prop (default false), 고급 모드 100% 기존 동작 유지

---

## 백엔드 API

### POST /api/chord-search
- **요청**: `{ "query": "Let It Be", "artist": "Beatles" }`
- **응답**: Song 객체 (name, artist, key, bpm, timeSignature, sections[])
- **구현**: Anthropic Claude API + tool_use (structured output)
- **에러 처리**: `.get()` 기본값, `isinstance` 필터, try/except 래핑

---

## 알려진 제한사항

1. **LLM 코드 정확도**: AI 생성 코드 진행은 실제 곡과 다를 수 있음 (면책 문구 표시)
2. **오프라인 제한**: 네트워크 없이는 시드 데이터 15곡만 이용 가능
3. **백엔드 의존**: AI 검색은 master-core:8000 서버 실행 필요
4. **API 키 필요**: Anthropic API 키가 master-core 환경변수에 설정되어야 함
5. **코드 파싱 범위**: parseChordName()은 기본 코드 품질만 매칭 (복잡한 텐션 코드는 가장 가까운 매칭으로 폴백)
