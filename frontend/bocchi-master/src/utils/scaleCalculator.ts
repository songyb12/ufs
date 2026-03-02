import type { NoteName } from '../types/music'
import { CHROMATIC_SCALE } from '../constants/notes'

// ----- Types -----

export interface ScaleDefinition {
  name: string
  intervals: number[] // semitones from root
}

export interface ChordDefinition {
  name: string
  intervals: number[]
}

// ----- Scale Library -----

export const SCALES: ScaleDefinition[] = [
  { name: 'Major',            intervals: [0, 2, 4, 5, 7, 9, 11] },
  { name: 'Natural Minor',    intervals: [0, 2, 3, 5, 7, 8, 10] },
  { name: 'Harmonic Minor',   intervals: [0, 2, 3, 5, 7, 8, 11] },
  { name: 'Pentatonic Major', intervals: [0, 2, 4, 7, 9] },
  { name: 'Pentatonic Minor', intervals: [0, 3, 5, 7, 10] },
  { name: 'Blues',            intervals: [0, 3, 5, 6, 7, 10] },
  { name: 'Dorian',           intervals: [0, 2, 3, 5, 7, 9, 10] },
  { name: 'Mixolydian',       intervals: [0, 2, 4, 5, 7, 9, 10] },
]

// ----- Chord Library -----

export const CHORDS: ChordDefinition[] = [
  { name: 'Major',  intervals: [0, 4, 7] },
  { name: 'Minor',  intervals: [0, 3, 7] },
  { name: '7th',    intervals: [0, 4, 7, 10] },
  { name: 'm7',     intervals: [0, 3, 7, 10] },
  { name: 'Maj7',   intervals: [0, 4, 7, 11] },
  { name: 'dim',    intervals: [0, 3, 6] },
  { name: 'aug',    intervals: [0, 4, 8] },
  { name: 'sus2',   intervals: [0, 2, 7] },
  { name: 'sus4',   intervals: [0, 5, 7] },
]

// ----- Functions -----

/**
 * Get note names in a scale/chord given a root and interval pattern.
 * Octave-agnostic: returns NoteName[] (e.g., ['C', 'E', 'G']).
 */
export function getScaleNoteNames(
  root: NoteName,
  definition: ScaleDefinition | ChordDefinition,
): NoteName[] {
  const rootIndex = CHROMATIC_SCALE.indexOf(root)
  return definition.intervals.map(
    (interval) => CHROMATIC_SCALE[(rootIndex + interval) % 12],
  )
}

/**
 * Check if a note name is in a set of scale note names.
 */
export function isNoteNameInScale(
  noteName: NoteName,
  scaleNotes: NoteName[],
): boolean {
  return scaleNotes.includes(noteName)
}
