interface BpmSliderProps {
  bpm: number
  onChange: (bpm: number) => void
}

export function BpmSlider({ bpm, onChange }: BpmSliderProps) {
  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => onChange(Math.max(20, bpm - 1))}
        className="w-8 h-8 rounded bg-slate-700 hover:bg-slate-600 text-white font-bold"
        aria-label="Decrease BPM"
      >
        -
      </button>

      <input
        type="range"
        min={20}
        max={300}
        value={bpm}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 h-2 accent-orange-500"
        aria-label={`BPM: ${bpm}`}
        aria-valuemin={20}
        aria-valuemax={300}
        aria-valuenow={bpm}
      />

      <button
        onClick={() => onChange(Math.min(300, bpm + 1))}
        className="w-8 h-8 rounded bg-slate-700 hover:bg-slate-600 text-white font-bold"
        aria-label="Increase BPM"
      >
        +
      </button>
    </div>
  )
}
