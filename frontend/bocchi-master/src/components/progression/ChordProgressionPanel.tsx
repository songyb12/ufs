import type { NoteName } from '../../types/music'
import { CHROMATIC_SCALE } from '../../constants/notes'
import {
  PROGRESSION_PRESETS,
  resolveProgression,
  type ProgressionPreset,
  type ResolvedChord,
} from '../../utils/chordProgression'

interface ChordProgressionPanelProps {
  progressionKey: NoteName | null
  progressionPreset: ProgressionPreset | null
  activeChordIndex: number
  isPlaying: boolean
  onKeyChange: (key: NoteName | null) => void
  onPresetChange: (preset: ProgressionPreset | null) => void
  onChordClick: (index: number) => void
}

export function ChordProgressionPanel({
  progressionKey,
  progressionPreset,
  activeChordIndex,
  isPlaying,
  onKeyChange,
  onPresetChange,
  onChordClick,
}: ChordProgressionPanelProps) {
  // Resolve progression into concrete chords
  const resolvedChords: ResolvedChord[] =
    progressionKey && progressionPreset
      ? resolveProgression(progressionKey, progressionPreset)
      : []

  const handleClear = () => {
    onKeyChange(null)
    onPresetChange(null)
  }

  return (
    <div className="bg-slate-800 rounded-lg px-4 py-3 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Chord Progression
        </h2>
        {(progressionKey || progressionPreset) && (
          <button
            onClick={handleClear}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Clear
          </button>
        )}
      </div>

      {/* Top row: key selector + preset dropdown */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Preset dropdown */}
        <select
          value={progressionPreset?.name ?? ''}
          onChange={(e) => {
            const found = PROGRESSION_PRESETS.find(
              (p) => p.name === e.target.value,
            )
            onPresetChange(found ?? null)
          }}
          className="bg-slate-700 text-slate-300 text-sm rounded px-2 py-1 outline-none border border-slate-600"
        >
          <option value="">Select progression...</option>
          {PROGRESSION_PRESETS.map((preset) => (
            <option key={preset.name} value={preset.name}>
              {preset.name}
            </option>
          ))}
        </select>

        {/* Key label */}
        {progressionKey && (
          <span className="text-xs text-slate-500">
            Key: <span className="text-slate-300 font-semibold">{progressionKey}</span>
          </span>
        )}
      </div>

      {/* Key buttons */}
      <div className="flex gap-1 flex-wrap">
        {CHROMATIC_SCALE.map((note) => {
          const isSelected = progressionKey === note
          return (
            <button
              key={note}
              onClick={() => onKeyChange(isSelected ? null : note)}
              className={`w-9 h-7 rounded text-xs font-semibold transition-colors ${
                isSelected
                  ? 'bg-emerald-500 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600 hover:text-slate-200'
              }`}
            >
              {note}
            </button>
          )
        })}
      </div>

      {/* Chord sequence blocks */}
      {resolvedChords.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {resolvedChords.map((chord, index) => {
            const isActive = index === activeChordIndex
            return (
              <button
                key={`${chord.label}-${index}`}
                onClick={() => onChordClick(index)}
                className={`flex flex-col items-center px-3 py-2 rounded-lg border-2 transition-all min-w-[60px] ${
                  isActive && isPlaying
                    ? 'border-emerald-400 bg-emerald-500/20 shadow-lg shadow-emerald-500/10'
                    : isActive && !isPlaying
                      ? 'border-emerald-500/50 bg-emerald-500/10'
                      : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                }`}
              >
                <span
                  className={`text-xs font-bold ${
                    isActive
                      ? 'text-emerald-400'
                      : 'text-slate-400'
                  }`}
                >
                  {chord.label}
                </span>
                <span
                  className={`text-sm font-semibold ${
                    isActive
                      ? 'text-white'
                      : 'text-slate-300'
                  }`}
                >
                  {chord.chordName}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {/* Empty state */}
      {resolvedChords.length === 0 && (
        <p className="text-xs text-slate-600 text-center py-1">
          Select a key and progression preset to display chords
        </p>
      )}
    </div>
  )
}
