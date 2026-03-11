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
    { scaleName: 'Major (Ionian)', reason: 'Chord scale' },
    { scaleName: 'Lydian', reason: 'Bright, dreamy' },
    { scaleName: 'Pentatonic Major', reason: 'Safe choice' },
    { scaleName: 'Mixolydian', reason: 'Bluesy feel' },
  ],
  Minor: [
    { scaleName: 'Natural Minor (Aeolian)', reason: 'Chord scale' },
    { scaleName: 'Dorian', reason: 'Brighter minor' },
    { scaleName: 'Pentatonic Minor', reason: 'Safe choice' },
    { scaleName: 'Phrygian', reason: 'Dark, Spanish' },
    { scaleName: 'Blues', reason: 'Blues licks' },
  ],
  '7th': [
    { scaleName: 'Mixolydian', reason: 'Chord scale' },
    { scaleName: 'Lydian Dominant', reason: 'Jazz fusion' },
    { scaleName: 'Pentatonic Major', reason: 'Safe choice' },
    { scaleName: 'Blues', reason: 'Blues licks' },
  ],
  m7: [
    { scaleName: 'Dorian', reason: 'Chord scale' },
    { scaleName: 'Pentatonic Minor', reason: 'Safe choice' },
    { scaleName: 'Natural Minor (Aeolian)', reason: 'Dark feel' },
    { scaleName: 'Blues', reason: 'Blues licks' },
  ],
  Maj7: [
    { scaleName: 'Major (Ionian)', reason: 'Chord scale' },
    { scaleName: 'Lydian', reason: '#4 color tone' },
    { scaleName: 'Pentatonic Major', reason: 'Safe choice' },
  ],
  mMaj7: [
    { scaleName: 'Melodic Minor', reason: 'Chord scale' },
    { scaleName: 'Harmonic Minor', reason: 'Classic sound' },
  ],
  dim: [
    { scaleName: 'Diminished (HW)', reason: 'Chord scale' },
    { scaleName: 'Harmonic Minor', reason: 'Parent scale' },
  ],
  dim7: [
    { scaleName: 'Diminished (HW)', reason: 'Chord scale' },
    { scaleName: 'Harmonic Minor', reason: 'Parent scale' },
  ],
  'm7b5': [
    { scaleName: 'Locrian', reason: 'Chord scale' },
    { scaleName: 'Half-Whole Diminished', reason: 'Jazz option' },
  ],
  aug: [
    { scaleName: 'Whole Tone', reason: 'Chord scale' },
    { scaleName: 'Melodic Minor', reason: 'From 3rd degree' },
  ],
  sus2: [
    { scaleName: 'Major (Ionian)', reason: 'Parent scale' },
    { scaleName: 'Pentatonic Major', reason: 'Safe choice' },
  ],
  sus4: [
    { scaleName: 'Mixolydian', reason: 'Natural choice' },
    { scaleName: 'Pentatonic Major', reason: 'Safe choice' },
  ],
  '7sus4': [
    { scaleName: 'Mixolydian', reason: 'Chord scale' },
    { scaleName: 'Pentatonic Minor', reason: 'Modal flavor' },
  ],
  '9th': [
    { scaleName: 'Mixolydian', reason: 'Chord scale' },
    { scaleName: 'Blues', reason: 'Funky flavor' },
  ],
  m9: [
    { scaleName: 'Dorian', reason: 'Chord scale' },
    { scaleName: 'Pentatonic Minor', reason: 'Safe choice' },
  ],
  Maj9: [
    { scaleName: 'Major (Ionian)', reason: 'Chord scale' },
    { scaleName: 'Lydian', reason: 'Dream pop' },
  ],
  add9: [
    { scaleName: 'Major (Ionian)', reason: 'Chord scale' },
    { scaleName: 'Pentatonic Major', reason: 'Safe choice' },
  ],
  madd9: [
    { scaleName: 'Dorian', reason: 'Natural 9th' },
    { scaleName: 'Natural Minor (Aeolian)', reason: 'Dark feel' },
  ],
  '5 (Power)': [
    { scaleName: 'Pentatonic Minor', reason: 'Rock default' },
    { scaleName: 'Blues', reason: 'Blues rock' },
    { scaleName: 'Natural Minor (Aeolian)', reason: 'Metal/rock' },
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
