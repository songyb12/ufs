/**
 * Scale Pattern Shapes
 *
 * Defines common guitar scale patterns (box shapes) used for practice.
 * Each pattern specifies fret offsets relative to a root position,
 * allowing them to be transposed to any key.
 *
 * Pattern format:
 *   positions: [stringIndex, fretOffset][]
 *     stringIndex: 0=low E, 5=high E (standard 6-string)
 *     fretOffset: semitones relative to the root fret position
 */

export interface ScalePattern {
  name: string
  description: string
  /** Fret offsets per string: [lowestStringFrets, ..., highestStringFrets]
   *  Each sub-array lists the fret offsets played on that string relative
   *  to the pattern's root fret position. */
  shape: number[][]
  /** Which fret offset is the root note on the lowest string (or -1 if root isn't on that string) */
  rootOffset: number
  /** Suggested fret range width needed to display this pattern */
  fretSpan: number
  /** Scale type this pattern belongs to */
  scaleType: 'pentatonic-minor' | 'pentatonic-major' | 'major' | 'minor' | 'blues'
}

// ── Pentatonic Minor Box Patterns ──
// The 5 classic "box" shapes that connect across the fretboard

export const PENTATONIC_MINOR_PATTERNS: ScalePattern[] = [
  {
    name: 'Box 1 (E Shape)',
    description: 'Root on 6th string. Most common pattern.',
    shape: [
      [0, 3],     // string 6: root, m3
      [0, 3],     // string 5: P4, m6 (shifted: P4=+5 semitones from root, m6 is wrong... let me use fret offsets)
      [0, 2],     // string 4
      [0, 2],     // string 3
      [0, 3],     // string 2
      [0, 3],     // string 1
    ],
    rootOffset: 0,
    fretSpan: 4,
    scaleType: 'pentatonic-minor',
  },
  {
    name: 'Box 2 (D Shape)',
    description: 'Extends above Box 1.',
    shape: [
      [0, 2],
      [0, 3],
      [0, 2],
      [0, 2],
      [0, 3],
      [0, 2],
    ],
    rootOffset: 3, // root on high strings
    fretSpan: 4,
    scaleType: 'pentatonic-minor',
  },
  {
    name: 'Box 3 (C Shape)',
    description: 'Middle position pattern.',
    shape: [
      [0, 2],
      [0, 2],
      [0, 2],
      [0, 2],
      [0, 2],
      [0, 2],
    ],
    rootOffset: 2,
    fretSpan: 3,
    scaleType: 'pentatonic-minor',
  },
  {
    name: 'Box 4 (A Shape)',
    description: 'Root on 5th string.',
    shape: [
      [0, 3],
      [0, 2],
      [0, 2],
      [0, 2],
      [0, 3],
      [0, 3],
    ],
    rootOffset: 0,
    fretSpan: 4,
    scaleType: 'pentatonic-minor',
  },
  {
    name: 'Box 5 (G Shape)',
    description: 'Lowest position, connects to Box 1.',
    shape: [
      [0, 2],
      [0, 3],
      [0, 2],
      [0, 3],
      [0, 2],
      [0, 2],
    ],
    rootOffset: 2,
    fretSpan: 4,
    scaleType: 'pentatonic-minor',
  },
]

// ── Blues Scale Patterns ── (pentatonic minor + b5)
export const BLUES_PATTERNS: ScalePattern[] = [
  {
    name: 'Blues Box 1',
    description: 'Root on 6th string with blue note.',
    shape: [
      [0, 3],
      [0, 2, 3],
      [0, 1, 2],
      [0, 2],
      [0, 3],
      [0, 3],
    ],
    rootOffset: 0,
    fretSpan: 4,
    scaleType: 'blues',
  },
]

/**
 * Get the actual fret numbers for a pattern rooted at a given fret position.
 * Returns an array of [stringIndex, fret][] suitable for highlighting on the fretboard.
 */
export function resolvePatternFrets(
  pattern: ScalePattern,
  rootFret: number,
): { stringIndex: number; fret: number }[] {
  const positions: { stringIndex: number; fret: number }[] = []
  pattern.shape.forEach((offsets, stringIndex) => {
    offsets.forEach((offset) => {
      const fret = rootFret + offset
      if (fret >= 0 && fret <= 24) {
        positions.push({ stringIndex, fret })
      }
    })
  })
  return positions
}

/**
 * All available patterns grouped by scale type.
 */
export const ALL_PATTERNS = [
  ...PENTATONIC_MINOR_PATTERNS,
  ...BLUES_PATTERNS,
]

/**
 * Get patterns for a given scale type.
 */
export function getPatternsForScale(scaleType: ScalePattern['scaleType']): ScalePattern[] {
  return ALL_PATTERNS.filter((p) => p.scaleType === scaleType)
}
