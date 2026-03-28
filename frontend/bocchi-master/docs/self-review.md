# Bocchi-master 자체 검토 리포트

> 검토 일자: 2026-03-22
> 코드베이스: `frontend/bocchi-master/src/` (~22K lines, ~90 files)

---

## 1. 컴포넌트 구조 분석

### 디렉토리별 현황

| 디렉토리 | 파일 수 | 역할 |
|----------|---------|------|
| `components/backing/` | 1 | 드럼+베이스 반주 트랙 컨트롤 |
| `components/curriculum/` | 5 + 1ts | 커리큘럼 모드: 진도맵, 레슨뷰, 드릴실행, 업적, 사운드이펙트 |
| `components/fretboard/` | 5 | SVG 프렛보드, 줄, 노트 라벨, 프렛 마커, 튜닝 스위치 |
| `components/help/` | 1 | 키보드 단축키 오버레이 |
| `components/layout/` | 2 | AppShell 레이아웃, Header (악기 전환) |
| `components/metronome/` | 7 | 메트로놈 패널, BPM 슬라이더, 펜듈럼, 탭템포, 비트플래시, 템포트레이너 |
| `components/midi/` | 2 | MIDI 상태 표시, 디바이스 리스트 |
| `components/onboarding/` | 1 | 첫 실행 온보딩 위저드 |
| `components/practice/` | 7 | 연습 패널, 리듬채점, 타이머, 히스토리, 드론톤, 약점분석, 리마인더/공유 |
| `components/progression/` | 4 | 코드진행 패널, 다이어그램, 커스텀 편집, 보이싱 비교 |
| `components/rhythm/` | 2 | 스트럼 패턴 패널, 리듬 노테이션 |
| `components/scale/` | 4 | 스케일 셀렉터, 스케일 파인더, 스케일 패턴, 스케일 제안 |
| `components/theory/` | 1 | 5도권 (Circle of Fifths) |
| `components/trainer/` | 5 | 프렛보드퀴즈, 인터벌트레이너, 코드전환타이머, 코드톤드릴, 콜앤리스폰스 |
| `components/tuner/` | 1 | 크로매틱 튜너 |
| `components/ui/` | 1 | 노트 토스트 알림 |
| `components/gamification/` | 0 | (빈 디렉토리 — 게이미피케이션 로직은 `data/gamification.ts`에 존재) |
| `components/song/` | 0 | (빈 디렉토리 — 곡 플레이어 미구현) |

**합계: 49개 컴포넌트(.tsx) + 1개 유틸리티(.ts), 18개 디렉토리 (2개 빈 디렉토리)**

### 비컴포넌트 소스 파일

| 디렉토리 | 파일 수 | 총 라인 | 역할 |
|----------|---------|---------|------|
| `hooks/` | 10 | ~1,400 | 커스텀 훅 (오디오, MIDI, 메트로놈, 커리큘럼 등) |
| `utils/` | 21 | ~3,600 | 음악이론, 합성, 스케줄링, 저장소, 피치감지 |
| `data/` | 4 | ~4,300 | 커리큘럼(2,556L), 게이미피케이션, J-Pop진행, 곡DB |
| `types/` | 2 | ~33 | 음악/MIDI 타입 정의 |
| `constants/` | 2 | ~216 | 크로매틱 스케일, 악기 튜닝 |

---

## 2. App.tsx 라우팅/네비게이션 분석

### 최상위 모드 전환

```
App (1,240 lines)
├── OnboardingWizard (조건부: 첫 실행 시만)
└── AppShell
    ├── [모드 탭] 🎸 자유 연습 | 📚 커리큘럼
    ├── IF 커리큘럼 → CurriculumMode (단일 컴포넌트, 내부 라우팅)
    └── IF 자유 연습 → 26개 패널 렌더링 (아래 상세)
```

