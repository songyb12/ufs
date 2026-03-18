# Bocchi-master J-Pop 커리큘럼 기반 대개편 계획

## 1. 교육 철학: "J-Pop 기타/베이스를 가르치는 선생님"

### J-Pop 음악의 특성 (왜 별도 커리큘럼이 필요한가)
J-Pop은 서양 팝/록과 근본적으로 다른 화성 구조를 가짐:
- **텐션 코드 과다**: Am7, FM7, Dm9 등 7th/9th가 기본 — 서양 팝의 트라이어드 중심과 다름
- **전조 빈번**: 한 곡에 2~3번 전조 (특히 사비 직전 반음 올림)
- **복잡한 코드 진행**: IV△7→V7→iii7→vi (소위 "왕도진행"), ii→V→I 재즈적 요소 혼합
- **리듬 특성**: 8비트/16비트 셔플, 싱코페이션, 브릿지에서 리듬 체인지
- **베이스라인**: 멜로디컬한 무빙 베이스라인 (옥타브 런, 워킹 베이스 요소)
- **기타 보이싱**: 하이 포지션 코드, 카포 활용, 아르페지오+스트럼 혼합

### 커리큘럼 구조 (6 Level)

```
Level 1: 기초 (Foundation)        — 오픈 코드, 파워 코드, 기본 스트럼
Level 2: 코드 확장 (Chord Expand)  — 바레 코드, 7th, sus, add9
Level 3: J-Pop 입문 (J-Pop Intro)  — 왕도진행, 카논진행, 기본 J-Pop 곡
Level 4: 테크닉 (Technique)       — 아르페지오, 뮤트, 하머링/풀링, 슬라이드
Level 5: 실전 (Performance)       — 풀 곡 연주, 밴드 합주 시뮬레이션
Level 6: 고급 (Advanced)          — 전조 대응, 텐션 보이싱, 즉흥 솔로
```

각 Level 내에 "Lesson → Drill → Song → Challenge" 사이클 반복

---

## 2. Gemini 구상 vs 현재 구현 상태 GAP 분석

| Gemini 구상 | 현재 Bocchi-master | GAP/결정 |
|---|---|---|
| 코드→타브/지판 동기화 | ✅ Fretboard + voicing overlay 있음 | **확장**: 시간축 스크롤 필요 |
| 운지 최적화 알고리즘 | ✅ `voicingOptimizer.ts` 존재 (voice leading) | **확장**: 손가락 번호 최적화 강화 |
| BPM 커스텀 스크롤 | ❌ 없음 (메트로놈은 있으나 스크롤 없음) | **신규**: ScrollingTab 컴포넌트 |
| 듀얼 스킨 시스템 | ❌ 다크 테마만 | **신규**: ThemeProvider + 스킨 시스템 |
| TV+모바일 연동 | 부분적 (RPi3 키오스크 계획 있음) | **후순위**: 기존 RPi3 계획과 통합 |
| 게임화 요소 | 기초적 (퀴즈, 스트릭, 별점) | **대폭 확장**: XP, 레벨, 업적, 미션 |
| J-Pop 특화 콘텐츠 | ❌ 서양 팝/재즈 프리셋만 | **핵심 신규**: J-Pop 진행/곡 DB |
| 곡 기반 학습 | ❌ 없음 | **핵심 신규**: SongPlayer 시스템 |
| 커리큘럼/레슨 시스템 | ❌ 없음 (자유 연습만) | **핵심 신규**: Curriculum 엔진 |
| 캐릭터/모딩 | ❌ 없음 | **후순위**: 스킨 시스템 안에서 |

---

## 3. 구현 계획 — Phase별 상세

### Phase 1: 커리큘럼 엔진 + J-Pop 콘텐츠 기반 (이번 세션)

**목표**: 레슨/드릴/곡 기반 학습 구조의 뼈대

#### 1-A. 데이터 모델 신규 생성

