import { useState, useEffect, useRef, memo } from 'react'

interface TempoTrainerProps {
  currentBpm: number
  setBpm: (bpm: number) => void
  isPlaying: boolean
  currentMeasure: number
}

/**
 * Tempo Trainer — gradually increases BPM over measures.
 * Essential practice technique: start slow, build up speed incrementally.
 */
export const TempoTrainer = memo(function TempoTrainer({
  currentBpm,
  setBpm,
  isPlaying,
  currentMeasure,
}: TempoTrainerProps) {
  const [enabled, setEnabled] = useState(false)
  const [startBpm, setStartBpm] = useState(80)
  const [targetBpm, setTargetBpm] = useState(140)
  const [increment, setIncrement] = useState(5)
  const [everyBars, setEveryBars] = useState(4)

  // Track the measure at which the trainer was activated
  const activationMeasureRef = useRef(0)
  const lastStepRef = useRef(-1)

  // When enabling, set BPM to start value and record activation point
  const handleToggle = () => {
    if (!enabled) {
      setBpm(startBpm)
      activationMeasureRef.current = currentMeasure
      lastStepRef.current = -1
      setEnabled(true)
    } else {
      setEnabled(false)
    }
  }

  // Auto-increase BPM based on measure progress
  useEffect(() => {
    if (!enabled || !isPlaying) return

    const elapsed = currentMeasure - activationMeasureRef.current
    if (elapsed < 0) return

    const step = Math.floor(elapsed / everyBars)
    if (step === lastStepRef.current) return
    lastStepRef.current = step

    const newBpm = Math.min(startBpm + step * increment, targetBpm)
    if (newBpm !== currentBpm) {
      setBpm(newBpm)
    }
  }, [enabled, isPlaying, currentMeasure, startBpm, targetBpm, increment, everyBars, currentBpm, setBpm])

  // Progress percentage
  const range = targetBpm - startBpm
  const progress = range > 0
    ? Math.min(100, ((currentBpm - startBpm) / range) * 100)
    : 100
  const reachedTarget = enabled && currentBpm >= targetBpm

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500">Tempo Trainer</span>
        <button
          onClick={handleToggle}
          className={`px-2 py-0.5 rounded text-xs font-semibold transition-colors border ${
            enabled
              ? 'border-emerald-500/50 bg-emerald-500/20 text-emerald-400'
              : 'border-slate-600 bg-slate-700 text-slate-500 hover:text-slate-300'
          }`}
        >
          {enabled ? 'ON' : 'OFF'}
        </button>
      </div>

      {/* Parameter controls */}
      <div className="grid grid-cols-4 gap-1.5 text-xs">
        <label className="flex flex-col items-center gap-0.5">
          <span className="text-slate-500">Start</span>
          <input
            type="number"
            min={40}
            max={240}
            value={startBpm}
            onChange={(e) => setStartBpm(Math.max(40, Math.min(240, Number(e.target.value))))}
            disabled={enabled}
            className="w-full bg-slate-700 text-slate-300 text-center rounded px-1 py-0.5 outline-none disabled:opacity-50 tabular-nums"
          />
        </label>
        <label className="flex flex-col items-center gap-0.5">
          <span className="text-slate-500">Target</span>
          <input
            type="number"
            min={40}
            max={240}
            value={targetBpm}
            onChange={(e) => setTargetBpm(Math.max(40, Math.min(240, Number(e.target.value))))}
            disabled={enabled}
            className="w-full bg-slate-700 text-slate-300 text-center rounded px-1 py-0.5 outline-none disabled:opacity-50 tabular-nums"
          />
        </label>
        <label className="flex flex-col items-center gap-0.5">
          <span className="text-slate-500">+BPM</span>
          <input
            type="number"
            min={1}
            max={20}
            value={increment}
            onChange={(e) => setIncrement(Math.max(1, Math.min(20, Number(e.target.value))))}
            disabled={enabled}
            className="w-full bg-slate-700 text-slate-300 text-center rounded px-1 py-0.5 outline-none disabled:opacity-50 tabular-nums"
          />
        </label>
        <label className="flex flex-col items-center gap-0.5">
          <span className="text-slate-500">Bars</span>
          <input
            type="number"
            min={1}
            max={16}
            value={everyBars}
            onChange={(e) => setEveryBars(Math.max(1, Math.min(16, Number(e.target.value))))}
            disabled={enabled}
            className="w-full bg-slate-700 text-slate-300 text-center rounded px-1 py-0.5 outline-none disabled:opacity-50 tabular-nums"
          />
        </label>
      </div>

      {/* Progress bar */}
      {enabled && (
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500 tabular-nums w-7">{startBpm}</span>
          <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                reachedTarget ? 'bg-emerald-400' : 'bg-sky-400'
              }`}
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-[10px] text-slate-500 tabular-nums w-7 text-right">{targetBpm}</span>
          {reachedTarget && (
            <span className="text-[10px] text-emerald-400 font-semibold">Done!</span>
          )}
        </div>
      )}
    </div>
  )
})
