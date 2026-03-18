/**
 * Curriculum state management hook.
 * Manages lesson/drill progress, XP tracking, and curriculum navigation.
 */

import { useState, useCallback, useEffect, useMemo } from 'react'
import {
  GUITAR_CURRICULUM,
  BASS_CURRICULUM,
  type Curriculum,
  type Level,
  type Lesson,
  type Drill,
  type CurriculumProgress,
  type DrillScore,
  findLevel,
  findLesson,
  findDrill,
  isLevelUnlocked,
  getLessonProgress,
  getLevelProgress,
} from '../data/curriculum'
import {
  type PlayerProfile,
  loadPlayerProfile,
  savePlayerProfile,
  createDefaultProfile,
  addXP,
  updateStreak,
  checkAchievements,
  getPlayerLevel,
  getXPToNextLevel,
  type Achievement,
} from '../data/gamification'

// ─── Types ──────────────────────────────────────────

export type CurriculumView = 'map' | 'lesson' | 'drill'

export interface CurriculumState {
  /** Current curriculum */
  curriculum: Curriculum
  /** Player profile */
  profile: PlayerProfile
  /** Current view */
  view: CurriculumView
  /** Currently selected level */
  selectedLevel: Level | null
  /** Currently selected lesson */
  selectedLesson: Lesson | null
  /** Currently running drill */
  activeDrill: Drill | null
  /** Recently earned achievements (for popup) */
  pendingAchievements: Achievement[]
}

export interface CurriculumActions {
  /** Select a level to view its lessons */
  selectLevel: (levelId: string) => void
  /** Select a lesson to view its details */
  selectLesson: (lessonId: string) => void
  /** Start a drill */
  startDrill: (drillId: string) => void
  /** Complete a drill with score */
  completeDrill: (drillId: string, score: DrillScore) => void
  /** Complete a lesson */
  completeLesson: (lessonId: string) => void
  /** Go back to previous view */
  goBack: () => void
  /** Go to curriculum map */
  goToMap: () => void
  /** Dismiss achievement popup */
  dismissAchievement: () => void
  /** Switch instrument/curriculum */
  switchCurriculum: (instrument: 'guitar' | 'bass') => void
  /** Get level progress */
  getLevelProgressPercent: (level: Level) => number
  /** Get lesson progress */
  getLessonProgressPercent: (lesson: Lesson) => number
  /** Check if level is unlocked */
  isUnlocked: (level: Level) => boolean
  /** Get XP info */
  xpInfo: { current: number; required: number; progress: number }
  /** Get player level info */
  levelInfo: { level: number; title: string; icon: string }
}

// ─── Storage ────────────────────────────────────────

const PROGRESS_KEY = 'bocchi-curriculum-progress'

