/**
 * Song Database for Bocchi-master
 *
 * 곡 데이터베이스 — 코드 진행 + 구조 정보만 저장.
 * 멜로디/가사 없음 (저작권 안전).
 * 코드 진행 자체는 저작권 대상이 아님.
 *
 * 곡 분류:
 * - practice: 커리큘럼용 연습 곡 (오리지널/전통)
 * - reference: 실제 J-Pop 곡의 코드 진행 구조 참조
 */

import type { NoteName } from '../types/music'

// ─── Types ──────────────────────────────────────────

export interface Song {
  id: string
  title: string
  artist?: string
  anime?: string              // 애니 출처 (있는 경우)
  bpm: number
  key: NoteName
  timeSignature: [number, number]  // [beats, beatUnit] e.g. [4, 4]
  difficulty: 1 | 2 | 3 | 4 | 5
  genre: SongGenre[]
  sections: SongSection[]
  tags: string[]
  levelId: string             // 커리큘럼 레벨 매핑
  type: 'practice' | 'reference'
  /** 추천 카포 위치 (0 = no capo) */
  capo?: number
  /** 추천 연주 스타일 */
  playStyle: PlayStyle[]
  /** 곡 설명/해설 */
  description?: string
}

export type SongGenre = 'jpop' | 'jrock' | 'anime' | 'citypop' | 'ballad' | 'vocaloid' | 'practice'
export type PlayStyle = 'strum' | 'arpeggio' | 'fingerpicking' | 'power-chord' | 'mix'

export interface SongSection {
  name: SectionName
  /** 이 섹션의 반복 횟수 (기본 1) */
  repeat?: number
  chords: SectionChord[]
  /** 추천 스트럼 패턴 (strumPatterns.ts 참조) */
  strumPattern?: string
  /** 연주 팁 */
  notes?: string
  /** 이 섹션의 BPM 오버라이드 (전조/템포 체인지) */
  bpmOverride?: number
  /** 전조: 이 섹션에서의 키 변경 */
  keyChange?: NoteName
}

export type SectionName =
  | 'intro' | 'verse' | 'pre-chorus' | 'chorus'
  | 'bridge' | 'interlude' | 'solo' | 'outro'
  | 'verse2' | 'chorus2' | 'final-chorus'

export interface SectionChord {
  /** 코드 심볼 (예: 'FM7', 'G7', 'Am') */
  chord: string
  /** 이 코드가 차지하는 박자 수 */
  beats: number
  /** 보이싱 힌트 */
  voicingHint?: 'open' | 'barre' | 'high-position' | 'power' | 'capo'
  /** 특별 주석 (뮤트, 아르페지오 등) */
  technique?: string
}

// ─── Practice Songs (오리지널/전통곡) ────────────────

