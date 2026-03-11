import { memo } from 'react'
import type { ScaleSuggestion } from '../../utils/scaleAdvisor'

interface ScaleSuggestionPanelProps {
  suggestions: ScaleSuggestion[]
  activeIndex: number | null
  onSelect: (index: number | null) => void
}

export const ScaleSuggestionPanel = memo(function ScaleSuggestionPanel({
  suggestions,
  activeIndex,
  onSelect,
}: ScaleSuggestionPanelProps) {
  if (suggestions.length === 0) return null

  return (
    <div className="bg-slate-800 rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-amber-400 uppercase tracking-wider">
          Scale Suggestions
        </h3>
        {activeIndex !== null && (
          <button
            onClick={() => onSelect(null)}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Clear
          </button>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {suggestions.map((s, i) => {
          const isActive = activeIndex === i
          return (
            <button
              key={`${s.root}-${s.scale.name}`}
              onClick={() => onSelect(isActive ? null : i)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                isActive
                  ? 'bg-amber-500/30 text-amber-300 ring-1 ring-amber-500/50'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
              title={s.reason}
            >
              {s.root} {s.scale.name}
              <span className="ml-1 text-[10px] opacity-60">{s.reason}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
})
