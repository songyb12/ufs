import { useRef, useCallback, useState } from 'react'

interface TapTempoProps {
  onTempoDetected: (bpm: number) => void
}

const MAX_TAP_GAP_MS = 2000
const TAP_HISTORY_SIZE = 4

export function TapTempo({ onTempoDetected }: TapTempoProps) {
  const tapsRef = useRef<number[]>([])
  const [tapCount, setTapCount] = useState(0)

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

    setTapCount(taps.length)

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
      className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
        tapCount >= 2
          ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
          : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
      }`}
    >
      TAP{tapCount >= 2 ? ` (${tapCount})` : ''}
    </button>
  )
}

/** Quick-access buttons for common practice tempos */
const QUICK_TEMPOS = [60, 80, 100, 120, 140, 160, 200]

export function QuickTempos({ currentBpm, onSelect }: { currentBpm: number; onSelect: (bpm: number) => void }) {
  return (
    <div className="flex items-center gap-1">
      {QUICK_TEMPOS.map((t) => (
        <button
          key={t}
          onClick={() => onSelect(t)}
          className={`px-1.5 py-0.5 rounded text-[10px] font-medium tabular-nums transition-colors ${
            currentBpm === t
              ? 'bg-sky-500/20 text-sky-400 ring-1 ring-sky-500/40'
              : 'bg-slate-700/50 text-slate-600 hover:text-slate-400'
          }`}
        >
          {t}
        </button>
      ))}
    </div>
  )
}
