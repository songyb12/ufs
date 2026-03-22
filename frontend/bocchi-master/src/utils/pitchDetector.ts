/**
 * Pitch detection using the YIN autocorrelation algorithm.
 *
 * YIN is well-suited for monophonic pitch detection of guitar/bass strings.
 * Reference: De Cheveigné & Kawahara (2002), "YIN, a fundamental frequency
 * estimator for speech and music."
 */

const YIN_THRESHOLD = 0.15
const YIN_PROBABILITY_THRESHOLD = 0.3

/**
 * Detect fundamental frequency from a time-domain audio buffer.
 *
 * @param buffer Float32Array of audio samples (from AnalyserNode.getFloatTimeDomainData)
 * @param sampleRate AudioContext sample rate (e.g. 48000)
 * @returns Detected frequency in Hz, or null if no clear pitch found
 */
export function detectPitch(buffer: Float32Array, sampleRate: number): number | null {
  const halfLen = Math.floor(buffer.length / 2)

  // Step 1: Compute difference function d(tau)
  const yinBuffer = new Float32Array(halfLen)
  for (let tau = 0; tau < halfLen; tau++) {
    let sum = 0
    for (let i = 0; i < halfLen; i++) {
      const delta = buffer[i] - buffer[i + tau]
      sum += delta * delta
    }
    yinBuffer[tau] = sum
  }

  // Step 2: Cumulative mean normalized difference function d'(tau)
  yinBuffer[0] = 1
  let runningSum = 0
  for (let tau = 1; tau < halfLen; tau++) {
    runningSum += yinBuffer[tau]
    yinBuffer[tau] *= tau / runningSum
  }

  // Step 3: Absolute threshold — find first tau where d'(tau) < threshold
  let tauEstimate = -1
  for (let tau = 2; tau < halfLen; tau++) {
    if (yinBuffer[tau] < YIN_THRESHOLD) {
      // Walk to the local minimum
      while (tau + 1 < halfLen && yinBuffer[tau + 1] < yinBuffer[tau]) {
        tau++
      }
      tauEstimate = tau
      break
    }
  }

  if (tauEstimate === -1) return null

  // Check confidence
  if (yinBuffer[tauEstimate] >= YIN_PROBABILITY_THRESHOLD) return null

  // Step 4: Parabolic interpolation for sub-sample accuracy
  const s0 = tauEstimate > 0 ? yinBuffer[tauEstimate - 1] : yinBuffer[tauEstimate]
  const s1 = yinBuffer[tauEstimate]
  const s2 = tauEstimate + 1 < halfLen ? yinBuffer[tauEstimate + 1] : yinBuffer[tauEstimate]

  let betterTau = tauEstimate
  const denominator = 2 * s1 - s2 - s0
  if (denominator !== 0) {
    betterTau = tauEstimate + (s0 - s2) / (2 * denominator)
  }

  return sampleRate / betterTau
}

/**
 * Convert frequency to the nearest MIDI note number + cents offset.
 *
 * @returns { midi, cents } where cents is -50..+50
 */
export function frequencyToNote(freq: number): { midi: number; cents: number } {
  const midiFloat = 12 * Math.log2(freq / 440) + 69
  const midi = Math.round(midiFloat)
  const cents = Math.round((midiFloat - midi) * 100)
  return { midi, cents }
}

/**
 * Convert MIDI note number to frequency.
 */
export function midiToFrequency(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12)
}
