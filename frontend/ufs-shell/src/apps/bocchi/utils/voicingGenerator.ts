import type { NoteName, Note, InstrumentConfig } from '../types/music'
import { CHROMATIC_SCALE } from '../constants/notes'
import { CHORDS, getScaleNoteNames } from './scaleCalculator'
import type { ChordVoicing } from './voicingLibrary'

// ----- Configuration -----

const MAX_FRET_SPAN = 4       // maximum stretch between lowest and highest fretted note
const MIN_STRINGS_PLAYED = 3  // minimum non-muted strings
const MAX_RESULTS = 5          // return top N voicings

// ----- Helper Functions -----

/**
 * Get the note name at a given fret on a given string.
 */
function getNoteNameAtFret(openNote: Note, fret: number): NoteName {
  return CHROMATIC_SCALE[(openNote.midiNumber + fret) % 12]
}

/**
 * Find all frets (0..maxFret) on a string where a chord tone appears.
 * Returns array of { fret, noteName } pairs.
 */
function findChordToneFretsOnString(
  openNote: Note,
  chordNotes: Set<NoteName>,
  maxFret: number,
): { fret: number; noteName: NoteName }[] {
  const results: { fret: number; noteName: NoteName }[] = []

  for (let fret = 0; fret <= maxFret; fret++) {
    const noteName = getNoteNameAtFret(openNote, fret)
    if (chordNotes.has(noteName)) {
      results.push({ fret, noteName })
    }
  }

  return results
}

/**
 * Check if a combination has the root note as the lowest sounding note.
 * "Lowest" = lowest string index that is not muted (-1).
 */
function hasRootAsLowest(
  frets: number[],
  tuning: Note[],
  root: NoteName,
): boolean {
  for (let i = 0; i < frets.length; i++) {
    if (frets[i] >= 0) {
      const noteName = getNoteNameAtFret(tuning[i], frets[i])
      return noteName === root
    }
  }
  return false
}

/**
 * Calculate the fret span of a voicing (fretted notes only, excluding open strings).
 */
function fretSpan(frets: number[]): number {
  const fretted = frets.filter((f) => f > 0)
  if (fretted.length <= 1) return 0
  return Math.max(...fretted) - Math.min(...fretted)
}

/**
 * Score a voicing for ranking (lower = better).
 * Factors: position height, muted strings, fret span.
 */
function scoreVoicing(frets: number[]): number {
  const played = frets.filter((f) => f >= 0)
  const fretted = frets.filter((f) => f > 0)
  const mutedCount = frets.filter((f) => f === -1).length

  // Average fret position (prefer lower positions)
  const avgFret = fretted.length > 0
    ? fretted.reduce((sum, f) => sum + f, 0) / fretted.length
    : 0

  // Penalties
  const mutePenalty = mutedCount * 5
  const spanPenalty = fretSpan(frets) * 2
  const openBonus = played.filter((f) => f === 0).length > 0 ? -3 : 0

  return avgFret + mutePenalty + spanPenalty + openBonus
}

// ----- Core Algorithm -----

/**
 * Generate voicings using backtracking search.
 *
 * For each string, the candidate set is:
 *   - All frets that produce a chord tone (within a reasonable fret window)
 *   - -1 (mute the string)
 *
 * Constraints applied during search:
 *   1. Fret span of all fretted notes ≤ MAX_FRET_SPAN
 *   2. At least MIN_STRINGS_PLAYED strings are not muted
 *   3. Root must be the lowest sounding note
 *   4. All chord tones must appear at least once
 */
function searchVoicings(
  tuning: Note[],
  chordNotes: NoteName[],
  root: NoteName,
  maxFret: number,
): number[][] {
  const stringCount = tuning.length
  const chordNoteSet = new Set(chordNotes)
  const results: number[][] = []

  // Pre-compute candidate frets per string
  // For each string: list of valid frets (chord tones) + -1 (mute)
  const candidates: number[][] = tuning.map((openNote) => {
    const tones = findChordToneFretsOnString(openNote, chordNoteSet, maxFret)
    const frets = tones.map((t) => t.fret)
    return [-1, ...frets] // -1 = mute option first
  })

  // Backtracking DFS
  const current: number[] = new Array(stringCount).fill(-1)

  function dfs(stringIdx: number): void {
    // Prune: too many results already
    if (results.length >= MAX_RESULTS * 10) return

    if (stringIdx === stringCount) {
      // Check minimum strings played
      const playedCount = current.filter((f) => f >= 0).length
      if (playedCount < MIN_STRINGS_PLAYED) return

      // Check root is the lowest sounding note
      if (!hasRootAsLowest(current, tuning, root)) return

      // Check all chord tones are covered
      const coveredNotes = new Set<NoteName>()
      for (let i = 0; i < stringCount; i++) {
        if (current[i] >= 0) {
          coveredNotes.add(getNoteNameAtFret(tuning[i], current[i]))
        }
      }
      const allCovered = chordNotes.every((n) => coveredNotes.has(n))
      if (!allCovered) return

      // Valid voicing found
      results.push([...current])
      return
    }

    for (const fret of candidates[stringIdx]) {
      current[stringIdx] = fret

      // Early pruning: check fret span constraint
      if (fret > 0) {
        const frettedSoFar = current.slice(0, stringIdx + 1).filter((f) => f > 0)
        if (frettedSoFar.length > 1) {
          const span = Math.max(...frettedSoFar) - Math.min(...frettedSoFar)
          if (span > MAX_FRET_SPAN) continue
        }
      }

      dfs(stringIdx + 1)
    }

    current[stringIdx] = -1 // reset for backtrack
  }

  dfs(0)
  return results
}

// ----- Public API -----

/**
 * Algorithmically generate practical chord voicings.
 *
 * @param root       - Root note name
 * @param quality    - Chord quality (matches CHORDS[].name)
 * @param instrument - Instrument config
 * @returns Top N ranked voicings
 */
export function generateVoicings(
  root: NoteName,
  quality: string,
  instrument: InstrumentConfig,
): ChordVoicing[] {
  const chordDef = CHORDS.find((c) => c.name === quality)
  if (!chordDef) return []

  const chordNotes = getScaleNoteNames(root, chordDef)
  const rawVoicings = searchVoicings(
    instrument.tuning,
    chordNotes,
    root,
    instrument.fretCount,
  )

  // Score and rank
  const scored = rawVoicings.map((frets) => ({
    frets,
    score: scoreVoicing(frets),
  }))

  scored.sort((a, b) => a.score - b.score)

  // Take top results and format
  return scored.slice(0, MAX_RESULTS).map((item, index) => {
    const fretted = item.frets.filter((f) => f > 0)
    const minFret = fretted.length > 0 ? Math.min(...fretted) : 0
    const posLabel = minFret > 0 ? `fret ${minFret}` : 'open'

    return {
      name: `Auto #${index + 1} (${posLabel})`,
      frets: item.frets,
      source: 'auto' as const,
    }
  })
}
