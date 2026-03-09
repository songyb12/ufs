import type { NoteName } from '../../types/music'
import { CHROMATIC_SCALE } from '../../constants/notes'
import {
  PROGRESSION_PRESETS,
  resolveProgression,
  type ProgressionPreset,
  type ProgressionStep,
  type ResolvedChord,
} from '../../utils/chordProgression'
import { CustomProgressionEditor } from './CustomProgressionEditor'
import { ChordDiagram } from './ChordDiagram'

export type VoicingMode = 'all' | 'voicing'
export type VoicingSource = 'caged' | 'auto'

interface ChordProgressionPanelProps {
  progressionKey: NoteName | null
  progressionPreset: ProgressionPreset | null
  activeChordIndex: number
  isPlaying: boolean
  onKeyChange: (key: NoteName | null) => void
  onPresetChange: (preset: ProgressionPreset | null) => void
  onChordClick: (index: number) => void
  // Voicing controls
  voicingMode: VoicingMode
  onVoicingModeChange: (mode: VoicingMode) => void
  voicingSource: VoicingSource
  onVoicingSourceChange: (source: VoicingSource) => void
  voicingIndex: number
  onVoicingIndexChange: (index: number) => void
  voicingCount: number
  voicingName: string
  // Voice leading optimization
  isOptimized: boolean
  onOptimizedChange: (optimized: boolean) => void
  // Current voicing frets for chord diagram
  voicingFrets?: number[]
  activeChordName?: string
  // Loop control
  loopCount: number
  onLoopCountChange: (count: number) => void
  // Custom progression
  isCustom: boolean
  onCustomToggle: () => void
  customSteps: ProgressionStep[]
  onCustomStepsChange: (steps: ProgressionStep[]) => void
}

