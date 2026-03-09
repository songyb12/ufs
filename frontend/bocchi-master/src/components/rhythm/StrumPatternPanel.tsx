import { useState, useEffect, useRef } from 'react'
import {
  STRUM_PATTERNS,
  STRUM_CATEGORIES,
  type StrumPattern,
  type StrokeType,
} from '../../utils/strumPatterns'

interface StrumPatternPanelProps {
  /** Current beat index (0-based) to highlight active stroke */
  currentBeat: number
  /** Beats per measure */
  beatsPerMeasure: number
  /** Whether metronome is playing */
  isPlaying: boolean
}

/** Arrow glyph for a stroke type */
function StrokeArrow({ type, active }: { type: StrokeType; active: boolean }) {
  const base = 'flex flex-col items-center justify-center w-7 h-10 rounded transition-all duration-75'

  if (type === '-') {
    return (
      <div className={`${base} ${active ? 'bg-slate-600' : ''}`}>
        <span className="text-slate-600 text-lg">·</span>
      </div>
    )
  }

  const isDown = type === 'D'
  const arrow = isDown ? '↓' : '↑'
  const activeColor = isDown
    ? 'bg-sky-500/30 text-sky-300 ring-1 ring-sky-400/50'
    : 'bg-violet-500/30 text-violet-300 ring-1 ring-violet-400/50'
  const inactiveColor = isDown
    ? 'text-sky-500/70'
    : 'text-violet-500/70'

  return (
    <div className={`${base} ${active ? activeColor : inactiveColor}`}>
      <span className="text-xl font-bold leading-none">{arrow}</span>
      <span className="text-[8px] font-mono opacity-70">{type}</span>
    </div>
  )
}

export function StrumPatternPanel({
  currentBeat,
  beatsPerMeasure,
  isPlaying,
}: StrumPatternPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const [selectedPattern, setSelectedPattern] = useState<StrumPattern | null>(null)
  const [activeCategory, setActiveCategory] = useState<StrumPattern['category']>('basic')
  const scrollRef = useRef<HTMLDivElement>(null)

  // Map beat to stroke index based on pattern length and time signature
  const activeStrokeIndex = (() => {
    if (!selectedPattern || !isPlaying || currentBeat < 0) return -1
    const patLen = selectedPattern.strokes.length
    const strokesPerBeat = patLen / beatsPerMeasure
    return Math.floor(currentBeat * strokesPerBeat) % patLen
  })()

  // Auto-scroll to active stroke
  useEffect(() => {
    if (scrollRef.current && activeStrokeIndex >= 0) {
      const child = scrollRef.current.children[activeStrokeIndex] as HTMLElement | undefined
      child?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
    }
  }, [activeStrokeIndex])

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full text-xs text-slate-600 hover:text-slate-400 py-1 transition-colors"
      >
        Strum Patterns (rhythm guide)...
      </button>
    )
  }

  const filteredPatterns = STRUM_PATTERNS.filter((p) => p.category === activeCategory)

  return (
    <div className="bg-slate-800 rounded-lg px-4 py-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Strum Patterns
        </h2>
        <div className="flex items-center gap-2">
          {selectedPattern && (
            <button
              onClick={() => setSelectedPattern(null)}
              className="text-xs text-slate-500 hover:text-slate-300"
            >
              Clear
            </button>
          )}
          <button
            onClick={() => { setExpanded(false); setSelectedPattern(null) }}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Collapse
          </button>
        </div>
      </div>

      {/* Category tabs */}
      <div className="flex gap-1 flex-wrap">
        {STRUM_CATEGORIES.map((cat) => (
          <button
            key={cat.key}
            onClick={() => setActiveCategory(cat.key)}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              activeCategory === cat.key
                ? 'bg-sky-500/20 text-sky-400 ring-1 ring-sky-500/40'
                : 'bg-slate-700 text-slate-500 hover:text-slate-300'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Pattern list */}
      <div className="flex gap-1 flex-wrap">
        {filteredPatterns.map((pat) => (
          <button
            key={pat.name}
            onClick={() => setSelectedPattern(selectedPattern === pat ? null : pat)}
            className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
              selectedPattern === pat
                ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40'
                : 'bg-slate-700 text-slate-400 hover:bg-slate-600 hover:text-slate-200'
            }`}
            title={pat.description}
          >
            {pat.name}
          </button>
        ))}
      </div>

      {/* Visual strum display */}
      {selectedPattern && (
        <>
          <div
            ref={scrollRef}
            className="flex gap-0.5 justify-center items-end overflow-x-auto py-1"
          >
            {selectedPattern.strokes.map((stroke, i) => {
              // Show beat numbers below certain strokes
              const patLen = selectedPattern.strokes.length
              const strokesPerBeat = patLen / beatsPerMeasure
              const isBeatStart = i % strokesPerBeat === 0

              return (
                <div key={i} className="flex flex-col items-center">
                  <StrokeArrow
                    type={stroke}
                    active={activeStrokeIndex === i}
                  />
                  {isBeatStart && (
                    <span className="text-[8px] text-slate-500 mt-0.5">
                      {Math.floor(i / strokesPerBeat) + 1}
                    </span>
                  )}
                </div>
              )
            })}
          </div>

          {/* Pattern description */}
          <p className="text-[10px] text-slate-600 text-center">
            {selectedPattern.description}
          </p>

          {/* Text notation */}
          <div className="text-center">
            <span className="text-xs font-mono text-slate-400 tracking-wider">
              {selectedPattern.strokes.join(' ')}
            </span>
          </div>
        </>
      )}
    </div>
  )
}
