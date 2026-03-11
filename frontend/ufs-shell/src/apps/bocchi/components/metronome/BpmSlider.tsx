interface BpmSliderProps {
  bpm: number
  onChange: (bpm: number) => void
}

export function BpmSlider({ bpm, onChange }: BpmSliderProps) {
  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => onChange(bpm - 1)}
        className="w-8 h-8 rounded bg-slate-700 hover:bg-slate-600 text-white font-bold"
      >
        -
      </button>

      <input
        type="range"
        min={40}
        max={240}
        value={bpm}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 h-2 accent-orange-500"
      />

      <button
        onClick={() => onChange(bpm + 1)}
        className="w-8 h-8 rounded bg-slate-700 hover:bg-slate-600 text-white font-bold"
      >
        +
      </button>
    </div>
  )
}
