import { useState, useMemo } from 'react'
import type { NoteName } from '../../types/music'
import { CHROMATIC_SCALE } from '../../constants/notes'
import { findBestScales, type ScaleMatch } from '../../utils/scaleFinder'

interface ScaleFinderPanelProps {
  onScaleSelect?: (root: NoteName, scaleName: string) => void
}

export function ScaleFinderPanel({ onScaleSelect }: ScaleFinderPanelProps) {
  const [selectedNotes, setSelectedNotes] = useState<Set<NoteName>>(new Set())
  const [expanded, setExpanded] = useState(false)

  const toggleNote = (note: NoteName) => {
    setSelectedNotes((prev) => {
      const next = new Set(prev)
      if (next.has(note)) next.delete(note)
      else next.add(note)
      return next
    })
  }

  const matches: ScaleMatch[] = useMemo(() => {
    if (selectedNotes.size < 2) return []
    return findBestScales([...selectedNotes], 8, 0.8)
  }, [selectedNotes])

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full text-xs text-slate-600 hover:text-slate-400 py-1 transition-colors"
      >
        Scale Finder (identify scales from notes)...
      </button>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg px-4 py-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Scale Finder
        </h2>
        <div className="flex items-center gap-2">
          {selectedNotes.size > 0 && (
            <button
              onClick={() => setSelectedNotes(new Set())}
              className="text-xs text-slate-500 hover:text-slate-300"
            >
              Clear
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

      <p className="text-xs text-slate-600">
        Select notes you hear or see — matching scales will appear below.
      </p>

      {/* Note selection buttons */}
      <div className="flex gap-1 flex-wrap">
        {CHROMATIC_SCALE.map((note) => (
          <button
            key={note}
            onClick={() => toggleNote(note)}
            className={`w-9 h-7 rounded text-xs font-semibold transition-colors ${
              selectedNotes.has(note)
                ? 'bg-violet-500 text-white'
                : 'bg-slate-700 text-slate-400 hover:bg-slate-600 hover:text-slate-200'
            }`}
          >
            {note}
          </button>
        ))}
      </div>

      {/* Results */}
      {selectedNotes.size >= 2 && (
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {matches.length === 0 ? (
            <p className="text-xs text-slate-600 italic">No matching scales found.</p>
          ) : (
            matches.map((m, idx) => (
              <button
                key={`${m.root}-${m.scale.name}-${idx}`}
                onClick={() => onScaleSelect?.(m.root, m.scale.name)}
                className="w-full flex items-center justify-between px-2 py-1.5 rounded bg-slate-700/50 hover:bg-slate-700 transition-colors text-left"
              >
                <div>
                  <span className="text-sm font-semibold text-white">
                    {m.root} {m.scale.name}
                  </span>
                  {m.coverage < 1 && m.extraNotes.length > 0 && (
                    <span className="text-xs text-amber-400 ml-2">
                      ({m.extraNotes.join(', ')} outside)
                    </span>
                  )}
                </div>
                <span className={`text-xs font-mono ${
                  m.coverage === 1 ? 'text-emerald-400' : 'text-slate-500'
                }`}>
                  {Math.round(m.coverage * 100)}%
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
