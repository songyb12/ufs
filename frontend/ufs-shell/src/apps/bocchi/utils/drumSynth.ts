/**
 * Drum Synthesis — all sounds are synthesized via Web Audio API.
 * No samples needed. Scheduled with precise AudioContext time.
 */

// Shared noise buffer (cached)
let noiseBuffer: AudioBuffer | null = null

function getNoiseBuffer(ctx: AudioContext): AudioBuffer {
  if (noiseBuffer && noiseBuffer.sampleRate === ctx.sampleRate) return noiseBuffer
  const size = ctx.sampleRate * 2 // 2 seconds
  const buffer = ctx.createBuffer(1, size, ctx.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < size; i++) {
    data[i] = Math.random() * 2 - 1
  }
  noiseBuffer = buffer
  return buffer
}

/**
 * Kick: 150→50Hz pitch drop + exponential decay
 */
export function scheduleKick(ctx: AudioContext, time: number, volume = 0.7): void {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)

  osc.frequency.setValueAtTime(150, time)
  osc.frequency.exponentialRampToValueAtTime(50, time + 0.08)
  gain.gain.setValueAtTime(volume, time)
  gain.gain.exponentialRampToValueAtTime(0.001, time + 0.4)

  osc.start(time)
  osc.stop(time + 0.4)
}

/**
 * Snare: white noise + bandpass + quick decay
 */
export function scheduleSnare(ctx: AudioContext, time: number, volume = 0.5): void {
  const noise = ctx.createBufferSource()
  noise.buffer = getNoiseBuffer(ctx)
  const filter = ctx.createBiquadFilter()
  filter.type = 'bandpass'
  filter.frequency.value = 2000
  filter.Q.value = 0.5
  const gain = ctx.createGain()
  noise.connect(filter)
  filter.connect(gain)
  gain.connect(ctx.destination)

  gain.gain.setValueAtTime(volume, time)
  gain.gain.exponentialRampToValueAtTime(0.001, time + 0.15)

  // Add tonal body
  const osc = ctx.createOscillator()
  const oscGain = ctx.createGain()
  osc.connect(oscGain)
  oscGain.connect(ctx.destination)
  osc.frequency.value = 200
  oscGain.gain.setValueAtTime(volume * 0.4, time)
  oscGain.gain.exponentialRampToValueAtTime(0.001, time + 0.08)
  osc.start(time)
  osc.stop(time + 0.08)

  noise.start(time)
  noise.stop(time + 0.15)
}

/**
 * Hihat: white noise + highpass (closed=short, open=longer)
 */
export function scheduleHihat(ctx: AudioContext, time: number, open = false, volume = 0.3): void {
  const noise = ctx.createBufferSource()
  noise.buffer = getNoiseBuffer(ctx)
  const filter = ctx.createBiquadFilter()
  filter.type = 'highpass'
  filter.frequency.value = 8000
  const gain = ctx.createGain()
  noise.connect(filter)
  filter.connect(gain)
  gain.connect(ctx.destination)

  const duration = open ? 0.25 : 0.05
  gain.gain.setValueAtTime(volume, time)
  gain.gain.exponentialRampToValueAtTime(0.001, time + duration)

  noise.start(time)
  noise.stop(time + duration)
}

/**
 * Bass: triangle oscillator at given MIDI note
 */
export function scheduleBassNote(
  ctx: AudioContext,
  midiNote: number,
  time: number,
  duration: number,
  volume = 0.5,
): void {
  const freq = 440 * Math.pow(2, (midiNote - 69) / 12)
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = 'triangle'
  osc.frequency.value = freq
  osc.connect(gain)
  gain.connect(ctx.destination)

  gain.gain.setValueAtTime(volume, time)
  gain.gain.setValueAtTime(volume, time + duration * 0.8)
  gain.gain.exponentialRampToValueAtTime(0.001, time + duration)

  osc.start(time)
  osc.stop(time + duration)
}
