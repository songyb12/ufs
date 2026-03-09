import { useState } from 'react'
import type { InstrumentConfig } from '../../types/music'
import { GUITAR_TUNINGS, BASS_TUNINGS } from '../../constants/tunings'

interface TuningQuickSwitchProps {
  instrument: InstrumentConfig
  onInstrumentChange: (config: InstrumentConfig) => void
}

/** Short display labels for common tunings */
const SHORT_LABELS: Record<string, string> = {
  'Standard Guitar': 'Standard',
  'Drop D': 'Drop D',
  'Half Step Down (Eb)': 'Eb',
  'Open G': 'Open G',
  'Open D': 'Open D',
  'Open E': 'Open E',
  'DADGAD': 'DADGAD',
  '7-String Standard': '7-Str',
  'Standard Bass': 'Standard',
  'Drop D Bass': 'Drop D',
  '5-String Bass': '5-Str',
  '6-String Bass': '6-Str',
}

/**
 * Compact tuning quick-switch bar.
 * Shows pill buttons for all tunings of the current instrument type,
 * allowing one-click tuning changes without the header dropdown.
 */
export function TuningQuickSwitch({
  instrument,
  onInstrumentChange,
}: TuningQuickSwitchProps) {
  const [expanded, setExpanded] = useState(false)

  const isGuitar = instrument.type === 'guitar'
  const tunings = isGuitar ? GUITAR_TUNINGS : BASS_TUNINGS

  // Always show active tuning display + expand toggle
  if (!expanded) {
    return (
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-slate-500">Tuning:</span>
        <span className="text-xs text-slate-300 font-semibold">
          {instrument.name}
        </span>
        <span className="text-[10px] text-slate-600 font-mono">
          ({instrument.tuning.map((n) => n.name).join(' ')})
        </span>
        <button
          onClick={() => setExpanded(true)}
          className="text-[10px] text-slate-600 hover:text-slate-400 ml-1"
        >
          Change...
        </button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="text-xs text-slate-500">Tuning:</span>
      {tunings.map((t) => {
        const isActive = t.name === instrument.name
        const label = SHORT_LABELS[t.name] ?? t.name
        return (
          <button
            key={t.name}
            onClick={() => {
              onInstrumentChange(t)
              setExpanded(false)
            }}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              isActive
                ? 'bg-sky-500/20 text-sky-400 ring-1 ring-sky-500/40'
                : 'bg-slate-700 text-slate-500 hover:text-slate-300'
            }`}
            title={`${t.name}: ${t.tuning.map((n) => n.name).join('-')}`}
          >
            {label}
          </button>
        )
      })}
      {/* Switch instrument type */}
      <span className="text-slate-700 mx-0.5">|</span>
      <button
        onClick={() => {
          const target = isGuitar ? BASS_TUNINGS[0] : GUITAR_TUNINGS[0]
          onInstrumentChange(target)
        }}
        className="px-2 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-500 hover:text-slate-300 transition-colors"
      >
        → {isGuitar ? 'Bass' : 'Guitar'}
      </button>
      <button
        onClick={() => setExpanded(false)}
        className="text-[10px] text-slate-500 hover:text-slate-300 ml-1"
      >
        Done
      </button>
    </div>
  )
}