**`src/data/curriculum.ts`** — 커리큘럼 정의
```typescript
interface Curriculum {
  levels: Level[]
}
interface Level {
  id: string              // 'level-1'
  name: string            // '기초'
  nameEn: string          // 'Foundation'
  description: string
  requiredXP: number      // 이 레벨 언락에 필요한 XP
  lessons: Lesson[]
}
interface Lesson {
  id: string              // 'l1-open-chords'
  title: string
  objectives: string[]    // 학습 목표
  theory?: TheoryContent  // 이론 설명 (마크다운)
  drills: Drill[]         // 연습 과제
  songs?: SongRef[]       // 관련 곡
  unlockCondition?: UnlockCondition
}
interface Drill {
  id: string
  type: 'chord-change' | 'strum-pattern' | 'arpeggio' | 'scale-run'
       | 'fretboard-quiz' | 'rhythm' | 'ear-training' | 'song-section'
  title: string
  config: DrillConfig     // 타입별 설정 (BPM, 코드, 패턴 등)
  passCriteria: PassCriteria  // 통과 조건
  xpReward: number
}
```

**`src/data/jpopProgressions.ts`** — J-Pop 특화 코드 진행 DB
```typescript
// 기존 PROGRESSION_PRESETS 확장
const JPOP_PROGRESSIONS = [
  { name: '왕도진행 (Royal Road)',    steps: 'IV△7-V7-iii7-vi' },
  { name: '카논진행 (Canon)',         steps: 'I-V-vi-iii-IV-I-IV-V' },
  { name: '소악마진행 (Devilish)',    steps: 'IV-V-iii-vi' },
  { name: '저스트더투 (Just the Two)', steps: 'I-III7-vi-V' },
  { name: 'J-Pop Minor',             steps: 'vi-IV-V-I' },
  { name: '느와르 (Noir)',            steps: 'i-bVI-bVII-i' },
  { name: '전조 사비 (Key Change)',   steps: 'IV-V-I (→ bII:IV-V-I)' },
  // ... 10-15개 더
]
```

**`src/data/songDatabase.ts`** — 곡 데이터베이스
```typescript
interface Song {
  id: string
  title: string           // 곡명
  artist: string
  anime?: string          // 애니 출처 (있으면)
  bpm: number
  key: NoteName
  timeSignature: [number, number]
  difficulty: 1 | 2 | 3 | 4 | 5
  genre: ('jpop' | 'jrock' | 'anime' | 'city-pop')[]
  sections: SongSection[]
  tags: string[]          // 'arpegio', 'power-chord', 'fingerpicking' 등
  levelId: string         // 커리큘럼 레벨 매핑
}
interface SongSection {
  name: string            // 'intro' | 'verse' | 'chorus' | 'bridge' | 'outro'
  chords: SectionChord[]
  strumPattern?: string   // 스트럼 패턴 ref
  notes?: string          // 연주 팁
}
interface SectionChord {
  chord: string           // 'FM7', 'G7', 'Am'
  beats: number           // 몇 박자
  voicingHint?: string    // 'open', 'barre-5', 'high-pos' 등
}
```

> **저작권 주의**: 곡 DB에는 멜로디/가사 없음. 코드 진행 + 구조 정보만 저장 (코드 진행은 저작권 대상 아님)

#### 1-B. 기존 코드 확장

**`src/utils/chordProgression.ts`** 확장:
- `JPOP_PROGRESSIONS` 추가 (기존 PROGRESSION_PRESETS에 J-Pop 카테고리)
- Secondary Dominant (II7→V), Substitute Dominant (bII7) 지원
- Minor key degree system 추가 (현재 Major만 있음)

**`src/utils/voicingLibrary.ts`** 확장:
- J-Pop 특유의 하이포지션 보이싱 추가
- 카포 적용 보이싱 (capo 변환 함수)
- 텐션 코드 전용 보이싱 (△7, 9, add9 계열)

#### 1-C. UI 신규 컴포넌트

**`src/components/curriculum/`** 폴더:
- `CurriculumView.tsx` — 레벨 맵 (게임 월드맵 스타일)
- `LessonView.tsx` — 개별 레슨 (이론 + 드릴 목록)
- `DrillRunner.tsx` — 드릴 실행 엔진 (기존 컴포넌트 조합)
- `ProgressBar.tsx` — XP/레벨 진행률

**`src/components/song/`** 폴더:
- `SongBrowser.tsx` — 곡 목록/검색/필터
- `SongPlayer.tsx` — 곡 재생 뷰 (BPM 스크롤 + 지판 동기화)
- `ScrollingChordChart.tsx` — 시간축 코드 차트 (기타 히어로 스타일)

---

### Phase 2: 게이미피케이션 시스템

