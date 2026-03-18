/**
 * J-Pop 특화 코드 진행 데이터베이스
 *
 * J-Pop 음악의 대표적인 코드 진행 패턴들.
 * 기존 chordProgression.ts의 ProgressionPreset과 호환되는 형식.
 *
 * 참고: 코드 진행 자체는 저작권 대상이 아님.
 */

import type { ProgressionStep } from '../utils/chordProgression'

// ─── J-Pop 진행에 필요한 확장 Degree 시스템 ─────────

/**
 * 기존 MAJOR_DEGREES는 다이어토닉 7개만 지원.
 * J-Pop은 Secondary Dominant, borrowed chord 등이 빈번하므로
 * 확장 표기법을 사용.
 *
 * 이 파일은 "preset name + chord symbols" 형태로 정의하고,
 * 실제 resolve는 jpopResolveProgression()에서 처리.
 */

export interface JPopChordStep {
  /** 코드 심볼 (예: 'IVMaj7', 'V7', 'iii7', 'vi') */
  symbol: string
  /** 루트의 반음 오프셋 from key root (0=I, 2=II, 4=III, 5=IV, 7=V, 9=VI, 11=VII) */
  semitones: number
  /** 코드 퀄리티 (CHORDS[].name 참조) */
  quality: string
  /** 박자 수 (기본 4) */
  beats?: number
}

export interface JPopProgression {
  id: string
  name: string
  nameJa?: string          // 일본어 명칭
  nameKo: string           // 한국어 명칭
  category: JPopProgressionCategory
  description: string
  mood: string[]           // ['밝은', '감성적', '긴장감'] 등
  difficulty: 1 | 2 | 3 | 4 | 5
  steps: JPopChordStep[]
  /** 대표적으로 사용된 곡/장르 (구체적 곡명 없이 장르/시대로) */
  usedIn: string[]
  /** 추천 BPM 범위 */
  bpmRange: [number, number]
  /** 추천 스트럼/아르페지오 */
  suggestedStyle?: 'strum' | 'arpeggio' | 'fingerpicking' | 'mix'
}

export type JPopProgressionCategory =
  | 'standard'     // 왕도/정석 진행
  | 'minor'        // 마이너 키 진행
  | 'dramatic'     // 드라마틱/전개용
  | 'citypop'      // 시티팝/네오시티팝
  | 'ballad'       // 발라드
  | 'rock'         // J-Rock
  | 'anime'        // 애니 OP/ED 특화

// ─── J-Pop 코드 진행 라이브러리 ─────────────────────