- **모드 전환**: `appMode` 상태 ('free' | 'curriculum'), localStorage에 영속화
- **온보딩**: `isOnboardingDone()` 체크 → 미완료 시 풀스크린 위저드 오버레이
- **커리큘럼 모드**: `CurriculumMode` 컴포넌트가 내부적으로 map/lesson/drill/achievements 뷰 관리

### 자유 연습 모드 — 렌더링되는 모든 패널 (26개)

패널 배치 순서 (위→아래):

```
① ScaleSelector            — 루트음 + 스케일/코드 선택
② Fretboard + 컨트롤바     — SVG 프렛보드, 라벨모드, 카포, 줄 토글 등 (15+ 컨트롤)
③ ScaleSuggestionPanel     — (조건부) 코드 위 즉흥연주 스케일 추천
④ ChordProgressionPanel    — 코드진행 프리셋, 보이싱 모드, 커스텀 편집

   ┌─────── 2열 그리드 ───────┐
   │ ⑤ MetronomePanel         │ ⑥ BackingTrackPanel    │
   │ ⑦ PracticePanel          │ ⑧ RhythmScorePanel     │
   │ ⑨ MidiStatus             │ ⑩ IntervalTrainerPanel  │
   └──────────────────────────┘

⑪ ScaleFinderPanel          — 노트 → 스케일 역검색
⑫ CircleOfFifths            — 인터랙티브 5도권
⑬ ScalePatternPanel         — CAGED 박스 패턴 오버레이

── Warm-up / Preparation ──
⑭ TunerPanel                — 크로매틱 튜너 (마이크)
⑮ DroneTonePanel            — 지속음 레퍼런스
⑯ StrumPatternPanel         — 13개 스트럼 패턴
⑰ TempoTrainerPanel         — 메트로놈 없이 템포 유지 훈련

── Drills & Exercises ──
⑱ ChordTransitionTimer      — 코드 전환 속도 훈련
⑲ ChordToneDrillPanel       — 코드톤 타깃팅 (MIDI)
⑳ CallResponsePanel         — 콜앤리스폰스 (MIDI)
㉑ FretboardQuizPanel        — 지판 노트 퀴즈
㉒ PracticeTimerPanel        — 스톱워치/카운트다운 + 일일 목표

── Analytics & Settings ──
㉓ WeaknessAnalysisPanel     — 약점 분석 대시보드
㉔ ReminderSharePanel        — 리마인더 + 성과 공유
㉕ PracticeHistoryPanel      — 연습 기록 (100세션)
㉖ ShortcutHelpOverlay       — (? 버튼 클릭 시) 단축키 도움말
```

### UI 진입점 카운트

| 카테고리 | 진입점 수 | 예시 |
|----------|-----------|------|
| 프렛보드 컨트롤바 | 15+ | 라벨모드(3), 이명동음, 고스트, 핑거링, 코드톤, 좌우손, 카포(13), 프렛범위(2), 오토줌, 줄토글(6+1) |
| 스케일/코드 선택 | 3 | 루트, 정의, 모드(scale/chord) |
| 코드 진행 | 5+ | 키, 프리셋, 코드 클릭, 보이싱 모드/소스, 최적화 토글 |
| 그리드 패널 | 6 | 메트로놈, 반주, 연습, 리듬, MIDI, 인터벌 |
| expand/collapse 패널 | 15 | ⑪~㉕ 모두 접기/펼치기 토글 |
| 모드 전환 | 2 | 자유연습, 커리큘럼 |
| **합계** | **~46개** | |

### 상태 변수 카운트

App.tsx 내 `useState` 호출: **34개 → 리팩토링 후 ~12개** (3개 커스텀 훅으로 추출: useAppSettings, useFretboardSettings, useChordProgression)

---

## 3. 기능 카테고리 분류 (사용자 관점)

### Core — 초보자가 바로 쓸 수 있는 핵심 기능

