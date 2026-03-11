/**
 * Interval Trainer — Ear training engine for musicians.
 *
 * Generates random interval pairs, plays them via Web Audio,
 * and tracks accuracy statistics.
 */

import type { NoteName } from '../types/music'
import { CHROMATIC_SCALE } from '../constants/notes'

// ── Interval Names ──

export const INTERVAL_NAMES: Record<number, string> = {
  0: 'Unison (P1)',
  1: 'Minor 2nd (m2)',
  2: 'Major 2nd (M2)',
  3: 'Minor 3rd (m3)',
  4: 'Major 3rd (M3)',
  5: 'Perfect 4th (P4)',
  6: 'Tritone (TT)',
  7: 'Perfect 5th (P5)',
  8: 'Minor 6th (m6)',
  9: 'Major 6th (M6)',
  10: 'Minor 7th (m7)',
  11: 'Major 7th (M7)',
  12: 'Octave (P8)',
}

export const INTERVAL_SHORT: Record<number, string> = {
  0: 'P1',
  1: 'm2',
  2: 'M2',
  3: 'm3',
  4: 'M3',
  5: 'P4',
  6: 'TT',
  7: 'P5',
  8: 'm6',
  9: 'M6',
  10: 'm7',
  11: 'M7',
  12: 'P8',
}

// ── Difficulty Presets ──

export interface IntervalSet {
  name: string
  intervals: number[]  // semitone values to include
}

export const INTERVAL_SETS: IntervalSet[] = [
  {
    name: 'Easy (P4, P5, Oct)',
    intervals: [5, 7, 12],
  },
  {
    name: 'Thirds & Fifths',
    intervals: [3, 4, 7],
  },
  {
    name: 'All Basic',
    intervals: [1, 2, 3, 4, 5, 7],
  },
  {
    name: 'All Intervals',
    intervals: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
  },
  {
    name: 'Tricky (m2/M2, m3/M3)',
    intervals: [1, 2, 3, 4],
  },
  {
    name: 'Jazz (m7/M7, TT)',
    intervals: [6, 10, 11],
  },
]

// ── Types ──

export type IntervalDirection = 'ascending' | 'descending' | 'random'

export interface IntervalQuestion {
  rootMidi: number
  rootNote: NoteName
  targetMidi: number
  targetNote: NoteName
  semitones: number
  direction: 'ascending' | 'descending'
}

export interface IntervalStats {
  total: number
  correct: number
  accuracy: number
  /** Per-interval accuracy tracking */
  perInterval: Record<number, { total: number; correct: number }>
}

// ── Question Generator ──

export function generateQuestion(
  availableIntervals: number[],
  direction: IntervalDirection = 'ascending',
): IntervalQuestion {
  if (availableIntervals.length === 0) {
    availableIntervals = [7]  // fallback: P5
  }

  // Pick random interval
  const semitones = availableIntervals[
    Math.floor(Math.random() * availableIntervals.length)
  ]

  // Pick random root note in a comfortable range (MIDI 48-72 = C3-C5)
  const rootMidi = 48 + Math.floor(Math.random() * 24)
  const rootNote = CHROMATIC_SCALE[rootMidi % 12]

  // Determine direction
  let actualDirection: 'ascending' | 'descending'
  if (direction === 'random') {
    actualDirection = Math.random() > 0.5 ? 'ascending' : 'descending'
  } else {
    actualDirection = direction
  }

  const targetMidi = actualDirection === 'ascending'
    ? rootMidi + semitones
    : rootMidi - semitones
  const targetNote = CHROMATIC_SCALE[((targetMidi % 12) + 12) % 12]

  return {
    rootMidi,
    rootNote,
    targetMidi,
    targetNote,
    semitones,
    direction: actualDirection,
  }
}

// ── Audio Playback ──

export function playInterval(
  ctx: AudioContext,
  question: IntervalQuestion,
  delay = 0.6,
): void {
  playTone(ctx, question.rootMidi, ctx.currentTime + 0.05, 0.5)
  playTone(ctx, question.targetMidi, ctx.currentTime + 0.05 + delay, 0.5)
}

export function playTone(
  ctx: AudioContext,
  midiNote: number,
  time: number,
  duration: number,
  volume = 0.3,
): void {
  const freq = 440 * Math.pow(2, (midiNote - 69) / 12)

  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = 'sine'
  osc.frequency.value = freq
  osc.connect(gain)
  gain.connect(ctx.destination)

  gain.gain.setValueAtTime(0, time)
  gain.gain.linearRampToValueAtTime(volume, time + 0.02)
  gain.gain.setValueAtTime(volume, time + duration - 0.05)
  gain.gain.linearRampToValueAtTime(0, time + duration)

  osc.start(time)
  osc.stop(time + duration)
}

// ── Stats Helper ──

export function createEmptyStats(): IntervalStats {
  return {
    total: 0,
    correct: 0,
    accuracy: 0,
    perInterval: {},
  }
}

export function recordAnswer(
  stats: IntervalStats,
  semitones: number,
  isCorrect: boolean,
): IntervalStats {
  const newStats = { ...stats }
  newStats.total += 1
  if (isCorrect) newStats.correct += 1
  newStats.accuracy = newStats.total > 0 ? newStats.correct / newStats.total : 0

  // Per-interval tracking
  const prev = newStats.perInterval[semitones] ?? { total: 0, correct: 0 }
  newStats.perInterval = {
    ...newStats.perInterval,
    [semitones]: {
      total: prev.total + 1,
      correct: prev.correct + (isCorrect ? 1 : 0),
    },
  }

  return newStats
}
