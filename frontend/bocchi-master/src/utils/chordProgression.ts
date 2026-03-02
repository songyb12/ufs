import type { NoteName } from '../types/music'
import { CHROMATIC_SCALE } from '../constants/notes'
import { CHORDS, getScaleNoteNames } from './scaleCalculator'

// ----- Types -----

export interface DegreeInfo {
  semitones: number   // semitones from root (major scale: 0,2,4,5,7,9,11)
  quality: string     // default chord quality — references CHORDS[].name
  label: string       // Roman numeral label
}

export interface ProgressionStep {
  degreeIndex: number       // 0~6 → index into MAJOR_DEGREES
  qualityOverride?: string  // override default quality (e.g., '7th' for dominant V7)
}

export interface ProgressionPreset {
  name: string
  steps: ProgressionStep[]
}

export interface ResolvedChord {
  root: NoteName
  quality: string     // chord quality name (matches CHORDS[].name)
  label: string       // degree label (e.g., 'I', 'vi')
  chordName: string   // display name (e.g., 'C Maj', 'Am')
  notes: NoteName[]   // all note names in this chord
}

// ----- Major Scale Degrees -----

export const MAJOR_DEGREES: DegreeInfo[] = [
  { semitones: 0,  quality: 'Major', label: 'I' },
  { semitones: 2,  quality: 'Minor', label: 'ii' },
  { semitones: 4,  quality: 'Minor', label: 'iii' },
  { semitones: 5,  quality: 'Major', label: 'IV' },
  { semitones: 7,  quality: 'Major', label: 'V' },
  { semitones: 9,  quality: 'Minor', label: 'vi' },
  { semitones: 11, quality: 'dim',   label: 'vii°' },
]

// ----- Preset Library -----

export const PROGRESSION_PRESETS: ProgressionPreset[] = [
  {
    name: 'Pop (I-V-vi-IV)',
    steps: [
      { degreeIndex: 0 },  // I
      { degreeIndex: 4 },  // V
      { degreeIndex: 5 },  // vi
      { degreeIndex: 3 },  // IV
    ],
  },
  {
    name: 'Basic (I-IV-V-I)',
    steps: [
      { degreeIndex: 0 },  // I
      { degreeIndex: 3 },  // IV
      { degreeIndex: 4 },  // V
      { degreeIndex: 0 },  // I
    ],
  },
  {
    name: '50s (I-vi-IV-V)',
    steps: [
      { degreeIndex: 0 },  // I
      { degreeIndex: 5 },  // vi
      { degreeIndex: 3 },  // IV
      { degreeIndex: 4 },  // V
    ],
  },
  {
    name: 'Jazz ii-V-I',
    steps: [
      { degreeIndex: 1 },  // ii
      { degreeIndex: 4 },  // V
      { degreeIndex: 0 },  // I
    ],
  },
  {
    name: '12-bar Blues',
    steps: [
      { degreeIndex: 0 },                          // I
      { degreeIndex: 0 },                          // I
      { degreeIndex: 0 },                          // I
      { degreeIndex: 0 },                          // I
      { degreeIndex: 3 },                          // IV
      { degreeIndex: 3 },                          // IV
      { degreeIndex: 0 },                          // I
      { degreeIndex: 0 },                          // I
      { degreeIndex: 4, qualityOverride: '7th' },  // V7
      { degreeIndex: 3 },                          // IV
      { degreeIndex: 0 },                          // I
      { degreeIndex: 4, qualityOverride: '7th' },  // V7 (turnaround)
    ],
  },
]

// ----- Functions -----

/**
 * Get the chord display name (e.g., "C Maj", "Am", "G7")
 */
function formatChordName(root: NoteName, quality: string): string {
  const shortQuality: Record<string, string> = {
    'Major': 'Maj',
    'Minor': 'm',
    '7th': '7',
    'm7': 'm7',
    'Maj7': 'Maj7',
    'dim': 'dim',
    'aug': 'aug',
    'sus2': 'sus2',
    'sus4': 'sus4',
  }
  return `${root}${shortQuality[quality] ?? quality}`
}

/**
 * Get the note names for a chord given root and quality name.
 * Looks up ChordDefinition from CHORDS array.
 */
export function getChordNotes(root: NoteName, quality: string): NoteName[] {
  const chordDef = CHORDS.find((c) => c.name === quality)
  if (!chordDef) return [root]
  return getScaleNoteNames(root, chordDef)
}

/**
 * Resolve a progression preset into concrete chords for a given key.
 */
export function resolveProgression(
  key: NoteName,
  preset: ProgressionPreset,
): ResolvedChord[] {
  const keyIndex = CHROMATIC_SCALE.indexOf(key)

  return preset.steps.map((step) => {
    const degree = MAJOR_DEGREES[step.degreeIndex]
    const root = CHROMATIC_SCALE[(keyIndex + degree.semitones) % 12]
    const quality = step.qualityOverride ?? degree.quality
    const notes = getChordNotes(root, quality)
    const label = step.qualityOverride
      ? `${degree.label}${step.qualityOverride === '7th' ? '7' : ''}`
      : degree.label

    return {
      root,
      quality,
      label,
      chordName: formatChordName(root, quality),
      notes,
    }
  })
}
