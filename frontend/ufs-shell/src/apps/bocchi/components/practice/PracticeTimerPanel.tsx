import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import { loadDailyGoal, saveDailyGoal, addDailyPracticeTime } from '../../utils/storage'

interface PracticeTimerPanelProps {
  /** Whether any practice activity is happening (metronome, practice mode, etc.) */
  isActive: boolean
}

type TimerMode = 'stopwatch' | 'countdown'

const PRESETS_MINUTES = [5, 10, 15, 20, 30]
const DAILY_GOAL_PRESETS = [15, 30, 45, 60, 90]

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

/**
 * Practice session timer with daily goal tracking.
 * - Stopwatch: tracks elapsed time
 * - Countdown: counts down from a set duration, chimes when done
 * - Daily Goal: persistent progress bar toward daily practice target
 */
export function PracticeTimerPanel({ isActive }: PracticeTimerPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const [mode, setMode] = useState<TimerMode>('stopwatch')
  const [running, setRunning] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [goalMinutes, setGoalMinutes] = useState(10)
  const [completed, setCompleted] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const lastSavedRef = useRef(0) // tracks last saved elapsed to compute delta

  // Daily goal state
  const [dailyGoal, setDailyGoal] = useState(() => loadDailyGoal())
  const today = useMemo(() => new Date().toISOString().slice(0, 10), [])
  const todaySeconds = dailyGoal.dailyLog[today] ?? 0
  const dailyTargetSeconds = dailyGoal.targetMinutes * 60
  const dailyPct = dailyTargetSeconds > 0 ? Math.min(100, (todaySeconds / dailyTargetSeconds) * 100) : 0
  const dailyGoalMet = todaySeconds >= dailyTargetSeconds

  // Session history (in-memory, current session only)
  const [sessions, setSessions] = useState<{ duration: number; timestamp: number }[]>([])

  const totalGoalSeconds = goalMinutes * 60

  // Save elapsed time to daily log periodically (every 30s) and on pause/reset
  const flushToDailyLog = useCallback(() => {
    const delta = elapsedSeconds - lastSavedRef.current
    if (delta > 0) {
      addDailyPracticeTime(delta)
      lastSavedRef.current = elapsedSeconds
      setDailyGoal(loadDailyGoal())
    }
  }, [elapsedSeconds])

  const startTimer = useCallback(() => {
    setRunning(true)
    setCompleted(false)
  }, [])

  const pauseTimer = useCallback(() => {
    setRunning(false)
    flushToDailyLog()
  }, [flushToDailyLog])

  const resetTimer = useCallback(() => {
    flushToDailyLog()
    if (elapsedSeconds > 10) {
      setSessions((prev) => [
        { duration: elapsedSeconds, timestamp: Date.now() },
        ...prev.slice(0, 9),
      ])
    }
    setRunning(false)
    setElapsedSeconds(0)
    lastSavedRef.current = 0
    setCompleted(false)
  }, [elapsedSeconds, flushToDailyLog])

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

  // Auto-flush to daily log every 30 seconds while running
  useEffect(() => {
    if (running && elapsedSeconds > 0 && elapsedSeconds % 30 === 0) {
      flushToDailyLog()
    }
  }, [running, elapsedSeconds, flushToDailyLog])

  // Check countdown completion
  useEffect(() => {
    if (mode === 'countdown' && running && elapsedSeconds >= totalGoalSeconds) {
      setRunning(false)
      setCompleted(true)
      flushToDailyLog()
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
        playTone(523, 0)
        playTone(659, 0.2)
        playTone(784, 0.4)
      } catch { /* ignore audio errors */ }
    }
  }, [elapsedSeconds, mode, running, totalGoalSeconds, flushToDailyLog])

  // Auto-start when external activity begins
  useEffect(() => {
    if (isActive && !running && elapsedSeconds === 0 && expanded) {
      startTimer()
    }
  }, [isActive]) // eslint-disable-line react-hooks/exhaustive-deps

  // Flush on unmount
  useEffect(() => () => {
    const delta = elapsedSeconds - lastSavedRef.current
    if (delta > 0) addDailyPracticeTime(delta)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const displaySeconds = mode === 'countdown'
    ? Math.max(0, totalGoalSeconds - elapsedSeconds)
    : elapsedSeconds

  const progressPct = mode === 'countdown'
    ? Math.min(100, (elapsedSeconds / totalGoalSeconds) * 100)
    : 0

  // Update daily goal target
  const setDailyTarget = useCallback((minutes: number) => {
    const goal = loadDailyGoal()
    goal.targetMinutes = minutes
    saveDailyGoal(goal)
    setDailyGoal(goal)
  }, [])

  // Weekly streak (consecutive days with goal met)
  const weekStreak = useMemo(() => {
    let streak = 0
    const d = new Date()
    // Start from yesterday (today may not be complete yet)
    d.setDate(d.getDate() - 1)
    for (let i = 0; i < 30; i++) {
      const dateStr = d.toISOString().slice(0, 10)
      const secs = dailyGoal.dailyLog[dateStr] ?? 0
      if (secs >= dailyTargetSeconds) {
        streak++
        d.setDate(d.getDate() - 1)
      } else {
        break
      }
    }
    // Add today if goal already met
    if (dailyGoalMet) streak++
    return streak
  }, [dailyGoal.dailyLog, dailyTargetSeconds, dailyGoalMet])

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
            onClick={() => { if (running) flushToDailyLog(); setExpanded(false) }}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Collapse
          </button>
        </div>
      </div>

      {/* Daily Goal Progress */}
      <div className="bg-slate-900/50 rounded-lg px-3 py-2 flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider">
            Daily Goal
          </span>
          <div className="flex items-center gap-1">
            {weekStreak > 0 && (
              <span className="text-[10px] text-orange-400 font-semibold">
                {weekStreak}d streak
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                dailyGoalMet ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
              style={{ width: `${dailyPct}%` }}
            />
          </div>
          <span className={`text-[10px] font-semibold tabular-nums ${
            dailyGoalMet ? 'text-emerald-400' : 'text-slate-400'
          }`}>
            {Math.floor(todaySeconds / 60)}/{dailyGoal.targetMinutes}m
          </span>
        </div>
        {/* Daily target presets */}
        <div className="flex items-center gap-1">
          <span className="text-[9px] text-slate-600">Target:</span>
          {DAILY_GOAL_PRESETS.map((m) => (
            <button
              key={m}
              onClick={() => setDailyTarget(m)}
              className={`px-1.5 py-0.5 rounded text-[9px] font-medium transition-colors ${
                dailyGoal.targetMinutes === m
                  ? 'bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/40'
                  : 'bg-slate-700/50 text-slate-600 hover:text-slate-400'
              }`}
            >
              {m}m
            </button>
          ))}
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
          <span className="text-xs text-slate-500">Session:</span>
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
          {sessions.map((s) => (
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
