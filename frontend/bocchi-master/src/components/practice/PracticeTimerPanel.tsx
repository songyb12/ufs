import { useState, useRef, useCallback, useEffect } from 'react'

interface PracticeTimerPanelProps {
  /** Whether any practice activity is happening (metronome, practice mode, etc.) */
  isActive: boolean
}

type TimerMode = 'stopwatch' | 'countdown'

const PRESETS_MINUTES = [5, 10, 15, 20, 30]

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

/**
 * Practice session timer. Two modes:
 * - Stopwatch: tracks elapsed time
 * - Countdown: counts down from a set duration, chimes when done
 */
export function PracticeTimerPanel({ isActive }: PracticeTimerPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const [mode, setMode] = useState<TimerMode>('stopwatch')
  const [running, setRunning] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [goalMinutes, setGoalMinutes] = useState(10)
  const [completed, setCompleted] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Session history (in-memory, current session only)
  const [sessions, setSessions] = useState<{ duration: number; timestamp: number }[]>([])

  const totalGoalSeconds = goalMinutes * 60

  const startTimer = useCallback(() => {
    setRunning(true)
    setCompleted(false)
  }, [])

  const pauseTimer = useCallback(() => {
    setRunning(false)
  }, [])

  const resetTimer = useCallback(() => {
    if (elapsedSeconds > 10) {
      // Save session before reset
      setSessions((prev) => [
        { duration: elapsedSeconds, timestamp: Date.now() },
        ...prev.slice(0, 9), // keep last 10
      ])
    }
    setRunning(false)
    setElapsedSeconds(0)
    setCompleted(false)
  }, [elapsedSeconds])

  // Tick every second when running
  useEffect(() => {
    if (running) {
      intervalRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1)
      }, 1000)
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [running])

  // Check countdown completion
  useEffect(() => {
    if (mode === 'countdown' && running && elapsedSeconds >= totalGoalSeconds) {
      setRunning(false)
      setCompleted(true)
      // Play a completion chime via AudioContext
      try {
        const ctx = new AudioContext()
        const playTone = (freq: number, delay: number) => {
          const osc = ctx.createOscillator()
          const gain = ctx.createGain()
          osc.connect(gain)
          gain.connect(ctx.destination)
          osc.frequency.value = freq
          osc.type = 'sine'
          gain.gain.setValueAtTime(0.4, ctx.currentTime + delay)
          gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.5)
          osc.start(ctx.currentTime + delay)
          osc.stop(ctx.currentTime + delay + 0.5)
        }
        // Three-note ascending chime
        playTone(523, 0)    // C5
        playTone(659, 0.2)  // E5
        playTone(784, 0.4)  // G5
      } catch { /* ignore audio errors */ }
    }
  }, [elapsedSeconds, mode, running, totalGoalSeconds])

  // Auto-start when external activity begins
  useEffect(() => {
    if (isActive && !running && elapsedSeconds === 0 && expanded) {
      startTimer()
    }
  }, [isActive]) // eslint-disable-line react-hooks/exhaustive-deps

  const displaySeconds = mode === 'countdown'
    ? Math.max(0, totalGoalSeconds - elapsedSeconds)
    : elapsedSeconds

  const progressPct = mode === 'countdown'
    ? Math.min(100, (elapsedSeconds / totalGoalSeconds) * 100)
    : 0

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full text-xs text-slate-600 hover:text-slate-400 py-1 transition-colors"
      >
        Practice Timer (timed sessions)...
      </button>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg px-4 py-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Practice Timer
        </h2>
        <div className="flex items-center gap-2">
          {elapsedSeconds > 0 && (
            <button
              onClick={resetTimer}
              className="text-xs text-slate-500 hover:text-slate-300"
            >
              Reset
            </button>
          )}
          <button
            onClick={() => setExpanded(false)}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Collapse
          </button>
        </div>
      </div>

      {/* Mode selector */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-500">Mode:</span>
        {(['stopwatch', 'countdown'] as const).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); resetTimer() }}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              mode === m
                ? 'bg-rose-500/20 text-rose-400 ring-1 ring-rose-500/40'
                : 'bg-slate-700 text-slate-500 hover:text-slate-300'
            }`}
          >
            {m === 'stopwatch' ? 'Stopwatch' : 'Countdown'}
          </button>
        ))}
      </div>

      {/* Goal duration (countdown mode only) */}
      {mode === 'countdown' && !running && elapsedSeconds === 0 && (
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-500">Goal:</span>
          {PRESETS_MINUTES.map((min) => (
            <button
              key={min}
              onClick={() => setGoalMinutes(min)}
              className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                goalMinutes === min
                  ? 'bg-rose-500/20 text-rose-400 ring-1 ring-rose-500/40'
                  : 'bg-slate-700 text-slate-500 hover:text-slate-300'
              }`}
            >
              {min}m
            </button>
          ))}
        </div>
      )}

      {/* Timer display */}
      <div className="flex items-center justify-center gap-4 py-1">
        <div
          className={`text-4xl font-bold tabular-nums font-mono ${
            completed
              ? 'text-emerald-400'
              : running
                ? 'text-white'
                : 'text-slate-400'
          }`}
        >
          {formatTime(displaySeconds)}
        </div>
        <button
          onClick={running ? pauseTimer : startTimer}
          disabled={completed && mode === 'countdown'}
          className={`w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold transition-colors ${
            running
              ? 'bg-rose-500 hover:bg-rose-600 text-white'
              : completed
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
          }`}
          aria-label={running ? 'Pause timer' : 'Start timer'}
        >
          {completed ? '✓' : running ? '⏸' : '▶'}
        </button>
      </div>

      {/* Progress bar (countdown mode) */}
      {mode === 'countdown' && (
        <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ${
              completed ? 'bg-emerald-400' : 'bg-rose-400'
            }`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      )}

      {completed && (
        <div className="text-center text-xs text-emerald-400 font-semibold">
          Session complete! {goalMinutes} minutes practiced.
        </div>
      )}

      {/* Recent sessions */}
      {sessions.length > 0 && (
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider">Recent Sessions</span>
          {sessions.map((s, i) => (
            <div key={s.timestamp} className="flex items-center justify-between text-[10px]">
              <span className="text-slate-500">
                {new Date(s.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
              <span className="text-slate-400 font-mono">
                {formatTime(s.duration)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
