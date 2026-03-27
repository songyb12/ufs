export type NoteName =
  | 'C' | 'C#' | 'D' | 'D#' | 'E' | 'F'
  | 'F#' | 'G' | 'G#' | 'A' | 'A#' | 'B'

export interface Note {
  name: NoteName
  octave: number
  midiNumber: number // 0-127, middle C = 60
}

export type InstrumentType = 'guitar' | 'bass'

/** Chord quality names — mirrors CHORDS[].name in scaleCalculator.ts */
export type ChordQuality =
  | 'Major' | 'Minor' | 'dim' | 'aug' | 'sus2' | 'sus4'
  | '7th' | 'm7' | 'Maj7' | 'mMaj7' | 'dim7' | 'm7b5' | '7sus4'
  | 'add9' | 'madd9' | '9th' | 'm9' | 'Maj9'
  | '5 (Power)'

export interface InstrumentConfig {
  type: InstrumentType
  name: string
  stringCount: number
  fretCount: number
  tuning: Note[] // open string notes, lowest (thickest) → highest
}
