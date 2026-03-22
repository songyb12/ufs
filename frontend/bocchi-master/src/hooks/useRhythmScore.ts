import { useState, useCallback, useRef } from 'react'

// ── Rating thresholds (ms from beat center) ──
const PERFECT_MS = 30
const GOOD_MS = 60
const OK_MS = 120

export type RhythmRating = 'perfect' | 'good' | 'ok' | 'miss'

export interface RhythmHit {
  offsetMs: number  // negative = early, positive = late
  rating: RhythmRating
}

export interface RhythmStats {
  total: number
  perfect: number
  good: number
  ok: number
  miss: number
  avgOffsetMs: number
  accuracy: number  // 0-100 weighted score
  recentHits: RhythmHit[]  // last 16
}

const EMPTY_STATS: RhythmStats = {
  total: 0, perfect: 0, good: 0, ok: 0, miss: 0,
  avgOffsetMs: 0, accuracy: 0, recentHits: [],
}

function rateOffset(absMs: number): RhythmRating {
  if (absMs <= PERFECT_MS) return 'perfect'
  if (absMs <= GOOD_MS) return 'good'
  if (absMs <= OK_MS) return 'ok'
  return 'miss'
}

function weightForRating(r: RhythmRating): number {
  switch (r) {
    case 'perfect': return 100
    case 'good': return 75
    case 'ok': return 40
    case 'miss': return 0
  }
}

/**
 * Rhythm accuracy scoring hook.
 *
 * Call `recordBeat()` from the metronome's onBeatSchedule callback
 * to capture beat timestamps. Call `evaluate()` when a MIDI note
 * arrives to score its timing against the nearest beat.
 */
export function useRhythmScore() {
  const [active, setActive] = useState(false)
  const [stats, setStats] = useState<RhythmStats>(EMPTY_STATS)
  const [lastHit, setLastHit] = useState<RhythmHit | null>(null)

  // Ring buffer of recent beat timestamps (performance.now())
  const beatTimesRef = useRef<number[]>([])
  const activeRef = useRef(false)
  activeRef.current = active

  // Seconds per beat (for "window" calculation — don't score if too far from any beat)
  const beatIntervalMsRef = useRef(500) // default 120 BPM

  const recordBeat = useCallback((beat: number, bpm: number) => {
    if (!activeRef.current) return
    void beat // beat number not needed for timing, just timestamp
    beatIntervalMsRef.current = (60 / bpm) * 1000
    const now = performance.now()
    const buf = beatTimesRef.current
    buf.push(now)
    // Keep last 8 beats (enough for lookback)
    if (buf.length > 8) buf.shift()
  }, [])

  const evaluate = useCallback((): RhythmHit | null => {
    if (!activeRef.current) return null
    const buf = beatTimesRef.current
    if (buf.length === 0) return null

    const now = performance.now()
    const halfBeat = beatIntervalMsRef.current / 2

    // Find nearest beat
    let minDelta = Infinity
    for (const bt of buf) {
      const d = now - bt
      if (Math.abs(d) < Math.abs(minDelta)) minDelta = d
    }

    // Also consider next expected beat (extrapolate)
    const lastBeat = buf[buf.length - 1]
    const nextExpected = lastBeat + beatIntervalMsRef.current
    const deltaToNext = now - nextExpected
    if (Math.abs(deltaToNext) < Math.abs(minDelta)) minDelta = deltaToNext

    // If more than half a beat away from any beat, it's a miss
    if (Math.abs(minDelta) > halfBeat) {
      minDelta = Math.abs(minDelta) > halfBeat ? (minDelta > 0 ? halfBeat : -halfBeat) : minDelta
    }

    const offsetMs = Math.round(minDelta)
    const rating = rateOffset(Math.abs(offsetMs))
    const hit: RhythmHit = { offsetMs, rating }

    setLastHit(hit)
    setStats(prev => {
      const total = prev.total + 1
      const perfect = prev.perfect + (rating === 'perfect' ? 1 : 0)
      const good = prev.good + (rating === 'good' ? 1 : 0)
      const ok = prev.ok + (rating === 'ok' ? 1 : 0)
      const miss = prev.miss + (rating === 'miss' ? 1 : 0)
      const sumOffset = prev.avgOffsetMs * prev.total + offsetMs
      const avgOffsetMs = Math.round(sumOffset / total)
      const sumWeight = prev.accuracy * prev.total + weightForRating(rating)
      const accuracy = Math.round(sumWeight / total)
      const recentHits = [hit, ...prev.recentHits].slice(0, 16)
      return { total, perfect, good, ok, miss, avgOffsetMs, accuracy, recentHits }
    })

    return hit
  }, [])

  const start = useCallback(() => {
    beatTimesRef.current = []
    setStats(EMPTY_STATS)
    setLastHit(null)
    setActive(true)
  }, [])

  const stop = useCallback(() => {
    setActive(false)
    beatTimesRef.current = []
  }, [])

  const reset = useCallback(() => {
    beatTimesRef.current = []
    setStats(EMPTY_STATS)
    setLastHit(null)
  }, [])

  return {
    active,
    stats,
    lastHit,
    start,
    stop,
    reset,
    recordBeat,
    evaluate,
  }
}
