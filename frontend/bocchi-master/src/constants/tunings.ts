import type { InstrumentConfig } from '../types/music'

export const STANDARD_GUITAR: InstrumentConfig = {
  type: 'guitar',
  name: 'Standard Guitar',
  stringCount: 6,
  fretCount: 22,
  tuning: [
    { name: 'E', octave: 2, midiNumber: 40 },
    { name: 'A', octave: 2, midiNumber: 45 },
    { name: 'D', octave: 3, midiNumber: 50 },
    { name: 'G', octave: 3, midiNumber: 55 },
    { name: 'B', octave: 3, midiNumber: 59 },
    { name: 'E', octave: 4, midiNumber: 64 },
  ],
}

export const STANDARD_BASS: InstrumentConfig = {
  type: 'bass',
  name: 'Standard Bass',
  stringCount: 4,
  fretCount: 20,
  tuning: [
    { name: 'E', octave: 1, midiNumber: 28 },
    { name: 'A', octave: 1, midiNumber: 33 },
    { name: 'D', octave: 2, midiNumber: 38 },
    { name: 'G', octave: 2, midiNumber: 43 },
  ],
}

export const INSTRUMENTS: InstrumentConfig[] = [STANDARD_GUITAR, STANDARD_BASS]
