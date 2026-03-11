import { useState, useCallback, useRef } from 'react'
import type { NoteName } from '../types/music'
import { CHROMATIC_SCALE } from '../constants/notes'
import { addPracticeSession } from '../utils/storage'

export interface PracticeResult {
  noteName: NoteName
  correct: boolean
  timestamp: number
}

export interface PracticeStats {
  totalAttempts: number
  correctAttempts: number
  accuracy: number // 0-100
  recentResults: PracticeResult[] // most recent first, max 10
}

export function usePracticeMode() {
  const [active, setActive] = useState(false)
  const [stats, setStats] = useState<PracticeStats>({
    totalAttempts: 0,
    correctAttempts: 0,
    accuracy: 0,
    recentResults: [],
  })
  const [lastResult, setLastResult] = useState<'correct' | 'incorrect' | null>(null)

  // Target note names (the set of acceptable notes)
  const targetRef = useRef<Set<NoteName>>(new Set())
  const startTimeRef = useRef<number>(0)
  const targetDescRef = useRef<string>('')

  const activate = useCallback((targetNotes: NoteName[], description?: string) => {
    targetRef.current = new Set(targetNotes)
    startTimeRef.current = Date.now()
    targetDescRef.current = description ?? `${targetNotes.slice(0, 3).join('-')}... (${targetNotes.length} notes)`
    setActive(true)
    setStats({
      totalAttempts: 0,
      correctAttempts: 0,
      accuracy: 0,
      recentResults: [],
    })
    setLastResult(null)
  }, [])

  const deactivate = useCallback(() => {
    // Save session to practice history (if at least 3 attempts)
    setStats((currentStats) => {
      if (currentStats.totalAttempts >= 3) {
        const durationSeconds = Math.round((Date.now() - startTimeRef.current) / 1000)
        addPracticeSession({
          date: new Date().toISOString(),
          accuracy: currentStats.accuracy,
          totalAttempts: currentStats.totalAttempts,
          correctAttempts: currentStats.correctAttempts,
          targetDescription: targetDescRef.current,
          durationSeconds,
        })
      }
      return currentStats
    })
    setActive(false)
    setLastResult(null)
  }, [])

  const updateTarget = useCallback((targetNotes: NoteName[]) => {
    targetRef.current = new Set(targetNotes)
  }, [])

  const evaluateNote = useCallback((midiNote: number) => {
    if (!active) return
    const noteName = CHROMATIC_SCALE[midiNote % 12]
    const correct = targetRef.current.has(noteName)
    const result: PracticeResult = {
      noteName,
      correct,
      timestamp: Date.now(),
    }

    setLastResult(correct ? 'correct' : 'incorrect')
    setStats((prev) => {
      const total = prev.totalAttempts + 1
      const correctCount = prev.correctAttempts + (correct ? 1 : 0)
      return {
        totalAttempts: total,
        correctAttempts: correctCount,
        accuracy: Math.round((correctCount / total) * 100),
        recentResults: [result, ...prev.recentResults].slice(0, 10),
      }
    })
  }, [active])

  const reset = useCallback(() => {
    setStats({
      totalAttempts: 0,
      correctAttempts: 0,
      accuracy: 0,
      recentResults: [],
    })
    setLastResult(null)
  }, [])

  return {
    active,
    stats,
    lastResult,
    activate,
    deactivate,
    updateTarget,
    evaluateNote,
    reset,
  }
}
