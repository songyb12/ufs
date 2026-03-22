/**
 * Gamification System for Bocchi-master
 *
 * XP, 레벨, 업적, 칭호, 일일 미션 등 게임화 요소.
 * Life-Master의 게이미피케이션 시스템(27단계 RPG 칭호)을 참고하되
 * 음악/기타에 특화된 구조.
 */

// ─── Player Profile ─────────────────────────────────

export interface PlayerProfile {
  /** 누적 경험치 */
  xp: number
  /** 현재 레벨 (0-based index into PLAYER_LEVELS) */
  level: number
  /** 달성한 업적 ID 목록 */
  achievements: string[]
  /** 연속 연습 일수 (현재) */
  streakDays: number
  /** 최대 연속 연습 일수 */
  bestStreakDays: number
  /** 총 연습 시간 (분) */
  totalPracticeMinutes: number
  /** 완료한 레슨 ID */
  completedLessons: string[]
  /** 완료한 드릴 ID */
  completedDrills: string[]
  /** 완료한 곡 ID */
  completedSongs: string[]
  /** 드릴별 최고 점수 */
  drillScores: Record<string, DrillBestScore>
  /** 마지막 연습 날짜 (YYYY-MM-DD) */
  lastPracticeDate: string
  /** 일일 연습 기록 (날짜 → 초) */
  dailyPracticeLog: Record<string, number>
  /** 선택한 악기 */
  instrument: 'guitar' | 'bass'
  /** 선택한 커리큘럼 ID */
  curriculumId: string
  /** 프로필 생성 날짜 */
  createdAt: string
}

export interface DrillBestScore {
  accuracy: number
  bpm?: number
  streak?: number
  completedAt: string
  attempts: number
}

// ─── Level System (27 Levels) ───────────────────────

export interface PlayerLevel {
  level: number
  title: string           // 한국어 칭호
  titleEn: string         // 영어 칭호
  titleJa?: string        // 일본어 칭호 (봇치 테마용)
  requiredXP: number      // 이 레벨에 필요한 누적 XP
  icon: string
  color: string           // Tailwind color class
}

