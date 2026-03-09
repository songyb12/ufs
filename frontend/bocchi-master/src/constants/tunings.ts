import type { InstrumentConfig } from '../types/music'

// ── Standard Tunings ──

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

// ── Alternate Guitar Tunings ──

export const DROP_D_GUITAR: InstrumentConfig = {
  type: 'guitar',
  name: 'Drop D',
  stringCount: 6,
  fretCount: 22,
  tuning: [
    { name: 'D', octave: 2, midiNumber: 38 },
    { name: 'A', octave: 2, midiNumber: 45 },
    { name: 'D', octave: 3, midiNumber: 50 },
    { name: 'G', octave: 3, midiNumber: 55 },
    { name: 'B', octave: 3, midiNumber: 59 },
    { name: 'E', octave: 4, midiNumber: 64 },
  ],
}

export const OPEN_G_GUITAR: InstrumentConfig = {
  type: 'guitar',
  name: 'Open G',
  stringCount: 6,
  fretCount: 22,
  tuning: [
    { name: 'D', octave: 2, midiNumber: 38 },
    { name: 'G', octave: 2, midiNumber: 43 },
    { name: 'D', octave: 3, midiNumber: 50 },
    { name: 'G', octave: 3, midiNumber: 55 },
    { name: 'B', octave: 3, midiNumber: 59 },
    { name: 'D', octave: 4, midiNumber: 62 },
  ],
}

export const OPEN_D_GUITAR: InstrumentConfig = {
  type: 'guitar',
  name: 'Open D',
  stringCount: 6,
  fretCount: 22,
  tuning: [
    { name: 'D', octave: 2, midiNumber: 38 },
    { name: 'A', octave: 2, midiNumber: 45 },
    { name: 'D', octave: 3, midiNumber: 50 },
    { name: 'F#', octave: 3, midiNumber: 54 },
    { name: 'A', octave: 3, midiNumber: 57 },
    { name: 'D', octave: 4, midiNumber: 62 },
  ],
}

export const DADGAD_GUITAR: InstrumentConfig = {
  type: 'guitar',
  name: 'DADGAD',
  stringCount: 6,
  fretCount: 22,
  tuning: [
    { name: 'D', octave: 2, midiNumber: 38 },
    { name: 'A', octave: 2, midiNumber: 45 },
    { name: 'D', octave: 3, midiNumber: 50 },
    { name: 'G', octave: 3, midiNumber: 55 },
    { name: 'A', octave: 3, midiNumber: 57 },
    { name: 'D', octave: 4, midiNumber: 62 },
  ],
}

export const HALF_STEP_DOWN_GUITAR: InstrumentConfig = {
  type: 'guitar',
  name: 'Half Step Down (Eb)',
  stringCount: 6,
  fretCount: 22,
  tuning: [
    { name: 'D#', octave: 2, midiNumber: 39 },
    { name: 'G#', octave: 2, midiNumber: 44 },
    { name: 'C#', octave: 3, midiNumber: 49 },
    { name: 'F#', octave: 3, midiNumber: 54 },
    { name: 'A#', octave: 3, midiNumber: 58 },
    { name: 'D#', octave: 4, midiNumber: 63 },
  ],
}

export const OPEN_E_GUITAR: InstrumentConfig = {
  type: 'guitar',
  name: 'Open E',
  stringCount: 6,
  fretCount: 22,
  tuning: [
    { name: 'E', octave: 2, midiNumber: 40 },
    { name: 'B', octave: 2, midiNumber: 47 },
    { name: 'E', octave: 3, midiNumber: 52 },
    { name: 'G#', octave: 3, midiNumber: 56 },
    { name: 'B', octave: 3, midiNumber: 59 },
    { name: 'E', octave: 4, midiNumber: 64 },
  ],
}

// ── Extended Range Guitar ──

export const SEVEN_STRING_GUITAR: InstrumentConfig = {
  type: 'guitar',
  name: '7-String Standard',
  stringCount: 7,
  fretCount: 24,
  tuning: [
    { name: 'B', octave: 1, midiNumber: 35 },
    { name: 'E', octave: 2, midiNumber: 40 },
    { name: 'A', octave: 2, midiNumber: 45 },
    { name: 'D', octave: 3, midiNumber: 50 },
    { name: 'G', octave: 3, midiNumber: 55 },
    { name: 'B', octave: 3, midiNumber: 59 },
    { name: 'E', octave: 4, midiNumber: 64 },
  ],
}

// ── Alternate Bass Tunings ──

export const FIVE_STRING_BASS: InstrumentConfig = {
  type: 'bass',
  name: '5-String Bass',
  stringCount: 5,
  fretCount: 22,
  tuning: [
    { name: 'B', octave: 0, midiNumber: 23 },
    { name: 'E', octave: 1, midiNumber: 28 },
    { name: 'A', octave: 1, midiNumber: 33 },
    { name: 'D', octave: 2, midiNumber: 38 },
    { name: 'G', octave: 2, midiNumber: 43 },
  ],
}

export const DROP_D_BASS: InstrumentConfig = {
  type: 'bass',
  name: 'Drop D Bass',
  stringCount: 4,
  fretCount: 20,
  tuning: [
    { name: 'D', octave: 1, midiNumber: 26 },
    { name: 'A', octave: 1, midiNumber: 33 },
    { name: 'D', octave: 2, midiNumber: 38 },
    { name: 'G', octave: 2, midiNumber: 43 },
  ],
}

export const SIX_STRING_BASS: InstrumentConfig = {
  type: 'bass',
  name: '6-String Bass',
  stringCount: 6,
  fretCount: 24,
  tuning: [
    { name: 'B', octave: 0, midiNumber: 23 },
    { name: 'E', octave: 1, midiNumber: 28 },
    { name: 'A', octave: 1, midiNumber: 33 },
    { name: 'D', octave: 2, midiNumber: 38 },
    { name: 'G', octave: 2, midiNumber: 43 },
    { name: 'C', octave: 3, midiNumber: 48 },
  ],
}

// ── Exports ──

export const GUITAR_TUNINGS: InstrumentConfig[] = [
  STANDARD_GUITAR,
  DROP_D_GUITAR,
  HALF_STEP_DOWN_GUITAR,
  OPEN_G_GUITAR,
  OPEN_D_GUITAR,
  OPEN_E_GUITAR,
  DADGAD_GUITAR,
  SEVEN_STRING_GUITAR,
]

export const BASS_TUNINGS: InstrumentConfig[] = [
  STANDARD_BASS,
  DROP_D_BASS,
  FIVE_STRING_BASS,
  SIX_STRING_BASS,
]

/** All instruments (flat list) — used for lookup by name */
export const INSTRUMENTS: InstrumentConfig[] = [
  ...GUITAR_TUNINGS,
  ...BASS_TUNINGS,
]
