import { useState, useCallback, useRef, useEffect } from 'react'

interface TempoTrainerPanelProps {
  currentBpm: number
  isPlaying: boolean
  currentMeasure: number
  onBpmChange: (bpm: number) => void
}

interface TempoGoal {
  startBpm: number
  targetBpm: number
  /** Increase every N measures */
  measuresPerStep: number
  /** BPM increase per step */
  bpmPerStep: number
}

const PRESETS: { label: string; goal: TempoGoal }[] = [
  {
    label: 'Slow Build (5 BPM / 8 bars)',
    goal: { startBpm: 60, targetBpm: 120, measuresPerStep: 8, bpmPerStep: 5 },
  },
  {
    label: 'Medium Build (5 BPM / 4 bars)',
    goal: { startBpm: 80, targetBpm: 140, measuresPerStep: 4, bpmPerStep: 5 },
  },
  {
    label: 'Fast Ladder (10 BPM / 4 bars)',
    goal: { startBpm: 100, targetBpm: 200, measuresPerStep: 4, bpmPerStep: 10 },
  },
  {
    label: 'Fine Grain (1 BPM / 2 bars)',
    goal: { startBpm: 80, targetBpm: 100, measuresPerStep: 2, bpmPerStep: 1 },
  },
]

/**
 * Dynamic Tempo Trainer — automatically increases BPM during practice.
 * Start slow, build speed systematically over measured intervals.
 */
export function TempoTrainerPanel({
  currentBpm,
  isPlaying,
  currentMeasure,
  onBpmChange,
}: TempoTrainerPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const [active, setActive] = useState(false)
  const [goal, setGoal] = useState<TempoGoal>(PRESETS[0].goal)
  const [reachedTarget, setReachedTarget] = useState(false)

  // Custom controls
  const [customStart, setCustomStart] = useState(goal.startBpm)
  const [customTarget, setCustomTarget] = useState(goal.targetBpm)
  const [customMeasures, setCustomMeasures] = useState(goal.measuresPerStep)
  const [customStep, setCustomStep] = useState(goal.bpmPerStep)

  // Track the last measure we applied a tempo increase
  const lastStepMeasureRef = useRef(-1)

  const handleStart = useCallback(() => {
    const g: TempoGoal = {
      startBpm: customStart,
      targetBpm: customTarget,
      measuresPerStep: customMeasures,
      bpmPerStep: customStep,
    }
    setGoal(g)
    setActive(true)
    setReachedTarget(false)
    lastStepMeasureRef.current = -1
    onBpmChange(g.startBpm)
  }, [customStart, customTarget, customMeasures, customStep, onBpmChange])

  const handleStop = useCallback(() => {
    setActive(false)
    setReachedTarget(false)
    lastStepMeasureRef.current = -1
  }, [])

  const applyPreset = useCallback((g: TempoGoal) => {
    setCustomStart(g.startBpm)
    setCustomTarget(g.targetBpm)
    setCustomMeasures(g.measuresPerStep)
    setCustomStep(g.bpmPerStep)
  }, [])

  // Auto-increase BPM based on measure count
  useEffect(() => {
    if (!active || !isPlaying || reachedTarget) return

    // Which step are we on?
    const stepNumber = Math.floor(currentMeasure / goal.measuresPerStep)

    if (stepNumber > lastStepMeasureRef.current) {
      lastStepMeasureRef.current = stepNumber
      const newBpm = goal.startBpm + stepNumber * goal.bpmPerStep

      if (newBpm >= goal.targetBpm) {
        onBpmChange(goal.targetBpm)
        setReachedTarget(true)
      } else {
        onBpmChange(newBpm)
      }
    }
  }, [active, isPlaying, currentMeasure, goal, reachedTarget, onBpmChange])

  // Stop trainer when metronome stops
  useEffect(() => {
    if (!isPlaying && active) {
      handleStop()
    }
  }, [isPlaying]) // eslint-disable-line react-hooks/exhaustive-deps

  // Progress calculation
  const progress = active
    ? Math.min(100, ((currentBpm - goal.startBpm) / Math.max(1, goal.targetBpm - goal.startBpm)) * 100)
    : 0

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full text-xs text-slate-600 hover:text-slate-400 py-1 transition-colors"
      >
        Tempo Trainer (gradual BPM increase)...
      </button>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg px-4 py-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Tempo Trainer
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

      {/* Preset buttons */}
      {!active && (
        <div className="flex gap-1 flex-wrap">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              onClick={() => applyPreset(p.goal)}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                customStart === p.goal.startBpm &&
                customTarget === p.goal.targetBpm &&
                customMeasures === p.goal.measuresPerStep &&
                customStep === p.goal.bpmPerStep
                  ? 'bg-cyan-500/20 text-cyan-400 ring-1 ring-cyan-500/40'
                  : 'bg-slate-700 text-slate-500 hover:text-slate-300'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      )}

      {/* Custom config */}
      {!active && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <label className="flex items-center gap-1">
            <span className="text-slate-500 w-12">Start:</span>
            <input
              type="number"
              min={40}
              max={200}
              value={customStart}
              onChange={(e) => setCustomStart(Number(e.target.value))}
              className="w-16 bg-slate-700 text-slate-300 rounded px-1.5 py-0.5 outline-none"
            />
            <span className="text-slate-600">BPM</span>
          </label>
          <label className="flex items-center gap-1">
            <span className="text-slate-500 w-12">Target:</span>
            <input
              type="number"
              min={customStart + 1}
              max={240}
              value={customTarget}
              onChange={(e) => setCustomTarget(Number(e.target.value))}
              className="w-16 bg-slate-700 text-slate-300 rounded px-1.5 py-0.5 outline-none"
            />
            <span className="text-slate-600">BPM</span>
          </label>
          <label className="flex items-center gap-1">
            <span className="text-slate-500 w-12">Every:</span>
            <input
              type="number"
              min={1}
              max={32}
              value={customMeasures}
              onChange={(e) => setCustomMeasures(Number(e.target.value))}
              className="w-16 bg-slate-700 text-slate-300 rounded px-1.5 py-0.5 outline-none"
            />
            <span className="text-slate-600">bars</span>
          </label>
          <label className="flex items-center gap-1">
            <span className="text-slate-500 w-12">+Step:</span>
            <input
              type="number"
              min={1}
              max={20}
              value={customStep}
              onChange={(e) => setCustomStep(Number(e.target.value))}
              className="w-16 bg-slate-700 text-slate-300 rounded px-1.5 py-0.5 outline-none"
            />
            <span className="text-slate-600">BPM</span>
          </label>
        </div>
      )}

      {/* Active display */}
      {active && (
        <>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">
              {goal.startBpm} → <span className="text-cyan-400 font-bold">{currentBpm}</span> → {goal.targetBpm} BPM
            </span>
            <span className="text-slate-500">
              +{goal.bpmPerStep} every {goal.measuresPerStep} bars
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                reachedTarget ? 'bg-emerald-400' : 'bg-cyan-400'
              }`}
              style={{ width: `${progress}%` }}
            />
          </div>

          {reachedTarget && (
            <div className="text-center text-xs text-emerald-400 font-semibold">
              Target reached! {goal.targetBpm} BPM
            </div>
          )}
        </>
      )}

      {!active && !isPlaying && (
        <p className="text-[10px] text-slate-600">
          Start the metronome first, then activate the tempo trainer.
        </p>
      )}
    </div>
  )
}
