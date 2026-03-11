/**
 * Backing Track Style Patterns
 *
 * Each style defines a drum + bass pattern for a given time signature.
 * Patterns are defined per-beat with actions to schedule.
 *
 * Drum actions: 'kick' | 'snare' | 'hihat' | 'hihat-open' | 'rest'
 * Bass actions: 'root' | 'fifth' | 'octave' | 'walk-up' | 'walk-down' | 'rest'
 *
 * Subdivision: each beat can have sub-beats (e.g., 8th notes = 2 per beat)
 */

import {
  scheduleKick,
  scheduleSnare,
  scheduleHihat,
  scheduleBassNote,
} from './drumSynth'
import { CHROMATIC_SCALE } from '../constants/notes'
import type { NoteName } from '../types/music'

// ── Types ──

export interface DrumHit {
  type: 'kick' | 'snare' | 'hihat' | 'hihat-open'
  volume: number  // multiplier (0-1)
}

export interface BassHit {
  type: 'root' | 'fifth' | 'octave' | 'third' | 'chromatic-up' | 'chromatic-down'
  volume: number
  duration: number  // in beats
}

export interface SubBeat {
  drums: DrumHit[]
  bass: BassHit | null
}

export interface StylePattern {
  name: string
  description: string
  subdivisions: number  // sub-beats per beat (1 = quarter, 2 = eighth, 3 = triplet)
  beatsPerMeasure: number
  /** Pattern indexed by [beat * subdivisions + subBeat] */
  pattern: SubBeat[]
}

// ── Pattern Definitions ──

/**
 * Rock/Pop: Standard 4/4 beat
 * Kick+HH on 1&3, Snare+HH on 2&4, 8th note HH throughout
 */
const ROCK: StylePattern = {
  name: 'Rock',
  description: 'Standard 8th-note rock beat',
  subdivisions: 2,
  beatsPerMeasure: 4,
  pattern: [
    // Beat 1: kick + hihat, then hihat
    { drums: [{ type: 'kick', volume: 1.0 }, { type: 'hihat', volume: 0.5 }], bass: { type: 'root', volume: 0.8, duration: 1 } },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: null },
    // Beat 2: snare + hihat, then hihat
    { drums: [{ type: 'snare', volume: 0.8 }, { type: 'hihat', volume: 0.5 }], bass: null },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: null },
    // Beat 3: kick + hihat, then hihat
    { drums: [{ type: 'kick', volume: 0.9 }, { type: 'hihat', volume: 0.5 }], bass: { type: 'fifth', volume: 0.7, duration: 1 } },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: null },
    // Beat 4: snare + hihat, then hihat
    { drums: [{ type: 'snare', volume: 0.8 }, { type: 'hihat', volume: 0.5 }], bass: null },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: null },
  ],
}

/**
 * Jazz: Swing feel with ride cymbal pattern
 * Uses triplet subdivision for swing feel
 */
const JAZZ: StylePattern = {
  name: 'Jazz',
  description: 'Swing ride pattern with walking bass',
  subdivisions: 3,
  beatsPerMeasure: 4,
  pattern: [
    // Beat 1: ride + kick, skip, ride
    { drums: [{ type: 'hihat', volume: 0.6 }, { type: 'kick', volume: 0.5 }], bass: { type: 'root', volume: 0.7, duration: 1 } },
    { drums: [], bass: null },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: null },
    // Beat 2: ride, skip, ride
    { drums: [{ type: 'hihat', volume: 0.5 }], bass: { type: 'third', volume: 0.6, duration: 1 } },
    { drums: [], bass: null },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: null },
    // Beat 3: ride + kick, skip, ride
    { drums: [{ type: 'hihat', volume: 0.6 }], bass: { type: 'fifth', volume: 0.7, duration: 1 } },
    { drums: [], bass: null },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: null },
    // Beat 4: ride + snare ghost, skip, ride
    { drums: [{ type: 'hihat', volume: 0.5 }, { type: 'snare', volume: 0.25 }], bass: { type: 'chromatic-up', volume: 0.6, duration: 1 } },
    { drums: [], bass: null },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: null },
  ],
}

