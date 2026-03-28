import type { Song } from '../types/song'

const NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'] as const

const FLAT_MAP: Record<string, string> = {
  Db: 'C#', Eb: 'D#', Fb: 'E', Gb: 'F#', Ab: 'G#', Bb: 'A#', Cb: 'B',
}

function normalizeRoot(root: string): string {
  return FLAT_MAP[root] ?? root
}

function transposeRoot(root: string, semitones: number): string {
  const normalized = normalizeRoot(root)
  const idx = NOTES.indexOf(normalized as typeof NOTES[number])
  if (idx === -1) return root
  return NOTES[((idx + semitones) % 12 + 12) % 12]
}

const CHORD_ROOT_RE = /^([A-G][#b]?)(.*)/

export function transposeChord(chord: string, semitones: number): string {
  if (semitones === 0) return chord

  // Handle slash chords: Am/G -> transpose both parts
  const slashIdx = chord.indexOf('/')
  if (slashIdx > 0) {
    const base = transposeChord(chord.slice(0, slashIdx), semitones)
    const bass = transposeChord(chord.slice(slashIdx + 1), semitones)
    return `${base}/${bass}`
  }

  const match = chord.match(CHORD_ROOT_RE)
  if (!match) return chord

  const [, root, suffix] = match
  return transposeRoot(root, semitones) + suffix
}

/** Parse chord string like "Am7", "F#dim", "Bb/F" into root + quality */
export function parseChordName(chord: string): { root: string; quality: string } | null {
  // Strip slash bass note
  const slashIdx = chord.indexOf('/')
  const base = slashIdx > 0 ? chord.slice(0, slashIdx) : chord

  const match = base.match(CHORD_ROOT_RE)
  if (!match) return null

  const [, root, suffix] = match
  return { root: normalizeRoot(root), quality: suffix || 'Major' }
}

export function transposeSong(song: Song, semitones: number): Song {
  if (semitones === 0) return song

  return {
    ...song,
    key: song.key ? transposeRoot(song.key, semitones) : song.key,
    sections: song.sections.map(section => ({
      ...section,
      chords: section.chords.map(c => ({
        ...c,
        chord: transposeChord(c.chord, semitones),
      })),
    })),
  }
}
