import { memo } from 'react'
import { BACKING_STYLES } from '../../utils/backingPatterns'

interface BackingTrackPanelProps {
  enabled: boolean
  drumVolume: number
  bassVolume: number
  styleIndex: number
  onToggle: () => void
  onDrumVolumeChange: (v: number) => void
  onBassVolumeChange: (v: number) => void
  onStyleChange: (idx: number) => void
}

export const BackingTrackPanel = memo(function BackingTrackPanel({
  enabled,
  drumVolume,
  bassVolume,
  styleIndex,
  onToggle,
  onDrumVolumeChange,
  onBassVolumeChange,
  onStyleChange,
}: BackingTrackPanelProps) {
  return (
    <div className="bg-slate-800 rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Backing Track
        </h2>
        <button
          onClick={onToggle}
          className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
            enabled
              ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40'
              : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
          }`}
          aria-label={enabled ? 'Disable backing track' : 'Enable backing track'}
        >
          {enabled ? 'ON' : 'OFF'}
        </button>
      </div>

      {/* Style selector */}
      <div className="flex gap-1.5 flex-wrap">
        {BACKING_STYLES.map((style, idx) => (
          <button
            key={style.name}
            onClick={() => onStyleChange(idx)}
            className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
              idx === styleIndex
                ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40'
                : 'bg-slate-700 text-slate-500 hover:text-slate-300 hover:bg-slate-600'
            }`}
            title={style.description}
          >
            {style.name}
          </button>
        ))}
      </div>

      {enabled && (
        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <span className="w-12">Drums</span>
            <input
              type="range"
              min={0}
              max={100}
              value={Math.round(drumVolume * 100)}
              onChange={(e) => onDrumVolumeChange(Number(e.target.value) / 100)}
              className="flex-1 h-1 accent-emerald-500"
              aria-label="Drum volume"
            />
            <span className="w-8 text-right text-slate-500">
              {Math.round(drumVolume * 100)}
            </span>
          </label>
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <span className="w-12">Bass</span>
            <input
              type="range"
              min={0}
              max={100}
              value={Math.round(bassVolume * 100)}
              onChange={(e) => onBassVolumeChange(Number(e.target.value) / 100)}
              className="flex-1 h-1 accent-emerald-500"
              aria-label="Bass volume"
            />
            <span className="w-8 text-right text-slate-500">
              {Math.round(bassVolume * 100)}
            </span>
          </label>
        </div>
      )}
    </div>
  )
})
