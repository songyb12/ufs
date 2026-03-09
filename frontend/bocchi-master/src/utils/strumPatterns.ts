/**
 * Strum Pattern Definitions
 *
 * Each strum pattern defines the picking hand motion for one measure.
 * Strokes are evenly divided across the measure based on the pattern length.
 *
 * D = Down strum, U = Up strum, - = Rest (mute)
 */

export type StrokeType = 'D' | 'U' | '-'

export interface StrumPattern {
  name: string
  /** Category for grouping */
  category: 'basic' | 'pop' | 'folk' | 'funk' | 'blues'
  /** Stroke sequence for one measure. Length = total subdivisions per measure.
   *  8 = eighth notes, 16 = sixteenth notes */
  strokes: StrokeType[]
  /** Description / usage hint */
  description: string
}

export const STRUM_PATTERNS: StrumPattern[] = [
  // Basic patterns (easy for beginners)
  {
    name: 'All Down',
    category: 'basic',
    strokes: ['D', '-', 'D', '-', 'D', '-', 'D', '-'],
    description: 'Simplest pattern. Quarter note downstrokes.',
  },
  {
    name: 'Down-Up',
    category: 'basic',
    strokes: ['D', 'U', 'D', 'U', 'D', 'U', 'D', 'U'],
    description: 'Steady 8th-note pattern. Good for practice.',
  },
  {
    name: 'D DU',
    category: 'basic',
    strokes: ['D', '-', 'D', 'U', 'D', '-', 'D', 'U'],
    description: 'Common beginner pattern. Accent beats 1 and 3.',
  },

  // Pop / Rock patterns
  {
    name: 'Pop Standard',
    category: 'pop',
    strokes: ['D', '-', 'D', 'U', '-', 'U', 'D', 'U'],
    description: 'The iconic D-DU-UDU. Works for most pop/rock songs.',
  },
  {
    name: 'Island',
    category: 'pop',
    strokes: ['D', '-', 'D', 'U', '-', 'U', 'D', '-'],
    description: 'Reggae/island feel with muted upbeats.',
  },
  {
    name: 'Pop Ballad',
    category: 'pop',
    strokes: ['D', '-', '-', 'U', '-', 'U', 'D', '-'],
    description: 'Sparse pattern for slow ballads.',
  },

  // Folk / Country
  {
    name: 'Folk Boom-Chuck',
    category: 'folk',
    strokes: ['D', '-', '-', '-', 'D', 'U', 'D', 'U'],
    description: 'Bass note on 1, strums on 3-4.',
  },
  {
    name: 'Travis Pick Feel',
    category: 'folk',
    strokes: ['D', 'U', '-', 'U', 'D', 'U', '-', 'U'],
    description: 'Alternating bass simulation.',
  },

  // Funk
  {
    name: 'Funk Chick',
    category: 'funk',
    strokes: ['D', '-', 'U', '-', '-', 'U', 'D', 'U', '-', 'U', 'D', '-', '-', 'U', 'D', 'U'],
    description: '16th-note funk pattern with ghost strums.',
  },

  // Blues
  {
    name: 'Blues Shuffle',
    category: 'blues',
    strokes: ['D', '-', 'U', 'D', '-', 'U', 'D', '-', 'U', 'D', '-', 'U'],
    description: 'Triplet-based shuffle. Swing the "ands".',
  },
]

export function getPatternsByCategory(category: StrumPattern['category']): StrumPattern[] {
  return STRUM_PATTERNS.filter((p) => p.category === category)
}

export const STRUM_CATEGORIES: { key: StrumPattern['category']; label: string }[] = [
  { key: 'basic', label: 'Basic' },
  { key: 'pop', label: 'Pop/Rock' },
  { key: 'folk', label: 'Folk' },
  { key: 'funk', label: 'Funk' },
  { key: 'blues', label: 'Blues' },
]