export const PLAYER_LEVELS: PlayerLevel[] = [
  { level: 0,  title: '완전 초보',        titleEn: 'Absolute Beginner',   titleJa: 'ぼっち',           requiredXP: 0,     icon: '🌱', color: 'gray' },
  { level: 1,  title: '기타 입문자',      titleEn: 'Novice',             titleJa: '初心者',            requiredXP: 50,    icon: '🎸', color: 'gray' },
  { level: 2,  title: '코드 학습자',      titleEn: 'Chord Learner',      titleJa: 'コード練習生',       requiredXP: 150,   icon: '📖', color: 'green' },
  { level: 3,  title: '오픈 코드 마스터', titleEn: 'Open Chord Master',   titleJa: 'オープンコード師',   requiredXP: 300,   icon: '✅', color: 'green' },
  { level: 4,  title: '리듬 감지자',      titleEn: 'Rhythm Seeker',      titleJa: 'リズム探求者',       requiredXP: 500,   icon: '🥁', color: 'green' },
  { level: 5,  title: '바레 코드 도전자', titleEn: 'Barre Challenger',    titleJa: 'バレーコード挑戦者', requiredXP: 750,   icon: '💪', color: 'blue' },
  { level: 6,  title: '세븐스 탐험가',   titleEn: 'Seventh Explorer',    titleJa: 'セブンス探検家',     requiredXP: 1000,  icon: '🔮', color: 'blue' },
  { level: 7,  title: 'J-Pop 입문자',    titleEn: 'J-Pop Newcomer',      titleJa: 'J-POP入門者',       requiredXP: 1400,  icon: '🎵', color: 'blue' },
  { level: 8,  title: '왕도진행 수련생', titleEn: 'Royal Road Student',   titleJa: '王道進行修練生',     requiredXP: 1800,  icon: '👑', color: 'blue' },
  { level: 9,  title: '코드 마스터',     titleEn: 'Chord Master',         titleJa: 'コードマスター',     requiredXP: 2400,  icon: '🏆', color: 'purple' },
  { level: 10, title: '아르페지오 견습', titleEn: 'Arpeggio Apprentice',  titleJa: 'アルペジオ見習い',   requiredXP: 3000,  icon: '🌊', color: 'purple' },
  { level: 11, title: '테크니션',       titleEn: 'Technician',            titleJa: 'テクニシャン',       requiredXP: 3800,  icon: '⚡', color: 'purple' },
  { level: 12, title: '펜타 워리어',    titleEn: 'Pentatonic Warrior',    titleJa: 'ペンタ戦士',        requiredXP: 4600,  icon: '⚔️', color: 'purple' },
  { level: 13, title: '밴드 멤버',      titleEn: 'Band Member',           titleJa: 'バンドメンバー',     requiredXP: 5500,  icon: '🎤', color: 'orange' },
  { level: 14, title: '곡 마스터',      titleEn: 'Song Master',           titleJa: 'ソングマスター',     requiredXP: 6500,  icon: '🎶', color: 'orange' },
  { level: 15, title: '스테이지 도전자', titleEn: 'Stage Challenger',     titleJa: 'ステージ挑戦者',     requiredXP: 7800,  icon: '🎪', color: 'orange' },
  { level: 16, title: '전조의 달인',    titleEn: 'Key Change Master',     titleJa: '転調の達人',        requiredXP: 9200,  icon: '🔄', color: 'orange' },
  { level: 17, title: '즉흥 연주자',    titleEn: 'Improviser',            titleJa: 'インプロバイザー',   requiredXP: 11000, icon: '💫', color: 'red' },
  { level: 18, title: '시티팝 마스터',  titleEn: 'City Pop Master',       titleJa: 'シティポップマスター', requiredXP: 13000, icon: '🌃', color: 'red' },
  { level: 19, title: '세션 기타리스트', titleEn: 'Session Guitarist',    titleJa: 'セッションギタリスト', requiredXP: 15500, icon: '🎙️', color: 'red' },
  { level: 20, title: '마에스트로',     titleEn: 'Maestro',               titleJa: 'マエストロ',        requiredXP: 18500, icon: '🎼', color: 'red' },
  { level: 21, title: '전설의 기타리스트', titleEn: 'Legendary Guitarist', titleJa: '伝説のギタリスト',  requiredXP: 22000, icon: '🌟', color: 'yellow' },
  { level: 22, title: '음악의 현인',    titleEn: 'Music Sage',            titleJa: '音楽の賢者',        requiredXP: 26000, icon: '🧙', color: 'yellow' },
  { level: 23, title: '결속밴드 멤버',  titleEn: 'Kessoku Band Member',   titleJa: '結束バンドメンバー', requiredXP: 31000, icon: '🎸', color: 'yellow' },
  { level: 24, title: '기타 히어로',    titleEn: 'Guitar Hero',           titleJa: 'ギターヒーロー',     requiredXP: 37000, icon: '🦸', color: 'yellow' },
  { level: 25, title: '음악의 신',      titleEn: 'God of Music',          titleJa: '音楽の神',          requiredXP: 45000, icon: '👼', color: 'yellow' },
  { level: 26, title: '봇치 마스터',    titleEn: 'Bocchi Master',         titleJa: 'ぼっちマスター',     requiredXP: 55000, icon: '🏅', color: 'yellow' },
]

// ─── Achievement System ─────────────────────────────

export type AchievementCategory =
  | 'milestone'     // 마일스톤 (첫 xx)
  | 'streak'        // 연속 기록
  | 'mastery'       // 마스터리 (기술 숙련)
  | 'collection'    // 수집 (곡, 코드, 스케일)
  | 'challenge'     // 도전 (특수 조건)
  | 'hidden'        // 히든 업적

export type AchievementRarity = 'common' | 'rare' | 'epic' | 'legendary'

export interface Achievement {
  id: string
  name: string
  nameJa?: string
  description: string
  icon: string
  category: AchievementCategory
  rarity: AchievementRarity
  xpReward: number
  /** 달성 조건 (코드에서 체크) */
  condition: AchievementCondition
}

