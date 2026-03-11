import type { Note, NoteName } from '../types/music'
import { CHROMATIC_SCALE } from '../constants/notes'

/**
 * Calculate the note at a given fret position.
 * Each fret = +1 semitone from the open string note.
 */
export function getNoteAtFret(openNote: Note, fret: number): Note {
  const midiNumber = openNote.midiNumber + fret
  const noteIndex = midiNumber % 12
  const octave = Math.floor(midiNumber / 12) - 1
  const name: NoteName = CHROMATIC_SCALE[noteIndex]
  return { name, octave, midiNumber }
}

/**
 * Calculate the X position of a fret using 12-TET (equal temperament) formula.
 * Frets get narrower toward the body, matching real guitar spacing.
 *
 * @param fretNumber - Fret number (0 = nut)
 * @param scaleLength - Total scale length in SVG units
 * @returns X position from the nut
 */
export function calculateFretX(fretNumber: number, scaleLength: number): number {
  return scaleLength * (1 - 1 / Math.pow(2, fretNumber / 12))
}