export function ChordProgressionPanel({
  progressionKey,
  progressionPreset,
  activeChordIndex,
  isPlaying,
  onKeyChange,
  onPresetChange,
  onChordClick,
  voicingMode,
  onVoicingModeChange,
  voicingSource,
  onVoicingSourceChange,
  voicingIndex,
  onVoicingIndexChange,
  voicingCount,
  voicingName,
  isOptimized,
  onOptimizedChange,
  voicingFrets,
  activeChordName,
  loopCount,
  onLoopCountChange,
  isCustom,
  onCustomToggle,
  customSteps,
  onCustomStepsChange,
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

  const hasChords = resolvedChords.length > 0

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
          value={isCustom ? '__custom__' : (progressionPreset?.name ?? '')}
          onChange={(e) => {
            if (e.target.value === '__custom__') {
              onCustomToggle()
            } else {
              if (isCustom) onCustomToggle()
              const found = PROGRESSION_PRESETS.find(
                (p) => p.name === e.target.value,
              )
              onPresetChange(found ?? null)
            }
          }}
          className="bg-slate-700 text-slate-300 text-sm rounded px-2 py-1 outline-none border border-slate-600"
        >
          <option value="">Select progression...</option>
          {PROGRESSION_PRESETS.map((preset) => (
            <option key={preset.name} value={preset.name}>
              {preset.name}
            </option>
          ))}
          <option value="__custom__">Custom...</option>
        </select>

        {/* Key label */}
        {progressionKey && (
          <span className="text-xs text-slate-500">
            Key: <span className="text-slate-300 font-semibold">{progressionKey}</span>
          </span>
        )}
      </div>

      {/* Custom editor */}
      {isCustom && (
        <CustomProgressionEditor
          steps={customSteps}
          onStepsChange={onCustomStepsChange}
        />
      )}

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
      {hasChords && (
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

          {/* Loop count control */}
          <div className="flex items-center gap-1 ml-auto">
            <span className="text-xs text-slate-500">Loop:</span>
            {[0, 1, 2, 4, 8].map((n) => (
              <button
                key={n}
                onClick={() => onLoopCountChange(n)}
                className={`w-6 h-6 rounded text-xs font-medium transition-colors ${
                  loopCount === n
                    ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40'
                    : 'bg-slate-700 text-slate-500 hover:text-slate-300'
                }`}
              >
                {n === 0 ? '∞' : n}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Voicing controls — shown when chords are active */}
      {hasChords && (
        <div className="flex items-center gap-3 flex-wrap border-t border-slate-700 pt-3">
          {/* Mode toggle: All Notes ↔ Voicing */}
          <div className="flex rounded overflow-hidden border border-slate-600">
            <button
              onClick={() => onVoicingModeChange('all')}
              className={`px-3 py-1 text-xs font-semibold transition-colors ${
                voicingMode === 'all'
                  ? 'bg-slate-600 text-white'
                  : 'bg-slate-750 text-slate-400 hover:text-slate-200'
              }`}
            >
              All Notes
            </button>
            <button
              onClick={() => onVoicingModeChange('voicing')}
              className={`px-3 py-1 text-xs font-semibold transition-colors ${
                voicingMode === 'voicing'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-750 text-slate-400 hover:text-slate-200'
              }`}
            >
              Voicing
            </button>
          </div>

          {/* Source + Navigator (only in voicing mode) */}
          {voicingMode === 'voicing' && (
            <>
              {/* Source selector: CAGED ↔ Auto */}
              <div className="flex rounded overflow-hidden border border-slate-600">
                <button
                  onClick={() => onVoicingSourceChange('caged')}
                  className={`px-2 py-1 text-xs font-semibold transition-colors ${
                    voicingSource === 'caged'
                      ? 'bg-slate-600 text-white'
                      : 'bg-slate-750 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  CAGED
                </button>
                <button
                  onClick={() => onVoicingSourceChange('auto')}
                  className={`px-2 py-1 text-xs font-semibold transition-colors ${
                    voicingSource === 'auto'
                      ? 'bg-slate-600 text-white'
                      : 'bg-slate-750 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Auto
                </button>
              </div>

              {/* Voice leading optimization toggle */}
              <button
                onClick={() => onOptimizedChange(!isOptimized)}
                className={`px-2 py-1 rounded text-xs font-semibold transition-colors border ${
                  isOptimized
                    ? 'border-amber-500/50 bg-amber-500/20 text-amber-400'
                    : 'border-slate-600 bg-slate-750 text-slate-500 hover:text-slate-300'
                }`}
                title="Voice leading optimization: selects voicings that minimize hand movement between chord changes"
              >
                Optimize
              </button>

              {/* Voicing navigator */}
              {voicingCount > 0 ? (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() =>
                      onVoicingIndexChange(
                        (voicingIndex - 1 + voicingCount) % voicingCount,
                      )
                    }
                    className="w-6 h-6 rounded bg-slate-700 text-slate-300 hover:bg-slate-600 flex items-center justify-center text-xs font-bold"
                  >
                    &lt;
                  </button>
                  <span className="text-xs text-slate-300 min-w-[120px] text-center">
                    <span className="text-slate-500">
                      {voicingIndex + 1}/{voicingCount}
                    </span>
                    {' '}
                    <span className="font-semibold">{voicingName}</span>
                  </span>
                  <button
                    onClick={() =>
                      onVoicingIndexChange((voicingIndex + 1) % voicingCount)
                    }
                    className="w-6 h-6 rounded bg-slate-700 text-slate-300 hover:bg-slate-600 flex items-center justify-center text-xs font-bold"
                  >
                    &gt;
                  </button>
                </div>
              ) : (
                <span className="text-xs text-slate-500 italic">
                  No voicings available
                </span>
              )}
            </>
          )}
        </div>
      )}

      {/* Chord diagram (shown in voicing mode with active voicing) */}
      {voicingMode === 'voicing' && voicingFrets && voicingFrets.length > 0 && (
        <div className="flex items-start gap-3 border-t border-slate-700 pt-2">
          <ChordDiagram
            frets={voicingFrets}
            name={activeChordName}
          />
          <div className="text-xs text-slate-500 pt-1">
            <div className="font-mono tracking-wider">
              {voicingFrets.map((f) => f === -1 ? 'x' : f).join(' ')}
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!hasChords && (
        <p className="text-xs text-slate-600 text-center py-1">
          Select a key and progression preset to display chords
        </p>
      )}
    </div>
  )
}
