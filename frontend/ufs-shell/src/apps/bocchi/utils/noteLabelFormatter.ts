/**
 * Note Label Formatting
 *
 * Generates different label texts for notes on the fretboard:
 * - 'name': Note name (C, D, E, F#, ...)
 * - 'interval': Interval from root (P1, m2, M3, P5, ...)
 * - 'degree': Scale degree number (1, ♭2, 2, ♭3, 3, ...)
 */

import type { NoteName } from '../types/music'
import { CHROMATIC_SCALE } from '../constants/notes'

export type NoteLabelMode = 'name' | 'interval' | 'degree'

const INTERVAL_LABELS: string[] = [
  'P1', 'm2', 'M2', 'm3', 'M3', 'P4',
  'TT', 'P5', 'm6', 'M6', 'm7', 'M7',
]

const DEGREE_LABELS: string[] = [
  '1', '♭2', '2', '♭3', '3', '4',
  '♭5', '5', '♭6', '6', '♭7', '7',
]

/**
 * Get the display label for a note based on the current label mode.
 *
 * @param noteName - The note to label
 * @param rootNote - The current root note (for interval/degree calculation)
 * @param mode - Label mode
 * @returns Display string for the fretboard
 */
export function getNoteLabel(
  noteName: NoteName,
  rootNote: NoteName | undefined,
  mode: NoteLabelMode,
): string {
  if (mode === 'name' || !rootNote) {
    return noteName
  }

  const rootIdx = CHROMATIC_SCALE.indexOf(rootNote)
  const noteIdx = CHROMATIC_SCALE.indexOf(noteName)
  const semitones = ((noteIdx - rootIdx) % 12 + 12) % 12

  if (mode === 'interval') {
    return INTERVAL_LABELS[semitones] ?? noteName
  }

  if (mode === 'degree') {
    return DEGREE_LABELS[semitones] ?? noteName
  }

  return noteName
}
