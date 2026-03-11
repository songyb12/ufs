import { useState, useCallback, useRef, useEffect } from 'react'

interface ChordTransitionTimerProps {
  /** Currently active chord name (changes trigger new timer) */
  activeChordName?: string
  /** Is metronome playing? */
  isPlaying: boolean
}

interface TransitionRecord {
  fromChord: string
  toChord: string
  timeMs: number
  timestamp: number
}

/**
 * Chord Transition Timer — measures how fast you can switch
 * between chord shapes during practice. Tracks timing from
 * chord change to player confirmation (tap/spacebar).
 */
export function ChordTransitionTimer({
  activeChordName,
  isPlaying,
}: ChordTransitionTimerProps) {
  const [expanded, setExpanded] = useState(false)
  const [active, setActive] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [records, setRecords] = useState<TransitionRecord[]>([])
  const [lastChord, setLastChord] = useState<string | null>(null)

  const timerStart = useRef<number | null>(null)
  const rafRef = useRef<number | null>(null)

  // Animate the timer display
  const updateTimer = useCallback(() => {
    if (timerStart.current !== null) {
      setCurrentTime(performance.now() - timerStart.current)
      rafRef.current = requestAnimationFrame(updateTimer)
    }
  }, [])

  // Start timer when chord changes
  useEffect(() => {
    if (!active || !activeChordName || !isPlaying) return

    if (lastChord && lastChord !== activeChordName) {
      // Chord changed — start the clock
      timerStart.current = performance.now()
      setCurrentTime(0)
      rafRef.current = requestAnimationFrame(updateTimer)
    }

    setLastChord(activeChordName)
  }, [activeChordName, active, isPlaying, lastChord, updateTimer])

  // Cleanup animation frame on unmount
  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [])

  // Stop timer when deactivated
  useEffect(() => {
    if (!active) {
      timerStart.current = null
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [active])

  const handleReady = useCallback(() => {
    if (timerStart.current === null || !lastChord || !activeChordName) return
    const elapsed = performance.now() - timerStart.current

    // Record the transition
    setRecords((prev) => [
      {
        fromChord: lastChord !== activeChordName ? lastChord : '?',
        toChord: activeChordName,
        timeMs: elapsed,
        timestamp: Date.now(),
      },
      ...prev.slice(0, 29), // Keep last 30 records
    ])

    // Stop timer
    timerStart.current = null
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    setCurrentTime(elapsed)
  }, [lastChord, activeChordName])

  const handleStart = useCallback(() => {
    setActive(true)
    setLastChord(activeChordName ?? null)
    timerStart.current = null
    setCurrentTime(0)
  }, [activeChordName])

  const handleStop = useCallback(() => {
    setActive(false)
    timerStart.current = null
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    setCurrentTime(0)
  }, [])

  const formatTime = (ms: number): string => {
    if (ms < 1000) return `${Math.round(ms)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  // Calculate averages
  const avgTime = records.length > 0
    ? records.reduce((sum, r) => sum + r.timeMs, 0) / records.length
    : 0
  const bestTime = records.length > 0
    ? Math.min(...records.map((r) => r.timeMs))
    : 0

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full text-xs text-slate-600 hover:text-slate-400 py-1 transition-colors"
      >
        Chord Transition Timer (measure switch speed)...
      </button>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg px-4 py-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Transition Timer
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={active ? handleStop : handleStart}
            disabled={!active && !isPlaying}
            className={`px-3 py-1 rounded text-xs font-semibold transition-colors ${
              active
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                : isPlaying
                  ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
                  : 'bg-slate-700/50 text-slate-600 cursor-not-allowed'
            }`}
          >
            {active ? 'Stop' : 'Start'}
          </button>
          <button
            onClick={() => { setExpanded(false); handleStop() }}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Collapse
          </button>
        </div>
      </div>

      {active && (
        <>
          {/* Current timer display */}
          <div className="flex items-center justify-center gap-4">
            <div className="text-center">
              <div className={`text-3xl font-bold tabular-nums ${
                timerStart.current !== null
                  ? 'text-amber-400 animate-pulse'
                  : currentTime > 0
                    ? 'text-emerald-400'
                    : 'text-slate-500'
              }`}>
                {formatTime(currentTime)}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                {timerStart.current !== null
                  ? `Switch to ${activeChordName}...`
                  : currentTime > 0
                    ? 'Done!'
                    : 'Waiting for chord change...'}
              </div>
            </div>

            {timerStart.current !== null && (
              <button
                onClick={handleReady}
                className="px-6 py-3 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-bold transition-colors shadow-lg shadow-emerald-500/20"
              >
                ✓ Ready
              </button>
            )}
          </div>

          {/* Stats */}
          {records.length > 0 && (
            <div className="flex items-center justify-center gap-6 text-xs">
              <div className="text-center">
                <span className="text-slate-500">Avg</span>
                <div className="text-slate-300 font-bold">{formatTime(avgTime)}</div>
              </div>
              <div className="text-center">
                <span className="text-slate-500">Best</span>
                <div className="text-cyan-400 font-bold">{formatTime(bestTime)}</div>
              </div>
              <div className="text-center">
                <span className="text-slate-500">Transitions</span>
                <div className="text-slate-300 font-bold">{records.length}</div>
              </div>
            </div>
          )}

          {/* Recent records */}
          {records.length > 0 && (
            <div className="max-h-24 overflow-y-auto">
              <div className="flex flex-col gap-0.5">
                {records.slice(0, 8).map((r, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-slate-500">
                      {r.fromChord} → {r.toChord}
                    </span>
                    <span className={`font-mono tabular-nums ${
                      r.timeMs === bestTime ? 'text-cyan-400 font-bold' : 'text-slate-400'
                    }`}>
                      {formatTime(r.timeMs)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {records.length > 0 && (
            <button
              onClick={() => setRecords([])}
              className="text-[10px] text-slate-600 hover:text-slate-400 text-center"
            >
              Clear history
            </button>
          )}
        </>
      )}

      {!active && !isPlaying && (
        <p className="text-[10px] text-slate-600">
          Start the metronome with a chord progression, then activate the timer.
        </p>
      )}
    </div>
  )
}
