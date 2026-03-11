import { useState, useMemo, useCallback, useEffect } from 'react'
import type { InstrumentConfig, NoteName } from '../../types/music'
import { CHROMATIC_SCALE } from '../../constants/notes'
import {
  PENTATONIC_MINOR_PATTERNS,
  BLUES_PATTERNS,
  type ScalePattern,
  resolvePatternFrets,
} from '../../utils/scalePatterns'

interface ScalePatternPanelProps {
  instrument: InstrumentConfig
  selectedRoot: NoteName | null
  onPatternPositionsChange: (positions: { stringIndex: number; fret: number }[] | null) => void
}

/** Find the lowest fret where a note appears on a given string (open string = Note object) */
function findRootFret(openNoteName: NoteName, targetNote: NoteName, maxFret: number): number {
  const openIdx = CHROMATIC_SCALE.indexOf(openNoteName)
  const targetIdx = CHROMATIC_SCALE.indexOf(targetNote)
  if (openIdx < 0 || targetIdx < 0) return 0
  const diff = (targetIdx - openIdx + 12) % 12
  return diff <= maxFret ? diff : 0
}

const PATTERN_GROUPS = [
  { label: 'Pentatonic Minor', patterns: PENTATONIC_MINOR_PATTERNS },
  { label: 'Blues', patterns: BLUES_PATTERNS },
]

export function ScalePatternPanel({
  instrument,
  selectedRoot,
  onPatternPositionsChange,
}: ScalePatternPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const [selectedPattern, setSelectedPattern] = useState<ScalePattern | null>(null)
  const [rootFretOverride, setRootFretOverride] = useState<number | null>(null)

  // Auto-detect root fret from selected root note and lowest string
  const autoRootFret = useMemo(() => {
    if (!selectedRoot) return 0
    const lowestString = instrument.tuning[0]
    return findRootFret(lowestString.name, selectedRoot, instrument.fretCount)
  }, [selectedRoot, instrument.tuning, instrument.fretCount])

  const rootFret = rootFretOverride ?? autoRootFret

  // Resolve pattern positions
  const patternPositions = useMemo(() => {
    if (!selectedPattern) return null
    return resolvePatternFrets(selectedPattern, rootFret)
  }, [selectedPattern, rootFret])

  // Notify parent when positions change
  useEffect(() => {
    onPatternPositionsChange(patternPositions)
  }, [patternPositions]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelect = useCallback((pattern: ScalePattern | null) => {
    setSelectedPattern(pattern)
    setRootFretOverride(null)
  }, [])

  const handleClear = useCallback(() => {
    setSelectedPattern(null)
    setRootFretOverride(null)
    onPatternPositionsChange(null)
  }, [onPatternPositionsChange])

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full text-xs text-slate-600 hover:text-slate-400 py-1 transition-colors"
      >
        Scale Patterns (box shapes for practice)...
      </button>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg px-4 py-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Scale Patterns
        </h2>
        <div className="flex items-center gap-2">
          {selectedPattern && (
            <button
              onClick={handleClear}
              className="text-xs text-slate-500 hover:text-slate-300"
            >
              Clear
            </button>
          )}
          <button
            onClick={() => { setExpanded(false); handleClear() }}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Collapse
          </button>
        </div>
      </div>

      {!selectedRoot && (
        <p className="text-xs text-amber-400/70">
          Select a root note above to auto-position patterns.
        </p>
      )}

      {/* Pattern groups */}
      {PATTERN_GROUPS.map((group) => (
        <div key={group.label}>
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">
            {group.label}
          </div>
          <div className="flex gap-1 flex-wrap">
            {group.patterns.map((pat) => (
              <button
                key={pat.name}
                onClick={() => handleSelect(selectedPattern === pat ? null : pat)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  selectedPattern === pat
                    ? 'bg-teal-500/20 text-teal-400 ring-1 ring-teal-500/40'
                    : 'bg-slate-700 text-slate-400 hover:bg-slate-600 hover:text-slate-200'
                }`}
                title={pat.description}
              >
                {pat.name}
              </button>
            ))}
          </div>
        </div>
      ))}

      {/* Root fret adjustment */}
      {selectedPattern && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Root fret:</span>
          <input
            type="range"
            min={0}
            max={Math.max(12, instrument.fretCount - (selectedPattern.fretSpan ?? 4))}
            value={rootFret}
            onChange={(e) => setRootFretOverride(Number(e.target.value))}
            className="flex-1 h-1 accent-teal-500"
          />
          <span className="text-xs text-teal-400 tabular-nums w-6 text-right font-semibold">
            {rootFret}
          </span>
          {rootFretOverride !== null && (
            <button
              onClick={() => setRootFretOverride(null)}
              className="text-[10px] text-slate-500 hover:text-slate-300"
            >
              Auto
            </button>
          )}
        </div>
      )}

      {/* Pattern info */}
      {selectedPattern && (
        <p className="text-[10px] text-slate-600">
          {selectedPattern.description} — {patternPositions?.length ?? 0} notes,
          frets {rootFret}–{rootFret + (selectedPattern.fretSpan ?? 4)}
          {selectedRoot && ` in ${selectedRoot}`}
        </p>
      )}
    </div>
  )
}