| 기능 | 패널 | 접근 방법 |
|------|------|-----------|
| 프렛보드 시각화 | Fretboard | 항상 표시 |
| 스케일/코드 선택 | ScaleSelector | 상단 드롭다운 |
| 메트로놈 | MetronomePanel | 그리드 패널 |
| 튜닝 | TunerPanel | expand/collapse |
| 온보딩 가이드 | OnboardingWizard | 첫 실행 자동 |
| 커리큘럼 학습 | CurriculumMode | 탭 전환 |
| 코드 다이어그램 | ChordDiagram | 코드 진행 내 |

### Practice — 중급자용 연습 도구

| 기능 | 패널 | 접근 방법 |
|------|------|-----------|
| 코드 진행 + 반주 | ChordProgressionPanel + BackingTrack | 항상 표시 / 그리드 |
| 코드 전환 타이머 | ChordTransitionTimer | expand/collapse |
| 스트럼 패턴 | StrumPatternPanel | expand/collapse |
| 연습 모드 (정확도) | PracticePanel | 그리드 패널 |
| 리듬 채점 | RhythmScorePanel | 그리드 패널 |
| 프렛보드 퀴즈 | FretboardQuizPanel | expand/collapse |
| 연습 타이머 | PracticeTimerPanel | expand/collapse |
| 코드톤 드릴 | ChordToneDrillPanel | expand/collapse |
| 콜앤리스폰스 | CallResponsePanel | expand/collapse |
| 드론 톤 | DroneTonePanel | expand/collapse |
| 템포 트레이너 | TempoTrainerPanel | expand/collapse |

### Advanced — 고급자/이론 학습 도구

| 기능 | 패널 | 접근 방법 |
|------|------|-----------|
| 5도권 | CircleOfFifths | expand/collapse |
| 스케일 파인더 (역검색) | ScaleFinderPanel | expand/collapse |
| 스케일 패턴 (박스) | ScalePatternPanel | expand/collapse |
| 인터벌 트레이너 | IntervalTrainerPanel | 그리드 패널 |
| 즉흥 스케일 추천 | ScaleSuggestionPanel | 조건부 자동 표시 |
| 보이싱 비교 | VoicingComparePanel | 코드 진행 내부 |
| 보이싱 최적화 (Viterbi) | 토글 | 코드 진행 설정 |
| 스케일 비교 오버레이 | 셀렉터 | 프렛보드 아래 |
| 이명동음/라벨 모드 | 버튼 | 프렛보드 컨트롤바 |

### Settings — 설정/유틸리티

| 기능 | 위치 | 접근 방법 |
|------|------|-----------|
| 악기 전환 (기타/베이스) | Header | 상단 드롭다운 |
| 튜닝 퀵스위치 | TuningQuickSwitch | 프렛보드 위 |
| 카포 설정 | 프렛보드 컨트롤바 | 숫자 셀렉터 |
| 좌우손 전환 | 프렛보드 컨트롤바 | 토글 버튼 |
| 프렛 범위 조절 | 프렛보드 컨트롤바 | 셀렉터 |
| MIDI 연결 | MidiStatus | 그리드 패널 |
| 약점 분석 | WeaknessAnalysisPanel | expand/collapse |
| 연습 기록/내보내기 | PracticeHistoryPanel | expand/collapse |
| 리마인더/공유 | ReminderSharePanel | expand/collapse |
| 키보드 단축키 | ShortcutHelpOverlay | ? 버튼 |

---

## 4. UX 문제점 식별

### 4.1 한 화면에 너무 많은 옵션이 노출되는 곳

**문제 (P0): 자유 연습 모드에 26개 패널이 동시 렌더링됨**
- 대부분 collapsed 상태이나, 헤더만으로도 26개 항목이 세로로 나열됨
- 스크롤 길이가 매우 길어짐 (모바일에서는 특히 심각)
- 위치: `App.tsx` L721-L1239, 모든 패널이 단일 `<>...</>` fragment 안에 평면적으로 배치

