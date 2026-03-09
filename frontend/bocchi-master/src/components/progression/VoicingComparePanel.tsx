import { useState } from 'react'
import { ChordDiagram } from './ChordDiagram'
import type { ChordVoicing } from '../../utils/voicingLibrary'

interface VoicingComparePanelProps {
  voicings: ChordVoicing[]
  activeIndex: number
  chordName?: string
  onSelect: (index: number) => void
  onPlayVoicing?: (index: number) => void
}

/**
 * Side-by-side voicing comparison panel.
 * Shows 3-5 voicings at once with chord diagrams, allowing quick
 * visual comparison of fingerings, fret positions, and shapes.
 */
export function VoicingComparePanel({
  voicings,
  activeIndex,
  chordName,
  onSelect,
  onPlayVoicing,
}: VoicingComparePanelProps) {
  const [expanded, setExpanded] = useState(false)

  if (voicings.length <= 1) return null

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full text-xs text-slate-600 hover:text-slate-400 py-1 transition-colors"
      >
        Compare voicings ({voicings.length} available)...
      </button>
    )
  }

  // Show a paginated set of voicings (5 at a time)
  const PAGE_SIZE = 5
  const totalPages = Math.ceil(voicings.length / PAGE_SIZE)
  const [page, setPage] = useState(Math.floor(activeIndex / PAGE_SIZE))
  const startIdx = page * PAGE_SIZE
  const pageVoicings = voicings.slice(startIdx, startIdx + PAGE_SIZE)

  return (
    <div className="bg-slate-800/50 rounded-lg px-3 py-2 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Compare Voicings
          {chordName && (
            <span className="text-slate-400 ml-1 normal-case">— {chordName}</span>
          )}
        </h3>
        <div className="flex items-center gap-2">
          {totalPages > 1 && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="w-5 h-5 rounded bg-slate-700 text-slate-400 hover:bg-slate-600 disabled:opacity-30 flex items-center justify-center text-xs"
              >
                ‹
              </button>
              <span className="text-[10px] text-slate-500 tabular-nums">
                {page + 1}/{totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page === totalPages - 1}
                className="w-5 h-5 rounded bg-slate-700 text-slate-400 hover:bg-slate-600 disabled:opacity-30 flex items-center justify-center text-xs"
              >
                ›
              </button>
            </div>
          )}
          <button
            onClick={() => setExpanded(false)}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Collapse
          </button>
        </div>
      </div>

      {/* Voicing cards grid */}
      <div className="flex gap-2 flex-wrap">
        {pageVoicings.map((voicing, i) => {
          const globalIdx = startIdx + i
          const isActive = globalIdx === activeIndex
          return (
            <div
              key={globalIdx}
              className={`flex flex-col items-center px-2 py-1.5 rounded-lg border-2 cursor-pointer transition-all ${
                isActive
                  ? 'border-emerald-400 bg-emerald-500/10'
                  : 'border-slate-700 bg-slate-800 hover:border-slate-600'
              }`}
              onClick={() => onSelect(globalIdx)}
            >
              {/* Voicing label */}
              <div className="flex items-center gap-1 mb-1">
                <span
                  className={`text-[10px] font-bold ${
                    isActive ? 'text-emerald-400' : 'text-slate-500'
                  }`}
                >
                  #{globalIdx + 1}
                </span>
                <span
                  className={`text-[10px] ${
                    isActive ? 'text-slate-300' : 'text-slate-600'
                  }`}
                >
                  {voicing.name}
                </span>
              </div>

              {/* Mini chord diagram */}
              <ChordDiagram frets={voicing.frets} />

              {/* Fret string */}
              <div className="text-[9px] font-mono text-slate-600 mt-0.5 tracking-wider">
                {voicing.frets.map((f) => (f === -1 ? 'x' : f)).join(' ')}
              </div>

              {/* Play button */}
              {onPlayVoicing && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onPlayVoicing(globalIdx)
                  }}
                  className="mt-1 text-[10px] text-slate-500 hover:text-sky-400 transition-colors"
                  title="Play this voicing"
                >
                  ▶ Play
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
