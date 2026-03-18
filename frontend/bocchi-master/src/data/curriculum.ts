/**
 * Bocchi-master Curriculum Engine
 *
 * J-Pop 기타/베이스 학습을 위한 구조화된 커리큘럼.
 * "선생님이 가르치듯" 단계적 학습 경로를 정의.
 *
 * Level 1~6, 각 레벨 3~5 레슨, 레슨당 2~4 드릴.
 * Lesson → Drill → Song → Challenge 사이클.
 */

// ─── Core Types ─────────────────────────────────────────

export interface Curriculum {
  id: string
  name: string
  description: string
  instrument: 'guitar' | 'bass' | 'both'
  levels: Level[]
}

export interface Level {
  id: string
  index: number           // 0-based
  name: string            // '기초'
  nameEn: string          // 'Foundation'
  subtitle: string        // 짧은 설명
  description: string     // 상세 설명
  requiredXP: number      // 이 레벨 언락에 필요한 누적 XP
  icon: string            // emoji or icon id
  lessons: Lesson[]
}

export interface Lesson {
  id: string
  title: string
  titleEn: string
  objectives: string[]
  theory?: TheoryContent
  drills: Drill[]
  songs?: SongRef[]
  xpReward: number        // 레슨 완료 보너스
  unlockCondition?: UnlockCondition
}

export interface TheoryContent {
  markdown: string        // 이론 설명 (한국어)
  diagrams?: string[]     // 시각 자료 참조 ID
  videoUrl?: string       // 외부 영상 링크 (선택)
}

export interface SongRef {
  songId: string
  sectionFilter?: string[]  // 특정 섹션만 연습 ['verse', 'chorus']
  note?: string             // 연습 팁
}

// ─── Drill System ───────────────────────────────────────

export type DrillType =
  | 'chord-change'      // 코드 전환 연습 (기존 ChordTransitionTimer 활용)
  | 'strum-pattern'     // 스트럼 패턴 (기존 StrumPatternPanel 활용)
  | 'arpeggio'          // 아르페지오 패턴
  | 'scale-run'         // 스케일 연습 (기존 ScalePatternPanel 활용)
  | 'fretboard-quiz'    // 지판 퀴즈 (기존 FretboardQuizPanel 활용)
  | 'rhythm'            // 리듬 정확도
  | 'ear-training'      // 음정 훈련 (기존 IntervalTrainerPanel 활용)
  | 'song-section'      // 곡의 특정 구간 연습
  | 'voicing-match'     // 보이싱 맞추기 (코드 다이어그램 보고 짚기)
  | 'progression-play'  // 코드 진행 따라 연주

export interface Drill {
  id: string
  type: DrillType
  title: string
  description: string
  config: DrillConfig
  passCriteria: PassCriteria
  xpReward: number
  estimatedMinutes: number  // 예상 소요 시간
}

export interface DrillConfig {
  // chord-change
  chords?: string[]       // ['C', 'Am', 'F', 'G']
  targetBpm?: number
  // strum-pattern
  patternName?: string    // 기존 strumPatterns.ts 참조
  // scale-run
  scaleName?: string      // 'Major Pentatonic'
  rootNote?: string       // 'A'
  position?: number       // 프렛 포지션
  // fretboard-quiz
  quizDifficulty?: 'beginner' | 'intermediate' | 'advanced'
  noteFilter?: string[]   // 특정 음만 출제
  // song-section
  songId?: string
  sectionNames?: string[] // ['verse', 'chorus']
  startBpmPercent?: number // 원래 BPM의 몇%로 시작 (50~100)
  // voicing-match
  voicingType?: string    // 'open' | 'barre' | 'high-position'
  // progression-play
  progressionName?: string // JPOP_PROGRESSIONS 참조
  key?: string
  // 공통
  bpm?: number
  durationSeconds?: number
  loopCount?: number
}

export interface PassCriteria {
  minAccuracy?: number    // 0~100
  minBpm?: number         // 최소 BPM
  minCorrectStreak?: number
  minCompletions?: number // 최소 반복 횟수
  maxTimeSeconds?: number // 시간 제한
}

export interface UnlockCondition {
  type: 'lesson-complete' | 'xp-threshold' | 'drill-pass'
  lessonIds?: string[]    // 완료 필요 레슨
  drillIds?: string[]     // 통과 필요 드릴
  minXP?: number
}

// ─── 진행 상태 (localStorage) ───────────────────────────

export interface CurriculumProgress {
  currentLevelIndex: number
  completedLessons: string[]     // lesson IDs
  completedDrills: string[]      // drill IDs
  drillBestScores: Record<string, DrillScore>  // drill ID → best score
  unlockedLevels: number[]       // unlocked level indices
}

export interface DrillScore {
  accuracy: number
  bpm?: number
  streak?: number
  completedAt: string     // ISO date
  attempts: number
}

// ─── Guitar Curriculum (J-Pop Focus) ─────────────────────