export type AchievementCondition =
  | { type: 'xp_total'; amount: number }
  | { type: 'streak_days'; days: number }
  | { type: 'lessons_completed'; count: number }
  | { type: 'drills_completed'; count: number }
  | { type: 'songs_completed'; count: number }
  | { type: 'practice_minutes'; minutes: number }
  | { type: 'level_reached'; level: number }
  | { type: 'drill_accuracy'; drillType: string; accuracy: number }
  | { type: 'specific_drill'; drillId: string }
  | { type: 'specific_lesson'; lessonId: string }
  | { type: 'chord_count'; count: number }  // 유니크 코드 수
  | { type: 'hidden' }

export const ACHIEVEMENTS: Achievement[] = [
  // ═══ Milestone ═══
  { id: 'first-chord',      name: '첫 코드',          nameJa: '初めてのコード',      description: '처음으로 코드를 연주했습니다',          icon: '🎸', category: 'milestone', rarity: 'common',    xpReward: 10,  condition: { type: 'drills_completed', count: 1 } },
  { id: 'first-lesson',     name: '첫 레슨 완료',     nameJa: '初レッスンクリア',     description: '첫 번째 레슨을 완료했습니다',           icon: '📖', category: 'milestone', rarity: 'common',    xpReward: 20,  condition: { type: 'lessons_completed', count: 1 } },
  { id: 'first-song',       name: '첫 곡 완주',       nameJa: '初めての1曲',         description: '처음으로 곡을 끝까지 연주했습니다',     icon: '🎵', category: 'milestone', rarity: 'common',    xpReward: 50,  condition: { type: 'songs_completed', count: 1 } },
  { id: 'barre-breaker',    name: '바레 코드 돌파',    nameJa: 'バレーコード突破',     description: '바레 코드 레슨을 완료했습니다',         icon: '💪', category: 'milestone', rarity: 'rare',      xpReward: 100, condition: { type: 'specific_lesson', lessonId: 'l2-01-barre-chords' } },
  { id: 'jpop-initiate',    name: 'J-Pop 입문 완료',  nameJa: 'J-POP入門クリア',     description: 'J-Pop 레벨을 클리어했습니다',           icon: '🇯🇵', category: 'milestone', rarity: 'rare',      xpReward: 200, condition: { type: 'level_reached', level: 8 } },
  { id: 'royal-road-master', name: '왕도진행 마스터',  nameJa: '王道進行マスター',     description: '왕도진행을 완벽하게 연주했습니다',      icon: '👑', category: 'milestone', rarity: 'epic',      xpReward: 150, condition: { type: 'specific_drill', drillId: 'd3-01-royal-c' } },

  // ═══ Streak ═══
  { id: 'streak-3',         name: '3일 연속',          nameJa: '3日連続',             description: '3일 연속으로 연습했습니다',              icon: '🔥', category: 'streak', rarity: 'common',    xpReward: 15,  condition: { type: 'streak_days', days: 3 } },
  { id: 'streak-7',         name: '일주일 연속',       nameJa: '1週間連続',            description: '7일 연속으로 연습했습니다',              icon: '🔥', category: 'streak', rarity: 'common',    xpReward: 50,  condition: { type: 'streak_days', days: 7 } },
  { id: 'streak-30',        name: '한 달 연속',        nameJa: '1ヶ月連続',            description: '30일 연속으로 연습했습니다',             icon: '🔥', category: 'streak', rarity: 'rare',      xpReward: 200, condition: { type: 'streak_days', days: 30 } },
  { id: 'streak-100',       name: '100일 연속',        nameJa: '100日連続',            description: '100일 연속으로 연습했습니다!',           icon: '🔥', category: 'streak', rarity: 'epic',      xpReward: 500, condition: { type: 'streak_days', days: 100 } },
  { id: 'streak-365',       name: '1년 연속',          nameJa: '1年間連続',            description: '365일 연속 연습! 당신은 진정한 마스터', icon: '🔥', category: 'streak', rarity: 'legendary', xpReward: 2000, condition: { type: 'streak_days', days: 365 } },

  // ═══ Mastery ═══
  { id: 'perfect-drill',    name: '완벽한 드릴',       nameJa: 'パーフェクトドリル',    description: '드릴에서 100% 정확도를 달성했습니다',   icon: '💎', category: 'mastery', rarity: 'rare',      xpReward: 50,  condition: { type: 'drill_accuracy', drillType: 'any', accuracy: 100 } },
  { id: 'speed-demon',      name: '스피드 데몬',       nameJa: 'スピードデーモン',     description: 'BPM 180 이상에서 드릴을 통과했습니다',  icon: '⚡', category: 'mastery', rarity: 'epic',      xpReward: 100, condition: { type: 'drill_accuracy', drillType: 'chord-change', accuracy: 80 } },
  { id: 'ear-master',       name: '절대 음감(?)      ', nameJa: '絶対音感(?)',         description: '청음 훈련에서 90% 이상 정확도',        icon: '👂', category: 'mastery', rarity: 'epic',      xpReward: 150, condition: { type: 'drill_accuracy', drillType: 'ear-training', accuracy: 90 } },

  // ═══ Collection ═══
  { id: 'chord-10',         name: '코드 10개 마스터',   nameJa: '10コードマスター',     description: '10종류의 코드를 배웠습니다',            icon: '📚', category: 'collection', rarity: 'common',  xpReward: 30,  condition: { type: 'chord_count', count: 10 } },
  { id: 'chord-30',         name: '코드 30개 마스터',   nameJa: '30コードマスター',     description: '30종류의 코드를 배웠습니다',            icon: '📚', category: 'collection', rarity: 'rare',    xpReward: 100, condition: { type: 'chord_count', count: 30 } },
  { id: 'song-5',           name: '5곡 완주',          nameJa: '5曲クリア',            description: '5곡을 끝까지 연주했습니다',             icon: '🎶', category: 'collection', rarity: 'common',  xpReward: 50,  condition: { type: 'songs_completed', count: 5 } },
  { id: 'song-20',          name: '20곡 완주',         nameJa: '20曲クリア',           description: '20곡을 끝까지 연주했습니다',            icon: '🎶', category: 'collection', rarity: 'rare',    xpReward: 200, condition: { type: 'songs_completed', count: 20 } },

  // ═══ Practice Time ═══
  { id: 'hour-1',           name: '1시간 연습',        nameJa: '1時間練習',            description: '총 1시간 연습했습니다',                 icon: '⏰', category: 'milestone', rarity: 'common',  xpReward: 20,  condition: { type: 'practice_minutes', minutes: 60 } },
  { id: 'hour-10',          name: '10시간 연습',       nameJa: '10時間練習',           description: '총 10시간 연습했습니다',                icon: '⏰', category: 'milestone', rarity: 'common',  xpReward: 100, condition: { type: 'practice_minutes', minutes: 600 } },
  { id: 'hour-100',         name: '100시간 연습',      nameJa: '100時間練習',          description: '총 100시간! 진정한 연습벌레',           icon: '⏰', category: 'milestone', rarity: 'epic',    xpReward: 500, condition: { type: 'practice_minutes', minutes: 6000 } },

  // ═══ Hidden ═══
  { id: 'night-owl',        name: '올빼미 연습가',     nameJa: '夜更かし練習家',        description: '새벽 3시에 연습한 당신…',               icon: '🦉', category: 'hidden', rarity: 'rare',      xpReward: 30,  condition: { type: 'hidden' } },
  { id: 'bocchi-reference', name: '봇치의 벽장',       nameJa: 'ぼっちの押し入れ',      description: '봇치처럼 혼자서 묵묵히 연습 중…',      icon: '🏠', category: 'hidden', rarity: 'rare',      xpReward: 50,  condition: { type: 'hidden' } },
]

