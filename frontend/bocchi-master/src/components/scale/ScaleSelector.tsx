import type { NoteName } from '../../types/music'
import { CHROMATIC_SCALE } from '../../constants/notes'
import {
  SCALES,
  CHORDS,
  type ScaleDefinition,
  type ChordDefinition,
} from '../../utils/scaleCalculator'

type Mode = 'scale' | 'chord'

interface ScaleSelectorProps {
  selectedRoot: NoteName | null
  selectedDefinition: ScaleDefinition | ChordDefinition | null
  mode: Mode
  onRootChange: (root: NoteName | null) => void
  onDefinitionChange: (def: ScaleDefinition | ChordDefinition | null) => void
  onModeChange: (mode: Mode) => void
}

export function ScaleSelector({
  selectedRoot,
  selectedDefinition,
  mode,
  onRootChange,
  onDefinitionChange,
  onModeChange,
}: ScaleSelectorProps) {
  const definitions = mode === 'scale' ? SCALES : CHORDS

  const handleClear = () => {
    onRootChange(null)
    onDefinitionChange(null)
  }

  return (
    <div className="bg-slate-800 rounded-lg px-4 py-3 flex flex-col gap-2">
      {/* Top row: mode tabs + dropdown + clear */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Mode tabs */}
        <div className="flex rounded overflow-hidden border border-slate-600">
          <button
            onClick={() => onModeChange('scale')}
            className={`px-3 py-1 text-xs font-semibold transition-colors ${
              mode === 'scale'
                ? 'bg-sky-500 text-white'
                : 'bg-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            Scale
          </button>
          <button
            onClick={() => onModeChange('chord')}
            className={`px-3 py-1 text-xs font-semibold transition-colors ${
              mode === 'chord'
                ? 'bg-sky-500 text-white'
                : 'bg-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            Chord
          </button>
        </div>

        {/* Definition dropdown */}
        <select
          value={selectedDefinition?.name ?? ''}
          onChange={(e) => {
            const found = definitions.find((d) => d.name === e.target.value)
            onDefinitionChange(found ?? null)
          }}
          className="bg-slate-700 text-slate-300 text-sm rounded px-2 py-1 outline-none border border-slate-600"
        >
          <option value="">
            {mode === 'scale' ? 'Select scale...' : 'Select chord...'}
          </option>
          {definitions.map((def) => (
            <option key={def.name} value={def.name}>
              {def.name}
            </option>
          ))}
        </select>

        {/* Clear button */}
        {(selectedRoot || selectedDefinition) && (
          <button
            onClick={handleClear}
            className="text-xs text-slate-500 hover:text-slate-300 ml-auto"
          >
            Clear
          </button>
        )}
      </div>

      {/* Root note buttons */}
      <div className="flex gap-1 flex-wrap">
        {CHROMATIC_SCALE.map((note) => {
          const isSelected = selectedRoot === note
          return (
            <button
              key={note}
              onClick={() => onRootChange(isSelected ? null : note)}
              className={`w-9 h-7 rounded text-xs font-semibold transition-colors ${
                isSelected
                  ? 'bg-sky-500 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600 hover:text-slate-200'
              }`}
            >
              {note}
            </button>
          )
        })}
      </div>
    </div>
  )
}
