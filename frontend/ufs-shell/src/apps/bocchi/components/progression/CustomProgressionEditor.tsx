import { memo, useState } from 'react'
import { MAJOR_DEGREES, type ProgressionStep } from '../../utils/chordProgression'
import { CHORDS } from '../../utils/scaleCalculator'

interface CustomProgressionEditorProps {
  steps: ProgressionStep[]
  onStepsChange: (steps: ProgressionStep[]) => void
}

const QUALITIES = CHORDS.map((c) => c.name)

export const CustomProgressionEditor = memo(function CustomProgressionEditor({
  steps,
  onStepsChange,
}: CustomProgressionEditorProps) {
  const [showAdd, setShowAdd] = useState(false)

  const addStep = (degreeIndex: number, qualityOverride?: string) => {
    onStepsChange([...steps, { degreeIndex, qualityOverride }])
    setShowAdd(false)
  }

  const removeStep = (index: number) => {
    onStepsChange(steps.filter((_, i) => i !== index))
  }

  const moveStep = (from: number, to: number) => {
    if (to < 0 || to >= steps.length) return
    const next = [...steps]
    const [item] = next.splice(from, 1)
    next.splice(to, 0, item)
    onStepsChange(next)
  }

  const updateQuality = (index: number, quality: string | undefined) => {
    const next = [...steps]
    next[index] = { ...next[index], qualityOverride: quality }
    onStepsChange(next)
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Step list */}
      <div className="flex flex-wrap gap-1.5">
        {steps.map((step, i) => {
          const degree = MAJOR_DEGREES[step.degreeIndex]
          const label = step.qualityOverride
            ? `${degree.label}(${step.qualityOverride})`
            : degree.label
          return (
            <div
              key={i}
              className="flex items-center gap-0.5 bg-slate-700 rounded px-1.5 py-1 group"
            >
              <button
                onClick={() => moveStep(i, i - 1)}
                className="text-[10px] text-slate-500 hover:text-slate-300 opacity-0 group-hover:opacity-100"
                title="Move left"
              >
                ◀
              </button>
              <div className="flex flex-col items-center">
                <span className="text-xs font-medium text-slate-200">{label}</span>
                <select
                  value={step.qualityOverride ?? ''}
                  onChange={(e) =>
                    updateQuality(i, e.target.value || undefined)
                  }
                  className="bg-transparent text-[9px] text-slate-500 border-none outline-none cursor-pointer w-14 text-center"
                >
                  <option value="">default</option>
                  {QUALITIES.map((q) => (
                    <option key={q} value={q}>{q}</option>
                  ))}
                </select>
              </div>
              <button
                onClick={() => moveStep(i, i + 1)}
                className="text-[10px] text-slate-500 hover:text-slate-300 opacity-0 group-hover:opacity-100"
                title="Move right"
              >
                ▶
              </button>
              <button
                onClick={() => removeStep(i)}
                className="text-[10px] text-red-500/60 hover:text-red-400 ml-0.5 opacity-0 group-hover:opacity-100"
                title="Remove"
              >
                ×
              </button>
            </div>
          )
        })}

        {/* Add button */}
        <button
          onClick={() => setShowAdd((v) => !v)}
          className="px-2 py-1 rounded border border-dashed border-slate-600 text-xs text-slate-500 hover:text-slate-300 hover:border-slate-400 transition-colors"
        >
          +
        </button>
      </div>

      {/* Degree picker */}
      {showAdd && (
        <div className="flex flex-wrap gap-1 bg-slate-900/50 rounded p-2">
          {MAJOR_DEGREES.map((d, i) => (
            <button
              key={i}
              onClick={() => addStep(i)}
              className="px-2 py-1 rounded bg-slate-700 text-xs text-slate-300 hover:bg-slate-600 transition-colors"
            >
              {d.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
})