// ─── Daily Mission System ───────────────────────────

export type MissionType =
  | 'practice-time'     // N분 연습
  | 'drill-complete'    // 특정 타입 드릴 완료
  | 'chord-practice'    // 특정 코드 연습
  | 'song-section'      // 곡 섹션 연습
  | 'streak-maintain'   // 스트릭 유지

export interface DailyMission {
  id: string
  type: MissionType
  title: string
  description: string
  xpReward: number
  config: Record<string, unknown>
}

export const DAILY_MISSION_TEMPLATES: Omit<DailyMission, 'id'>[] = [
  { type: 'practice-time',  title: '오늘의 워밍업',       description: '10분 이상 연습하기',           xpReward: 15, config: { minutes: 10 } },
  { type: 'practice-time',  title: '집중 연습',           description: '30분 이상 연습하기',           xpReward: 40, config: { minutes: 30 } },
  { type: 'drill-complete', title: '코드 체인지 도전',    description: '코드 체인지 드릴 1회 완료',    xpReward: 20, config: { drillType: 'chord-change' } },
  { type: 'drill-complete', title: '지판 퀴즈 도전',      description: '지판 퀴즈 1회 완료',          xpReward: 20, config: { drillType: 'fretboard-quiz' } },
  { type: 'drill-complete', title: '귀 훈련',             description: '청음 훈련 1회 완료',          xpReward: 25, config: { drillType: 'ear-training' } },
  { type: 'drill-complete', title: '스트럼 연습',         description: '스트럼 패턴 드릴 1회 완료',   xpReward: 20, config: { drillType: 'strum-pattern' } },
  { type: 'chord-practice', title: '오늘의 코드',         description: '지정된 코드 5회 이상 연습',   xpReward: 15, config: { count: 5 } },
  { type: 'song-section',   title: '곡 한 구간 연습',     description: '아무 곡의 한 섹션 연습',      xpReward: 30, config: { sections: 1 } },
  { type: 'streak-maintain', title: '연습 스트릭 유지',    description: '오늘도 연습을 기록하세요!',   xpReward: 10, config: {} },
]

