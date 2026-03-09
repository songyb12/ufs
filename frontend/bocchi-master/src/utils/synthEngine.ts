/**
 * Guitar-like synthesis using Web Audio API.
 *
 * Sawtooth oscillator + lowpass filter + exponential decay envelope.
 * Produces a warm, plucked-string tone.
 */

export interface PlayNoteOptions {
  frequency: number    // Hz
  duration?: number    // seconds (default: 1.5)
  gain?: number        // 0-1 (default: 0.4)
  time?: number        // AudioContext.currentTime offset (default: now)
}

/**
 * Convert MIDI note number to frequency.
 * A4 = MIDI 69 = 440 Hz
 */
export function midiNoteToFrequency(midiNote: number): number {
  return 440 * Math.pow(2, (midiNote - 69) / 12)
}

/**
 * Play a single note with guitar-like timbre.
 */
export function playNote(ctx: AudioContext, opts: PlayNoteOptions): void {
  const { frequency, duration = 1.5, gain: vol = 0.4, time } = opts
  const t = time ?? ctx.currentTime

  const osc = ctx.createOscillator()
  const filter = ctx.createBiquadFilter()
  const gainNode = ctx.createGain()

  // Sawtooth wave has rich harmonics (guitar-like overtone series)
  osc.type = 'sawtooth'
  osc.frequency.value = frequency

  // Lowpass filter: cutoff at ~4× fundamental gives warmth
  filter.type = 'lowpass'
  filter.frequency.value = Math.min(frequency * 4, 12000)
  filter.Q.value = 1.0

  // Envelope: instant attack, exponential decay
  gainNode.gain.setValueAtTime(vol, t)
  gainNode.gain.exponentialRampToValueAtTime(0.001, t + duration)

  osc.connect(filter)
  filter.connect(gainNode)
  gainNode.connect(ctx.destination)

  osc.start(t)
  osc.stop(t + duration)
}

/**
 * Play a chord with strum effect (notes spaced by strumDelay).
 * Notes are played low to high.
 */
export function playChord(
  ctx: AudioContext,
  midiNotes: number[],
  strumDelayMs = 30,
): void {
  const now = ctx.currentTime
  midiNotes.forEach((midi, i) => {
    playNote(ctx, {
      frequency: midiNoteToFrequency(midi),
      time: now + (i * strumDelayMs) / 1000,
      gain: 0.25,
      duration: 2.0,
    })
  })
}