const PRACTICE_SONGS: Song[] = [
  {
    id: 'twinkle-star',
    title: 'きらきら星 (반짝반짝 작은별)',
    bpm: 100,
    key: 'C',
    timeSignature: [4, 4],
    difficulty: 1,
    genre: ['practice'],
    tags: ['beginner', 'open-chord'],
    levelId: 'level-1',
    type: 'practice',
    playStyle: ['strum'],
    description: '가장 기본적인 C-F-G 코드 진행 연습.',
    sections: [
      {
        name: 'verse',
        chords: [
          { chord: 'C', beats: 4 },
          { chord: 'C', beats: 4 },
          { chord: 'F', beats: 4 },
          { chord: 'C', beats: 4 },
          { chord: 'F', beats: 4 },
          { chord: 'C', beats: 4 },
          { chord: 'G', beats: 4 },
          { chord: 'C', beats: 4 },
        ],
        strumPattern: 'All Down',
        notes: '한 코드당 4박 다운 스트럼',
      },
    ],
  },
  {
    id: 'simple-punk-progression',
    title: '펑크 파워 코드 연습',
    bpm: 140,
    key: 'E',
    timeSignature: [4, 4],
    difficulty: 1,
    genre: ['practice'],
    tags: ['power-chord', 'punk', 'beginner'],
    levelId: 'level-1',
    type: 'practice',
    playStyle: ['power-chord'],
    description: '파워 코드만으로 구성된 간단한 펑크 진행.',
    sections: [
      {
        name: 'verse',
        repeat: 4,
        chords: [
          { chord: 'E5', beats: 4, voicingHint: 'power' },
          { chord: 'A5', beats: 4, voicingHint: 'power' },
          { chord: 'B5', beats: 4, voicingHint: 'power' },
          { chord: 'E5', beats: 4, voicingHint: 'power' },
        ],
        strumPattern: 'All Down',
        notes: '팜 뮤트 넣으면 더 좋음',
      },
    ],
  },

  // ─── Level 2 Practice ─────────────────────────────
  {
    id: 'seventh-practice',
    title: '세븐스 코드 연습곡',
    bpm: 75,
    key: 'C',
    timeSignature: [4, 4],
    difficulty: 2,
    genre: ['practice'],
    tags: ['seventh', 'jpop-feel'],
    levelId: 'level-2',
    type: 'practice',
    playStyle: ['strum', 'arpeggio'],
    description: 'CM7→Am7→FM7→G7 진행으로 세븐스 코드 연습.',
    sections: [
      {
        name: 'verse',
        repeat: 4,
        chords: [
          { chord: 'CM7', beats: 4 },
          { chord: 'Am7', beats: 4 },
          { chord: 'FM7', beats: 4 },
          { chord: 'G7', beats: 4 },
        ],
        strumPattern: 'Down-Up',
        notes: '첫째는 다운-업 스트럼, 익숙해지면 아르페지오로 전환',
      },
    ],
  },

  // ─── Level 3 Practice (J-Pop 입문) ────────────────
  {
    id: 'jpop-royal-road-1',
    title: '왕도진행 연습곡 #1',
    bpm: 80,
    key: 'C',
    timeSignature: [4, 4],
    difficulty: 2,
    genre: ['practice', 'jpop'],
    tags: ['royal-road', 'jpop-progression'],
    levelId: 'level-3',
    type: 'practice',
    playStyle: ['strum'],
    description: '왕도진행(FM7→G7→Em7→Am)을 반복 연습하는 곡.',
    sections: [
      {
        name: 'intro',
        chords: [
          { chord: 'CM7', beats: 8 },
        ],
        notes: '첫 코드를 아르페지오로 울리며 시작',
      },
      {
        name: 'verse',
        repeat: 2,
        chords: [
          { chord: 'FM7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'Em7', beats: 4 },
          { chord: 'Am', beats: 4 },
        ],
        strumPattern: 'Pop Standard',
        notes: '왕도진행: FM7→G7→Em7→Am',
      },
      {
        name: 'chorus',
        repeat: 2,
        chords: [
          { chord: 'FM7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'Em7', beats: 4 },
          { chord: 'Am', beats: 4 },
          { chord: 'FM7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'CM7', beats: 8 },
        ],
        strumPattern: 'Pop Standard',
        notes: '사비에서 마지막에 CM7으로 해결',
      },
      {
        name: 'outro',
        chords: [
          { chord: 'FM7', beats: 4 },
          { chord: 'CM7', beats: 8 },
        ],
      },
    ],
  },
  {
    id: 'jpop-beginner-1',
    title: 'J-Pop 입문곡 #1 (카논 + 왕도 Mix)',
    bpm: 85,
    key: 'G',
    timeSignature: [4, 4],
    difficulty: 2,
    genre: ['practice', 'jpop'],
    tags: ['canon', 'royal-road', 'beginner-jpop'],
    levelId: 'level-3',
    type: 'practice',
    capo: 0,
    playStyle: ['strum', 'arpeggio'],
    description: 'Verse는 카논진행, Chorus는 왕도진행으로 구성된 입문곡.',
    sections: [
      {
        name: 'intro',
        chords: [
          { chord: 'G', beats: 4, technique: 'arpeggio' },
          { chord: 'D', beats: 4, technique: 'arpeggio' },
          { chord: 'Em', beats: 4, technique: 'arpeggio' },
          { chord: 'Bm', beats: 4, technique: 'arpeggio' },
        ],
        notes: '아르페지오로 부드럽게 시작',
      },
      {
        name: 'verse',
        repeat: 2,
        chords: [
          { chord: 'G', beats: 4 },
          { chord: 'D', beats: 4 },
          { chord: 'Em', beats: 4 },
          { chord: 'Bm', beats: 4 },
          { chord: 'C', beats: 4 },
          { chord: 'G', beats: 4 },
          { chord: 'C', beats: 4 },
          { chord: 'D', beats: 4 },
        ],
        strumPattern: 'Down-Up',
        notes: '카논진행: G→D→Em→Bm→C→G→C→D',
      },
      {
        name: 'pre-chorus',
        chords: [
          { chord: 'C', beats: 4 },
          { chord: 'D', beats: 4 },
          { chord: 'Em', beats: 4 },
          { chord: 'D', beats: 4 },
        ],
        notes: '프리 코러스에서 텐션 빌드업',
      },
      {
        name: 'chorus',
        repeat: 2,
        chords: [
          { chord: 'CM7', beats: 4 },
          { chord: 'D7', beats: 4 },
          { chord: 'Bm7', beats: 4 },
          { chord: 'Em', beats: 4 },
        ],
        strumPattern: 'Pop Standard',
        notes: '왕도진행 (Key of G): CM7→D7→Bm7→Em',
      },
      {
        name: 'outro',
        chords: [
          { chord: 'C', beats: 4 },
          { chord: 'D', beats: 4 },
          { chord: 'G', beats: 8 },
        ],
        notes: '마지막은 G를 길게 울리며 마무리',
      },
    ],
  },

  // ─── Level 4~5 Practice ───────────────────────────
  {
    id: 'jpop-easy-1',
    title: 'J-Pop 중급곡 #1 (아르페지오 + 스트럼 Mix)',
    bpm: 95,
    key: 'C',
    timeSignature: [4, 4],
    difficulty: 3,
    genre: ['jpop', 'practice'],
    tags: ['arpeggio', 'strum-mix', 'level5'],
    levelId: 'level-5',
    type: 'practice',
    playStyle: ['mix'],
    description: 'Verse 아르페지오→Chorus 스트럼 전환 연습.',
    sections: [
      {
        name: 'intro',
        chords: [
          { chord: 'Am7', beats: 4, technique: 'arpeggio' },
          { chord: 'FM7', beats: 4, technique: 'arpeggio' },
        ],
        notes: '아르페지오로 시작',
      },
      {
        name: 'verse',
        repeat: 2,
        chords: [
          { chord: 'Am7', beats: 4, technique: 'arpeggio' },
          { chord: 'FM7', beats: 4, technique: 'arpeggio' },
          { chord: 'CM7', beats: 4, technique: 'arpeggio' },
          { chord: 'G', beats: 4, technique: 'arpeggio' },
        ],
        notes: 'Verse는 아르페지오로 연주',
      },
      {
        name: 'pre-chorus',
        chords: [
          { chord: 'FM7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'Em7', beats: 4 },
          { chord: 'Am', beats: 4 },
        ],
        strumPattern: 'D DU',
        notes: '프리코러스에서 스트럼으로 전환 시작',
      },
      {
        name: 'chorus',
        repeat: 2,
        chords: [
          { chord: 'FM7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'Em7', beats: 4 },
          { chord: 'Am', beats: 4 },
          { chord: 'Dm7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'CM7', beats: 8 },
        ],
        strumPattern: 'Pop Standard',
        notes: '사비는 풀 스트럼으로 에너지 업',
      },
      {
        name: 'bridge',
        chords: [
          { chord: 'Dm7', beats: 4, technique: 'arpeggio' },
          { chord: 'Em7', beats: 4, technique: 'arpeggio' },
          { chord: 'FM7', beats: 4 },
          { chord: 'G', beats: 4 },
        ],
        notes: '브릿지에서 잠시 다이나믹 낮추기',
      },
      {
        name: 'final-chorus',
        repeat: 2,
        chords: [
          { chord: 'FM7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'Em7', beats: 4 },
          { chord: 'Am', beats: 4 },
          { chord: 'Dm7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'CM7', beats: 8 },
        ],
        strumPattern: 'Pop Standard',
        notes: '라스트 사비 — 에너지 최고점',
      },
      {
        name: 'outro',
        chords: [
          { chord: 'FM7', beats: 4, technique: 'arpeggio' },
          { chord: 'CM7', beats: 8, technique: 'arpeggio' },
        ],
        notes: '아르페지오로 마무리',
      },
    ],
  },
]

// ─── Bass Practice Songs ─────────────────────────────

const BASS_PRACTICE_SONGS: Song[] = [
  // Level 1: 베이스 기초
  {
    id: 'bass-root-exercise-1',
    title: '루트 연주 기초 연습곡',
    bpm: 80,
    key: 'C',
    timeSignature: [4, 4],
    difficulty: 1,
    genre: ['practice'],
    tags: ['bass', 'beginner', 'root-only'],
    levelId: 'bass-level-1',
    type: 'practice',
    playStyle: ['fingerpicking'],
    description: 'C-G-Am-F 진행에서 루트만 연주하는 기초 연습.',
    sections: [
      {
        name: 'verse',
        repeat: 4,
        chords: [
          { chord: 'C', beats: 4 },
          { chord: 'G', beats: 4 },
          { chord: 'Am', beats: 4 },
          { chord: 'F', beats: 4 },
        ],
        notes: '매 마디 루트 음만 4분음표로 연주',
      },
    ],
  },
  {
    id: 'bass-eighth-root-1',
    title: '8비트 루트 연습곡',
    bpm: 85,
    key: 'G',
    timeSignature: [4, 4],
    difficulty: 1,
    genre: ['practice'],
    tags: ['bass', 'beginner', 'eighth-note'],
    levelId: 'bass-level-1',
    type: 'practice',
    playStyle: ['fingerpicking'],
    description: '8비트 루트 연주로 안정적인 타이밍 형성.',
    sections: [
      {
        name: 'verse',
        repeat: 4,
        chords: [
          { chord: 'G', beats: 4 },
          { chord: 'Em', beats: 4 },
          { chord: 'C', beats: 4 },
          { chord: 'D', beats: 4 },
        ],
        notes: '매 박 8분음표로 루트를 반복 연주',
      },
    ],
  },

  // Level 2: 리듬의 뼈대
  {
    id: 'bass-root-fifth-1',
    title: '루트-5도 패턴 연습곡',
    bpm: 90,
    key: 'C',
    timeSignature: [4, 4],
    difficulty: 2,
    genre: ['practice'],
    tags: ['bass', 'root-fifth', 'pattern'],
    levelId: 'bass-level-2',
    type: 'practice',
    playStyle: ['fingerpicking'],
    description: '루트와 5도를 교대하는 기본 베이스 패턴.',
    sections: [
      {
        name: 'verse',
        repeat: 4,
        chords: [
          { chord: 'C', beats: 4 },
          { chord: 'Am', beats: 4 },
          { chord: 'F', beats: 4 },
          { chord: 'G', beats: 4 },
        ],
        notes: '각 코드에서 루트→5도→루트→5도 패턴',
      },
    ],
  },
  {
    id: 'bass-octave-bounce-1',
    title: '옥타브 바운스 연습곡',
    bpm: 95,
    key: 'A',
    timeSignature: [4, 4],
    difficulty: 2,
    genre: ['practice', 'jpop'],
    tags: ['bass', 'octave', 'bounce'],
    levelId: 'bass-level-2',
    type: 'practice',
    playStyle: ['fingerpicking'],
    description: 'J-Pop 스타일 옥타브 바운스 패턴.',
    sections: [
      {
        name: 'verse',
        repeat: 4,
        chords: [
          { chord: 'Am', beats: 4 },
          { chord: 'F', beats: 4 },
          { chord: 'C', beats: 4 },
          { chord: 'G', beats: 4 },
        ],
        notes: '루트→옥타브 위→루트→옥타브 위 바운스',
      },
    ],
  },

  // Level 3: J-Pop 베이스라인 입문
  {
    id: 'bass-approach-1',
    title: '어프로치 노트 연습곡',
    bpm: 80,
    key: 'C',
    timeSignature: [4, 4],
    difficulty: 2,
    genre: ['practice', 'jpop'],
    tags: ['bass', 'approach-note', 'melodic'],
    levelId: 'bass-level-3',
    type: 'practice',
    playStyle: ['fingerpicking'],
    description: '코드 전환 시 크로매틱/다이어토닉 어프로치.',
    sections: [
      {
        name: 'verse',
        repeat: 2,
        chords: [
          { chord: 'C', beats: 4 },
          { chord: 'Am', beats: 4 },
          { chord: 'Dm', beats: 4 },
          { chord: 'G', beats: 4 },
        ],
        notes: '각 코드 마지막 박에서 다음 코드 루트로 어프로치',
      },
      {
        name: 'chorus',
        repeat: 2,
        chords: [
          { chord: 'FM7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'Em7', beats: 4 },
          { chord: 'Am', beats: 4 },
        ],
        notes: '왕도진행 어프로치 라인',
      },
    ],
  },
  {
    id: 'bass-walking-1',
    title: '워킹 베이스 연습곡',
    bpm: 75,
    key: 'C',
    timeSignature: [4, 4],
    difficulty: 3,
    genre: ['practice', 'jpop'],
    tags: ['bass', 'walking', 'chord-tone'],
    levelId: 'bass-level-3',
    type: 'practice',
    playStyle: ['fingerpicking'],
    description: '코드 톤을 활용한 워킹 베이스 연습.',
    sections: [
      {
        name: 'verse',
        repeat: 4,
        chords: [
          { chord: 'Dm7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'CM7', beats: 4 },
          { chord: 'Am7', beats: 4 },
        ],
        notes: '매 박 다른 음: R-3-5-approach → 다음 코드',
      },
    ],
  },

  // Level 4: 그루브와 테크닉
  {
    id: 'bass-ghost-groove-1',
    title: '고스트 노트 그루브 연습곡',
    bpm: 90,
    key: 'A',
    timeSignature: [4, 4],
    difficulty: 3,
    genre: ['practice'],
    tags: ['bass', 'ghost-note', 'groove', 'funky'],
    levelId: 'bass-level-4',
    type: 'practice',
    playStyle: ['fingerpicking'],
    description: '고스트 노트를 넣어 그루비한 베이스라인 연습.',
    sections: [
      {
        name: 'verse',
        repeat: 4,
        chords: [
          { chord: 'Am', beats: 4 },
          { chord: 'Dm', beats: 4 },
          { chord: 'G', beats: 4 },
          { chord: 'C', beats: 4 },
        ],
        notes: 'R-x-x-R-x-5-x-R 패턴 (x=고스트노트)',
      },
    ],
  },
  {
    id: 'bass-slap-intro-1',
    title: '슬랩 베이스 입문 연습곡',
    bpm: 75,
    key: 'E',
    timeSignature: [4, 4],
    difficulty: 3,
    genre: ['practice'],
    tags: ['bass', 'slap', 'thumb-pop'],
    levelId: 'bass-level-4',
    type: 'practice',
    playStyle: ['fingerpicking'],
    description: '썸-플럭 교대 기본 슬랩 패턴.',
    sections: [
      {
        name: 'verse',
        repeat: 4,
        chords: [
          { chord: 'Em', beats: 4 },
          { chord: 'Am', beats: 4 },
          { chord: 'D', beats: 4 },
          { chord: 'G', beats: 4 },
        ],
        notes: 'T-P-T-T-P 슬랩 패턴 (느린 템포)',
      },
    ],
  },

  // Level 5: J-Pop 심화
  {
    id: 'bass-citypop-1',
    title: '시티팝 베이스 연습곡',
    bpm: 100,
    key: 'C',
    timeSignature: [4, 4],
    difficulty: 4,
    genre: ['practice', 'citypop'],
    tags: ['bass', 'citypop', 'groove', 'tension'],
    levelId: 'bass-level-5',
    type: 'practice',
    playStyle: ['fingerpicking'],
    description: '시티팝 스타일의 그루비한 베이스라인.',
    sections: [
      {
        name: 'intro',
        chords: [
          { chord: 'CM7', beats: 8, technique: 'arpeggio' },
        ],
        notes: '코드 톤 아르페지오로 시작',
      },
      {
        name: 'verse',
        repeat: 2,
        chords: [
          { chord: 'CM7', beats: 4 },
          { chord: 'FM7', beats: 4 },
          { chord: 'Em7', beats: 4 },
          { chord: 'Am7', beats: 4 },
        ],
        notes: '코드 톤 + 크로매틱 경과음, 16비트 그루브',
      },
      {
        name: 'chorus',
        repeat: 2,
        chords: [
          { chord: 'Dm9', beats: 4 },
          { chord: 'G13', beats: 4 },
          { chord: 'CM7', beats: 4 },
          { chord: 'A7', beats: 4 },
        ],
        notes: 'ii-V-I 펑키 패턴으로 에너지 업',
      },
      {
        name: 'outro',
        chords: [
          { chord: 'FM7', beats: 4 },
          { chord: 'CM7', beats: 8 },
        ],
      },
    ],
  },
  {
    id: 'bass-jrock-drive-1',
    title: 'J-Rock 드라이브 연습곡',
    bpm: 155,
    key: 'A',
    timeSignature: [4, 4],
    difficulty: 4,
    genre: ['practice', 'jrock'],
    tags: ['bass', 'jrock', 'drive', 'fast'],
    levelId: 'bass-level-5',
    type: 'practice',
    playStyle: ['fingerpicking'],
    description: '빠른 BPM의 J-Rock 8비트 드라이브.',
    sections: [
      {
        name: 'verse',
        repeat: 2,
        chords: [
          { chord: 'Am', beats: 4 },
          { chord: 'F', beats: 4 },
          { chord: 'C', beats: 4 },
          { chord: 'G', beats: 4 },
        ],
        notes: 'verse: 루트 위주, 다이내믹 낮게',
      },
      {
        name: 'chorus',
        repeat: 2,
        chords: [
          { chord: 'Am', beats: 4 },
          { chord: 'F', beats: 4 },
          { chord: 'C', beats: 4 },
          { chord: 'G', beats: 4 },
        ],
        notes: 'chorus: 옥타브 + 풀 에너지',
      },
    ],
  },

  // Level 6: 밴드 시뮬레이션
  {
    id: 'bass-full-jpop-1',
    title: 'J-Pop 풀 구조 연습곡',
    bpm: 120,
    key: 'C',
    timeSignature: [4, 4],
    difficulty: 5,
    genre: ['practice', 'jpop'],
    tags: ['bass', 'full-structure', 'advanced'],
    levelId: 'bass-level-6',
    type: 'practice',
    playStyle: ['mix'],
    description: '풀 곡 구조에서 섹션별 다이내믹 변화를 적용한 종합 연습.',
    sections: [
      {
        name: 'intro',
        chords: [
          { chord: 'CM7', beats: 4, technique: 'arpeggio' },
          { chord: 'Am7', beats: 4, technique: 'arpeggio' },
        ],
        notes: '심플한 코드 톤 아르페지오',
      },
      {
        name: 'verse',
        repeat: 2,
        chords: [
          { chord: 'Am7', beats: 4 },
          { chord: 'FM7', beats: 4 },
          { chord: 'CM7', beats: 4 },
          { chord: 'G', beats: 4 },
        ],
        notes: 'A멜: 루트 위주 심플하게',
      },
      {
        name: 'pre-chorus',
        chords: [
          { chord: 'Dm7', beats: 4 },
          { chord: 'Em7', beats: 4 },
          { chord: 'FM7', beats: 4 },
          { chord: 'G', beats: 4 },
        ],
        notes: 'B멜: 점진적 빌드업, 어프로치 추가',
      },
      {
        name: 'chorus',
        repeat: 2,
        chords: [
          { chord: 'FM7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'Em7', beats: 4 },
          { chord: 'Am', beats: 4 },
          { chord: 'Dm7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'CM7', beats: 8 },
        ],
        notes: '사비: 풀 에너지, 옥타브+코드톤 워킹',
      },
      {
        name: 'bridge',
        chords: [
          { chord: 'Dm7', beats: 4, technique: 'arpeggio' },
          { chord: 'Em7', beats: 4, technique: 'arpeggio' },
          { chord: 'FM7', beats: 8 },
        ],
        notes: '브릿지: 다이내믹 다운',
      },
      {
        name: 'final-chorus',
        repeat: 2,
        chords: [
          { chord: 'FM7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'Em7', beats: 4 },
          { chord: 'Am', beats: 4 },
          { chord: 'Dm7', beats: 4 },
          { chord: 'G7', beats: 4 },
          { chord: 'CM7', beats: 8 },
        ],
        notes: '대사비: 필인 추가, 최대 에너지',
      },
      {
        name: 'outro',
        chords: [
          { chord: 'FM7', beats: 4 },
          { chord: 'G', beats: 4 },
          { chord: 'CM7', beats: 8 },
        ],
        notes: '아웃트로: 점진적 심플하게 마무리',
      },
    ],
  },
]

// ─── Song Database ──────────────────────────────────

export const SONG_DATABASE: Song[] = [
  ...PRACTICE_SONGS,
  ...BASS_PRACTICE_SONGS,
]

// ─── Helper Functions ───────────────────────────────

/** 레벨별 곡 필터 */
export function getSongsByLevel(levelId: string): Song[] {
  return SONG_DATABASE.filter(s => s.levelId === levelId)
}

/** 난이도별 곡 필터 */
export function getSongsByDifficulty(maxDifficulty: number): Song[] {
  return SONG_DATABASE.filter(s => s.difficulty <= maxDifficulty)
}

/** 장르별 곡 필터 */
export function getSongsByGenre(genre: SongGenre): Song[] {
  return SONG_DATABASE.filter(s => s.genre.includes(genre))
}

/** 태그 검색 */
export function searchSongsByTag(tag: string): Song[] {
  return SONG_DATABASE.filter(s =>
    s.tags.some(t => t.toLowerCase().includes(tag.toLowerCase())),
  )
}

/** 곡 ID로 찾기 */
export function findSong(songId: string): Song | undefined {
  return SONG_DATABASE.find(s => s.id === songId)
}

/** 곡의 전체 코드 수 (박자 기준) */
export function getSongTotalBeats(song: Song): number {
  return song.sections.reduce((total, section) => {
    const sectionBeats = section.chords.reduce((s, c) => s + c.beats, 0)
    return total + sectionBeats * (section.repeat ?? 1)
  }, 0)
}

/** 곡의 예상 연주 시간 (초) */
export function getSongDuration(song: Song): number {
  const totalBeats = getSongTotalBeats(song)
  const beatsPerSecond = song.bpm / 60
  return Math.round(totalBeats / beatsPerSecond)
}

/** 곡에서 사용되는 유니크 코드 목록 */
export function getSongUniqueChords(song: Song): string[] {
  const chords = new Set<string>()
  for (const section of song.sections) {
    for (const chord of section.chords) {
      chords.add(chord.chord)
    }
  }
  return Array.from(chords).sort()
}