// ─── Helper Functions ───────────────────────────────

const PROFILE_STORAGE_KEY = 'bocchi-player-profile'

/** 기본 프로필 생성 */
export function createDefaultProfile(instrument: 'guitar' | 'bass' = 'guitar'): PlayerProfile {
  return {
    xp: 0,
    level: 0,
    achievements: [],
    streakDays: 0,
    bestStreakDays: 0,
    totalPracticeMinutes: 0,
    completedLessons: [],
    completedDrills: [],
    completedSongs: [],
    drillScores: {},
    lastPracticeDate: '',
    dailyPracticeLog: {},
    instrument,
    curriculumId: instrument === 'guitar' ? 'jpop-guitar' : 'jpop-bass',
    createdAt: new Date().toISOString(),
  }
}

/** localStorage에서 프로필 로드 */
export function loadPlayerProfile(): PlayerProfile | null {
  try {
    const raw = localStorage.getItem(PROFILE_STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/** localStorage에 프로필 저장 */
export function savePlayerProfile(profile: PlayerProfile): void {
  localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile))
}

/** XP에 해당하는 레벨 계산 */
export function getPlayerLevel(xp: number): PlayerLevel {
  let result = PLAYER_LEVELS[0]
  for (const level of PLAYER_LEVELS) {
    if (xp >= level.requiredXP) {
      result = level
    } else {
      break
    }
  }
  return result
}

/** 다음 레벨까지 남은 XP */
export function getXPToNextLevel(xp: number): { current: number; required: number; progress: number } {
  const currentLevel = getPlayerLevel(xp)
  const nextLevelIdx = currentLevel.level + 1
  if (nextLevelIdx >= PLAYER_LEVELS.length) {
    return { current: xp, required: xp, progress: 100 }
  }
  const nextLevel = PLAYER_LEVELS[nextLevelIdx]
  const currentBase = currentLevel.requiredXP
  const needed = nextLevel.requiredXP - currentBase
  const earned = xp - currentBase
  return {
    current: earned,
    required: needed,
    progress: Math.min(100, Math.round((earned / needed) * 100)),
  }
}

/** XP 추가 + 레벨업 체크 */
export function addXP(profile: PlayerProfile, amount: number): { profile: PlayerProfile; leveledUp: boolean; newLevel?: PlayerLevel } {
  const oldLevel = getPlayerLevel(profile.xp)
  const newXP = profile.xp + amount
  const newLevel = getPlayerLevel(newXP)
  const leveledUp = newLevel.level > oldLevel.level

  return {
    profile: {
      ...profile,
      xp: newXP,
      level: newLevel.level,
    },
    leveledUp,
    newLevel: leveledUp ? newLevel : undefined,
  }
}

/** 스트릭 업데이트 */
export function updateStreak(profile: PlayerProfile): PlayerProfile {
  const today = new Date().toISOString().split('T')[0]
  if (profile.lastPracticeDate === today) return profile

  const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0]
  const isConsecutive = profile.lastPracticeDate === yesterday

  const newStreak = isConsecutive ? profile.streakDays + 1 : 1
  return {
    ...profile,
    streakDays: newStreak,
    bestStreakDays: Math.max(profile.bestStreakDays, newStreak),
    lastPracticeDate: today,
  }
}

