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
  // ── Major Modes ──
  { name: 'Major (Ionian)',   intervals: [0, 2, 4, 5, 7, 9, 11] },
  { name: 'Dorian',           intervals: [0, 2, 3, 5, 7, 9, 10] },
  { name: 'Phrygian',         intervals: [0, 1, 3, 5, 7, 8, 10] },
  { name: 'Lydian',           intervals: [0, 2, 4, 6, 7, 9, 11] },
  { name: 'Mixolydian',       intervals: [0, 2, 4, 5, 7, 9, 10] },
  { name: 'Natural Minor (Aeolian)', intervals: [0, 2, 3, 5, 7, 8, 10] },
  { name: 'Locrian',          intervals: [0, 1, 3, 5, 6, 8, 10] },
  // ── Minor Variants ──
  { name: 'Harmonic Minor',   intervals: [0, 2, 3, 5, 7, 8, 11] },
  { name: 'Melodic Minor',    intervals: [0, 2, 3, 5, 7, 9, 11] },
  // ── Pentatonic & Blues ──
  { name: 'Pentatonic Major', intervals: [0, 2, 4, 7, 9] },
  { name: 'Pentatonic Minor', intervals: [0, 3, 5, 7, 10] },
  { name: 'Blues',            intervals: [0, 3, 5, 6, 7, 10] },
  { name: 'Blues Major',      intervals: [0, 2, 3, 4, 7, 9] },
  // ── Exotic / Ethnic ──
  { name: 'Whole Tone',       intervals: [0, 2, 4, 6, 8, 10] },
  { name: 'Diminished (HW)',  intervals: [0, 1, 3, 4, 6, 7, 9, 10] },
  { name: 'Diminished (WH)',  intervals: [0, 2, 3, 5, 6, 8, 9, 11] },
  { name: 'Chromatic',        intervals: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11] },
  // ── Jazz ──
  { name: 'Altered (Super Locrian)', intervals: [0, 1, 3, 4, 6, 8, 10] },
  { name: 'Lydian Dominant',  intervals: [0, 2, 4, 6, 7, 9, 10] },
  { name: 'Half-Whole Diminished', intervals: [0, 1, 3, 4, 6, 7, 9, 10] },
]

// Legacy alias for backward compatibility
export const MAJOR_SCALE = SCALES[0]

// ----- Chord Library -----

export const CHORDS: ChordDefinition[] = [
  // ── Triads ──
  { name: 'Major',     intervals: [0, 4, 7] },
  { name: 'Minor',     intervals: [0, 3, 7] },
  { name: 'dim',       intervals: [0, 3, 6] },
  { name: 'aug',       intervals: [0, 4, 8] },
  { name: 'sus2',      intervals: [0, 2, 7] },
  { name: 'sus4',      intervals: [0, 5, 7] },
  // ── Seventh Chords ──
  { name: '7th',       intervals: [0, 4, 7, 10] },
  { name: 'm7',        intervals: [0, 3, 7, 10] },
  { name: 'Maj7',      intervals: [0, 4, 7, 11] },
  { name: 'mMaj7',     intervals: [0, 3, 7, 11] },
  { name: 'dim7',      intervals: [0, 3, 6, 9] },
  { name: 'm7b5',      intervals: [0, 3, 6, 10] },
  { name: '7sus4',     intervals: [0, 5, 7, 10] },
  // ── Extended Chords ──
  { name: 'add9',      intervals: [0, 4, 7, 14] },  // root, 3, 5, 9
  { name: 'madd9',     intervals: [0, 3, 7, 14] },  // root, b3, 5, 9
  { name: '9th',       intervals: [0, 4, 7, 10, 14] },
  { name: 'm9',        intervals: [0, 3, 7, 10, 14] },
  { name: 'Maj9',      intervals: [0, 4, 7, 11, 14] },
  // ── Power & Slash ──
  { name: '5 (Power)', intervals: [0, 7] },
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

/**
 * Key signature info for a major or natural minor key.
 * Returns the number of sharps or flats and which notes are altered.
 */
export interface KeySignature {
  sharps: NoteName[]
  flats: NoteName[]
}

// Order of sharps: F C G D A E B → order of flats: B E A D G C F
const SHARP_ORDER: NoteName[] = ['F#', 'C#', 'G#', 'D#', 'A#']
const FLAT_ORDER: NoteName[] = ['A#', 'D#', 'G#', 'C#', 'F#']  // enharmonic Bb Eb Ab Db Gb

// Major keys and their signature (positive = sharps, negative = flats)
const MAJOR_KEY_SIG: Record<NoteName, number> = {
  'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5,
  'F#': 6, 'C#': 7,
  'F': -1, 'A#': -2, 'D#': -3, 'G#': -4,
}

export function getKeySignature(root: NoteName, isMinor: boolean): KeySignature {
  // Minor key → use relative major (up 3 semitones)
  let majorRoot = root
  if (isMinor) {
    const idx = CHROMATIC_SCALE.indexOf(root)
    majorRoot = CHROMATIC_SCALE[(idx + 3) % 12]
  }

  const sig = MAJOR_KEY_SIG[majorRoot]
  if (sig == null || sig === 0) return { sharps: [], flats: [] }

  if (sig > 0) {
    return { sharps: SHARP_ORDER.slice(0, sig), flats: [] }
  }
  return { sharps: [], flats: FLAT_ORDER.slice(0, -sig) }
}