**`src/data/gamification.ts`**:
```typescript
interface PlayerProfile {
  xp: number
  level: number
  title: string           // RPG 칭호
  achievements: string[]  // 달성 업적 ID
  streakDays: number
  totalPracticeMinutes: number
  completedLessons: string[]
  completedSongs: string[]
  skillTree: SkillProgress[]
}
interface Achievement {
  id: string
  name: string
  nameJa?: string         // 일본어 (봇치 테마)
  description: string
  icon: string
  condition: AchievementCondition
  xpReward: number
  rarity: 'common' | 'rare' | 'epic' | 'legendary'
}
```

- XP 시스템: 드릴 완료, 곡 클리어, 연속 연습일수, 퀴즈 정답
- 레벨업: XP 누적 → 칭호 변경 (Life-Master의 27단계 시스템 참고)
- 업적: 50+ achievements (첫 코드, 첫 바레코드, 100일 연속 등)
- 일일 미션: 3개 랜덤 미션 (오늘의 코드, 오늘의 스케일, 오늘의 곡)
- 주간 챌린지: 특정 곡 마스터, 특정 테크닉 달성

---

### Phase 3: 스킨/테마 시스템

**`src/theme/`** 폴더:
```typescript
interface AppTheme {
  id: string
  name: string
  colors: ThemeColors
  fonts: ThemeFonts
  assets: ThemeAssets     // 캐릭터 이미지, 아이콘 세트
  sounds?: ThemeSounds    // UI 효과음
  uiVariant: 'standard' | 'bocchi' | 'custom'
}
```

- **Type A (Standard)**: 현재 다크 테마 기반, 깔끔한 프로 UI
- **Type B (Bocchi)**: 봇치더락 색상 팔레트, 캐릭터 요소, 핑크+네이비
- **Type C (Custom)**: 사용자 정의 색상/에셋 (향후 모딩 시스템)
- ThemeProvider Context로 전체 앱 감싸기
- CSS 변수 기반 전환 (Tailwind custom theme)

---

### Phase 4: 곡 재생 엔진 (ScrollingTab)

**핵심 신규 기능**: 기타히어로 스타일의 스크롤링 코드 차트

```
┌─────────────────────────────────────┐
│  ♩=120  Key: G                      │
│                                     │
│  [GM7] ─── [Am7] ─── [Bm7] ─── [CM7]  ← 현재 위치 하이라이트
│                                     │
│  ┌─────────────────────────────┐   │
│  │   Fretboard (실시간 보이싱)   │   │
│  └─────────────────────────────┘   │
│                                     │
│  ▶ Play  ⏸ Pause  🔄 Loop Section  │
└─────────────────────────────────────┘
```

- 메트로놈과 동기화된 코드 스크롤
- 현재 코드의 voicing이 fretboard에 실시간 표시
- 섹션 단위 루프 (verse만, chorus만 반복)
- 속도 조절 (0.5x ~ 2.0x)
- 기존 `useMetronome` + `Fretboard` + `voicingOptimizer` 조합

---

### Phase 5: 베이스 특화 모듈

현재 베이스 지원은 있으나 기타와 동일한 UX. 베이스 전용 기능:
- **루트 무빙 패턴**: 옥타브 런, 5th-root 교대, 워킹 베이스라인
- **베이스라인 생성기**: 코드 진행 → 자동 베이스라인 제안
- **슬랩 패턴 라이브러리**: 썸+팝 패턴 시각화
- **밴드 합주 모드**: 기타 백킹 + 드럼 위에 베이스 연습

---

## 4. 기존 코드 활용 매핑

| 기존 컴포넌트/유틸 | 커리큘럼에서 활용 |
|---|---|
| `Fretboard` + overlay | 모든 레슨의 지판 시각화, 드릴 시 보이싱 표시 |
| `MetronomePanel` + `useMetronome` | 드릴 BPM 제어, SongPlayer 동기화 |
| `ChordProgressionPanel` | J-Pop 진행 프리셋 확장, 레슨 코드 표시 |
| `voicingOptimizer` | 곡 재생 시 최적 보이싱 자동 선택 |
| `voicingLibrary` + CAGED | 레슨별 보이싱 제시, 난이도별 필터링 |
| `FretboardQuizPanel` | Level 1~2 드릴 (음이름 퀴즈) |
| `ChordTransitionTimer` | 드릴 타입: chord-change |
| `StrumPatternPanel` | 드릴 타입: strum-pattern |
| `IntervalTrainerPanel` | 드릴 타입: ear-training |
| `ScalePatternPanel` | Level 4+ 스케일 연습 |
| `BackingTrackPanel` | 곡 연주 시 드럼/베이스 반주 |
| `PracticeHistoryPanel` | 게이미피케이션 데이터 소스 |
| `useMidi` | MIDI 키보드 입력으로 드릴 자동 채점 |
| `storage.ts` | PlayerProfile 저장 확장 |
| `CircleOfFifths` | 이론 레슨 시각화 |