export const JPOP_PROGRESSIONS: JPopProgression[] = [
  // ═══ STANDARD (정석 진행) ═══
  {
    id: 'royal-road',
    name: 'Royal Road',
    nameJa: '王道進行',
    nameKo: '왕도진행',
    category: 'standard',
    description: 'J-Pop에서 가장 많이 사용되는 진행. 밝지만 약간의 멜랑꼴리.',
    mood: ['감성적', '밝은', '희망적'],
    difficulty: 2,
    steps: [
      { symbol: 'IVMaj7', semitones: 5, quality: 'Maj7', beats: 4 },
      { symbol: 'V7',     semitones: 7, quality: '7th',  beats: 4 },
      { symbol: 'iii7',   semitones: 4, quality: 'm7',   beats: 4 },
      { symbol: 'vi',     semitones: 9, quality: 'Minor', beats: 4 },
    ],
    usedIn: ['2000년대 이후 J-Pop 전반', '아이돌 곡', '애니 OP/ED'],
    bpmRange: [70, 140],
    suggestedStyle: 'strum',
  },
  {
    id: 'canon',
    name: 'Canon',
    nameJa: 'カノン進行',
    nameKo: '카논진행',
    category: 'standard',
    description: '파헬벨 카논 변형. 자연스러운 하행 베이스라인이 특징.',
    mood: ['따뜻한', '노스탤지어', '감동적'],
    difficulty: 2,
    steps: [
      { symbol: 'I',   semitones: 0, quality: 'Major', beats: 4 },
      { symbol: 'V',   semitones: 7, quality: 'Major', beats: 4 },
      { symbol: 'vi',  semitones: 9, quality: 'Minor', beats: 4 },
      { symbol: 'iii', semitones: 4, quality: 'Minor', beats: 4 },
      { symbol: 'IV',  semitones: 5, quality: 'Major', beats: 4 },
      { symbol: 'I',   semitones: 0, quality: 'Major', beats: 4 },
      { symbol: 'IV',  semitones: 5, quality: 'Major', beats: 4 },
      { symbol: 'V',   semitones: 7, quality: 'Major', beats: 4 },
    ],
    usedIn: ['90년대~현재 J-Pop', '졸업식 곡', '발라드'],
    bpmRange: [65, 130],
    suggestedStyle: 'arpeggio',
  },
  {
    id: 'just-the-two',
    name: 'Just the Two of Us',
    nameJa: 'Just the Two進行',
    nameKo: '저스트더투 진행',
    category: 'standard',
    description: 'AOR/소울에서 온 세련된 진행. 시티팝과 네오시티팝의 핵심.',
    mood: ['세련된', '어른스러운', '그루비'],
    difficulty: 3,
    steps: [
      { symbol: 'IVMaj7', semitones: 5, quality: 'Maj7', beats: 4 },
      { symbol: 'III7',   semitones: 4, quality: '7th',  beats: 4 },
      { symbol: 'vi7',    semitones: 9, quality: 'm7',   beats: 4 },
      { symbol: 'V7',     semitones: 7, quality: '7th',  beats: 2 },
      { symbol: 'I',      semitones: 0, quality: 'Major', beats: 2 },
    ],
    usedIn: ['시티팝', '네오시티팝', '2020년대 J-Pop R&B'],
    bpmRange: [80, 120],
    suggestedStyle: 'fingerpicking',
  },
  {
    id: 'pop-standard',
    name: 'Pop Standard',
    nameJa: 'ポップスタンダード',
    nameKo: '팝 스탠다드',
    category: 'standard',
    description: '가장 기본적인 J-Pop 진행. 단순하지만 효과적.',
    mood: ['밝은', '경쾌한', '친근한'],
    difficulty: 1,
    steps: [
      { symbol: 'I',   semitones: 0, quality: 'Major', beats: 4 },
      { symbol: 'V',   semitones: 7, quality: 'Major', beats: 4 },
      { symbol: 'vi',  semitones: 9, quality: 'Minor', beats: 4 },
      { symbol: 'IV',  semitones: 5, quality: 'Major', beats: 4 },
    ],
    usedIn: ['글로벌 팝 공통', 'J-Pop 초기 히트곡'],
    bpmRange: [100, 150],
    suggestedStyle: 'strum',
  },
  {
    id: 'maruwata',
    name: 'Maruwata',
    nameJa: '丸サ進行 (丸の内サディスティック)',
    nameKo: '마루사 진행',
    category: 'standard',
    description: 'I△7→III7→vi7→II7 진행. 세련된 재즈적 색채.',
    mood: ['세련된', '도시적', '재즈적'],
    difficulty: 4,
    steps: [
      { symbol: 'IMaj7',  semitones: 0, quality: 'Maj7', beats: 4 },
      { symbol: 'III7',   semitones: 4, quality: '7th',  beats: 4 },
      { symbol: 'vi7',    semitones: 9, quality: 'm7',   beats: 4 },
      { symbol: 'II7',    semitones: 2, quality: '7th',  beats: 4 },
    ],
    usedIn: ['시부야계', '네오시티팝', '어반 J-Pop'],
    bpmRange: [95, 130],
    suggestedStyle: 'fingerpicking',
  },

  // ═══ MINOR (마이너 키 진행) ═══
  {
    id: 'devilish',
    name: 'Devilish',
    nameJa: '小悪魔進行',
    nameKo: '소악마진행',
    category: 'minor',
    description: 'vi부터 시작하는 마이너 감성 진행. 중독성이 강함.',
    mood: ['미스터리', '중독적', '어두운 매력'],
    difficulty: 2,
    steps: [
      { symbol: 'vi',  semitones: 9, quality: 'Minor', beats: 4 },
      { symbol: 'IV',  semitones: 5, quality: 'Major', beats: 4 },
      { symbol: 'V',   semitones: 7, quality: 'Major', beats: 4 },
      { symbol: 'I',   semitones: 0, quality: 'Major', beats: 4 },
    ],
    usedIn: ['보컬로이드 곡', '애니 OP', 'J-Pop 인기곡'],
    bpmRange: [120, 180],
    suggestedStyle: 'strum',
  },
  {
    id: 'noir',
    name: 'Noir',
    nameJa: 'ノワール進行',
    nameKo: '느와르 진행',
    category: 'minor',
    description: 'Natural Minor 기반. ♭VI→♭VII 상행이 만드는 긴장감.',
    mood: ['어두운', '긴장감', '강렬한'],
    difficulty: 3,
    steps: [
      { symbol: 'i',    semitones: 0, quality: 'Minor', beats: 4 },
      { symbol: 'bVI',  semitones: 8, quality: 'Major', beats: 4 },
      { symbol: 'bVII', semitones: 10, quality: 'Major', beats: 4 },
      { symbol: 'i',    semitones: 0, quality: 'Minor', beats: 4 },
    ],
    usedIn: ['J-Rock', '애니 배틀 OST', '다크 팝'],
    bpmRange: [100, 160],
    suggestedStyle: 'strum',
  },
  {
    id: 'minor-royal',
    name: 'Minor Royal Road',
    nameJa: 'マイナー王道',
    nameKo: '마이너 왕도',
    category: 'minor',
    description: '왕도진행의 마이너 버전. 슬프면서도 전진하는 느낌.',
    mood: ['슬픈', '결의', '전진'],
    difficulty: 3,
    steps: [
      { symbol: 'iv7',  semitones: 5, quality: 'm7',  beats: 4 },
      { symbol: 'V7',   semitones: 7, quality: '7th', beats: 4 },
      { symbol: 'i',    semitones: 0, quality: 'Minor', beats: 4 },
      { symbol: 'i',    semitones: 0, quality: 'Minor', beats: 4 },
    ],
    usedIn: ['J-Pop 발라드', '드라마 OST'],
    bpmRange: [60, 100],
    suggestedStyle: 'arpeggio',
  },

  // ═══ DRAMATIC (드라마틱/전개) ═══
  {
    id: 'rising-sun',
    name: 'Rising Sun',
    nameJa: '上昇進行',
    nameKo: '상승진행',
    category: 'dramatic',
    description: '반음씩 올라가는 베이스. 클라이맥스 직전에 사용.',
    mood: ['고양', '클라이맥스', '감동'],
    difficulty: 4,
    steps: [
      { symbol: 'I',    semitones: 0, quality: 'Major', beats: 4 },
      { symbol: 'I/3',  semitones: 0, quality: 'Major', beats: 4 },  // 1st inversion
      { symbol: 'IV',   semitones: 5, quality: 'Major', beats: 4 },
      { symbol: 'iv',   semitones: 5, quality: 'Minor', beats: 4 },  // borrowed chord
    ],
    usedIn: ['애니 클라이맥스', 'J-Pop 라스트 사비', '뮤지컬'],
    bpmRange: [70, 130],
    suggestedStyle: 'mix',
  },
  {
    id: 'halfstep-modulation',
    name: 'Half-Step Modulation',
    nameJa: '半音転調',
    nameKo: '반음 전조',
    category: 'dramatic',
    description: 'J-Pop 최다 사용 전조 패턴. 라스트 사비에서 반음 올림.',
    mood: ['극적', '클라이맥스', '해방감'],
    difficulty: 4,
    steps: [
      // Key: C에서의 마지막 4마디
      { symbol: 'IV',  semitones: 5, quality: 'Major', beats: 4 },
      { symbol: 'V',   semitones: 7, quality: 'Major', beats: 4 },
      // → Key: Db로 전조
      { symbol: 'IV*', semitones: 6, quality: 'Major', beats: 4 },  // Gb (new IV)
      { symbol: 'V*',  semitones: 8, quality: 'Major', beats: 4 },  // Ab (new V)
    ],
    usedIn: ['J-Pop 라스트 사비', '아이돌 곡 클라이맥스'],
    bpmRange: [100, 150],
    suggestedStyle: 'strum',
  },

  // ═══ CITYPOP (시티팝) ═══
  {
    id: 'citypop-groove',
    name: 'City Pop Groove',
    nameJa: 'シティポップ基本',
    nameKo: '시티팝 기본',
    category: 'citypop',
    description: '80년대 시티팝의 기본 그루브. 재즈적 텐션이 특징.',
    mood: ['그루비', '레트로', '여유로운'],
    difficulty: 3,
    steps: [
      { symbol: 'IMaj7',  semitones: 0, quality: 'Maj7', beats: 4 },
      { symbol: 'IVMaj7', semitones: 5, quality: 'Maj7', beats: 4 },
      { symbol: 'iii7',   semitones: 4, quality: 'm7',   beats: 4 },
      { symbol: 'vi7',    semitones: 9, quality: 'm7',   beats: 4 },
    ],
    usedIn: ['80년대 시티팝', '네오시티팝', 'Lo-fi J-Pop'],
    bpmRange: [85, 115],
    suggestedStyle: 'fingerpicking',
  },
  {
    id: 'citypop-ii-v',
    name: 'City Pop ii-V',
    nameJa: 'シティポップ ii-V',
    nameKo: '시티팝 ii-V',
    category: 'citypop',
    description: '재즈 ii-V 진행의 시티팝 응용. 세련된 코드 워크.',
    mood: ['세련된', '도시적', '밤'],
    difficulty: 4,
    steps: [
      { symbol: 'ii9',    semitones: 2, quality: 'm9',   beats: 4 },
      { symbol: 'V7',     semitones: 7, quality: '7th',  beats: 4 },
      { symbol: 'IMaj7',  semitones: 0, quality: 'Maj7', beats: 4 },
      { symbol: 'vi7',    semitones: 9, quality: 'm7',   beats: 4 },
    ],
    usedIn: ['시티팝 후기', '퓨전 재즈', 'AOR'],
    bpmRange: [90, 120],
    suggestedStyle: 'fingerpicking',
  },

  // ═══ BALLAD (발라드) ═══
  {
    id: 'jpop-ballad',
    name: 'J-Pop Ballad',
    nameJa: 'バラード定番',
    nameKo: 'J-Pop 발라드',
    category: 'ballad',
    description: '전형적인 J-Pop 발라드 진행. 아르페지오와 궁합이 좋음.',
    mood: ['슬픈', '감성적', '고요한'],
    difficulty: 2,
    steps: [
      { symbol: 'I',    semitones: 0, quality: 'Major', beats: 4 },
      { symbol: 'iii',  semitones: 4, quality: 'Minor', beats: 4 },
      { symbol: 'vi',   semitones: 9, quality: 'Minor', beats: 4 },
      { symbol: 'IV',   semitones: 5, quality: 'Major', beats: 2 },
      { symbol: 'V',    semitones: 7, quality: 'Major', beats: 2 },
    ],
    usedIn: ['J-Pop 발라드', '드라마 엔딩', '졸업식 곡'],
    bpmRange: [55, 80],
    suggestedStyle: 'arpeggio',
  },

  // ═══ ROCK (J-Rock) ═══
  {
    id: 'jrock-power',
    name: 'J-Rock Power',
    nameJa: 'Jロック定番',
    nameKo: 'J-Rock 정석',
    category: 'rock',
    description: '파워 코드 기반의 직선적인 J-Rock 진행.',
    mood: ['에너지', '직선적', '열정'],
    difficulty: 2,
    steps: [
      { symbol: 'I5',    semitones: 0, quality: '5 (Power)', beats: 4 },
      { symbol: 'bVII5', semitones: 10, quality: '5 (Power)', beats: 4 },
      { symbol: 'IV5',   semitones: 5, quality: '5 (Power)', beats: 4 },
      { symbol: 'V5',    semitones: 7, quality: '5 (Power)', beats: 4 },
    ],
    usedIn: ['J-Rock', '펑크', '애니 OP (배틀물)'],
    bpmRange: [140, 200],
    suggestedStyle: 'strum',
  },
  {
    id: 'anime-rock',
    name: 'Anime Rock',
    nameJa: 'アニメロック',
    nameKo: '애니 록',
    category: 'anime',
    description: '애니 OP에 자주 등장하는 에너지 넘치는 진행.',
    mood: ['열혈', '모험', '희망'],
    difficulty: 3,
    steps: [
      { symbol: 'vi',  semitones: 9, quality: 'Minor', beats: 4 },
      { symbol: 'IV',  semitones: 5, quality: 'Major', beats: 4 },
      { symbol: 'I',   semitones: 0, quality: 'Major', beats: 4 },
      { symbol: 'V',   semitones: 7, quality: 'Major', beats: 4 },
    ],
    usedIn: ['애니 OP', '배틀 장면', '소년만화 주제가'],
    bpmRange: [140, 190],
    suggestedStyle: 'strum',
  },

  // ═══ ANIME (애니 특화) ═══
  {
    id: 'anime-emotional',
    name: 'Anime Emotional',
    nameJa: 'アニメ感動',
    nameKo: '애니 감동 진행',
    category: 'anime',
    description: '애니 ED/삽입곡의 감동적인 진행. 사비에서 폭발.',
    mood: ['감동', '눈물', '성장'],
    difficulty: 3,
    steps: [
      { symbol: 'IVMaj7', semitones: 5, quality: 'Maj7', beats: 4 },
      { symbol: 'V',      semitones: 7, quality: 'Major', beats: 4 },
      { symbol: 'vi',     semitones: 9, quality: 'Minor', beats: 4 },
      { symbol: 'I',      semitones: 0, quality: 'Major', beats: 4 },
    ],
    usedIn: ['애니 ED', '감동 장면 BGM', '졸업/이별 에피소드'],
    bpmRange: [70, 130],
    suggestedStyle: 'mix',
  },
  {
    id: 'bocchi-style',
    name: 'Bocchi-style',
    nameJa: 'ぼっち系',
    nameKo: '봇치 스타일',
    category: 'anime',
    description: '봇치 더 락 스타일의 인디/얼터너티브 록 진행.',
    mood: ['불안', '에너지', '반항'],
    difficulty: 3,
    steps: [
      { symbol: 'i',     semitones: 0, quality: 'Minor', beats: 4 },
      { symbol: 'bVI',   semitones: 8, quality: 'Major', beats: 4 },
      { symbol: 'III',   semitones: 3, quality: 'Major', beats: 4 },
      { symbol: 'bVII',  semitones: 10, quality: 'Major', beats: 4 },
    ],
    usedIn: ['인디 록', '얼터너티브', '봇치 더 락 스타일'],
    bpmRange: [130, 180],
    suggestedStyle: 'strum',
  },
]