/**
 * Funk: Syncopated 16th-note feel
 */
const FUNK: StylePattern = {
  name: 'Funk',
  description: 'Syncopated 16th-note groove',
  subdivisions: 2,
  beatsPerMeasure: 4,
  pattern: [
    // Beat 1: kick + hihat
    { drums: [{ type: 'kick', volume: 1.0 }, { type: 'hihat', volume: 0.6 }], bass: { type: 'root', volume: 0.9, duration: 0.5 } },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: { type: 'root', volume: 0.5, duration: 0.5 } },
    // Beat 2: snare + hihat
    { drums: [{ type: 'snare', volume: 0.9 }, { type: 'hihat', volume: 0.5 }], bass: null },
    { drums: [{ type: 'hihat', volume: 0.3 }, { type: 'kick', volume: 0.6 }], bass: { type: 'octave', volume: 0.6, duration: 0.5 } },
    // Beat 3: hihat + kick
    { drums: [{ type: 'hihat', volume: 0.5 }], bass: { type: 'fifth', volume: 0.7, duration: 0.5 } },
    { drums: [{ type: 'hihat', volume: 0.3 }, { type: 'kick', volume: 0.7 }], bass: { type: 'root', volume: 0.5, duration: 0.5 } },
    // Beat 4: snare + open hihat
    { drums: [{ type: 'snare', volume: 1.0 }, { type: 'hihat-open', volume: 0.4 }], bass: null },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: { type: 'chromatic-up', volume: 0.5, duration: 0.5 } },
  ],
}

/**
 * Bossa Nova: Latin 2-bar feel
 */
const BOSSA_NOVA: StylePattern = {
  name: 'Bossa Nova',
  description: 'Brazilian bossa nova pattern',
  subdivisions: 2,
  beatsPerMeasure: 4,
  pattern: [
    // Beat 1: kick + cross-stick
    { drums: [{ type: 'kick', volume: 0.6 }], bass: { type: 'root', volume: 0.7, duration: 1.5 } },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: null },
    // Beat 2: hihat
    { drums: [{ type: 'hihat', volume: 0.4 }], bass: null },
    { drums: [{ type: 'snare', volume: 0.3 }, { type: 'hihat', volume: 0.3 }], bass: { type: 'fifth', volume: 0.6, duration: 1 } },
    // Beat 3: kick
    { drums: [{ type: 'kick', volume: 0.5 }], bass: null },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: null },
    // Beat 4: cross-stick + hihat
    { drums: [{ type: 'snare', volume: 0.3 }, { type: 'hihat', volume: 0.4 }], bass: { type: 'root', volume: 0.5, duration: 1 } },
    { drums: [{ type: 'hihat', volume: 0.3 }], bass: null },
  ],
}

/**
 * Reggae: Off-beat emphasis
 */
const REGGAE: StylePattern = {
  name: 'Reggae',
  description: 'Off-beat skank pattern',
  subdivisions: 2,
  beatsPerMeasure: 4,
  pattern: [
    // Beat 1: kick (downbeat quiet)
    { drums: [{ type: 'kick', volume: 0.7 }], bass: { type: 'root', volume: 0.8, duration: 1.5 } },
    { drums: [{ type: 'hihat', volume: 0.5 }], bass: null },
    // Beat 2: snare (rim) on upbeat
    { drums: [], bass: null },
    { drums: [{ type: 'snare', volume: 0.6 }, { type: 'hihat', volume: 0.4 }], bass: null },
    // Beat 3: kick
    { drums: [{ type: 'kick', volume: 0.6 }], bass: { type: 'fifth', volume: 0.7, duration: 1.5 } },
    { drums: [{ type: 'hihat', volume: 0.5 }], bass: null },
    // Beat 4: snare on upbeat
    { drums: [], bass: null },
    { drums: [{ type: 'snare', volume: 0.6 }, { type: 'hihat', volume: 0.4 }], bass: null },
  ],
}

/**
 * Waltz: 3/4 time
 */
