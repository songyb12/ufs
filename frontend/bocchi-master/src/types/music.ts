export type NoteName =
  | 'C' | 'C#' | 'D' | 'D#' | 'E' | 'F'
  | 'F#' | 'G' | 'G#' | 'A' | 'A#' | 'B'

export interface Note {
  name: NoteName
  octave: number
  midiNumber: number // 0-127, middle C = 60
}

export type InstrumentType = 'guitar' | 'bass'

export interface InstrumentConfig {
  type: InstrumentType
  name: string
  stringCount: number
  fretCount: number
  tuning: Note[] // open string notes, lowest (thickest) → highest
}
