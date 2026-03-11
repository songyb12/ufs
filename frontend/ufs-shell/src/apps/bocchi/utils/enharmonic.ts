/**
 * Enharmonic note name conversion.
 *
 * Internal model always uses sharps (C, C#, D, D#, E, F, F#, G, G#, A, A#, B).
 * This utility provides display-level flat alternatives.
 */

import type { NoteName } from '../types/music'

export type EnharmonicMode = 'sharp' | 'flat'

/** Sharp → Flat mapping for display */
const FLAT_NAMES: Record<NoteName, string> = {
  'C': 'C',
  'C#': 'Db',
  'D': 'D',
  'D#': 'Eb',
  'E': 'E',
  'F': 'F',
  'F#': 'Gb',
  'G': 'G',
  'G#': 'Ab',
  'A': 'A',
  'A#': 'Bb',
  'B': 'B',
}

/**
 * Get the display name for a note based on the enharmonic mode.
 * In 'sharp' mode, returns the original name (C#, D#, etc.).
 * In 'flat' mode, returns the flat equivalent (Db, Eb, etc.).
 */
export function getEnharmonicName(name: NoteName, mode: EnharmonicMode): string {
  if (mode === 'flat') return FLAT_NAMES[name]
  return name
}

/**
 * Keys that are conventionally notated with flats.
 * Useful for auto-selecting the enharmonic mode based on the key.
 */
export const FLAT_KEYS: NoteName[] = ['F', 'A#', 'D#', 'G#', 'C#', 'F#']

/**
 * Suggest the most appropriate enharmonic mode for a given key.
 * Flat keys → 'flat', sharp keys → 'sharp'.
 */
export function suggestEnharmonicMode(key: NoteName): EnharmonicMode {
  return FLAT_KEYS.includes(key) ? 'flat' : 'sharp'
}
