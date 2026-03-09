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
  // ── Pop / Rock ──
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
    name: 'Sad (vi-IV-I-V)',
    steps: [
      { degreeIndex: 5 },  // vi
      { degreeIndex: 3 },  // IV
      { degreeIndex: 0 },  // I
      { degreeIndex: 4 },  // V
    ],
  },
  {
    name: 'Pachelbel (I-V-vi-iii-IV-I-IV-V)',
    steps: [
      { degreeIndex: 0 },  // I
      { degreeIndex: 4 },  // V
      { degreeIndex: 5 },  // vi
      { degreeIndex: 2 },  // iii
      { degreeIndex: 3 },  // IV
      { degreeIndex: 0 },  // I
      { degreeIndex: 3 },  // IV
      { degreeIndex: 4 },  // V
    ],
  },
  // ── Blues ──
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
  {
    name: 'Minor Blues',
    steps: [
      { degreeIndex: 0, qualityOverride: 'Minor' },  // i
      { degreeIndex: 0, qualityOverride: 'Minor' },  // i
      { degreeIndex: 0, qualityOverride: 'Minor' },  // i
      { degreeIndex: 0, qualityOverride: 'Minor' },  // i
      { degreeIndex: 3, qualityOverride: 'Minor' },  // iv
      { degreeIndex: 3, qualityOverride: 'Minor' },  // iv
      { degreeIndex: 0, qualityOverride: 'Minor' },  // i
      { degreeIndex: 0, qualityOverride: 'Minor' },  // i
      { degreeIndex: 4, qualityOverride: '7th' },    // V7
      { degreeIndex: 3, qualityOverride: 'Minor' },  // iv
      { degreeIndex: 0, qualityOverride: 'Minor' },  // i
      { degreeIndex: 4, qualityOverride: '7th' },    // V7
    ],
  },
  // ── Jazz ──
  {
    name: 'Jazz ii-V-I',
    steps: [
      { degreeIndex: 1, qualityOverride: 'm7' },    // ii7
      { degreeIndex: 4, qualityOverride: '7th' },   // V7
      { degreeIndex: 0, qualityOverride: 'Maj7' },  // IMaj7
    ],
  },
  {
    name: 'Jazz I-vi-ii-V',
    steps: [
      { degreeIndex: 0, qualityOverride: 'Maj7' },  // IMaj7
      { degreeIndex: 5, qualityOverride: 'm7' },    // vi7
      { degreeIndex: 1, qualityOverride: 'm7' },    // ii7
      { degreeIndex: 4, qualityOverride: '7th' },   // V7
    ],
  },
  {
    name: 'Autumn Leaves',
    steps: [
      { degreeIndex: 1, qualityOverride: 'm7' },    // ii7
      { degreeIndex: 4, qualityOverride: '7th' },   // V7
      { degreeIndex: 0, qualityOverride: 'Maj7' },  // IMaj7
      { degreeIndex: 3, qualityOverride: 'Maj7' },  // IVMaj7
      { degreeIndex: 6, qualityOverride: 'm7b5' },  // vii7b5
      { degreeIndex: 2, qualityOverride: '7th' },   // III7 (V/vi)
      { degreeIndex: 5, qualityOverride: 'm7' },    // vi7
      { degreeIndex: 5, qualityOverride: 'm7' },    // vi7
    ],
  },
  // ── Funk / R&B ──
  {
    name: 'Funk (I7-IV7)',
    steps: [
      { degreeIndex: 0, qualityOverride: '7th' },  // I7
      { degreeIndex: 0, qualityOverride: '7th' },  // I7
      { degreeIndex: 3, qualityOverride: '7th' },  // IV7
      { degreeIndex: 0, qualityOverride: '7th' },  // I7
    ],
  },
  // ── Bossa / Latin ──
  {
    name: 'Bossa (IMaj7-ii7-V7)',
    steps: [
      { degreeIndex: 0, qualityOverride: 'Maj7' },  // IMaj7
      { degreeIndex: 0, qualityOverride: 'Maj7' },  // IMaj7
      { degreeIndex: 1, qualityOverride: 'm7' },    // ii7
      { degreeIndex: 4, qualityOverride: '7th' },   // V7
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
    'mMaj7': 'mMaj7',
    'dim': 'dim',
    'dim7': 'dim7',
    'm7b5': 'm7♭5',
    'aug': 'aug',
    'sus2': 'sus2',
    'sus4': 'sus4',
    '7sus4': '7sus4',
    'add9': 'add9',
    'madd9': 'madd9',
    '9th': '9',
    'm9': 'm9',
    'Maj9': 'Maj9',
    '5 (Power)': '5',
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