**문제 (P1): 프렛보드 컨트롤바에 15+ 버튼이 한 줄에 나열**
- 라벨모드(3) + 이명동음 + 고스트 + 핑거링 + 코드톤 + 좌우손 + 카포(13) + 프렛범위(2) + 오토줌 + 줄토글(7)
- 좁은 화면에서 줄바꿈되면서 레이아웃이 불안정해짐
- 위치: `App.tsx` L748-L903

**문제 (P1): 그리드 내 6개 패널이 모두 기본 펼침 상태**
- MetronomePanel, BackingTrackPanel, PracticePanel, RhythmScorePanel, MidiStatus, IntervalTrainerPanel
- 이 중 초보자에게 즉시 필요한 것은 MetronomePanel뿐
- 위치: `App.tsx` L1057-L1135

### 4.2 기능 발견이 어려운 곳 (숨겨진 기능)

**문제 (P1): 적응형 난이도가 커리큘럼 모드에서만 동작하고 UI 피드백이 미약**
- DrillRunner의 ReadyScreen에서만 배지로 표시됨
- 사용자가 "왜 BPM이 달라졌는지" 인지하기 어려움
- 위치: `DrillRunner.tsx` L232-L245

**문제 (P1): 스케일 제안(ScaleSuggestionPanel)이 조건부로만 표시됨**
- 코드 진행 활성화 + 스케일 선택이 되어야 나타남
- 즉흥연주 학습자가 이 기능의 존재를 모를 수 있음
- 위치: `App.tsx` L1017-L1023

**문제 (P2): 보이싱 비교 패널이 코드 진행 내부에 중첩**
- VoicingComparePanel은 ChordProgressionPanel 내부에서만 접근 가능
- 별도 패널로 인식되지 않음
- 위치: `components/progression/ChordProgressionPanel.tsx` 내부

**문제 (P2): 리듬 채점 활성화 방법이 직관적이지 않음**
- 메트로놈이 재생 중이어야 Start 버튼 활성화
- MIDI 연결 + 메트로놈 재생 + RhythmScorePanel Start 3단계 필요
- 위치: `components/practice/RhythmScorePanel.tsx`

### 4.3 네비게이션이 직관적이지 않은 곳

**문제 (P0): 자유 연습과 커리큘럼 사이에 기능 단절**
- 자유 연습 모드의 26개 도구 vs 커리큘럼의 구조화된 드릴이 완전 분리됨
- 커리큘럼 드릴에서 "메트로놈을 켜고 싶다"면 자유 연습으로 돌아가야 함
- 자유 연습에서 "다음에 뭘 연습해야 하지?"라는 가이드가 없음
- 위치: `App.tsx` L718-L720 (모드 분기), `CurriculumMode.tsx`

**문제 (P1): 패널 간 연관 관계가 시각적으로 표시되지 않음**
- 메트로놈 ↔ 리듬채점 ↔ 반주 트랙이 서로 의존하지만, 시각적으로 별개 패널
- 코드톤 드릴 ↔ 코드 진행이 연동되지만, 화면상 거리가 멀어서 인지 어려움
- 위치: `App.tsx` 전반

**문제 (P2): expand/collapse 패널 15개의 상태가 독립적**
- 하나를 펼치면 다른 것들이 자동으로 접히지 않음 → 동시에 여러 패널이 펼쳐지면 화면 혼잡
- 아코디언 패턴이 아닌 독립 토글 방식

### 4.4 초보자에게 압도적일 수 있는 UI 영역

**문제 (P0): 온보딩 후 자유 연습 진입 시 26개 패널 노출**
- 온보딩 위저드가 커리큘럼으로 유도할 수 있지만, "자유 연습" 선택 시 보호장치 없음
- 초보자에게 ScaleFinderPanel, CircleOfFifths, IntervalTrainerPanel 등은 불필요

**문제 (P1): App.tsx의 34개 상태 변수가 단일 컴포넌트에 집중**
- 개발 관점: 상태가 한 곳에 몰려있어 유지보수 부담
- 사용자 관점: 모든 기능이 같은 레벨에 평면적으로 배치

