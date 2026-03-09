import type { NoteName } from '../types/music'
import type { ResolvedChord } from './chordProgression'
import { SCALES, type ScaleDefinition, getScaleNoteNames } from './scaleCalculator'

export interface ScaleSuggestion {
  scale: ScaleDefinition
  root: NoteName
  noteNames: NoteName[]
  reason: string
}

// Map chord quality → recommended scale names with reasons
const QUALITY_SCALE_MAP: Record<string, { scaleName: string; reason: string }[]> = {
  Major: [
    { scaleName: 'Major', reason: 'Chord scale' },
    { scaleName: 'Pentatonic Major', reason: 'Safe choice' },
    { scaleName: 'Mixolydian', reason: 'Bluesy feel' },
  ],
  Minor: [
    { scaleName: 'Natural Minor', reason: 'Chord scale' },
    { scaleName: 'Pentatonic Minor', reason: 'Safe choice' },
    { scaleName: 'Dorian', reason: 'Brighter minor' },
    { scaleName: 'Blues', reason: 'Blues licks' },
  ],
  '7th': [
    { scaleName: 'Mixolydian', reason: 'Chord scale' },
    { scaleName: 'Pentatonic Major', reason: 'Safe choice' },
    { scaleName: 'Blues', reason: 'Blues licks' },
  ],
  m7: [
    { scaleName: 'Dorian', reason: 'Chord scale' },
    { scaleName: 'Pentatonic Minor', reason: 'Safe choice' },
    { scaleName: 'Natural Minor', reason: 'Dark feel' },
    { scaleName: 'Blues', reason: 'Blues licks' },
  ],
  Maj7: [
    { scaleName: 'Major', reason: 'Chord scale' },
    { scaleName: 'Pentatonic Major', reason: 'Safe choice' },
  ],
  dim: [
    { scaleName: 'Harmonic Minor', reason: 'Parent scale' },
    { scaleName: 'Natural Minor', reason: 'Safe choice' },
  ],
  aug: [
    { scaleName: 'Major', reason: 'Parent scale' },
  ],
  sus2: [
    { scaleName: 'Major', reason: 'Parent scale' },
    { scaleName: 'Pentatonic Major', reason: 'Safe choice' },
  ],
  sus4: [
    { scaleName: 'Mixolydian', reason: 'Natural choice' },
    { scaleName: 'Pentatonic Major', reason: 'Safe choice' },
  ],
}

const scaleByName = new Map(SCALES.map((s) => [s.name, s]))

/**
 * Get scale suggestions for a chord. Returns scales rooted on the chord root
 * that work well for improvisation over the chord.
 */
export function getScaleSuggestions(chord: ResolvedChord): ScaleSuggestion[] {
  const mappings = QUALITY_SCALE_MAP[chord.quality] ?? QUALITY_SCALE_MAP['Major']!
  const suggestions: ScaleSuggestion[] = []

  for (const { scaleName, reason } of mappings) {
    const scale = scaleByName.get(scaleName)
    if (!scale) continue
    suggestions.push({
      scale,
      root: chord.root,
      noteNames: getScaleNoteNames(chord.root, scale),
      reason,
    })
  }

  return suggestions
}
