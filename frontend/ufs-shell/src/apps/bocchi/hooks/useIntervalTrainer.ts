import { useState, useCallback, useRef } from 'react'
import { getSharedAudioContext } from '../utils/audioContextSingleton'
import {
  generateQuestion,
  playInterval,
  createEmptyStats,
  recordAnswer,
  INTERVAL_SETS,
  type IntervalQuestion,
  type IntervalStats,
  type IntervalDirection,
} from '../utils/intervalTrainer'

export interface IntervalTrainerState {
  active: boolean
  question: IntervalQuestion | null
  stats: IntervalStats
  setIndex: number
  direction: IntervalDirection
  lastAnswer: { semitones: number; correct: boolean } | null
  revealed: boolean

  start: () => void
  stop: () => void
  setSetIndex: (idx: number) => void
  setDirection: (d: IntervalDirection) => void
  answer: (semitones: number) => void
  replay: () => void
  next: () => void
  reset: () => void
}

export function useIntervalTrainer(): IntervalTrainerState {
  const [active, setActive] = useState(false)
  const [question, setQuestion] = useState<IntervalQuestion | null>(null)
  const [stats, setStats] = useState<IntervalStats>(createEmptyStats())
  const [setIndex, setSetIndex] = useState(0)
  const [direction, setDirection] = useState<IntervalDirection>('ascending')
  const [lastAnswer, setLastAnswer] = useState<{ semitones: number; correct: boolean } | null>(null)
  const [revealed, setRevealed] = useState(false)

  const ctxRef = useRef<AudioContext | null>(null)

  const getCtx = useCallback(async () => {
    if (!ctxRef.current) {
      ctxRef.current = await getSharedAudioContext()
    }
    return ctxRef.current
  }, [])

  const playCurrentQuestion = useCallback(
    async (q: IntervalQuestion) => {
      const ctx = await getCtx()
      playInterval(ctx, q)
    },
    [getCtx],
  )

  const generateAndPlay = useCallback(
    async () => {
      const intervals = INTERVAL_SETS[setIndex]?.intervals ?? [7]
      const q = generateQuestion(intervals, direction)
      setQuestion(q)
      setLastAnswer(null)
      setRevealed(false)
      await playCurrentQuestion(q)
    },
    [setIndex, direction, playCurrentQuestion],
  )

  const start = useCallback(async () => {
    setActive(true)
    setStats(createEmptyStats())
    setLastAnswer(null)
    setRevealed(false)
    // Generate first question after activating
    const intervals = INTERVAL_SETS[setIndex]?.intervals ?? [7]
    const q = generateQuestion(intervals, direction)
    setQuestion(q)
    const ctx = await getCtx()
    playInterval(ctx, q)
  }, [setIndex, direction, getCtx])

  const stop = useCallback(() => {
    setActive(false)
    setQuestion(null)
    setLastAnswer(null)
    setRevealed(false)
  }, [])

  const answer = useCallback(
    (semitones: number) => {
      if (!question || revealed) return
      const correct = semitones === question.semitones
      setLastAnswer({ semitones, correct })
      setRevealed(true)
      setStats((prev) => recordAnswer(prev, question.semitones, correct))
    },
    [question, revealed],
  )

  const replay = useCallback(async () => {
    if (!question) return
    await playCurrentQuestion(question)
  }, [question, playCurrentQuestion])

  const next = useCallback(() => {
    generateAndPlay()
  }, [generateAndPlay])

  const reset = useCallback(() => {
    setStats(createEmptyStats())
    setLastAnswer(null)
    setRevealed(false)
  }, [])

  return {
    active,
    question,
    stats,
    setIndex,
    direction,
    lastAnswer,
    revealed,
    start,
    stop,
    setSetIndex,
    setDirection,
    answer,
    replay,
    next,
    reset,
  }
}