**문제 (P2): 프렛보드 아래 컨트롤바의 아이콘/약어가 설명 없음**
- "CT", "👻", "1234" 같은 라벨만으로는 초보자가 기능을 파악하기 어려움
- 툴팁이 일부만 존재
- 위치: `App.tsx` L748-L903

---

## 5. 개선 제안

### P0 — 즉시 해결 필요 (사용자 경험에 직접 영향)

#### P0-1: 패널 그룹화 (5개 탭/섹션) — ✅ 완료

5개 탭(진행/반주, 연습/드릴, 이론, 도구, 분석)으로 22개 패널을 그룹화. ScaleSelector + Fretboard는 탭 위에 항상 표시. `src/utils/panelConfig.ts`에 타입/상수/헬퍼 추출. 한 화면 패널 수 26개→5-6개.

#### P0-2: 난이도별 UI 프로파일 — ✅ 완료

3단계 프로파일(초급/중급/고급) 도입. 모드 헤더바에 세그먼트 버튼 배치. 패널별 최소 레벨 매핑(`PANEL_MIN_LEVEL`), 초급은 탭바 숨기고 플랫뷰(5개 패널만), 프로파일 전환 시 탭 자동전환. 초급 전용 가이드 텍스트 추가.

#### P0-3: 자유 연습 ↔ 커리큘럼 통합 강화 — ❌ 미구현

---

### P1 — 중요 개선 (사용성 + 발견성)

#### P1-1: 프렛보드 컨트롤바 2단 분리 — ✅ 완료

1단(항상 표시): Labels, #/♭, Left/Right, Frets range, Auto-zoom. 2단(접힘 가능): Ghost, Fingering, CT, Capo, Strings dim. chevron 토글로 펼침/접힘, localStorage 저장(기본 접힘).

#### P1-2: 그리드 패널 기본 접힘 — ✅ 완료

`CollapsibleSection` 래퍼 컴포넌트 신규 생성. 8개 비-collapsible 패널 래핑. 각 탭 첫 패널은 기본 펼침, 나머지 접힘. 기존 collapsible 패널 중 탭 첫 패널 3개(ScaleFinder, Tuner, WeaknessAnalysis) 기본값 true로 변경.

#### P1-3: 패널 간 연결 힌트 추가 — ❌ 미구현

#### P1-4: 프렛보드 컨트롤바 버튼에 툴팁 통일 — ❌ 미구현

---

### P2 — 점진적 개선 (완성도 향상)

#### P2-1: App.tsx 상태 분리 (리팩토링) — ✅ 완료

3개 커스텀 훅 추출: `useAppSettings` (105줄, 앱 전역 설정), `useFretboardSettings` (100줄, 프렛보드 표시 상태), `useChordProgression` (229줄, 코드 진행+보이싱+동기화). App.tsx 1,392줄→1,106줄 (-286줄, -20.5%).

#### P2-2: 빈 디렉토리 정리 — ❌ 미구현

#### P2-3: 아코디언 패턴 통일 — ❌ 미구현

#### P2-4: 모바일 반응형 최적화 — ❌ 미구현

---

## 부록: 수치 요약

| 지표 | 값 |
|------|-----|
| 총 소스 파일 | ~90개 |
| 총 코드 라인 | ~22,000 |
| 컴포넌트 수 | 49개 (.tsx) |
| 커스텀 훅 수 | 10개 |
| 유틸리티 모듈 수 | 21개 |
| App.tsx 라인 수 | 1,240 |
| App.tsx useState 수 | 34개 |
| 자유 연습 패널 수 | 26개 (동시 렌더링) |
| expand/collapse 패널 수 | 15개 |
| 프렛보드 컨트롤 버튼 수 | 15+ |
| 커리큘럼 드릴 타입 수 | 10종 |
| 곡 DB 항목 수 | 40+ |
| 업적 수 | 24+ |
| 레벨 단계 수 | 27 |
