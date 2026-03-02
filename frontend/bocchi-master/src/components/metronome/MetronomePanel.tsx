import { BpmSlider } from './BpmSlider'
import { TapTempo } from './TapTempo'

export interface MetronomePanelProps {
  bpm: number
  setBpm: (bpm: number) => void
  isPlaying: boolean
  toggle: () => void
  currentBeat: number
  beatsPerMeasure: number
  setBeatsPerMeasure: (beats: number) => void
}

export function MetronomePanel({
  bpm,
  setBpm,
  isPlaying,
  toggle,
  currentBeat,
  beatsPerMeasure,
  setBeatsPerMeasure,
}: MetronomePanelProps) {
  return (
    <div className="bg-slate-800 rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Metronome
        </h2>

        {/* Time signature selector */}
        <select
          value={beatsPerMeasure}
          onChange={(e) => setBeatsPerMeasure(Number(e.target.value))}
          className="bg-slate-700 text-slate-300 text-sm rounded px-2 py-1 outline-none"
        >
          <option value={3}>3/4</option>
          <option value={4}>4/4</option>
          <option value={6}>6/8</option>
        </select>
      </div>

      {/* BPM display + play button */}
      <div className="flex items-center gap-4">
        <button
          onClick={toggle}
          className={`w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold transition-colors ${
            isPlaying
              ? 'bg-orange-500 hover:bg-orange-600 text-white'
              : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
          }`}
          aria-label={isPlaying ? 'Stop metronome' : 'Start metronome'}
        >
          {isPlaying ? '■' : '▶'}
        </button>

        <div className="text-center">
          <span className="text-4xl font-bold text-white tabular-nums">
            {bpm}
          </span>
          <span className="text-sm text-slate-500 ml-1">BPM</span>
        </div>

        <TapTempo onTempoDetected={setBpm} />
      </div>

      {/* Beat indicator dots */}
      <div className="flex gap-2 justify-center">
        {Array.from({ length: beatsPerMeasure }, (_, i) => (
          <div
            key={i}
            className={`w-4 h-4 rounded-full transition-colors ${
              currentBeat === i
                ? i === 0
                  ? 'bg-orange-500'
                  : 'bg-sky-400'
                : 'bg-slate-700'
            }`}
          />
        ))}
      </div>

      {/* BPM slider */}
      <BpmSlider bpm={bpm} onChange={setBpm} />
    </div>
  )
}
