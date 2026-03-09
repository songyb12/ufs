import { useState, useMemo } from 'react'
import { ChordDiagram } from './ChordDiagram'
import { classifyDifficulty, type ChordVoicing, type VoicingDifficulty } from '../../utils/voicingLibrary'

const DIFFICULTY_LABELS: Record<VoicingDifficulty, { label: string; color: string }> = {
  open: { label: 'Open', color: 'text-emerald-400 bg-emerald-500/20 ring-emerald-500/40' },
  barre: { label: 'Barre', color: 'text-amber-400 bg-amber-500/20 ring-amber-500/40' },
  advanced: { label: 'Adv', color: 'text-rose-400 bg-rose-500/20 ring-rose-500/40' },
}

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
  const [difficultyFilter, setDifficultyFilter] = useState<VoicingDifficulty | 'all'>('all')

  // Classify each voicing
  const classified = useMemo(() =>
    voicings.map((v, i) => ({ voicing: v, difficulty: classifyDifficulty(v), originalIndex: i })),
    [voicings],
  )

  // Filter voicings
  const filtered = difficultyFilter === 'all'
    ? classified
    : classified.filter((c) => c.difficulty === difficultyFilter)

  // Count per difficulty
  const counts = useMemo(() => {
    const c = { open: 0, barre: 0, advanced: 0 }
    for (const item of classified) c[item.difficulty]++
    return c
  }, [classified])

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

  // Show a paginated set of filtered voicings (5 at a time)
  const PAGE_SIZE = 5
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const [page, setPage] = useState(Math.floor(activeIndex / PAGE_SIZE))
  const startIdx = page * PAGE_SIZE
  const pageItems = filtered.slice(startIdx, startIdx + PAGE_SIZE)

  return (
    <div className="bg-slate-800/50 rounded-lg px-3 py-2 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Compare Voicings
          {chordName && (
            <span className="text-slate-400 ml-1 normal-case">— {chordName}</span>
          )}
        </h3>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Difficulty filter */}
          <div className="flex items-center gap-1">
            {(['all', 'open', 'barre', 'advanced'] as const).map((d) => {
              const count = d === 'all' ? classified.length : counts[d]
              const isActive = difficultyFilter === d
              const style = d === 'all'
                ? isActive ? 'text-sky-400 bg-sky-500/20 ring-1 ring-sky-500/40' : 'text-slate-500 bg-slate-700'
                : isActive ? `${DIFFICULTY_LABELS[d].color} ring-1` : 'text-slate-500 bg-slate-700'
              return (
                <button
                  key={d}
                  onClick={() => { setDifficultyFilter(d); setPage(0) }}
                  disabled={count === 0}
                  className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors disabled:opacity-30 ${style}`}
                >
                  {d === 'all' ? 'All' : DIFFICULTY_LABELS[d].label} ({count})
                </button>
              )
            })}
          </div>
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
        {filtered.length === 0 && (
          <p className="text-xs text-slate-600 italic">No voicings match this filter.</p>
        )}
        {pageItems.map((item) => {
          const { voicing, difficulty, originalIndex } = item
          const isActive = originalIndex === activeIndex
          const diffStyle = DIFFICULTY_LABELS[difficulty]
          return (
            <div
              key={originalIndex}
              className={`flex flex-col items-center px-2 py-1.5 rounded-lg border-2 cursor-pointer transition-all ${
                isActive
                  ? 'border-emerald-400 bg-emerald-500/10'
                  : 'border-slate-700 bg-slate-800 hover:border-slate-600'
              }`}
              onClick={() => onSelect(originalIndex)}
            >
              {/* Voicing label + difficulty badge */}
              <div className="flex items-center gap-1 mb-1">
                <span
                  className={`text-[10px] font-bold ${
                    isActive ? 'text-emerald-400' : 'text-slate-500'
                  }`}
                >
                  #{originalIndex + 1}
                </span>
                <span className={`text-[8px] px-1 rounded ${diffStyle.color}`}>
                  {diffStyle.label}
                </span>
              </div>
              <span
                className={`text-[10px] mb-0.5 ${
                  isActive ? 'text-slate-300' : 'text-slate-600'
                }`}
              >
                {voicing.name}
              </span>

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
                    onPlayVoicing(originalIndex)
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
