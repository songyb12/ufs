import { useRef, useCallback } from 'react'

interface TapTempoProps {
  onTempoDetected: (bpm: number) => void
}

const MAX_TAP_GAP_MS = 2000
const TAP_HISTORY_SIZE = 4

export function TapTempo({ onTempoDetected }: TapTempoProps) {
  const tapsRef = useRef<number[]>([])

  const handleTap = useCallback(() => {
    const now = performance.now()
    const taps = tapsRef.current

    // Reset if too long since last tap
    if (taps.length > 0 && now - taps[taps.length - 1] > MAX_TAP_GAP_MS) {
      taps.length = 0
    }

    taps.push(now)

    // Keep only the last N taps
    if (taps.length > TAP_HISTORY_SIZE) {
      taps.shift()
    }

    // Need at least 2 taps to calculate BPM
    if (taps.length >= 2) {
      const intervals: number[] = []
      for (let i = 1; i < taps.length; i++) {
        intervals.push(taps[i] - taps[i - 1])
      }
      const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length
      const detectedBpm = Math.round(60000 / avgInterval)
      onTempoDetected(detectedBpm)
    }
  }, [onTempoDetected])

  return (
    <button
      onClick={handleTap}
      className="px-4 py-2 rounded bg-slate-700 hover:bg-slate-600 text-sm text-slate-300 font-medium transition-colors"
    >
      TAP
    </button>
  )
}
