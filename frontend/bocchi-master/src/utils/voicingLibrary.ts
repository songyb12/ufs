import type { NoteName, Note, InstrumentConfig } from '../types/music'
import { CHROMATIC_SCALE } from '../constants/notes'

// ----- Types -----

export interface ChordVoicing {
  name: string           // 'E Shape (fret 3)', 'Auto #1', etc.
  frets: number[]        // per-string fret numbers. -1=mute, 0=open, 1+=fret
  source: 'caged' | 'auto'
}

export interface CAGEDShape {
  name: string           // 'E Shape', 'A Shape', etc.
  rootString: number     // string index where root lives (0=low E in standard tuning)
  rootFretInShape: number // fret of root note in the base (open) position
  frets: number[]        // base position fret array (-1=mute, 0=open)
}

// ----- CAGED Shape Library -----
// String order: [6th(lowE), 5th(A), 4th(D), 3rd(G), 2nd(B), 1st(highE)]
// Matches tuning[] array index: 0=lowE .. 5=highE

const CAGED_MAJOR: CAGEDShape[] = [
  { name: 'E Shape',  rootString: 0, rootFretInShape: 0, frets: [0, 2, 2, 1, 0, 0] },
  { name: 'A Shape',  rootString: 1, rootFretInShape: 0, frets: [-1, 0, 2, 2, 2, 0] },
  { name: 'D Shape',  rootString: 2, rootFretInShape: 0, frets: [-1, -1, 0, 2, 3, 2] },
  { name: 'C Shape',  rootString: 1, rootFretInShape: 3, frets: [-1, 3, 2, 0, 1, 0] },
  { name: 'G Shape',  rootString: 0, rootFretInShape: 3, frets: [3, 2, 0, 0, 0, 3] },
]

const CAGED_MINOR: CAGEDShape[] = [
  { name: 'Em Shape', rootString: 0, rootFretInShape: 0, frets: [0, 2, 2, 0, 0, 0] },
  { name: 'Am Shape', rootString: 1, rootFretInShape: 0, frets: [-1, 0, 2, 2, 1, 0] },
  { name: 'Dm Shape', rootString: 2, rootFretInShape: 0, frets: [-1, -1, 0, 2, 3, 1] },
]

const CAGED_7TH: CAGEDShape[] = [
  { name: 'E7 Shape', rootString: 0, rootFretInShape: 0, frets: [0, 2, 0, 1, 0, 0] },
  { name: 'A7 Shape', rootString: 1, rootFretInShape: 0, frets: [-1, 0, 2, 0, 2, 0] },
  { name: 'D7 Shape', rootString: 2, rootFretInShape: 0, frets: [-1, -1, 0, 2, 1, 2] },
]

const CAGED_M7: CAGEDShape[] = [
  { name: 'Em7 Shape', rootString: 0, rootFretInShape: 0, frets: [0, 2, 0, 0, 0, 0] },
  { name: 'Am7 Shape', rootString: 1, rootFretInShape: 0, frets: [-1, 0, 2, 0, 1, 0] },
]

const CAGED_MAJ7: CAGEDShape[] = [
  { name: 'Cmaj7 Shape', rootString: 1, rootFretInShape: 3, frets: [-1, 3, 2, 0, 0, 0] },
  { name: 'Amaj7 Shape', rootString: 1, rootFretInShape: 0, frets: [-1, 0, 2, 1, 2, 0] },
]

// Map quality names (matching CHORDS[].name in scaleCalculator.ts) to shape sets
const CAGED_SHAPES: Record<string, CAGEDShape[]> = {
  Major: CAGED_MAJOR,
  Minor: CAGED_MINOR,
  '7th': CAGED_7TH,
  m7: CAGED_M7,
  Maj7: CAGED_MAJ7,
}

// ----- Helper Functions -----

/**
 * Find all fret positions where a target note name appears on a given string.
 * Returns frets from 0 to maxFret.
 */
function findNoteFretsOnString(
  openNote: Note,
  targetNoteName: NoteName,
  maxFret: number,
): number[] {
  const openIndex = CHROMATIC_SCALE.indexOf(openNote.name)
  const targetIndex = CHROMATIC_SCALE.indexOf(targetNoteName)
  const frets: number[] = []

  // Base semitone distance (mod 12)
  let fret = ((targetIndex - openIndex) % 12 + 12) % 12

  while (fret <= maxFret) {
    frets.push(fret)
    fret += 12
  }

  return frets
}

/**
 * Transpose a single CAGED shape to all valid positions for a target root.
 */
function transposeCagedShape(
  shape: CAGEDShape,
  targetRoot: NoteName,
  tuning: Note[],
  fretCount: number,
): ChordVoicing[] {
  // CAGED shapes are defined for 6-string guitar
  if (tuning.length !== 6) return []

  // Find where the root note falls on the shape's root string
  const rootFrets = findNoteFretsOnString(
    tuning[shape.rootString],
    targetRoot,
    fretCount,
  )

  const voicings: ChordVoicing[] = []

  for (const targetRootFret of rootFrets) {
    const offset = targetRootFret - shape.rootFretInShape

    // Transpose all frets by offset (muted strings stay muted)
    const transposedFrets = shape.frets.map((fret) =>
      fret === -1 ? -1 : fret + offset,
    )

    // Validate: all non-muted frets must be within [0, fretCount]
    const valid = transposedFrets.every(
      (fret) => fret === -1 || (fret >= 0 && fret <= fretCount),
    )
    if (!valid) continue

    // Check fret span of fretted notes (exclude open and muted)
    const frettedNotes = transposedFrets.filter((f) => f > 0)
    if (frettedNotes.length > 0) {
      const span = Math.max(...frettedNotes) - Math.min(...frettedNotes)
      if (span > 5) continue // too wide for a normal hand span
    }

    // Build display name with position indicator
    const minFretted = frettedNotes.length > 0 ? Math.min(...frettedNotes) : 0
    const posLabel = minFretted > 0 ? ` (fret ${minFretted})` : ' (open)'

    voicings.push({
      name: `${shape.name}${posLabel}`,
      frets: transposedFrets,
      source: 'caged',
    })
  }

  return voicings
}

// ----- Public API -----

/**
 * Get all CAGED voicings for a given root note and chord quality.
 * Returns empty array for non-6-string instruments or unsupported qualities.
 *
 * @param root      - Root note name (e.g., 'C', 'F#')
 * @param quality   - Chord quality name matching CHORDS[].name ('Major', 'Minor', '7th', etc.)
 * @param instrument - Instrument config (tuning + fretCount)
 */
export function getCAGEDVoicings(
  root: NoteName,
  quality: string,
  instrument: InstrumentConfig,
): ChordVoicing[] {
  // CAGED system only applies to standard 6-string guitar
  if (instrument.stringCount !== 6) return []

  const shapes = CAGED_SHAPES[quality]
  if (!shapes) return []

  const allVoicings: ChordVoicing[] = []

  for (const shape of shapes) {
    const voicings = transposeCagedShape(
      shape,
      root,
      instrument.tuning,
      instrument.fretCount,
    )
    allVoicings.push(...voicings)
  }

  // Sort by position (lowest fretted note first, then by name)
  allVoicings.sort((a, b) => {
    const aFretted = a.frets.filter((f) => f >= 0)
    const bFretted = b.frets.filter((f) => f >= 0)
    const aMin = aFretted.length > 0 ? Math.min(...aFretted) : 0
    const bMin = bFretted.length > 0 ? Math.min(...bFretted) : 0
    return aMin - bMin
  })

  return allVoicings
}