const WALTZ: StylePattern = {
  name: 'Waltz',
  description: '3/4 waltz pattern',
  subdivisions: 1,
  beatsPerMeasure: 3,
  pattern: [
    // Beat 1: kick (strong)
    { drums: [{ type: 'kick', volume: 0.8 }], bass: { type: 'root', volume: 0.8, duration: 1 } },
    // Beat 2: hihat (weak)
    { drums: [{ type: 'hihat', volume: 0.4 }], bass: { type: 'fifth', volume: 0.5, duration: 1 } },
    // Beat 3: hihat (weak)
    { drums: [{ type: 'hihat', volume: 0.4 }], bass: { type: 'fifth', volume: 0.5, duration: 1 } },
  ],
}

/**
 * Metronome: Simple click (no groove, just counting)
 */
const METRONOME_ONLY: StylePattern = {
  name: 'Metronome',
  description: 'Simple click, no groove',
  subdivisions: 1,
  beatsPerMeasure: 4,
  pattern: [
    { drums: [{ type: 'hihat', volume: 0.7 }], bass: null },
    { drums: [{ type: 'hihat', volume: 0.4 }], bass: null },
    { drums: [{ type: 'hihat', volume: 0.4 }], bass: null },
    { drums: [{ type: 'hihat', volume: 0.4 }], bass: null },
  ],
}

// ── Exports ──

export const BACKING_STYLES: StylePattern[] = [
  ROCK,
  JAZZ,
  FUNK,
  BOSSA_NOVA,
  REGGAE,
  WALTZ,
  METRONOME_ONLY,
]

// ── Schedule Engine ──

/**
 * Resolve a bass note type to a MIDI note relative to the chord root.
 */
function resolveBassNote(root: NoteName, type: BassHit['type']): number {
  const rootIdx = CHROMATIC_SCALE.indexOf(root)
  const baseMidi = 36 + rootIdx  // C2 region

  switch (type) {
    case 'root': return baseMidi
    case 'third': return baseMidi + 4  // major third (approximation)
    case 'fifth': return baseMidi + 7
    case 'octave': return baseMidi + 12
    case 'chromatic-up': return baseMidi + 11  // leading tone (semitone below next root)
    case 'chromatic-down': return baseMidi - 1
    default: return baseMidi
  }
}

/**
 * Schedule all drum and bass events for a single beat within a pattern.
 *
 * @param ctx - AudioContext
 * @param style - The active style pattern
 * @param beat - Beat index within the measure (0-based)
 * @param time - AudioContext time for this beat
 * @param secondsPerBeat - Duration of one beat in seconds
 * @param chordRoot - Current chord root note
 * @param drumVol - Master drum volume (0-1)
 * @param bassVol - Master bass volume (0-1)
 */
export function schedulePatternBeat(
  ctx: AudioContext,
  style: StylePattern,
  beat: number,
  time: number,
  secondsPerBeat: number,
  chordRoot: NoteName | null,
  drumVol: number,
  bassVol: number,
): void {
  const subDuration = secondsPerBeat / style.subdivisions

  for (let sub = 0; sub < style.subdivisions; sub++) {
    const idx = (beat % style.beatsPerMeasure) * style.subdivisions + sub
    if (idx >= style.pattern.length) continue

    const subBeat = style.pattern[idx]
    const subTime = time + sub * subDuration

    // Schedule drum hits
    for (const hit of subBeat.drums) {
      const vol = hit.volume * drumVol
      switch (hit.type) {
        case 'kick':
          scheduleKick(ctx, subTime, vol)
          break
        case 'snare':
          scheduleSnare(ctx, subTime, vol)
          break
        case 'hihat':
          scheduleHihat(ctx, subTime, false, vol)
          break
        case 'hihat-open':
          scheduleHihat(ctx, subTime, true, vol)
          break
      }
    }

    // Schedule bass hit
    if (subBeat.bass && chordRoot && bassVol > 0) {
      const midiNote = resolveBassNote(chordRoot, subBeat.bass.type)
      const noteDuration = subBeat.bass.duration * secondsPerBeat
      scheduleBassNote(ctx, midiNote, subTime, noteDuration, subBeat.bass.volume * bassVol)
    }
  }
}
