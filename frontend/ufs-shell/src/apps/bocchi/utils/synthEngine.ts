/**
 * Guitar-like synthesis using Web Audio API.
 *
 * Two detuned sawtooth oscillators + lowpass filter + pluck noise burst
 * + exponential decay envelope. Produces a warm, plucked-string tone
 * with natural-sounding chorus width.
 */

export interface PlayNoteOptions {
  frequency: number    // Hz
  duration?: number    // seconds (default: 1.5)
  gain?: number        // 0-1 (default: 0.4)
  time?: number        // AudioContext.currentTime offset (default: now)
  /** Whether to add pluck attack transient (default: true) */
  pluckAttack?: boolean
}

/**
 * Convert MIDI note number to frequency.
 * A4 = MIDI 69 = 440 Hz
 */
export function midiNoteToFrequency(midiNote: number): number {
  return 440 * Math.pow(2, (midiNote - 69) / 12)
}

/**
 * Play a single note with enhanced guitar-like timbre.
 * Uses dual oscillators with slight detune for chorus width,
 * lowpass filter for warmth, and optional pluck attack noise.
 */
export function playNote(ctx: AudioContext, opts: PlayNoteOptions): void {
  const { frequency, duration = 1.5, gain: vol = 0.4, time, pluckAttack = true } = opts
  const t = time ?? ctx.currentTime

  const gainNode = ctx.createGain()
  const filter = ctx.createBiquadFilter()

  // Lowpass filter: cutoff decays from bright to warm (mimics string decay)
  filter.type = 'lowpass'
  filter.frequency.setValueAtTime(Math.min(frequency * 6, 14000), t)
  filter.frequency.exponentialRampToValueAtTime(Math.min(frequency * 2, 4000), t + duration * 0.6)
  filter.Q.value = 0.8

  // Dual oscillators with ±3 cent detune for natural chorus
  const osc1 = ctx.createOscillator()
  const osc2 = ctx.createOscillator()
  osc1.type = 'sawtooth'
  osc2.type = 'sawtooth'
  osc1.frequency.value = frequency
  osc2.frequency.value = frequency * Math.pow(2, 3 / 1200) // +3 cents

  const mixGain1 = ctx.createGain()
  const mixGain2 = ctx.createGain()
  mixGain1.gain.value = 0.55
  mixGain2.gain.value = 0.45

  osc1.connect(mixGain1)
  osc2.connect(mixGain2)
  mixGain1.connect(filter)
  mixGain2.connect(filter)

  // Envelope: fast attack, exponential decay
  gainNode.gain.setValueAtTime(vol, t)
  gainNode.gain.exponentialRampToValueAtTime(vol * 0.5, t + 0.01)
  gainNode.gain.exponentialRampToValueAtTime(0.001, t + duration)

  filter.connect(gainNode)
  gainNode.connect(ctx.destination)

  osc1.start(t)
  osc2.start(t)
  osc1.stop(t + duration)
  osc2.stop(t + duration)

  // Pluck attack: brief noise burst simulating pick/finger striking string
  if (pluckAttack) {
    const bufferSize = Math.floor(ctx.sampleRate * 0.015) // 15ms
    const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate)
    const data = noiseBuffer.getChannelData(0)
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize) // decaying noise
    }
    const noiseSrc = ctx.createBufferSource()
    noiseSrc.buffer = noiseBuffer
    const noiseGain = ctx.createGain()
    noiseGain.gain.setValueAtTime(vol * 0.3, t)
    noiseGain.gain.exponentialRampToValueAtTime(0.001, t + 0.015)
    const noiseFilter = ctx.createBiquadFilter()
    noiseFilter.type = 'bandpass'
    noiseFilter.frequency.value = frequency * 3
    noiseFilter.Q.value = 0.5

    noiseSrc.connect(noiseFilter)
    noiseFilter.connect(noiseGain)
    noiseGain.connect(ctx.destination)
    noiseSrc.start(t)
    noiseSrc.stop(t + 0.02)
  }
}

/** Chord play mode */
export type ChordPlayMode = 'strum' | 'arpeggiate' | 'simultaneous'

/**
 * Play a chord with configurable strumming style.
 * - strum: quick down-strum with short delay between notes (default)
 * - arpeggiate: slower arpeggio for musical effect
 * - simultaneous: all notes at once (power chord feel)
 */
export function playChord(
  ctx: AudioContext,
  midiNotes: number[],
  mode: ChordPlayMode = 'strum',
): void {
  const now = ctx.currentTime
  const delays: Record<ChordPlayMode, number> = {
    strum: 30,       // ms between notes (fast strum)
    arpeggiate: 100,  // ms between notes (audible arpeggio)
    simultaneous: 0,  // all at once
  }
  const delayMs = delays[mode]

  midiNotes.forEach((midi, i) => {
    playNote(ctx, {
      frequency: midiNoteToFrequency(midi),
      time: now + (i * delayMs) / 1000,
      gain: 0.22,
      duration: mode === 'arpeggiate' ? 2.5 : 2.0,
      pluckAttack: mode !== 'simultaneous',
    })
  })
}