---

## 5. 구현 우선순위 (이번 세션)

### 🎯 이번 세션 목표: Phase 1 핵심 뼈대

1. **데이터 구조 정의** (~30min)
   - `src/data/curriculum.ts` — 커리큘럼/레슨/드릴 타입 정의
   - `src/data/jpopProgressions.ts` — J-Pop 코드 진행 15개+
   - `src/data/songDatabase.ts` — 곡 모델 + 샘플 5곡
   - `src/data/gamification.ts` — XP/레벨/업적 기본 구조

2. **커리큘럼 콘텐츠 작성** (~30min)
   - Level 1~6 전체 레슨 목록 (제목 + 목표 + 드릴 목록)
   - 각 레벨 3~5개 레슨, 레슨당 2~4개 드릴
   - J-Pop 곡 매핑 (레벨별 추천곡)

3. **기존 chordProgression.ts 확장** (~20min)
   - J-Pop 진행 프리셋 추가
   - Minor key degree 지원

4. **커리큘럼 UI 컴포넌트** (~40min)
   - `CurriculumView.tsx` — 레벨 선택 화면
   - `LessonView.tsx` — 레슨 상세 + 드릴 실행
   - `DrillRunner.tsx` — 기존 컴포넌트 조합으로 드릴 실행

5. **App.tsx 라우팅 확장** (~15min)
   - 모드 전환: Free Practice (현재) ↔ Curriculum Mode
   - 상단 탭 또는 사이드 네비게이션

---

## 6. 파일 구조 (최종 목표)

```
src/
├── App.tsx                        # 모드 전환 (Free/Curriculum) 추가
├── data/                          # 🆕 콘텐츠 데이터
│   ├── curriculum.ts              # 커리큘럼 구조 + Level 1~6 콘텐츠
│   ├── jpopProgressions.ts        # J-Pop 코드 진행 DB
│   ├── songDatabase.ts            # 곡 DB (코드 진행 only)
│   └── gamification.ts            # XP/레벨/업적 정의
├── components/
│   ├── curriculum/                 # 🆕 커리큘럼 UI
│   │   ├── CurriculumView.tsx     # 레벨 맵 (월드맵 스타일)
│   │   ├── LessonView.tsx         # 레슨 상세
│   │   ├── DrillRunner.tsx        # 드릴 실행 엔진
│   │   └── ProgressBar.tsx        # XP 바
│   ├── song/                      # 🆕 곡 재생 (Phase 4)
│   │   ├── SongBrowser.tsx
│   │   ├── SongPlayer.tsx
│   │   └── ScrollingChordChart.tsx
│   ├── gamification/              # 🆕 게임 요소 (Phase 2)
│   │   ├── PlayerCard.tsx
│   │   ├── AchievementPopup.tsx
│   │   └── DailyMission.tsx
│   └── (기존 components 유지)
├── theme/                          # 🆕 스킨 시스템 (Phase 3)
│   ├── ThemeProvider.tsx
│   ├── themes/
│   │   ├── standard.ts
│   │   └── bocchi.ts
│   └── types.ts
├── hooks/
│   ├── useGameProgress.ts         # 🆕 게이미피케이션 상태
│   ├── useCurriculum.ts           # 🆕 커리큘럼 진행 상태
│   └── (기존 hooks 유지)
└── utils/
    ├── chordProgression.ts        # 확장: J-Pop + Minor key
    ├── voicingLibrary.ts          # 확장: 하이포지션, 카포
    ├── basslineGenerator.ts       # 🆕 베이스라인 자동 생성 (Phase 5)
    └── (기존 utils 유지)
```

---

## 7. 비즈니스 확장 고려사항

- **프리미엄 콘텐츠**: Level 1~3 무료, Level 4~6 유료 (향후)
- **곡 팩**: 아티스트별/애니별 곡 팩 판매 가능 구조
- **커뮤니티 콘텐츠**: 사용자 제작 곡/커리큘럼 공유 (Steam 창작마당 모델)
- **스킨 마켓**: 테마/캐릭터 스킨 판매
- **데이터 구조가 이 모든 것의 기초** — 타입을 제대로 잡아야 확장 가능