/** 업적 달성 체크 */
export function checkAchievements(profile: PlayerProfile): Achievement[] {
  const newAchievements: Achievement[] = []

  for (const ach of ACHIEVEMENTS) {
    if (profile.achievements.includes(ach.id)) continue

    const { condition } = ach
    let earned = false

    switch (condition.type) {
      case 'xp_total':
        earned = profile.xp >= condition.amount
        break
      case 'streak_days':
        earned = profile.streakDays >= condition.days
        break
      case 'lessons_completed':
        earned = profile.completedLessons.length >= condition.count
        break
      case 'drills_completed':
        earned = profile.completedDrills.length >= condition.count
        break
      case 'songs_completed':
        earned = profile.completedSongs.length >= condition.count
        break
      case 'practice_minutes':
        earned = profile.totalPracticeMinutes >= condition.minutes
        break
      case 'level_reached':
        earned = profile.level >= condition.level
        break
      case 'specific_drill':
        earned = profile.completedDrills.includes(condition.drillId)
        break
      case 'specific_lesson':
        earned = profile.completedLessons.includes(condition.lessonId)
        break
      case 'drill_accuracy': {
        // drillType이 'any'면 전체 드릴 중 하나라도 조건 충족
        const scores = Object.entries(profile.drillScores)
        if (condition.drillType === 'any') {
          earned = scores.some(([, s]) => s.accuracy >= condition.accuracy)
        } else {
          earned = scores.some(([id, s]) =>
            id.includes(condition.drillType) && s.accuracy >= condition.accuracy
          )
        }
        break
      }
      case 'chord_count': {
        // TODO: 실제 유니크 코드 수를 프로필에 별도 추적 필요.
        // 현재는 드릴 ID 기반 추정치 — 정확도 낮음 (드릴당 ~3코드 가정).
        const chordDrills = profile.completedDrills.filter(
          id => id.includes('chord') || id.includes('voicing')
        )
        const estimatedChords = new Set(chordDrills.flatMap(id => {
          const score = profile.drillScores[id]
          return score ? [id] : []
        }))
        earned = estimatedChords.size * 3 >= condition.count
        break
      }
      case 'hidden':
        // hidden 업적은 외부에서 직접 부여 (triggerHiddenAchievement 사용)
        break
      default:
        break
    }

    if (earned) {
      newAchievements.push(ach)
    }
  }

  return newAchievements
}

/** 히든 업적 트리거 (조건을 외부에서 직접 판단하여 부여) */
export function triggerHiddenAchievement(profile: PlayerProfile, achievementId: string): Achievement | null {
  if (profile.achievements.includes(achievementId)) return null
  const ach = ACHIEVEMENTS.find(a => a.id === achievementId && a.condition.type === 'hidden')
  return ach ?? null
}

/** 오늘의 일일 미션 생성 (3개, 시드 기반 결정적) */
export function generateDailyMissions(dateStr?: string): DailyMission[] {
  const date = dateStr ?? new Date().toISOString().split('T')[0]
  // 날짜 기반 시드로 동일 날짜엔 동일 미션
  const seed = hashString(date)
  const shuffled = [...DAILY_MISSION_TEMPLATES].sort((a, b) => {
    const ha = hashString(a.title + date)
    const hb = hashString(b.title + date)
    return ha - hb
  })

  return shuffled.slice(0, 3).map((template, i) => ({
    ...template,
    id: `daily-${date}-${i}-${seed % 1000}`,
  }))
}

function hashString(str: string): number {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash |= 0
  }
  return Math.abs(hash)
}
