import { memo } from 'react'
import {
  INTERVAL_SETS,
  INTERVAL_SHORT,
  INTERVAL_NAMES,
  type IntervalDirection,
  type IntervalQuestion,
  type IntervalStats,
} from '../../utils/intervalTrainer'

interface IntervalTrainerPanelProps {
  active: boolean
  question: IntervalQuestion | null
  stats: IntervalStats
  setIndex: number
  direction: IntervalDirection
  lastAnswer: { semitones: number; correct: boolean } | null
  revealed: boolean
  onStart: () => void
  onStop: () => void
  onSetChange: (idx: number) => void
  onDirectionChange: (d: IntervalDirection) => void
  onAnswer: (semitones: number) => void
  onReplay: () => void
  onNext: () => void
  onReset: () => void
}

export const IntervalTrainerPanel = memo(function IntervalTrainerPanel({
  active,
  question,
  stats,
  setIndex,
  direction,
  lastAnswer,
  revealed,
  onStart,
  onStop,
  onSetChange,
  onDirectionChange,
  onAnswer,
  onReplay,
  onNext,
  onReset,
}: IntervalTrainerPanelProps) {
  const currentSet = INTERVAL_SETS[setIndex]

  return (
    <div className="bg-slate-800 rounded-lg p-4 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          🎵 Interval Trainer
        </h2>
        <button
          onClick={active ? onStop : onStart}
          className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
            active
              ? 'bg-purple-500/20 text-purple-400 ring-1 ring-purple-500/40'
              : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
          }`}
        >
          {active ? 'Stop' : 'Start'}
        </button>
      </div>

      {/* Settings (visible when not active) */}
      {!active && (
        <div className="flex flex-col gap-2">
          {/* Difficulty */}
          <div className="flex gap-1.5 flex-wrap">
            {INTERVAL_SETS.map((set, idx) => (
              <button
                key={set.name}
                onClick={() => onSetChange(idx)}
                className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                  idx === setIndex
                    ? 'bg-purple-500/20 text-purple-400 ring-1 ring-purple-500/40'
                    : 'bg-slate-700 text-slate-500 hover:text-slate-300 hover:bg-slate-600'
                }`}
              >
                {set.name}
              </button>
            ))}
          </div>

          {/* Direction */}
          <div className="flex gap-1.5">
            {(['ascending', 'descending', 'random'] as IntervalDirection[]).map((d) => (
              <button
                key={d}
                onClick={() => onDirectionChange(d)}
                className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                  d === direction
                    ? 'bg-purple-500/20 text-purple-400 ring-1 ring-purple-500/40'
                    : 'bg-slate-700 text-slate-500 hover:text-slate-300 hover:bg-slate-600'
                }`}
              >
                {d === 'ascending' ? '↑ Up' : d === 'descending' ? '↓ Down' : '↕ Random'}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Active quiz */}
      {active && question && (
        <div className="flex flex-col gap-3">
          {/* Stats bar */}
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>
              {stats.correct}/{stats.total} correct
            </span>
            {stats.total > 0 && (
              <span className={stats.accuracy >= 0.8 ? 'text-emerald-400' : stats.accuracy >= 0.5 ? 'text-yellow-400' : 'text-red-400'}>
                {Math.round(stats.accuracy * 100)}%
              </span>
            )}
            <button onClick={onReset} className="ml-auto text-slate-600 hover:text-slate-400 text-xs">
              Reset
            </button>
          </div>

          {/* Question display */}
          <div className="text-center py-2">
            <div className="text-slate-400 text-xs mb-1">
              {question.direction === 'ascending' ? '↑ Ascending' : '↓ Descending'} from{' '}
              <span className="text-white font-mono">{question.rootNote}</span>
            </div>
            {revealed && (
              <div className="mt-1">
                <span className={`text-lg font-bold ${lastAnswer?.correct ? 'text-emerald-400' : 'text-red-400'}`}>
                  {lastAnswer?.correct ? '✓ ' : '✗ '}
                  {INTERVAL_NAMES[question.semitones]}
                </span>
                {!lastAnswer?.correct && lastAnswer && (
                  <div className="text-xs text-slate-500 mt-0.5">
                    You answered: {INTERVAL_NAMES[lastAnswer.semitones]}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Answer buttons */}
          {!revealed && currentSet && (
            <div className="grid grid-cols-3 gap-1.5">
              {currentSet.intervals.map((semitones) => (
                <button
                  key={semitones}
                  onClick={() => onAnswer(semitones)}
                  className="px-2 py-2 rounded bg-slate-700 text-slate-300 text-xs font-medium
                    hover:bg-purple-500/20 hover:text-purple-300 transition-colors
                    active:bg-purple-500/40"
                >
                  {INTERVAL_SHORT[semitones]}
                </button>
              ))}
            </div>
          )}

          {/* Control buttons */}
          <div className="flex gap-2">
            <button
              onClick={onReplay}
              className="flex-1 px-3 py-1.5 rounded bg-slate-700 text-slate-400 text-xs
                hover:bg-slate-600 hover:text-slate-300 transition-colors"
            >
              🔁 Replay
            </button>
            {revealed && (
              <button
                onClick={onNext}
                className="flex-1 px-3 py-1.5 rounded bg-purple-500/20 text-purple-400 text-xs
                  ring-1 ring-purple-500/40 hover:bg-purple-500/30 transition-colors"
              >
                Next →
              </button>
            )}
          </div>

          {/* Per-interval breakdown (collapsed) */}
          {stats.total >= 5 && (
            <details className="text-xs text-slate-500">
              <summary className="cursor-pointer hover:text-slate-400">
                Interval breakdown
              </summary>
              <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5">
                {Object.entries(stats.perInterval)
                  .sort(([a], [b]) => Number(a) - Number(b))
                  .map(([sem, data]) => {
                    const pct = data.total > 0 ? Math.round((data.correct / data.total) * 100) : 0
                    return (
                      <div key={sem} className="flex justify-between">
                        <span>{INTERVAL_SHORT[Number(sem)]}</span>
                        <span className={pct >= 80 ? 'text-emerald-500' : pct >= 50 ? 'text-yellow-500' : 'text-red-500'}>
                          {data.correct}/{data.total} ({pct}%)
                        </span>
                      </div>
                    )
                  })}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  )
})