// ─── Helper Functions ───────────────────────────────

/** 카테고리별 진행 필터링 */
export function getProgressionsByCategory(category: JPopProgressionCategory): JPopProgression[] {
  return JPOP_PROGRESSIONS.filter(p => p.category === category)
}

/** 난이도별 진행 필터링 */
export function getProgressionsByDifficulty(maxDifficulty: number): JPopProgression[] {
  return JPOP_PROGRESSIONS.filter(p => p.difficulty <= maxDifficulty)
}

/** 무드별 진행 검색 */
export function searchProgressionsByMood(mood: string): JPopProgression[] {
  return JPOP_PROGRESSIONS.filter(p =>
    p.mood.some(m => m.includes(mood)),
  )
}

/**
 * J-Pop 진행을 기존 PROGRESSION_PRESETS 형식의 ProgressionStep[]으로 변환.
 * 기존 resolveProgression()과 호환되도록.
 *
 * NOTE: 기존 시스템은 다이어토닉 7도만 지원하므로,
 * secondary dominant 등은 qualityOverride로 처리.
 */
export function toProgressionSteps(prog: JPopProgression): ProgressionStep[] {
  return prog.steps.map(step => {
    // semitones → 가장 가까운 diatonic degree index 매핑
    const degreeMap: Record<number, number> = {
      0: 0, 2: 1, 3: 2, 4: 2, 5: 3, 7: 4, 8: 5, 9: 5, 10: 6, 11: 6,
    }
    const degreeIndex = degreeMap[step.semitones] ?? 0
    return {
      degreeIndex,
      qualityOverride: step.quality !== getDefaultQuality(degreeIndex) ? step.quality : undefined,
    }
  })
}

function getDefaultQuality(degreeIndex: number): string {
  const defaults = ['Major', 'Minor', 'Minor', 'Major', 'Major', 'Minor', 'dim']
  return defaults[degreeIndex] ?? 'Major'
}