export const GUITAR_CURRICULUM: Curriculum = {
  id: 'jpop-guitar',
  name: 'J-Pop 기타 마스터',
  description: 'J-Pop을 연주하기 위한 체계적 기타 학습 커리큘럼',
  instrument: 'guitar',
  levels: [
    // ═══ LEVEL 1: 기초 ═══
    {
      id: 'level-1',
      index: 0,
      name: '기초',
      nameEn: 'Foundation',
      subtitle: '기타를 처음 잡는 당신에게',
      description: '오픈 코드, 파워 코드, 기본 스트럼 패턴을 익히고 간단한 곡을 연주합니다.',
      requiredXP: 0,
      icon: '🌱',
      lessons: [
        {
          id: 'l1-01-open-chords',
          title: '오픈 코드 기초',
          titleEn: 'Open Chord Basics',
          objectives: [
            'C, G, Am, Em, D 오픈 코드 폼 암기',
            '각 코드의 깨끗한 소리 확인',
            '코드 다이어그램 읽는 법',
          ],
          theory: {
            markdown: `## 오픈 코드란?\n\n개방현(0프렛)을 포함하는 코드입니다. 기타의 가장 기본이 되는 코드 형태로, 대부분의 J-Pop 곡에서 카포와 함께 사용됩니다.\n\n### 필수 5개 코드\n- **C** — 가장 기본, 5번줄 루트\n- **G** — 6번줄 루트, 풍성한 소리\n- **Am** — C의 관계 단조, J-Pop 필수\n- **Em** — 가장 쉬운 코드\n- **D** — 4번줄 루트, 밝은 소리`,
          },
          drills: [
            {
              id: 'd1-01-chord-shapes',
              type: 'voicing-match',
              title: '코드 폼 암기',
              description: '코드 다이어그램을 보고 정확한 포지션 기억하기',
              config: {
                chords: ['C', 'G', 'Am', 'Em', 'D'],
                voicingType: 'open',
              },
              passCriteria: { minAccuracy: 80, minCompletions: 3 },
              xpReward: 20,
              estimatedMinutes: 5,
            },
            {
              id: 'd1-01-chord-change-slow',
              type: 'chord-change',
              title: '느린 코드 체인지',
              description: 'BPM 60에서 C→Am→G→Em 전환',
              config: {
                chords: ['C', 'Am', 'G', 'Em'],
                bpm: 60,
                loopCount: 4,
              },
              passCriteria: { minBpm: 60, minCompletions: 4 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
          ],
          songs: [
            { songId: 'twinkle-star', note: '기본 C-F-G 진행으로 연습' },
          ],
          xpReward: 50,
        },
        {
          id: 'l1-02-strumming-basics',
          title: '기본 스트럼 패턴',
          titleEn: 'Basic Strumming',
          objectives: [
            '다운 스트럼 일정하게 유지',
            '다운-업 교대 스트럼',
            'BPM 80에서 안정적 리듬',
          ],
          theory: {
            markdown: `## 스트럼의 기본\n\n피킹 손(오른손)의 일관된 움직임이 핵심입니다.\n\n### 기본 규칙\n1. **다운비트**(1, 2, 3, 4)에서 다운 스트럼\n2. **업비트**(&)에서 업 스트럼\n3. 팔꿈치가 아닌 **손목**으로 스트럼\n4. 모든 줄을 균일하게 치기`,
          },
          drills: [
            {
              id: 'd1-02-all-down',
              type: 'strum-pattern',
              title: '올 다운 스트럼',
              description: 'BPM 80에서 다운 스트럼만으로 리듬 유지',
              config: {
                patternName: 'All Down',
                bpm: 80,
                durationSeconds: 60,
              },
              passCriteria: { minCompletions: 4 },
              xpReward: 20,
              estimatedMinutes: 3,
            },
            {
              id: 'd1-02-down-up',
              type: 'strum-pattern',
              title: '다운-업 스트럼',
              description: 'BPM 80에서 다운-업 교대 스트럼',
              config: {
                patternName: 'Down-Up',
                bpm: 80,
                durationSeconds: 60,
              },
              passCriteria: { minCompletions: 4 },
              xpReward: 25,
              estimatedMinutes: 3,
            },
          ],
          xpReward: 40,
        },
        {
          id: 'l1-03-power-chords',
          title: '파워 코드',
          titleEn: 'Power Chords',
          objectives: [
            '5th (파워) 코드 폼 이해',
            '6번줄/5번줄 루트 파워 코드',
            '팜 뮤트 기초',
          ],
          theory: {
            markdown: `## 파워 코드 (5th Chord)\n\n루트 + 5도만으로 구성된 코드. J-Rock/애니송에서 매우 빈번하게 사용됩니다.\n\n### 장점\n- 메이저/마이너 구분 없이 사용 가능\n- 디스토션과 궁합이 좋음\n- 이동이 쉬움 (같은 폼 이동)`,
          },
          drills: [
            {
              id: 'd1-03-power-shapes',
              type: 'voicing-match',
              title: '파워 코드 포지션',
              description: '6번줄, 5번줄 루트 파워 코드 위치 암기',
              config: {
                chords: ['E5', 'A5', 'D5', 'G5', 'B5'],
                voicingType: 'open',
              },
              passCriteria: { minAccuracy: 80 },
              xpReward: 25,
              estimatedMinutes: 5,
            },
            {
              id: 'd1-03-power-move',
              type: 'chord-change',
              title: '파워 코드 이동',
              description: 'BPM 100에서 파워 코드 이동 연습',
              config: {
                chords: ['E5', 'G5', 'A5', 'B5'],
                bpm: 100,
                loopCount: 4,
              },
              passCriteria: { minBpm: 100, minCompletions: 4 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
          ],
          songs: [
            { songId: 'simple-punk-progression', note: '파워 코드만으로 연주' },
          ],
          xpReward: 50,
        },
        {
          id: 'l1-04-fretboard-nav',
          title: '지판 이해하기',
          titleEn: 'Fretboard Navigation',
          objectives: [
            '6번줄, 5번줄 음이름 암기',
            '옥타브 관계 이해',
            '코드의 루트 위치 찾기',
          ],
          drills: [
            {
              id: 'd1-04-string6-quiz',
              type: 'fretboard-quiz',
              title: '6번줄 음이름 퀴즈',
              description: '6번줄 12프렛까지 음이름 맞추기',
              config: {
                quizDifficulty: 'beginner',
                noteFilter: ['E', 'F', 'G', 'A', 'B'],
              },
              passCriteria: { minAccuracy: 80, minCorrectStreak: 5 },
              xpReward: 25,
              estimatedMinutes: 5,
            },
            {
              id: 'd1-04-string5-quiz',
              type: 'fretboard-quiz',
              title: '5번줄 음이름 퀴즈',
              description: '5번줄 12프렛까지 음이름 맞추기',
              config: {
                quizDifficulty: 'beginner',
                noteFilter: ['A', 'B', 'C', 'D', 'E'],
              },
              passCriteria: { minAccuracy: 80, minCorrectStreak: 5 },
              xpReward: 25,
              estimatedMinutes: 5,
            },
          ],
          xpReward: 40,
        },
      ],
    },

    // ═══ LEVEL 2: 코드 확장 ═══
    {
      id: 'level-2',
      index: 1,
      name: '코드 확장',
      nameEn: 'Chord Expansion',
      subtitle: 'J-Pop의 색채를 만드는 코드들',
      description: '바레 코드, 7th, sus, add9 등 J-Pop에 필수적인 확장 코드를 익힙니다.',
      requiredXP: 300,
      icon: '🎸',
      lessons: [
        {
          id: 'l2-01-barre-chords',
          title: '바레 코드 정복',
          titleEn: 'Barre Chord Mastery',
          objectives: [
            'F 바레 코드 (6번줄 루트 E폼)',
            'Bm 바레 코드 (5번줄 루트 Am폼)',
            '바레 코드 클린 사운드 체크',
          ],
          theory: {
            markdown: `## 바레 코드: J-Pop의 관문\n\n검지로 전체 줄을 눌러 카포 역할을 합니다. J-Pop에서 F, Bm, B♭ 등이 빈번하게 등장하므로 반드시 정복해야 합니다.\n\n### 핵심 팁\n1. 검지 **옆면**으로 누르기\n2. 엄지 위치를 넥 뒤쪽 중앙에\n3. 처음엔 높은 프렛(5~7프렛)에서 연습 → 점점 낮은 프렛으로`,
          },
          drills: [
            {
              id: 'd2-01-barre-f',
              type: 'voicing-match',
              title: 'F 바레 코드',
              description: '6번줄 루트 E폼 바레 코드 연습',
              config: { chords: ['F', 'G', 'A', 'Bb'], voicingType: 'barre' },
              passCriteria: { minAccuracy: 70, minCompletions: 5 },
              xpReward: 40,
              estimatedMinutes: 10,
            },
            {
              id: 'd2-01-barre-am-form',
              type: 'voicing-match',
              title: 'Am폼 바레 코드',
              description: '5번줄 루트 Am폼 바레 코드 연습',
              config: { chords: ['Bm', 'Cm', 'Dm', 'Em'], voicingType: 'barre' },
              passCriteria: { minAccuracy: 70, minCompletions: 5 },
              xpReward: 40,
              estimatedMinutes: 10,
            },
          ],
          xpReward: 80,
        },
        {
          id: 'l2-02-seventh-chords',
          title: '세븐스 코드 — J-Pop의 색채',
          titleEn: 'Seventh Chords',
          objectives: [
            'Maj7, m7, 7th 코드 구조 이해',
            'CM7, Am7, FM7, G7 오픈 보이싱',
            '트라이어드 vs 세븐스 사운드 차이 구분',
          ],
          theory: {
            markdown: `## 세븐스 코드: J-Pop의 DNA\n\nJ-Pop이 서양 팝과 가장 다른 점이 바로 세븐스 코드의 일상적 사용입니다.\n\n### 3가지 종류\n- **Maj7** (△7): 밝고 투명한 느낌 — FM7, CM7\n- **m7**: 부드럽고 멜랑꼴리 — Am7, Dm7\n- **7th** (dominant): 긴장감, 해결 요구 — G7, C7\n\n### J-Pop에서의 활용\n거의 모든 J-Pop 곡이 7th 코드를 기본으로 사용합니다.\n일반 Pop: C → Am → F → G\nJ-Pop: CM7 → Am7 → FM7 → G7`,
          },
          drills: [
            {
              id: 'd2-02-7th-shapes',
              type: 'voicing-match',
              title: '세븐스 코드 폼',
              description: 'CM7, Am7, FM7, Dm7, G7 오픈 보이싱',
              config: { chords: ['CM7', 'Am7', 'FM7', 'Dm7', 'G7'], voicingType: 'open' },
              passCriteria: { minAccuracy: 75, minCompletions: 3 },
              xpReward: 35,
              estimatedMinutes: 8,
            },
            {
              id: 'd2-02-7th-change',
              type: 'chord-change',
              title: '세븐스 코드 체인지',
              description: 'CM7→Am7→FM7→G7 전환 (BPM 60)',
              config: { chords: ['CM7', 'Am7', 'FM7', 'G7'], bpm: 60, loopCount: 4 },
              passCriteria: { minBpm: 60, minCompletions: 4 },
              xpReward: 40,
              estimatedMinutes: 5,
            },
            {
              id: 'd2-02-ear-7th',
              type: 'ear-training',
              title: '세븐스 청음',
              description: 'Maj vs Maj7 vs m7 vs 7th 구분하기',
              config: { durationSeconds: 120 },
              passCriteria: { minAccuracy: 60 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
          ],
          xpReward: 70,
        },
        {
          id: 'l2-03-sus-add',
          title: 'sus & add 코드',
          titleEn: 'Suspended & Added Tone',
          objectives: [
            'sus2, sus4, add9 구조 이해',
            '코드 내 텐션의 역할 (해결/장식)',
            'Dsus4→D, Asus2 실전 활용',
          ],
          drills: [
            {
              id: 'd2-03-sus-shapes',
              type: 'voicing-match',
              title: 'sus/add 코드 폼',
              description: 'Dsus4, Dsus2, Asus2, Csus4, Gadd9',
              config: { chords: ['Dsus4', 'Dsus2', 'Asus2', 'Cadd9', 'Gadd9'] },
              passCriteria: { minAccuracy: 75 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
            {
              id: 'd2-03-sus-resolve',
              type: 'chord-change',
              title: 'sus → 해결 연습',
              description: 'Dsus4→D→Dsus2→D 해결 패턴',
              config: { chords: ['Dsus4', 'D', 'Dsus2', 'D'], bpm: 70 },
              passCriteria: { minBpm: 70, minCompletions: 4 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
          ],
          xpReward: 50,
        },
        {
          id: 'l2-04-capo-usage',
          title: '카포 활용법',
          titleEn: 'Capo Strategies',
          objectives: [
            '카포 원리 이해 (전조 도구)',
            'J-Pop에서 카포 위치 선택법',
            '카포 2→ 실제 키 변환',
          ],
          theory: {
            markdown: `## 카포: J-Pop 기타의 필수 아이템\n\n대부분의 J-Pop 기타 연주에서 카포를 사용합니다.\n이유: 오픈 코드 폼을 유지하면서 다양한 키로 연주 가능.\n\n### 일반적인 카포 위치\n- **카포 2**: D키 곡을 C폼으로\n- **카포 3**: Eb키 곡을 C폼으로\n- **카포 4**: E키 곡을 C폼으로\n- **카포 5**: F키 곡을 C폼으로`,
          },
          drills: [
            {
              id: 'd2-04-capo-transpose',
              type: 'fretboard-quiz',
              title: '카포 변환 퀴즈',
              description: '카포 위치에 따른 실제 키/코드 맞추기',
              config: { quizDifficulty: 'intermediate' },
              passCriteria: { minAccuracy: 70 },
              xpReward: 35,
              estimatedMinutes: 5,
            },
          ],
          xpReward: 40,
        },
      ],
    },

    // ═══ LEVEL 3: J-Pop 입문 ═══
    {
      id: 'level-3',
      index: 2,
      name: 'J-Pop 입문',
      nameEn: 'J-Pop Intro',
      subtitle: '드디어 J-Pop을 연주한다',
      description: '왕도진행, 카논진행 등 J-Pop 특유의 코드 진행을 학습하고 실제 곡을 연주합니다.',
      requiredXP: 800,
      icon: '🎵',
      lessons: [
        {
          id: 'l3-01-royal-road',
          title: '왕도진행 (Royal Road)',
          titleEn: 'The Royal Road Progression',
          objectives: [
            'IV△7→V7→iii7→vi 진행 이해',
            'Key of C: FM7→G7→Em7→Am 연습',
            'J-Pop에서 왕도진행이 쓰이는 위치 파악',
          ],
          theory: {
            markdown: `## 왕도진행 (おうどうしんこう)\n\nJ-Pop에서 가장 많이 사용되는 코드 진행입니다.\n\n### 구조: IV△7 → V7 → iii7 → vi\nKey of C: **FM7 → G7 → Em7 → Am**\nKey of G: **CM7 → D7 → Bm7 → Em**\n\n### 특징\n- 밝으면서도 약간의 멜랑꼴리\n- 사비(サビ) 전반부에 주로 사용\n- 수천 곡의 J-Pop이 이 진행을 사용\n\n### 대표곡에서의 활용\n거의 모든 아이돌/애니 OP/ED에서 찾을 수 있는 진행입니다.`,
          },
          drills: [
            {
              id: 'd3-01-royal-c',
              type: 'progression-play',
              title: '왕도진행 Key of C',
              description: 'FM7→G7→Em7→Am (BPM 70)',
              config: {
                progressionName: 'Royal Road (왕도진행)',
                key: 'C',
                bpm: 70,
                loopCount: 8,
              },
              passCriteria: { minBpm: 70, minCompletions: 8 },
              xpReward: 50,
              estimatedMinutes: 8,
            },
            {
              id: 'd3-01-royal-g',
              type: 'progression-play',
              title: '왕도진행 Key of G',
              description: 'CM7→D7→Bm7→Em (BPM 70)',
              config: {
                progressionName: 'Royal Road (왕도진행)',
                key: 'G',
                bpm: 70,
                loopCount: 8,
              },
              passCriteria: { minBpm: 70, minCompletions: 8 },
              xpReward: 50,
              estimatedMinutes: 8,
            },
          ],
          songs: [
            { songId: 'jpop-royal-road-1', note: '왕도진행 연습곡' },
          ],
          xpReward: 100,
        },
        {
          id: 'l3-02-canon-progression',
          title: '카논진행 (Canon)',
          titleEn: 'Canon Progression',
          objectives: [
            'I→V→vi→iii→IV→I→IV→V 진행',
            '파헬벨 카논의 변형 이해',
            'J-Pop 카논진행 vs 서양 카논 차이',
          ],
          drills: [
            {
              id: 'd3-02-canon-c',
              type: 'progression-play',
              title: '카논진행 Key of C',
              description: 'C→G→Am→Em→F→C→F→G (BPM 65)',
              config: {
                progressionName: 'Canon (カノン進行)',
                key: 'C',
                bpm: 65,
                loopCount: 4,
              },
              passCriteria: { minBpm: 65, minCompletions: 4 },
              xpReward: 50,
              estimatedMinutes: 8,
            },
          ],
          xpReward: 80,
        },
        {
          id: 'l3-03-minor-progressions',
          title: 'J-Pop 마이너 진행',
          titleEn: 'J-Pop Minor Progressions',
          objectives: [
            'vi→IV→V→I (소악마진행) 이해',
            'i→♭VI→♭VII→i (느와르진행)',
            '마이너 키 곡의 분위기 표현',
          ],
          drills: [
            {
              id: 'd3-03-devilish',
              type: 'progression-play',
              title: '소악마진행',
              description: 'Am→F→G→C (Key of C minor relative)',
              config: {
                progressionName: 'Devilish (小悪魔進行)',
                key: 'C',
                bpm: 70,
                loopCount: 8,
              },
              passCriteria: { minBpm: 70, minCompletions: 8 },
              xpReward: 45,
              estimatedMinutes: 8,
            },
          ],
          xpReward: 80,
        },
        {
          id: 'l3-04-first-jpop-song',
          title: '첫 J-Pop 곡 도전',
          titleEn: 'Your First J-Pop Song',
          objectives: [
            '전체 곡 구조(Intro-Verse-Chorus) 이해',
            '섹션별 연습 후 통으로 연주',
            'BPM 80%에서 시작 → 원래 속도',
          ],
          drills: [
            {
              id: 'd3-04-song-verse',
              type: 'song-section',
              title: '곡 Verse 연습',
              description: '첫 J-Pop 곡의 Verse 구간',
              config: {
                songId: 'jpop-beginner-1',
                sectionNames: ['verse'],
                startBpmPercent: 70,
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 40,
              estimatedMinutes: 10,
            },
            {
              id: 'd3-04-song-chorus',
              type: 'song-section',
              title: '곡 Chorus 연습',
              description: '첫 J-Pop 곡의 Chorus 구간',
              config: {
                songId: 'jpop-beginner-1',
                sectionNames: ['chorus'],
                startBpmPercent: 70,
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 40,
              estimatedMinutes: 10,
            },
            {
              id: 'd3-04-song-full',
              type: 'song-section',
              title: '풀 곡 도전',
              description: 'Intro→Verse→Chorus 전체 연주',
              config: {
                songId: 'jpop-beginner-1',
                startBpmPercent: 80,
              },
              passCriteria: { minCompletions: 1 },
              xpReward: 80,
              estimatedMinutes: 15,
            },
          ],
          xpReward: 120,
        },
      ],
    },

    // ═══ LEVEL 4: 테크닉 ═══
    {
      id: 'level-4',
      index: 3,
      name: '테크닉',
      nameEn: 'Technique',
      subtitle: '표현력을 높이는 기술들',
      description: '아르페지오, 뮤트, 하머링/풀링, 슬라이드 등 J-Pop 곡에 생명을 불어넣는 테크닉.',
      requiredXP: 1800,
      icon: '⚡',
      lessons: [
        {
          id: 'l4-01-arpeggio',
          title: '아르페지오 패턴',
          titleEn: 'Arpeggio Patterns',
          objectives: [
            '기본 아르페지오 패턴 3가지',
            'J-Pop 발라드 아르페지오',
            'BPM 60에서 안정적 핑거피킹',
          ],
          drills: [
            {
              id: 'd4-01-arp-basic',
              type: 'arpeggio',
              title: '기본 아르페지오',
              description: 'p-i-m-a 패턴으로 코드 분산',
              config: { chords: ['Am', 'C', 'G', 'Em'], bpm: 60, loopCount: 4 },
              passCriteria: { minCompletions: 4 },
              xpReward: 40,
              estimatedMinutes: 8,
            },
            {
              id: 'd4-01-arp-jpop',
              type: 'arpeggio',
              title: 'J-Pop 발라드 아르페지오',
              description: 'Am7→FM7→CM7→G 아르페지오 연습',
              config: { chords: ['Am7', 'FM7', 'CM7', 'G'], bpm: 65, loopCount: 4 },
              passCriteria: { minCompletions: 4 },
              xpReward: 50,
              estimatedMinutes: 10,
            },
          ],
          xpReward: 80,
        },
        {
          id: 'l4-02-muting',
          title: '뮤트 & 커팅',
          titleEn: 'Muting & Cutting',
          objectives: [
            '팜 뮤트 (Palm Mute) 테크닉',
            '브러시 뮤트 (Brush Mute/Cutting)',
            '뮤트를 활용한 리드미컬한 스트럼',
          ],
          drills: [
            {
              id: 'd4-02-palm-mute',
              type: 'strum-pattern',
              title: '팜 뮤트 스트럼',
              description: '파워 코드 + 팜 뮤트 조합',
              config: { patternName: 'All Down', bpm: 100 },
              passCriteria: { minCompletions: 4 },
              xpReward: 35,
              estimatedMinutes: 5,
            },
          ],
          xpReward: 60,
        },
        {
          id: 'l4-03-hammer-pull',
          title: '하머링 & 풀링',
          titleEn: 'Hammer-on & Pull-off',
          objectives: [
            '하머링 온 (Hammer-on) 기본',
            '풀링 오프 (Pull-off) 기본',
            '하머링/풀링 조합 리프',
          ],
          drills: [
            {
              id: 'd4-03-hammer-scale',
              type: 'scale-run',
              title: '하머링 스케일 런',
              description: 'Am 펜타토닉에서 하머링으로 상행',
              config: { scaleName: 'Minor Pentatonic', rootNote: 'A', position: 5 },
              passCriteria: { minCompletions: 4 },
              xpReward: 40,
              estimatedMinutes: 8,
            },
          ],
          xpReward: 60,
        },
        {
          id: 'l4-04-pentatonic',
          title: '펜타토닉 스케일',
          titleEn: 'Pentatonic Scale',
          objectives: [
            '마이너 펜타토닉 Box 1 암기',
            '5개 Box 연결 이해',
            'J-Pop 기타 솔로의 기본 어휘',
          ],
          drills: [
            {
              id: 'd4-04-penta-box1',
              type: 'scale-run',
              title: 'Am 펜타 Box 1',
              description: '5포지션 Am 마이너 펜타토닉',
              config: { scaleName: 'Minor Pentatonic', rootNote: 'A', position: 5 },
              passCriteria: { minCompletions: 4 },
              xpReward: 40,
              estimatedMinutes: 8,
            },
            {
              id: 'd4-04-penta-quiz',
              type: 'fretboard-quiz',
              title: '펜타토닉 음 맞추기',
              description: 'Am 펜타토닉에 속하는 음 퀴즈',
              config: { quizDifficulty: 'intermediate' },
              passCriteria: { minAccuracy: 75, minCorrectStreak: 5 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
          ],
          xpReward: 70,
        },
      ],
    },

    // ═══ LEVEL 5: 실전 ═══
    {
      id: 'level-5',
      index: 4,
      name: '실전',
      nameEn: 'Performance',
      subtitle: '곡을 처음부터 끝까지',
      description: '전체 곡 연주, 밴드 합주 시뮬레이션, 전조 대응 등 실전 연주력.',
      requiredXP: 3500,
      icon: '🎤',
      lessons: [
        {
          id: 'l5-01-full-song-easy',
          title: '실전 곡 연주 (Easy)',
          titleEn: 'Full Song Performance (Easy)',
          objectives: [
            '난이도 2 곡 3개 완주',
            '곡 구조 전체 암기',
            '원래 BPM 90% 이상으로 연주',
          ],
          drills: [
            {
              id: 'd5-01-song1',
              type: 'song-section',
              title: '실전곡 #1 풀 연주',
              description: '난이도 2 곡 전체 연주',
              config: { songId: 'jpop-easy-1', startBpmPercent: 90 },
              passCriteria: { minCompletions: 1 },
              xpReward: 100,
              estimatedMinutes: 15,
            },
          ],
          xpReward: 120,
        },
        {
          id: 'l5-02-band-sim',
          title: '밴드 합주 시뮬레이션',
          titleEn: 'Band Simulation',
          objectives: [
            '드럼+베이스 백킹과 함께 연주',
            '박자 안정성 유지',
            '다른 파트 들으면서 연주하는 연습',
          ],
          drills: [
            {
              id: 'd5-02-band-easy',
              type: 'song-section',
              title: '밴드 합주 (Easy)',
              description: '백킹 트랙과 함께 연주',
              config: { songId: 'jpop-easy-1', startBpmPercent: 100 },
              passCriteria: { minCompletions: 1 },
              xpReward: 80,
              estimatedMinutes: 15,
            },
          ],
          xpReward: 100,
        },
        {
          id: 'l5-03-key-change',
          title: '전조 대응',
          titleEn: 'Key Change Navigation',
          objectives: [
            '반음 올림 전조 (가장 흔한 J-Pop 전조)',
            '카포 이동 vs 코드폼 변경 판단',
            '전조 전후 코드 연결',
          ],
          drills: [
            {
              id: 'd5-03-halfstep-up',
              type: 'progression-play',
              title: '반음 전조 연습',
              description: 'C키 사비 → C#키 사비 전환',
              config: { bpm: 70, loopCount: 4 },
              passCriteria: { minCompletions: 4 },
              xpReward: 60,
              estimatedMinutes: 10,
            },
          ],
          xpReward: 80,
        },
      ],
    },

    // ═══ LEVEL 6: 고급 ═══
    {
      id: 'level-6',
      index: 5,
      name: '고급',
      nameEn: 'Advanced',
      subtitle: '프로의 영역',
      description: '텐션 보이싱, 즉흥 솔로, 복잡한 리듬, 고급 J-Pop 테크닉.',
      requiredXP: 6000,
      icon: '👑',
      lessons: [
        {
          id: 'l6-01-tension-voicing',
          title: '텐션 보이싱',
          titleEn: 'Tension Voicings',
          objectives: [
            '9th, 11th, 13th 텐션 이해',
            'add9, m9, Maj9 보이싱',
            'J-Pop 시티팝 스타일 보이싱',
          ],
          drills: [
            {
              id: 'd6-01-9th-voicing',
              type: 'voicing-match',
              title: '9th 코드 보이싱',
              description: 'CM9, Am9, FM9, Dm9 하이 포지션',
              config: { chords: ['CM9', 'Am9', 'FM9', 'Dm9'], voicingType: 'high-position' },
              passCriteria: { minAccuracy: 70 },
              xpReward: 50,
              estimatedMinutes: 10,
            },
          ],
          xpReward: 100,
        },
        {
          id: 'l6-02-improvisation',
          title: '즉흥 솔로 입문',
          titleEn: 'Improvisation Basics',
          objectives: [
            '코드 톤 타게팅',
            '펜타토닉 + 코드 톤 조합',
            '백킹 트랙 위에서 즉흥 연주',
          ],
          drills: [
            {
              id: 'd6-02-chord-tone',
              type: 'scale-run',
              title: '코드 톤 연습',
              description: 'ii-V-I 진행에서 코드 톤만 연주',
              config: { scaleName: 'Major', rootNote: 'C' },
              passCriteria: { minCompletions: 4 },
              xpReward: 50,
              estimatedMinutes: 10,
            },
          ],
          xpReward: 100,
        },
        {
          id: 'l6-03-advanced-rhythm',
          title: '고급 리듬',
          titleEn: 'Advanced Rhythm',
          objectives: [
            '16비트 커팅',
            '싱코페이션 패턴',
            '폴리리듬 기초 (3 over 4)',
          ],
          drills: [
            {
              id: 'd6-03-16beat',
              type: 'strum-pattern',
              title: '16비트 커팅',
              description: 'Funk 스타일 16비트 스트럼',
              config: { patternName: 'Funk 16th', bpm: 90 },
              passCriteria: { minCompletions: 4 },
              xpReward: 50,
              estimatedMinutes: 10,
            },
          ],
          xpReward: 100,
        },
      ],
    },
  ],
}

// ─── Bass Curriculum (별도 정의, Phase 5에서 확장) ──────

export const BASS_CURRICULUM: Curriculum = {
  id: 'jpop-bass',
  name: 'J-Pop 베이스 마스터',
  description: 'J-Pop을 연주하기 위한 체계적 베이스 학습 커리큘럼',
  instrument: 'bass',
  levels: [
    // ═══════════════════════════════════════════════════════
    // Level 1: 베이스 기초 — 소리를 내는 법
    // ═══════════════════════════════════════════════════════
    {
      id: 'bass-level-1',
      index: 0,
      name: '베이스 기초',
      nameEn: 'Bass Foundation',
      subtitle: '소리를 내는 법부터',
      description: '핑거 피킹, 뮤트, 루트 연주, 기본 리듬감 형성. 베이스의 역할을 이해하고 안정적인 소리를 내는 것이 목표.',
      requiredXP: 0,
      icon: '🎵',
      lessons: [
        // L1-01: 핑거 피킹 기초
        {
          id: 'bl1-01-finger-basics',
          title: '핑거 피킹 기초',
          titleEn: 'Finger Picking Basics',
          objectives: [
            '검지-중지 교대 피킹 (alternating 2-finger)',
            '일정한 음량과 톤 유지하기',
            'BPM 80에서 4비트/8비트 루트 연주',
            '각 줄 이동 시 자연스러운 피킹',
          ],
          theory: {
            markdown: `## 핑거 피킹의 기본

베이스는 **검지(i)**와 **중지(m)**를 교대로 사용하여 피킹합니다.

### 핵심 포인트
- **손가락 끝**이 아닌 **살 부분**으로 줄을 걸어 올림
- 피킹 후 다음 줄에 손가락이 **기대는(rest stroke)** 느낌
- 엄지는 픽업 위 또는 E줄 위에 고정 (anchor)
- 처음엔 느린 BPM(60~80)에서 **균일한 음량** 연습이 최우선

### 연습 순서
1. 개방현 한 줄에서 i-m 교대 (BPM 60)
2. 두 줄 이동하며 교대 (E→A, A→D)
3. 네 줄 순서대로 이동
4. BPM을 점진적으로 올리기`,
          },
          drills: [
            {
              id: 'bd1-01-open-string',
              type: 'scale-run',
              title: '개방현 교대 피킹',
              description: 'E줄에서 i-m 교대 피킹, BPM 60',
              config: { bpm: 60, durationSeconds: 120 },
              passCriteria: { minCompletions: 4 },
              xpReward: 20,
              estimatedMinutes: 4,
            },
            {
              id: 'bd1-01-string-crossing',
              type: 'scale-run',
              title: '줄 이동 피킹',
              description: 'E→A→D→G 순서로 교대 피킹, BPM 70',
              config: { bpm: 70, durationSeconds: 120 },
              passCriteria: { minCompletions: 4 },
              xpReward: 25,
              estimatedMinutes: 5,
            },
            {
              id: 'bd1-01-root-eighth',
              type: 'scale-run',
              title: '8비트 루트 연주',
              description: 'E-A-D-G 루트를 8비트로, BPM 80',
              config: { bpm: 80, durationSeconds: 120 },
              passCriteria: { minCompletions: 4 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
          ],
          xpReward: 75,
        },
        // L1-02: 뮤트와 톤 컨트롤
        {
          id: 'bl1-02-muting',
          title: '뮤트와 톤 컨트롤',
          titleEn: 'Muting & Tone Control',
          objectives: [
            '왼손 뮤트 (fret-hand muting)',
            '오른손 팜 뮤트 (palm mute)',
            '노트 간 불필요한 잡음 제거',
            '강약(다이내믹) 조절 기초',
          ],
          theory: {
            markdown: `## 뮤트 — 베이시스트의 필수 기술

"좋은 베이시스트는 **안 내는 소리**로 실력이 드러난다."

### 왼손 뮤트
- 사용하지 않는 줄에 왼손 손가락을 가볍게 올려 잡음 차단
- 특히 낮은 줄 연주 시 높은 줄의 공명을 막아야 함

### 오른손 뮤트
- 피킹 직후 손가락 또는 손바닥으로 줄 진동을 멈춤
- **스타카토**와 **레가토** 느낌을 구분하는 핵심

### 다이내믹
- 피킹 강도로 음량 조절
- 같은 음이라도 강약에 따라 그루브가 달라짐`,
          },
          drills: [
            {
              id: 'bd1-02-mute-staccato',
              type: 'rhythm',
              title: '뮤트 스타카토 연습',
              description: '8비트에서 짧게 끊어 치기 (BPM 70)',
              config: { bpm: 70, durationSeconds: 120 },
              passCriteria: { minCompletions: 4 },
              xpReward: 25,
              estimatedMinutes: 5,
            },
            {
              id: 'bd1-02-dynamics',
              type: 'rhythm',
              title: '강약 조절 연습',
              description: '4마디마다 p(약)-f(강) 전환, BPM 75',
              config: { bpm: 75, durationSeconds: 120 },
              passCriteria: { minCompletions: 3 },
              xpReward: 25,
              estimatedMinutes: 5,
            },
          ],
          xpReward: 60,
        },
        // L1-03: 지판 기초 — 음이름과 포지션
        {
          id: 'bl1-03-fretboard',
          title: '지판 기초 — 음이름과 포지션',
          titleEn: 'Fretboard Fundamentals',
          objectives: [
            'E, A, D, G줄의 0~5프렛 음이름 암기',
            '옥타브 관계 이해 (같은 음, 다른 위치)',
            '지판 퀴즈로 빠른 음이름 인식',
          ],
          theory: {
            markdown: `## 베이스 지판 마스터의 첫걸음

4현 베이스 표준 튜닝: **E-A-D-G** (낮은 순)

### 0~5프렛 핵심 음
| 줄 | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| G | G | G#/Ab | A | A#/Bb | B | C |
| D | D | D#/Eb | E | F | F#/Gb | G |
| A | A | A#/Bb | B | C | C#/Db | D |
| E | E | F | F#/Gb | G | G#/Ab | A |

### 옥타브 규칙
- 같은 줄: 12프렛 위 = 한 옥타브 위
- **2줄 위 + 2프렛** = 같은 음 한 옥타브 위 (예: E줄 3프렛 G → D줄 5프렛 G)`,
          },
          drills: [
            {
              id: 'bd1-03-fretboard-quiz',
              type: 'fretboard-quiz',
              title: '지판 음이름 퀴즈 (0~5프렛)',
              description: '베이스 지판 0~5프렛 음이름 맞추기',
              config: { quizDifficulty: 'beginner' },
              passCriteria: { minAccuracy: 70, minCorrectStreak: 5 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
            {
              id: 'bd1-03-octave-find',
              type: 'fretboard-quiz',
              title: '옥타브 찾기',
              description: '주어진 음의 옥타브 위치를 지판에서 찾기',
              config: { quizDifficulty: 'beginner' },
              passCriteria: { minAccuracy: 60, minCorrectStreak: 3 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
          ],
          xpReward: 60,
        },
        // L1-04: 첫 번째 베이스라인
        {
          id: 'bl1-04-first-bassline',
          title: '첫 번째 베이스라인',
          titleEn: 'Your First Bassline',
          objectives: [
            '루트 온음표 (whole note) 베이스라인',
            'I-V-vi-IV 진행에서 루트만 연주',
            '코드 체인지에 맞춰 정확히 전환',
            'BPM 80에서 안정적인 연주',
          ],
          theory: {
            markdown: `## 베이스의 역할: 하모니의 뿌리

베이스는 밴드의 **화성적 토대**를 만듭니다.

### 루트 연주란?
- 코드 이름 = 루트 음 (C코드 → C음, Am코드 → A음)
- 처음엔 **루트만 정확히** 연주하는 것이 최고의 베이스라인
- 리듬 정확도 > 화려한 프레이즈

### 연습 순서
1. 온음표(4박): 한 마디에 한 음만
2. 2분음표(2박): 한 마디에 두 번
3. 4분음표(1박): 매 박 루트 연주
4. 코드 전환 시 **미리 손가락 이동** 준비`,
          },
          drills: [
            {
              id: 'bd1-04-root-whole',
              type: 'chord-change',
              title: '온음표 루트 체인지',
              description: 'C-G-Am-F 진행, 매 마디 루트 한 음 (BPM 70)',
              config: { chords: ['C', 'G', 'Am', 'F'], bpm: 70 },
              passCriteria: { minCompletions: 4 },
              xpReward: 25,
              estimatedMinutes: 5,
            },
            {
              id: 'bd1-04-root-quarter',
              type: 'chord-change',
              title: '4분음표 루트 체인지',
              description: 'C-G-Am-F 진행, 매 박 루트 (BPM 80)',
              config: { chords: ['C', 'G', 'Am', 'F'], bpm: 80 },
              passCriteria: { minCompletions: 4 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
            {
              id: 'bd1-04-root-eighth-line',
              type: 'progression-play',
              title: '8비트 루트 베이스라인',
              description: 'C-G-Am-F 진행에서 8비트 루트 (BPM 85)',
              config: { chords: ['C', 'G', 'Am', 'F'], bpm: 85, progressionName: 'Pop Standard' },
              passCriteria: { minCompletions: 3 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
          ],
          xpReward: 80,
        },
      ],
    },

    // ═══════════════════════════════════════════════════════
    // Level 2: 리듬의 뼈대 — 베이스라인 패턴
    // ═══════════════════════════════════════════════════════
    {
      id: 'bass-level-2',
      index: 1,
      name: '리듬의 뼈대',
      nameEn: 'Rhythm Backbone',
      subtitle: '루트-5도, 옥타브 패턴 마스터',
      description: '루트 한 음에서 벗어나 5도, 옥타브를 활용한 기본 패턴. 8비트/셔플 리듬 베이스라인.',
      requiredXP: 200,
      icon: '🥁',
      lessons: [
        // L2-01: 루트-5도 패턴
        {
          id: 'bl2-01-root-fifth',
          title: '루트-5도 패턴',
          titleEn: 'Root-Fifth Pattern',
          objectives: [
            '5도 음정 관계 이해 (C→G, A→E 등)',
            '루트-5도 교대 패턴 연주',
            '다양한 키에서 5도 위치 찾기',
            'BPM 90에서 안정적 연주',
          ],
          theory: {
            markdown: `## 루트-5도: 베이스라인의 기본 뼈대

가장 많이 쓰이는 베이스 패턴은 **루트와 5도의 교대**입니다.

### 5도 찾기 (같은 줄)
- 루트에서 **같은 줄 +7프렛** = 완전 5도
- 또는 **한 줄 위 +2프렛** = 같은 5도 (더 편한 운지)

### 패턴 예시 (C코드)
\`\`\`
|--1--·--1--|--5--·--5--|  = C C G G
\`\`\`

### 리듬 변형
1. 온음표: R - - - | 5 - - -
2. 2분음표: R - 5 - | R - 5 -
3. 8비트: R 5 R 5 | R 5 R 5
4. 랜덤 믹스: R R 5 R | 5 R R 5`,
          },
          drills: [
            {
              id: 'bd2-01-fifth-find',
              type: 'fretboard-quiz',
              title: '5도 음정 찾기',
              description: '주어진 루트의 5도를 지판에서 찾기',
              config: { quizDifficulty: 'beginner' },
              passCriteria: { minAccuracy: 70, minCorrectStreak: 5 },
              xpReward: 25,
              estimatedMinutes: 5,
            },
            {
              id: 'bd2-01-root-fifth-pattern',
              type: 'progression-play',
              title: '루트-5도 교대 연습',
              description: 'C-Am-F-G에서 루트-5도 패턴 (BPM 85)',
              config: { chords: ['C', 'Am', 'F', 'G'], bpm: 85, progressionName: 'Pop Standard' },
              passCriteria: { minCompletions: 4 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
            {
              id: 'bd2-01-root-fifth-keys',
              type: 'chord-change',
              title: '다양한 키에서 루트-5도',
              description: 'G-D-Em-C / A-E-F#m-D 전환 (BPM 85)',
              config: { chords: ['G', 'D', 'Em', 'C'], bpm: 85 },
              passCriteria: { minCompletions: 3 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
          ],
          xpReward: 80,
        },
        // L2-02: 옥타브 패턴
        {
          id: 'bl2-02-octave',
          title: '옥타브 패턴',
          titleEn: 'Octave Patterns',
          objectives: [
            '옥타브 위치 관계 완전 습득',
            '루트-옥타브 바운스 패턴',
            '옥타브를 활용한 리드미컬 라인',
            'J-Pop에서 자주 쓰이는 옥타브 러닝',
          ],
          theory: {
            markdown: `## 옥타브 — J-Pop 베이스의 시그니처

J-Pop 베이스에서 **옥타브 바운스**는 매우 자주 등장합니다.

### 옥타브 위치 (4현 베이스)
- 같은 줄: +12프렛
- **2줄 위 + 2프렛** (가장 많이 사용)
- 예: E줄 3프렛(G) → D줄 5프렛(G, 옥타브 위)

### 옥타브 바운스 패턴
\`\`\`
Low  High Low  High
R  - 8va- R  - 8va-    (8비트)
\`\`\`

### J-Pop에서의 활용
- 사비에서 에너지를 올릴 때 옥타브 라인 사용
- 인트로/간주의 멜로딕 옥타브 러닝
- 씨티팝 장르에서 특히 빈번`,
          },
          drills: [
            {
              id: 'bd2-02-octave-find',
              type: 'fretboard-quiz',
              title: '옥타브 위치 찾기',
              description: '지판에서 같은 음의 옥타브 위치 찾기',
              config: { quizDifficulty: 'intermediate' },
              passCriteria: { minAccuracy: 70, minCorrectStreak: 5 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
            {
              id: 'bd2-02-octave-bounce',
              type: 'progression-play',
              title: '옥타브 바운스 패턴',
              description: 'C-F-Am-G에서 옥타브 바운스 (BPM 90)',
              config: { chords: ['C', 'F', 'Am', 'G'], bpm: 90, progressionName: 'Pop Standard' },
              passCriteria: { minCompletions: 4 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
            {
              id: 'bd2-02-octave-eighth',
              type: 'rhythm',
              title: '8비트 옥타브 런',
              description: '8비트로 루트-옥타브 연속 러닝 (BPM 95)',
              config: { bpm: 95, durationSeconds: 120 },
              passCriteria: { minCompletions: 3 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
          ],
          xpReward: 80,
        },
        // L2-03: 8비트 리듬 패턴
        {
          id: 'bl2-03-eighth-patterns',
          title: '8비트 리듬 패턴',
          titleEn: 'Eighth-Note Patterns',
          objectives: [
            '다양한 8비트 베이스라인 패턴 습득',
            '리듬 변형: 타이, 쉼표, 싱코페이션',
            '메트로놈과 정확한 타이밍 연주',
            '일본 록/팝의 전형적 8비트 라인',
          ],
          theory: {
            markdown: `## 8비트 베이스 — J-Rock의 심장

대부분의 J-Pop/J-Rock에서 베이스는 **8비트 기반**입니다.

### 기본 8비트 변형
1. **풀 에이트**: 모든 8분음표 연주 (가장 기본)
2. **앞 빼기**: 1박 쉬고 &에서 시작 (당김음 효과)
3. **뒤 빼기**: 각 박의 & 생략 (무거운 느낌)
4. **타이 사용**: 음을 연결해 길게 (부드러운 느낌)

### 연습 팁
- 반드시 메트로놈 사용
- 오른발로 4분음표 탭핑하면서 연주
- **정확한 길이**로 음을 끊는 연습 (뮤트 기술 활용)`,
          },
          drills: [
            {
              id: 'bd2-03-full-eighth',
              type: 'rhythm',
              title: '풀 8비트 베이스라인',
              description: 'Am-F-C-G에서 풀 8비트 루트 (BPM 90)',
              config: { bpm: 90, durationSeconds: 120 },
              passCriteria: { minCompletions: 4 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
            {
              id: 'bd2-03-syncopation',
              type: 'rhythm',
              title: '싱코페이션 8비트',
              description: '타이와 당김음이 포함된 8비트 패턴 (BPM 85)',
              config: { bpm: 85, durationSeconds: 120 },
              passCriteria: { minCompletions: 3 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
          ],
          xpReward: 70,
        },
        // L2-04: 셔플과 스윙 필
        {
          id: 'bl2-04-shuffle',
          title: '셔플과 스윙 필',
          titleEn: 'Shuffle & Swing Feel',
          objectives: [
            '셔플(스윙) 리듬 이해',
            '스트레이트 vs 셔플 구분',
            '셔플 베이스라인 연주',
            'BPM 85~100에서 자연스러운 스윙감',
          ],
          theory: {
            markdown: `## 셔플/스윙 — 그루브의 비밀 무기

### 스트레이트 vs 셔플
- **스트레이트**: 8분음표가 균등 (1 & 2 & 3 & 4 &)
- **셔플**: 8분음표가 불균등, 뒷 음표가 늦음 (TA-ta TA-ta)
- 3연음의 앞 2개를 타이로 묶은 느낌

### J-Pop에서의 셔플
- 발라드, 시티팝에서 셔플 느낌이 많이 등장
- "약간 뒤에 놓는" 느낌의 레이드백
- 완전한 셔플보다 **하프 셔플** (중간) 사용 빈번`,
          },
          drills: [
            {
              id: 'bd2-04-shuffle-basic',
              type: 'rhythm',
              title: '셔플 리듬 기초',
              description: '스윙 느낌의 루트-5도 패턴 (BPM 85)',
              config: { bpm: 85, durationSeconds: 120 },
              passCriteria: { minCompletions: 4 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
            {
              id: 'bd2-04-shuffle-line',
              type: 'progression-play',
              title: '셔플 베이스라인',
              description: 'C-Am-Dm-G7 셔플 (BPM 90)',
              config: { chords: ['C', 'Am', 'Dm', 'G7'], bpm: 90, progressionName: 'Pop Shuffle' },
              passCriteria: { minCompletions: 3 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
          ],
          xpReward: 70,
        },
      ],
    },

    // ═══════════════════════════════════════════════════════
    // Level 3: J-Pop 베이스라인 입문
    // ═══════════════════════════════════════════════════════
    {
      id: 'bass-level-3',
      index: 2,
      name: 'J-Pop 베이스라인 입문',
      nameEn: 'J-Pop Bassline Intro',
      subtitle: '어프로치 노트와 워킹 라인',
      description: 'J-Pop 특유의 멜로딕 베이스라인. 크로매틱/다이어토닉 어프로치, 워킹 베이스, 메이저/마이너 스케일 활용.',
      requiredXP: 600,
      icon: '🎸',
      lessons: [
        // L3-01: 메이저/마이너 스케일
        {
          id: 'bl3-01-scales',
          title: '베이스를 위한 스케일 기초',
          titleEn: 'Bass Scale Fundamentals',
          objectives: [
            '메이저 스케일 (2옥타브) 포지션 연주',
            '내추럴 마이너 스케일 포지션 연주',
            '스케일 디그리(도수) 이해',
            '루트에서 스케일 톤으로 이동하는 감각 형성',
          ],
          theory: {
            markdown: `## 스케일 = 베이스라인의 재료

### 왜 스케일을 배워야 하는가?
베이스라인은 **코드 톤 + 스케일 톤**으로 구성됩니다.
스케일을 알면 코드 사이를 **자연스럽게 연결**할 수 있습니다.

### 메이저 스케일 (온-온-반-온-온-온-반)
\`\`\`
E줄: R - 2 - 3 4 - 5
A줄:               6 - 7 R
\`\`\`

### 마이너 스케일 (온-반-온-온-반-온-온)
- 어두운/감성적 분위기
- J-Pop의 verse(절)에서 많이 사용

### 연습 포인트
- **한 포지션**에서 2옥타브 커버
- 오르막/내리막 모두 연습
- 각 음의 **도수 번호** 말하면서 연주`,
          },
          drills: [
            {
              id: 'bd3-01-major-scale',
              type: 'scale-run',
              title: '메이저 스케일 2옥타브',
              description: 'C 메이저 스케일 오르막/내리막 (BPM 80)',
              config: { scaleName: 'Major', rootNote: 'C', bpm: 80 },
              passCriteria: { minCompletions: 4 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
            {
              id: 'bd3-01-minor-scale',
              type: 'scale-run',
              title: '마이너 스케일 2옥타브',
              description: 'A 마이너 스케일 오르막/내리막 (BPM 80)',
              config: { scaleName: 'Natural Minor', rootNote: 'A', bpm: 80 },
              passCriteria: { minCompletions: 4 },
              xpReward: 30,
              estimatedMinutes: 5,
            },
            {
              id: 'bd3-01-scale-degree',
              type: 'ear-training',
              title: '스케일 디그리 인식',
              description: '들리는 음이 몇 번째 음인지 맞추기',
              config: {},
              passCriteria: { minAccuracy: 60, minCorrectStreak: 3 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
          ],
          xpReward: 80,
        },
        // L3-02: 어프로치 노트
        {
          id: 'bl3-02-approach',
          title: '어프로치 노트 테크닉',
          titleEn: 'Approach Note Technique',
          objectives: [
            '크로매틱 어프로치 (반음 위/아래에서 접근)',
            '다이어토닉 어프로치 (스케일 음으로 접근)',
            '더블 어프로치 (2음 연속 접근)',
            '코드 체인지 직전 어프로치 사용',
          ],
          theory: {
            markdown: `## 어프로치 노트 — 프로 베이시스트의 비밀

### 어프로치 노트란?
다음 코드의 루트에 **반음 또는 온음 아래/위**에서 접근하는 음.
베이스라인을 **자연스럽게 연결**하는 핵심 기술.

### 종류
1. **크로매틱 어프로치**: 반음 아래에서 올라감
   - C → Am 전환: 마지막 박에서 Ab(또는 G#) → A
2. **다이어토닉 어프로치**: 스케일 음으로 접근
   - C → Am: 마지막 박에서 B → A (C스케일의 7번째 음)
3. **더블 어프로치**: 2음 연속
   - C → Am: G# → A 또는 B → Bb → A

### J-Pop에서의 활용
- 거의 모든 J-Pop 베이스라인에서 어프로치 사용
- 특히 코러스 진입 시 어프로치 → 긴장감 고조
- 발라드에서 섬세한 움직임 표현`,
          },
          drills: [
            {
              id: 'bd3-02-chromatic-approach',
              type: 'progression-play',
              title: '크로매틱 어프로치',
              description: 'C-Am-F-G 진행에서 반음 어프로치 (BPM 80)',
              config: { chords: ['C', 'Am', 'F', 'G'], bpm: 80, progressionName: 'Pop Standard' },
              passCriteria: { minCompletions: 4 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
            {
              id: 'bd3-02-diatonic-approach',
              type: 'progression-play',
              title: '다이어토닉 어프로치',
              description: 'C-Am-Dm-G 진행에서 스케일 어프로치 (BPM 80)',
              config: { chords: ['C', 'Am', 'Dm', 'G'], bpm: 80, progressionName: 'J-Pop Standard' },
              passCriteria: { minCompletions: 4 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
            {
              id: 'bd3-02-double-approach',
              type: 'progression-play',
              title: '더블 어프로치 연습',
              description: '코드 전환 시 2음 연속 어프로치 (BPM 75)',
              config: { chords: ['C', 'Am', 'F', 'G'], bpm: 75, progressionName: 'Pop Standard' },
              passCriteria: { minCompletions: 3 },
              xpReward: 40,
              estimatedMinutes: 7,
            },
          ],
          xpReward: 90,
        },
        // L3-03: 워킹 베이스라인
        {
          id: 'bl3-03-walking',
          title: '워킹 베이스라인 기초',
          titleEn: 'Walking Bassline Basics',
          objectives: [
            '코드 톤 (R-3-5-7) 활용한 워킹 라인',
            '스무스한 음 이동 (stepwise motion)',
            '4분음표 기반 워킹 패턴',
            'ii-V-I 진행에서 워킹 연습',
          ],
          theory: {
            markdown: `## 워킹 베이스 — 4분음표로 걷는다

### 워킹 베이스란?
매 박 다른 음을 연주하며 코드 진행을 "걸어가듯" 연결하는 주법.
재즈에서 유래했지만 J-Pop 발라드, 시티팝에서도 활용.

### 기본 규칙
1. **1번째 박**: 반드시 루트
2. **2-3번째 박**: 코드 톤 (3도, 5도) 또는 스케일 음
3. **4번째 박**: 다음 코드로의 어프로치 노트

### 예시 (C → Am)
\`\`\`
C코드: C - E - G - G#(approach)
Am코드: A - C - E - ...
\`\`\`

### 연습 팁
- 처음엔 R-3-5-approach 공식으로 시작
- 익숙해지면 경과음, 크로매틱 추가
- **노래를 부르듯** 멜로딕한 라인 만들기`,
          },
          drills: [
            {
              id: 'bd3-03-chord-tone-walk',
              type: 'progression-play',
              title: '코드 톤 워킹',
              description: 'C-Am-Dm-G에서 R-3-5 워킹 (BPM 75)',
              config: { chords: ['C', 'Am', 'Dm', 'G'], bpm: 75, progressionName: 'Pop Standard' },
              passCriteria: { minCompletions: 4 },
              xpReward: 40,
              estimatedMinutes: 7,
            },
            {
              id: 'bd3-03-walking-ii-V-I',
              type: 'progression-play',
              title: 'ii-V-I 워킹 베이스',
              description: 'Dm7-G7-Cmaj7 진행 워킹 (BPM 80)',
              config: { chords: ['Dm7', 'G7', 'CMaj7'], bpm: 80, progressionName: 'ii-V-I' },
              passCriteria: { minCompletions: 4 },
              xpReward: 45,
              estimatedMinutes: 7,
            },
          ],
          xpReward: 80,
        },
        // L3-04: J-Pop 왕도진행 베이스라인
        {
          id: 'bl3-04-jpop-royal',
          title: 'J-Pop 왕도진행 베이스라인',
          titleEn: 'J-Pop Royal Road Bassline',
          objectives: [
            '왕도진행 (IV-V-iii-vi) 이해',
            '왕도진행 기본 베이스라인 (루트+5도)',
            '어프로치 노트를 넣은 베이스라인',
            '왕도진행 곡 분석 및 카피',
          ],
          theory: {
            markdown: `## 왕도진행 (Royal Road) — J-Pop의 DNA

### 왕도진행이란?
**IV△7 → V7 → iii7 → vi**

J-Pop에서 가장 빈번하게 사용되는 코드 진행.
Key of C: F△7 → G7 → Em7 → Am

### 베이스라인 전략
1. **기본**: 루트만 (F-G-E-A)
2. **중급**: 루트-5도 패턴 (F-C-G-D-E-B-A-E)
3. **고급**: 코드 톤 + 어프로치
   - F(R)-A(3)-C(5)-F#(approach)
   - G(R)-B(3)-D(5)-E♭(approach)
   - Em(R)-G(3)-B(5)-G#(approach)
   - Am...

### 유명 곡 예시
- 수많은 J-Pop 히트곡에서 이 진행 사용
- 특히 사비(chorus)에서 감정 고조 효과`,
          },
          drills: [
            {
              id: 'bd3-04-royal-basic',
              type: 'progression-play',
              title: '왕도진행 기본 베이스라인',
              description: 'FMaj7-G7-Em7-Am 루트-5도 (BPM 85)',
              config: {
                chords: ['FMaj7', 'G7', 'Em7', 'Am'],
                bpm: 85,
                progressionName: 'J-Pop 왕도진행',
                key: 'C',
              },
              passCriteria: { minCompletions: 4 },
              xpReward: 40,
              estimatedMinutes: 6,
            },
            {
              id: 'bd3-04-royal-approach',
              type: 'progression-play',
              title: '왕도진행 어프로치 라인',
              description: '왕도진행에 어프로치 노트 추가 (BPM 80)',
              config: {
                chords: ['FMaj7', 'G7', 'Em7', 'Am'],
                bpm: 80,
                progressionName: 'J-Pop 왕도진행',
                key: 'C',
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 45,
              estimatedMinutes: 7,
            },
            {
              id: 'bd3-04-royal-full',
              type: 'progression-play',
              title: '왕도진행 풀 베이스라인',
              description: '코드 톤 + 스케일 + 어프로치 조합 (BPM 85)',
              config: {
                chords: ['FMaj7', 'G7', 'Em7', 'Am'],
                bpm: 85,
                progressionName: 'J-Pop 왕도진행',
                key: 'C',
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 50,
              estimatedMinutes: 8,
            },
          ],
          xpReward: 100,
        },
      ],
    },

    // ═══════════════════════════════════════════════════════
    // Level 4: 그루브와 테크닉
    // ═══════════════════════════════════════════════════════
    {
      id: 'bass-level-4',
      index: 3,
      name: '그루브와 테크닉',
      nameEn: 'Groove & Technique',
      subtitle: '고스트 노트, 슬라이드, 해머온/풀오프',
      description: '베이스라인에 그루브를 더하는 테크닉. 고스트 노트, 슬라이드, 해머온/풀오프, 16비트 패턴.',
      requiredXP: 1500,
      icon: '🔥',
      lessons: [
        // L4-01: 고스트 노트
        {
          id: 'bl4-01-ghost-notes',
          title: '고스트 노트',
          titleEn: 'Ghost Notes',
          objectives: [
            '고스트 노트 (뮤트된 퍼커시브 음) 테크닉',
            '8비트/16비트에 고스트 노트 삽입',
            '그루비한 패턴 만들기',
            '펑크/R&B 스타일 고스트 노트 라인',
          ],
          theory: {
            markdown: `## 고스트 노트 — 들리지 않지만 느껴지는 음

### 고스트 노트란?
왼손으로 뮤트한 채 오른손으로 튕기는 **퍼커시브한 음**.
음정은 없지만 리듬적 "텍스처"를 추가.

### 표기법
보통 **x**로 표기: x-R-x-R (고스트-루트-고스트-루트)

### 연습 방법
1. 왼손 손가락을 줄에 가볍게 올림 (프렛 사이)
2. 오른손으로 평소처럼 피킹
3. "둥" 대신 "턱" 하는 소리가 나야 함

### 기본 패턴
\`\`\`
16비트: R-x-x-R-x-5-x-R  (R=루트, x=고스트, 5=5도)
\`\`\`

### J-Pop 활용
- 밝은 J-Pop: 고스트 노트로 경쾌함 추가
- R&B/시티팝: 그루비한 바운스 느낌
- 애니 OP 빠른 곡: 16비트 드라이브`,
          },
          drills: [
            {
              id: 'bd4-01-ghost-basic',
              type: 'rhythm',
              title: '고스트 노트 기초',
              description: '8비트에 고스트 노트 삽입 (BPM 80)',
              config: { bpm: 80, durationSeconds: 120 },
              passCriteria: { minCompletions: 4 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
            {
              id: 'bd4-01-ghost-16th',
              type: 'rhythm',
              title: '16비트 고스트 패턴',
              description: 'R-x-x-R-x-5-x-R 패턴 (BPM 85)',
              config: { bpm: 85, durationSeconds: 120 },
              passCriteria: { minCompletions: 3 },
              xpReward: 40,
              estimatedMinutes: 7,
            },
            {
              id: 'bd4-01-ghost-groove',
              type: 'progression-play',
              title: '고스트 노트 그루브 라인',
              description: 'Am-Dm-G-C에서 고스트 그루브 (BPM 90)',
              config: { chords: ['Am', 'Dm', 'G', 'C'], bpm: 90 },
              passCriteria: { minCompletions: 3 },
              xpReward: 45,
              estimatedMinutes: 7,
            },
          ],
          xpReward: 100,
        },
        // L4-02: 슬라이드 & 해머온/풀오프
        {
          id: 'bl4-02-articulation',
          title: '슬라이드 & 해머온/풀오프',
          titleEn: 'Slides, Hammer-ons & Pull-offs',
          objectives: [
            '슬라이드 업/다운 테크닉',
            '해머온으로 부드러운 음 연결',
            '풀오프로 빠른 하행 패턴',
            '테크닉 조합한 표현력 있는 라인',
          ],
          theory: {
            markdown: `## 아티큘레이션 — 베이스라인에 "말투"를 입히다

### 슬라이드
- 한 음에서 다른 음으로 **미끄러지듯** 이동
- 위로(slide up) / 아래로(slide down)
- 코드 전환 시 자연스러운 연결

### 해머온 (Hammer-on)
- 한 음을 피킹 후 다른 손가락으로 **때려서** 다음 음
- 오른손 피킹 없이 왼손만으로 소리
- 빠른 스케일 런에 필수

### 풀오프 (Pull-off)
- 높은 음에서 낮은 음으로 손가락을 **당기며** 소리
- 해머온의 반대

### J-Pop에서의 활용
- 이행구(fill) 에서 슬라이드 업 → 에너지 상승
- verse의 부드러운 라인에 해머온/풀오프
- 인트로 러프에서 슬라이드 다운 효과`,
          },
          drills: [
            {
              id: 'bd4-02-slide',
              type: 'scale-run',
              title: '슬라이드 연습',
              description: '스케일을 슬라이드로 연결 (BPM 75)',
              config: { scaleName: 'Major', rootNote: 'C', bpm: 75 },
              passCriteria: { minCompletions: 4 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
            {
              id: 'bd4-02-hammer-pull',
              type: 'scale-run',
              title: '해머온/풀오프 연습',
              description: '스케일에서 H/P 조합 (BPM 80)',
              config: { scaleName: 'Minor Pentatonic', rootNote: 'A', bpm: 80 },
              passCriteria: { minCompletions: 4 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
            {
              id: 'bd4-02-articulation-line',
              type: 'progression-play',
              title: '아티큘레이션 조합 라인',
              description: '슬라이드+H/P로 표현력 있는 베이스라인 (BPM 85)',
              config: { chords: ['C', 'Am', 'F', 'G'], bpm: 85 },
              passCriteria: { minCompletions: 3 },
              xpReward: 40,
              estimatedMinutes: 7,
            },
          ],
          xpReward: 90,
        },
        // L4-03: 16비트 베이스 & 펑키 패턴
        {
          id: 'bl4-03-sixteenth',
          title: '16비트 베이스 & 펑키 패턴',
          titleEn: '16th-Note Bass & Funky Patterns',
          objectives: [
            '16비트 베이스라인 기초',
            '펑크 스타일 베이스 패턴',
            '16비트 + 고스트 노트 조합',
            'BPM 90~110에서 안정적 16비트',
          ],
          theory: {
            markdown: `## 16비트 베이스 — 에너지를 끌어올린다

### 8비트 vs 16비트
- 8비트: 한 박에 2개 음 (안정적, 무거운)
- 16비트: 한 박에 4개 음 (에너지, 드라이브)

### 기본 16비트 패턴
\`\`\`
1 e & a 2 e & a 3 e & a 4 e & a
R . . R . R . . R . . 5 . R . .
\`\`\`

### 펑키 패턴의 핵심
1. **쉼표 활용**: 빈 공간이 그루브를 만든다
2. **고스트 노트**: 빈 공간을 퍼커시브하게 채움
3. **악센트**: 강세 위치가 패턴의 캐릭터 결정
4. **뮤트**: 짧게 끊어서 타이트한 리듬

### J-Pop/애니에서의 16비트
- 애니 OP/ED 빠른 곡에서 16비트 드라이브
- 시티팝 리바이벌에서 펑키 베이스`,
          },
          drills: [
            {
              id: 'bd4-03-16th-basic',
              type: 'rhythm',
              title: '16비트 기초 패턴',
              description: '기본 16비트 베이스 패턴 (BPM 90)',
              config: { bpm: 90, durationSeconds: 120 },
              passCriteria: { minCompletions: 4 },
              xpReward: 40,
              estimatedMinutes: 7,
            },
            {
              id: 'bd4-03-funky-pattern',
              type: 'rhythm',
              title: '펑키 16비트 패턴',
              description: '고스트 노트 포함 펑키 라인 (BPM 95)',
              config: { bpm: 95, durationSeconds: 120 },
              passCriteria: { minCompletions: 3 },
              xpReward: 45,
              estimatedMinutes: 7,
            },
          ],
          xpReward: 80,
        },
        // L4-04: 슬랩 베이스 입문
        {
          id: 'bl4-04-slap-intro',
          title: '슬랩 베이스 입문',
          titleEn: 'Slap Bass Introduction',
          objectives: [
            '썸(thumb slap) 기초 — 엄지로 줄 때리기',
            '플럭(pop/pluck) 기초 — 검지로 줄 당기기',
            '썸-플럭 교대 패턴',
            '간단한 슬랩 베이스라인',
          ],
          theory: {
            markdown: `## 슬랩 베이스 — 타격의 예술

### 슬랩이란?
엄지로 줄을 **때리고(thumb)**, 검지로 줄을 **당기는(pop)** 주법.
강렬한 퍼커시브 사운드. 펑크, 퓨전, J-Pop에서 사용.

### 썸 (Thumb Slap)
1. 엄지의 뼈 부분으로 줄을 **내리쳐** 프렛에 부딪히게 함
2. 손목 회전으로 치기 (팔 전체가 아닌 손목)
3. 때린 후 바로 줄에서 떨어지기 (바운스)

### 플럭 (Pop)
1. 검지 또는 중지를 줄 아래에 넣기
2. 줄을 위로 **당겨서** 지판에 부딪히게 함
3. 높은 줄(D, G)에서 주로 사용

### 기본 패턴
\`\`\`
T-P-T-T-P  (T=Thumb, P=Pop)
\`\`\`

### 주의사항
- 처음엔 매우 느린 BPM(50~60)에서 시작
- 깨끗한 소리가 나도록 정확한 위치 타격
- 손목 통증 시 즉시 휴식`,
          },
          drills: [
            {
              id: 'bd4-04-thumb-basic',
              type: 'rhythm',
              title: '썸 슬랩 기초',
              description: '개방현에서 썸 슬랩 연습 (BPM 60)',
              config: { bpm: 60, durationSeconds: 120 },
              passCriteria: { minCompletions: 4 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
            {
              id: 'bd4-04-pop-basic',
              type: 'rhythm',
              title: '플럭 (팝) 기초',
              description: '검지로 줄 당기기 (BPM 60)',
              config: { bpm: 60, durationSeconds: 120 },
              passCriteria: { minCompletions: 4 },
              xpReward: 35,
              estimatedMinutes: 6,
            },
            {
              id: 'bd4-04-slap-combo',
              type: 'rhythm',
              title: '썸-플럭 교대 패턴',
              description: 'T-P-T-T-P 기본 패턴 (BPM 65)',
              config: { bpm: 65, durationSeconds: 120 },
              passCriteria: { minCompletions: 3 },
              xpReward: 40,
              estimatedMinutes: 7,
            },
          ],
          xpReward: 90,
        },
      ],
    },

    // ═══════════════════════════════════════════════════════
    // Level 5: J-Pop 심화 & 장르 확장
    // ═══════════════════════════════════════════════════════
    {
      id: 'bass-level-5',
      index: 4,
      name: 'J-Pop 심화 & 장르 확장',
      nameEn: 'Advanced J-Pop & Genre Expansion',
      subtitle: '다양한 J-Pop 진행과 장르별 스타일',
      description: '카논진행, 소악마진행, 시티팝, J-Rock 등 다양한 J-Pop 하위 장르의 베이스라인. 텐션 코드 대응, 멜로딕 라인.',
      requiredXP: 3000,
      icon: '🌟',
      lessons: [
        // L5-01: J-Pop 핵심 진행 마스터
        {
          id: 'bl5-01-jpop-progressions',
          title: 'J-Pop 핵심 진행 마스터',
          titleEn: 'J-Pop Core Progressions',
          objectives: [
            '카논진행 (I-V-vi-iii-IV-I-IV-V) 베이스라인',
            '소악마진행 (♭VI-♭VII-I-vi) 베이스라인',
            '마루사진행 (I△7-III7-vi-II7) 베이스라인',
            '각 진행의 감정적 효과 이해',
          ],
          theory: {
            markdown: `## J-Pop 4대 진행의 베이스 전략

### 1. 카논진행
**I → V → vi → iii → IV → I → IV → V**
- 안정감과 기대감의 교차
- 베이스: 순차 하행(C-B-A-G-F-E-F-G)이 핵심

### 2. 소악마진행
**♭VI → ♭VII → I (또는 vi → IV → V → I)**
- 어두움에서 밝음으로, 극적 전환
- 베이스: 반음/온음 상행이 긴장 → 해결

### 3. 마루사진행
**I△7 → III7 → vi7 → II7**
- 세컨더리 도미넌트 활용, 고급스러운 움직임
- 베이스: 워킹 라인이 잘 어울림

### 4. 시티팝 그루브
**I△7 → IV△7 → iii7 → vi7**
- 텐션(7th, 9th) 풍부, 세련된 분위기
- 베이스: 코드 톤 아르페지오 + 크로매틱 경과음`,
          },
          drills: [
            {
              id: 'bd5-01-canon',
              type: 'progression-play',
              title: '카논진행 베이스라인',
              description: 'I-V-vi-iii-IV-I-IV-V 순차 하행 라인 (BPM 85)',
              config: {
                chords: ['C', 'G', 'Am', 'Em', 'F', 'C', 'F', 'G'],
                bpm: 85,
                progressionName: '카논진행',
                key: 'C',
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 45,
              estimatedMinutes: 8,
            },
            {
              id: 'bd5-01-devilish',
              type: 'progression-play',
              title: '소악마진행 베이스라인',
              description: '♭VI-♭VII-I 극적 상승 라인 (BPM 90)',
              config: {
                chords: ['Ab', 'Bb', 'C', 'Am'],
                bpm: 90,
                progressionName: '소악마진행',
                key: 'C',
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 45,
              estimatedMinutes: 7,
            },
            {
              id: 'bd5-01-marusa',
              type: 'progression-play',
              title: '마루사진행 워킹 라인',
              description: 'I△7-III7-vi7-II7 워킹 베이스 (BPM 80)',
              config: {
                chords: ['CMaj7', 'E7', 'Am7', 'D7'],
                bpm: 80,
                progressionName: '마루사진행',
                key: 'C',
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 50,
              estimatedMinutes: 8,
            },
          ],
          xpReward: 120,
        },
        // L5-02: 시티팝 & 펑크 베이스
        {
          id: 'bl5-02-citypop-funk',
          title: '시티팝 & 펑크 베이스',
          titleEn: 'City Pop & Funk Bass',
          objectives: [
            '시티팝 특유의 그루비 라인',
            'ii-V-I 펑키 패턴',
            '코드 톤 아르페지오 + 크로매틱',
            '16비트 + 고스트 노트 시티팝 그루브',
          ],
          theory: {
            markdown: `## 시티팝 베이스 — 80년대 도시의 밤

### 시티팝 베이스의 특징
- **텐션 풍부**: 7th, 9th 코드에 맞는 코드 톤 활용
- **그루비한 16비트**: 고스트 노트와 싱코페이션
- **크로매틱 경과음**: 음과 음 사이를 반음으로 연결
- **옥타브 기법**: 옥타브 바운스 활발 사용

### 핵심 패턴
\`\`\`
CMaj7: R-x-3-x | 5-x-7-x | R(8va)-x-5-x | 7-x-approach
\`\`\`

### 시티팝 진행 예
- I△7 → IV△7 → iii7 → vi7
- I△7 → vi7 → ii9 → V7(13)

### 펑크 요소
- 뮤트와 고스트 노트가 핵심
- "빈 공간의 그루브" — 쉬는 곳이 더 중요`,
          },
          drills: [
            {
              id: 'bd5-02-citypop-groove',
              type: 'progression-play',
              title: '시티팝 그루브 라인',
              description: 'IMaj7-IVMaj7-iii7-vi7 시티팝 패턴 (BPM 100)',
              config: {
                chords: ['CMaj7', 'FMaj7', 'Em7', 'Am7'],
                bpm: 100,
                progressionName: '시티팝 그루브',
                key: 'C',
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 50,
              estimatedMinutes: 8,
            },
            {
              id: 'bd5-02-funk-ii-V',
              type: 'progression-play',
              title: '펑키 ii-V-I 라인',
              description: 'Dm9-G13-CMaj7 펑키 패턴 (BPM 95)',
              config: {
                chords: ['Dm9', 'G13', 'CMaj7'],
                bpm: 95,
                progressionName: 'Funky ii-V-I',
                key: 'C',
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 50,
              estimatedMinutes: 8,
            },
            {
              id: 'bd5-02-chromatic-fill',
              type: 'scale-run',
              title: '크로매틱 경과음 연습',
              description: '코드 톤 사이를 반음으로 연결 (BPM 85)',
              config: { scaleName: 'Chromatic', rootNote: 'C', bpm: 85 },
              passCriteria: { minCompletions: 3 },
              xpReward: 45,
              estimatedMinutes: 7,
            },
          ],
          xpReward: 120,
        },
        // L5-03: J-Rock & 애니 베이스
        {
          id: 'bl5-03-jrock-anime',
          title: 'J-Rock & 애니 베이스',
          titleEn: 'J-Rock & Anime Bass',
          objectives: [
            'J-Rock 파워 베이스 (피크 사용 고려)',
            '빠른 BPM (140~180) 8비트 드라이브',
            '애니 OP 스타일 베이스라인',
            '다이내믹 변화 (verse: 작게 → chorus: 크게)',
          ],
          theory: {
            markdown: `## J-Rock & 애니 베이스 — 에너지와 드라이브

### J-Rock 베이스의 특징
- **피크 연주**: 어택이 강하고 밝은 톤
- **8비트 드라이브**: 빠른 BPM에서 꾸준한 8비트
- **파워코드 동행**: 기타 파워코드에 맞춰 루트+5도
- **다이내믹**: verse(절)에서 부드럽게, chorus(사비)에서 강하게

### 애니 OP 스타일
- vi → IV → I → V (감정적 고조)
- BPM 160~180의 빠른 템포
- 사비에서 옥타브 러닝
- 기타 솔로 시 베이스 홀드(지속음)

### 연습 포인트
- BPM 120에서 시작 → 점진적으로 올리기
- 오른손 피로 관리 (힘 빼기)
- 메트로놈 정확도가 핵심`,
          },
          drills: [
            {
              id: 'bd5-03-jrock-eighth',
              type: 'rhythm',
              title: 'J-Rock 8비트 드라이브',
              description: '빠른 8비트 루트-5도 (BPM 140)',
              config: { bpm: 140, durationSeconds: 120 },
              passCriteria: { minCompletions: 3 },
              xpReward: 45,
              estimatedMinutes: 7,
            },
            {
              id: 'bd5-03-anime-op',
              type: 'progression-play',
              title: '애니 OP 베이스라인',
              description: 'Am-F-C-G 감정적 고조 라인 (BPM 155)',
              config: {
                chords: ['Am', 'F', 'C', 'G'],
                bpm: 155,
                progressionName: '애니 OP',
                key: 'C',
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 50,
              estimatedMinutes: 8,
            },
            {
              id: 'bd5-03-dynamic-shift',
              type: 'progression-play',
              title: '다이내믹 전환 연습',
              description: 'verse(p) → chorus(f) 전환 (BPM 150)',
              config: {
                chords: ['Am', 'Em', 'F', 'C', 'Am', 'F', 'C', 'G'],
                bpm: 150,
                progressionName: 'J-Rock Dynamic',
              },
              passCriteria: { minCompletions: 2 },
              xpReward: 50,
              estimatedMinutes: 8,
            },
          ],
          xpReward: 120,
        },
      ],
    },

    // ═══════════════════════════════════════════════════════
    // Level 6: 밴드 시뮬레이션 & 마스터리
    // ═══════════════════════════════════════════════════════
    {
      id: 'bass-level-6',
      index: 5,
      name: '밴드 시뮬레이션 & 마스터리',
      nameEn: 'Band Simulation & Mastery',
      subtitle: '실전 합주를 위한 종합 연습',
      description: '백킹 트랙과 함께 실전 연주. 곡 구조에 맞는 베이스라인 구성, 키 변환, 즉흥 필인, 밴드 앙상블 감각.',
      requiredXP: 5000,
      icon: '👑',
      lessons: [
        // L6-01: 곡 구조와 베이스 역할
        {
          id: 'bl6-01-song-structure',
          title: '곡 구조와 베이스의 역할',
          titleEn: 'Song Structure & Bass Role',
          objectives: [
            'Intro-Verse-Chorus-Bridge-Outro 구조 이해',
            '각 섹션별 베이스 역할 차별화',
            '빌드업/브레이크다운 베이스 전략',
            '전체 곡 흐름에 맞는 다이내믹 조절',
          ],
          theory: {
            markdown: `## 곡 전체를 보는 베이시스트

### J-Pop 곡 구조 (전형)
\`\`\`
Intro → A멜 → B멜 → 사비 → 간주 → A멜 → B멜 → 사비 → 대사비 → Outro
\`\`\`

### 섹션별 베이스 전략
| 섹션 | 에너지 | 베이스 접근 |
|------|--------|------------|
| Intro | 중 | 심플, 곡의 키/무드 제시 |
| A멜(Verse) | 낮음 | 루트 위주, 공간 많이 |
| B멜(Pre-chorus) | 상승 | 점진적 움직임 증가 |
| 사비(Chorus) | 높음 | 풀 에너지, 옥타브/코드톤 |
| 간주(Bridge) | 변화 | 대조적 패턴 or 브레이크 |
| 대사비(Last Chorus) | 최고 | 필인 추가, 최대 에너지 |
| Outro | 하강 | 점진적 심플하게 마무리 |

### 핵심 원칙
"밴드의 다이내믹을 **베이스가 주도**한다"`,
          },
          drills: [
            {
              id: 'bd6-01-section-contrast',
              type: 'progression-play',
              title: '섹션별 다이내믹 연습',
              description: 'Verse(심플) → Chorus(풀) 대비 연습 (BPM 120)',
              config: {
                chords: ['Am', 'F', 'C', 'G'],
                bpm: 120,
                progressionName: 'J-Pop Full Structure',
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 50,
              estimatedMinutes: 8,
            },
            {
              id: 'bd6-01-buildup',
              type: 'progression-play',
              title: '빌드업 베이스 연습',
              description: 'B멜 → 사비 빌드업 패턴 (BPM 130)',
              config: {
                chords: ['Dm', 'Em', 'F', 'G', 'Am', 'F', 'C', 'G'],
                bpm: 130,
                progressionName: 'J-Pop Build-up',
              },
              passCriteria: { minCompletions: 2 },
              xpReward: 55,
              estimatedMinutes: 9,
            },
          ],
          xpReward: 100,
        },
        // L6-02: 필인 (Fill-In) & 즉흥
        {
          id: 'bl6-02-fills',
          title: '필인 & 즉흥',
          titleEn: 'Fills & Improvisation',
          objectives: [
            '2박/4박 베이스 필인 패턴',
            '스케일 기반 필인 라인',
            '드럼 필인과 호흡 맞추기',
            '코드 진행 안에서 자유로운 즉흥',
          ],
          theory: {
            markdown: `## 필인 — 곡에 생명을 불어넣는 순간

### 필인이란?
반복되는 패턴 사이에 넣는 **변화 구간**.
보통 4마디 또는 8마디 끝에서 사용.

### 베이스 필인 유형
1. **스케일 런**: 빠른 상행/하행 스케일
2. **크로매틱 상행**: 반음씩 올라가기
3. **옥타브 점프**: 한 옥타브 위에서 내려오기
4. **슬라이드 필**: 슬라이드로 다음 코드 진입
5. **쉼표 필**: 갑자기 멈추기 (브레이크)

### 즉흥의 기본 규칙
1. **코드 톤** 위주 (R, 3, 5, 7)
2. **스케일 톤**으로 연결
3. **크로매틱** 경과음으로 양념
4. **리듬 변형**으로 생동감

### J-Pop에서의 활용
- 사비 진입 직전 필인 (긴장 → 해결)
- 간주(bridge) 시작 시 베이스 솔로적 필인
- 대사비에서 기존 패턴에 작은 변화 추가`,
          },
          drills: [
            {
              id: 'bd6-02-scale-fill',
              type: 'scale-run',
              title: '스케일 런 필인',
              description: '4박 내 스케일 상행/하행 필인 (BPM 100)',
              config: { scaleName: 'Major', rootNote: 'C', bpm: 100 },
              passCriteria: { minCompletions: 4 },
              xpReward: 45,
              estimatedMinutes: 7,
            },
            {
              id: 'bd6-02-chromatic-fill',
              type: 'progression-play',
              title: '크로매틱 필인 연습',
              description: '코드 전환 시 반음 상행 필인 (BPM 95)',
              config: { chords: ['C', 'Am', 'F', 'G'], bpm: 95 },
              passCriteria: { minCompletions: 3 },
              xpReward: 50,
              estimatedMinutes: 8,
            },
            {
              id: 'bd6-02-improv',
              type: 'progression-play',
              title: '코드 진행 즉흥 연습',
              description: 'FMaj7-G7-Em7-Am 위에서 자유 즉흥 (BPM 90)',
              config: {
                chords: ['FMaj7', 'G7', 'Em7', 'Am'],
                bpm: 90,
                progressionName: '왕도진행 즉흥',
                key: 'C',
              },
              passCriteria: { minCompletions: 3 },
              xpReward: 55,
              estimatedMinutes: 9,
            },
          ],
          xpReward: 120,
        },
        // L6-03: 종합 실전 — 밴드 시뮬레이션
        {
          id: 'bl6-03-band-sim',
          title: '종합 실전 — 밴드 시뮬레이션',
          titleEn: 'Full Band Simulation',
          objectives: [
            '백킹 트랙(드럼+기타)과 합주 연습',
            'J-Pop 풀 곡 구조 통주',
            '다양한 키에서 동일 진행 연주',
            '실전 레벨의 안정적 연주력',
          ],
          drills: [
            {
              id: 'bd6-03-backing-pop',
              type: 'song-section',
              title: 'J-Pop 스타일 풀 곡 연주',
              description: 'Intro~Outro 전체 구조 합주 (BPM 120)',
              config: { bpm: 120, durationSeconds: 240 },
              passCriteria: { minCompletions: 2 },
              xpReward: 60,
              estimatedMinutes: 10,
            },
            {
              id: 'bd6-03-backing-rock',
              type: 'song-section',
              title: 'J-Rock 스타일 풀 곡 연주',
              description: '에너지 넘치는 J-Rock 합주 (BPM 160)',
              config: { bpm: 160, durationSeconds: 240 },
              passCriteria: { minCompletions: 2 },
              xpReward: 60,
              estimatedMinutes: 10,
            },
            {
              id: 'bd6-03-key-change',
              type: 'progression-play',
              title: '키 체인지 대응 연습',
              description: '같은 진행을 C→G→D→A 키로 전환 (BPM 110)',
              config: {
                chords: ['FMaj7', 'G7', 'Em7', 'Am'],
                bpm: 110,
                progressionName: '왕도진행 키 체인지',
              },
              passCriteria: { minCompletions: 2 },
              xpReward: 55,
              estimatedMinutes: 9,
            },
            {
              id: 'bd6-03-final-challenge',
              type: 'progression-play',
              title: '파이널 챌린지',
              description: '모든 테크닉을 활용한 종합 베이스라인 연주',
              config: {
                chords: ['CMaj7', 'E7', 'Am7', 'FMaj7', 'Dm7', 'G7', 'CMaj7', 'A7'],
                bpm: 115,
                progressionName: 'J-Pop Medley',
                key: 'C',
              },
              passCriteria: { minCompletions: 2 },
              xpReward: 70,
              estimatedMinutes: 12,
            },
          ],
          xpReward: 150,
        },
      ],
    },
  ],
}

// ─── Helper: 전체 커리큘럼 목록 ─────────────────────────

export const ALL_CURRICULA: Curriculum[] = [
  GUITAR_CURRICULUM,
  BASS_CURRICULUM,
]

/** 레벨 ID로 레벨 찾기 */
export function findLevel(curriculum: Curriculum, levelId: string): Level | undefined {
  return curriculum.levels.find(l => l.id === levelId)
}

/** 레슨 ID로 레슨 찾기 */
export function findLesson(curriculum: Curriculum, lessonId: string): Lesson | undefined {
  for (const level of curriculum.levels) {
    const lesson = level.lessons.find(l => l.id === lessonId)
    if (lesson) return lesson
  }
  return undefined
}

/** 드릴 ID로 드릴 찾기 */
export function findDrill(curriculum: Curriculum, drillId: string): Drill | undefined {
  for (const level of curriculum.levels) {
    for (const lesson of level.lessons) {
      const drill = lesson.drills.find(d => d.id === drillId)
      if (drill) return drill
    }
  }
  return undefined
}

/** 레벨 언락 가능 여부 체크 */
export function isLevelUnlocked(level: Level, totalXP: number): boolean {
  return totalXP >= level.requiredXP
}

/** 레슨 완료율 계산 */
export function getLessonProgress(
  lesson: Lesson,
  completedDrills: string[],
): number {
  if (lesson.drills.length === 0) return 100
  const done = lesson.drills.filter(d => completedDrills.includes(d.id)).length
  return Math.round((done / lesson.drills.length) * 100)
}

/** 레벨 완료율 계산 */
export function getLevelProgress(
  level: Level,
  completedLessons: string[],
): number {
  if (level.lessons.length === 0) return 100
  const done = level.lessons.filter(l => completedLessons.includes(l.id)).length
  return Math.round((done / level.lessons.length) * 100)
}