function loadProgress(): CurriculumProgress {
  try {
    const raw = localStorage.getItem(PROGRESS_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return {
    currentLevelIndex: 0,
    completedLessons: [],
    completedDrills: [],
    drillBestScores: {},
    unlockedLevels: [0],
  }
}

function saveProgress(progress: CurriculumProgress): void {
  localStorage.setItem(PROGRESS_KEY, JSON.stringify(progress))
}

// ─── Hook ───────────────────────────────────────────

export function useCurriculum(): [CurriculumState, CurriculumActions] {
  // Load or create player profile
  const [profile, setProfile] = useState<PlayerProfile>(() => {
    return loadPlayerProfile() ?? createDefaultProfile()
  })

  // Load curriculum progress
  const [progress, setProgress] = useState<CurriculumProgress>(loadProgress)

  // Navigation state
  const [view, setView] = useState<CurriculumView>('map')
  const [selectedLevelId, setSelectedLevelId] = useState<string | null>(null)
  const [selectedLessonId, setSelectedLessonId] = useState<string | null>(null)
  const [activeDrillId, setActiveDrillId] = useState<string | null>(null)
  const [pendingAchievements, setPendingAchievements] = useState<Achievement[]>([])

  // Current curriculum based on instrument
  const curriculum = useMemo(() => {
    return profile.instrument === 'bass' ? BASS_CURRICULUM : GUITAR_CURRICULUM
  }, [profile.instrument])

  // Resolve selected entities
  const selectedLevel = useMemo(() => {
    return selectedLevelId ? findLevel(curriculum, selectedLevelId) ?? null : null
  }, [curriculum, selectedLevelId])

  const selectedLesson = useMemo(() => {
    return selectedLessonId ? findLesson(curriculum, selectedLessonId) ?? null : null
  }, [curriculum, selectedLessonId])

  const activeDrill = useMemo(() => {
    return activeDrillId ? findDrill(curriculum, activeDrillId) ?? null : null
  }, [curriculum, activeDrillId])

  // Persist profile changes
  useEffect(() => {
    savePlayerProfile(profile)
  }, [profile])

  // Persist progress changes
  useEffect(() => {
    saveProgress(progress)
  }, [progress])

  // ─── Actions ────────────────────────────────────

  const selectLevel = useCallback((levelId: string) => {
    setSelectedLevelId(levelId)
    setSelectedLessonId(null)
    setActiveDrillId(null)
    setView('map')
  }, [])

  const selectLesson = useCallback((lessonId: string) => {
    setSelectedLessonId(lessonId)
    setActiveDrillId(null)
    setView('lesson')
  }, [])

  const startDrill = useCallback((drillId: string) => {
    setActiveDrillId(drillId)
    setView('drill')
  }, [])

  const completeDrill = useCallback((drillId: string, score: DrillScore) => {
    // Update progress
    setProgress(prev => {
      const newDrills = prev.completedDrills.includes(drillId)
        ? prev.completedDrills
        : [...prev.completedDrills, drillId]

      const newScores = { ...prev.drillBestScores }
      const existing = newScores[drillId]
      if (!existing || score.accuracy > existing.accuracy) {
        newScores[drillId] = score
      }

      return {
        ...prev,
        completedDrills: newDrills,
        drillBestScores: newScores,
      }
    })

    // Add XP
    const drill = findDrill(curriculum, drillId)
    if (drill) {
      setProfile(prev => {
        const { profile: updated } = addXP(prev, drill.xpReward)
        const withStreak = updateStreak(updated)

        // Update completed drills
        const withDrills = {
          ...withStreak,
          completedDrills: withStreak.completedDrills.includes(drillId)
            ? withStreak.completedDrills
            : [...withStreak.completedDrills, drillId],
          drillScores: {
            ...withStreak.drillScores,
            [drillId]: score,
          },
        }

        // Check achievements
        const earned = checkAchievements(withDrills)
        if (earned.length > 0) {
          const totalBonusXP = earned.reduce((sum, a) => sum + a.xpReward, 0)
          setPendingAchievements(earned)
          return {
            ...withDrills,
            xp: withDrills.xp + totalBonusXP,
            achievements: [...withDrills.achievements, ...earned.map(a => a.id)],
          }
        }

        return withDrills
      })
    }

    // Go back to lesson view
    setActiveDrillId(null)
    setView('lesson')
  }, [curriculum])

  const completeLesson = useCallback((lessonId: string) => {
    setProgress(prev => ({
      ...prev,
      completedLessons: prev.completedLessons.includes(lessonId)
        ? prev.completedLessons
        : [...prev.completedLessons, lessonId],
    }))

    const lesson = findLesson(curriculum, lessonId)
    if (lesson) {
      setProfile(prev => {
        const { profile: updated } = addXP(prev, lesson.xpReward)
        return {
          ...updated,
          completedLessons: updated.completedLessons.includes(lessonId)
            ? updated.completedLessons
            : [...updated.completedLessons, lessonId],
        }
      })
    }
  }, [curriculum])

  const goBack = useCallback(() => {
    if (view === 'drill') {
      setActiveDrillId(null)
      setView('lesson')
    } else if (view === 'lesson') {
      setSelectedLessonId(null)
      setView('map')
    }
  }, [view])

  const goToMap = useCallback(() => {
    setView('map')
    setSelectedLessonId(null)
    setActiveDrillId(null)
  }, [])

  const dismissAchievement = useCallback(() => {
    setPendingAchievements(prev => prev.slice(1))
  }, [])

  const switchCurriculum = useCallback((instrument: 'guitar' | 'bass') => {
    setProfile(prev => ({
      ...prev,
      instrument,
      curriculumId: instrument === 'guitar' ? 'jpop-guitar' : 'jpop-bass',
    }))
    setView('map')
    setSelectedLevelId(null)
    setSelectedLessonId(null)
    setActiveDrillId(null)
  }, [])

  const getLevelProgressPercent = useCallback((level: Level) => {
    return getLevelProgress(level, progress.completedLessons)
  }, [progress.completedLessons])

  const getLessonProgressPercent = useCallback((lesson: Lesson) => {
    return getLessonProgress(lesson, progress.completedDrills)
  }, [progress.completedDrills])

  const isUnlocked = useCallback((level: Level) => {
    return isLevelUnlocked(level, profile.xp)
  }, [profile.xp])

  const playerLevel = getPlayerLevel(profile.xp)
  const xpInfo = getXPToNextLevel(profile.xp)

  // ─── Return ────────────────────────────────────

  const state: CurriculumState = {
    curriculum,
    profile,
    view,
    selectedLevel,
    selectedLesson,
    activeDrill,
    pendingAchievements,
  }

  const actions: CurriculumActions = {
    selectLevel,
    selectLesson,
    startDrill,
    completeDrill,
    completeLesson,
    goBack,
    goToMap,
    dismissAchievement,
    switchCurriculum,
    getLevelProgressPercent,
    getLessonProgressPercent,
    isUnlocked,
    xpInfo,
    levelInfo: {
      level: playerLevel.level,
      title: playerLevel.title,
      icon: playerLevel.icon,
    },
  }

  return [state, actions]
}
