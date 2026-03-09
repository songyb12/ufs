import { memo } from 'react'
import type { PracticeStats } from '../../hooks/usePracticeMode'

interface PracticePanelProps {
  active: boolean
  stats: PracticeStats
  lastResult: 'correct' | 'incorrect' | null
  hasTarget: boolean // whether there are notes to practice against
  onToggle: () => void
  onReset: () => void
}

export const PracticePanel = memo(function PracticePanel({
  active,
  stats,
  lastResult,
  hasTarget,
  onToggle,
  onReset,
}: PracticePanelProps) {
  return (
    <div className="bg-slate-800 rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Practice Mode
        </h2>
        <div className="flex items-center gap-2">
          {active && (
            <button
              onClick={onReset}
              className="text-xs text-slate-500 hover:text-slate-300"
            >
              Reset
            </button>
          )}
          <button
            onClick={onToggle}
            disabled={!hasTarget && !active}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              active
                ? 'bg-violet-500/20 text-violet-400 ring-1 ring-violet-500/40'
                : hasTarget
                  ? 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                  : 'bg-slate-700/50 text-slate-600 cursor-not-allowed'
            }`}
          >
            {active ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>

      {!hasTarget && !active && (
        <p className="text-xs text-slate-500">
          Select a scale or chord progression to enable practice mode.
        </p>
      )}

      {active && (
        <>
          {/* Accuracy display */}
          <div className="flex items-center gap-4">
            <div className="text-center">
              <div className={`text-2xl font-bold ${
                stats.accuracy >= 80 ? 'text-emerald-400' :
                stats.accuracy >= 50 ? 'text-amber-400' :
                stats.totalAttempts > 0 ? 'text-red-400' : 'text-slate-500'
              }`}>
                {stats.totalAttempts > 0 ? `${stats.accuracy}%` : '—'}
              </div>
              <div className="text-[10px] text-slate-500 uppercase">Accuracy</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-semibold text-slate-300">
                {stats.correctAttempts}/{stats.totalAttempts}
              </div>
              <div className="text-[10px] text-slate-500 uppercase">Correct</div>
            </div>
            {lastResult && (
              <div className={`px-3 py-1 rounded-full text-xs font-bold ${
                lastResult === 'correct'
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-red-500/20 text-red-400'
              }`}>
                {lastResult === 'correct' ? 'HIT' : 'MISS'}
              </div>
            )}
          </div>

          {/* Recent attempts */}
          {stats.recentResults.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {stats.recentResults.map((r, i) => (
                <span
                  key={r.timestamp}
                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                    r.correct
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-red-500/20 text-red-400'
                  } ${i === 0 ? 'ring-1 ring-white/20' : ''}`}
                >
                  {r.noteName}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
})
