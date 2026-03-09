import { useRef, useEffect } from 'react'
import { BpmSlider } from './BpmSlider'
import { TapTempo } from './TapTempo'
import type { ClickSound, Subdivision } from '../../utils/audioScheduler'

/** Standard tempo marking for a given BPM */
function getTempoMarking(bpm: number): string {
  if (bpm < 45) return 'Grave'
  if (bpm < 60) return 'Largo'
  if (bpm < 66) return 'Larghetto'
  if (bpm < 76) return 'Adagio'
  if (bpm < 92) return 'Andante'
  if (bpm < 108) return 'Moderato'
  if (bpm < 120) return 'Allegretto'
  if (bpm < 156) return 'Allegro'
  if (bpm < 176) return 'Vivace'
  if (bpm < 200) return 'Presto'
  return 'Prestissimo'
}

const CLICK_SOUNDS: { value: ClickSound; label: string }[] = [
  { value: 'sine', label: 'Sine' },
  { value: 'wood', label: 'Wood' },
  { value: 'hihat', label: 'Hi-hat' },
  { value: 'rimshot', label: 'Rim' },
]

const SUBDIVISIONS: { value: Subdivision; label: string; icon: string }[] = [
  { value: 1, label: 'Quarter', icon: '♩' },
  { value: 2, label: '8th', icon: '♪♪' },
  { value: 3, label: 'Triplet', icon: '♪³' },
  { value: 4, label: '16th', icon: '♬' },
]

export interface MetronomePanelProps {
  bpm: number
  setBpm: (bpm: number) => void
  isPlaying: boolean
  toggle: () => void
  currentBeat: number
  currentMeasure: number
  beatsPerMeasure: number
  setBeatsPerMeasure: (beats: number) => void
  countIn: boolean
  onCountInChange: (enabled: boolean) => void
  isCountingIn: boolean
  clickSound: ClickSound
  onClickSoundChange: (sound: ClickSound) => void
  subdivision: Subdivision
  onSubdivisionChange: (sub: Subdivision) => void
  swing: number
  onSwingChange: (amount: number) => void
}

/**
 * Beat dot with CSS scale pulse animation.
 */
function BeatDot({ active, isDownbeat }: { active: boolean; isDownbeat: boolean }) {
  const dotRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (active && dotRef.current) {
      dotRef.current.classList.remove('animate-beat-pulse')
      void dotRef.current.offsetWidth
      dotRef.current.classList.add('animate-beat-pulse')
    }
  }, [active])

  const baseColor = active
    ? isDownbeat
      ? 'bg-orange-500 shadow-orange-500/50 shadow-lg'
      : 'bg-sky-400 shadow-sky-400/40 shadow-md'
    : 'bg-slate-700'

  return (
    <div
      ref={dotRef}
      className={`w-4 h-4 rounded-full transition-colors duration-75 ${baseColor}`}
    />
  )
}

export function MetronomePanel({
  bpm,
  setBpm,
  isPlaying,
  toggle,
  currentBeat,
  currentMeasure,
  beatsPerMeasure,
  setBeatsPerMeasure,
  countIn,
  onCountInChange,
  isCountingIn,
  clickSound,
  onClickSoundChange,
  subdivision,
  onSubdivisionChange,
  swing,
  onSwingChange,
}: MetronomePanelProps) {
  return (
    <div className="bg-slate-800 rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Metronome
        </h2>

        <div className="flex items-center gap-2">
          {/* Measure counter */}
          {isPlaying && (
            <span className="text-xs text-slate-500 tabular-nums">
              m.{currentMeasure + 1}
            </span>
          )}

          {/* Time signature selector */}
          <select
            value={beatsPerMeasure}
            onChange={(e) => setBeatsPerMeasure(Number(e.target.value))}
            className="bg-slate-700 text-slate-300 text-sm rounded px-2 py-1 outline-none"
          >
            <option value={2}>2/4</option>
            <option value={3}>3/4</option>
            <option value={4}>4/4</option>
            <option value={5}>5/4</option>
            <option value={6}>6/8</option>
            <option value={7}>7/8</option>
          </select>
        </div>
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
          <div className="text-[10px] text-slate-500 italic -mt-0.5">
            {getTempoMarking(bpm)}
          </div>
        </div>

        <TapTempo onTempoDetected={setBpm} />
      </div>

      {/* Beat indicator dots */}
      <div className="flex gap-2 justify-center items-center">
        {isCountingIn && (
          <span className="text-xs text-amber-400 font-semibold mr-1 animate-beat-pulse">
            Count-in
          </span>
        )}
        {Array.from({ length: beatsPerMeasure }, (_, i) => (
          <BeatDot
            key={i}
            active={currentBeat === i}
            isDownbeat={i === 0}
          />
        ))}
      </div>

      {/* BPM slider + options row */}
      <div className="flex items-center gap-2">
        <div className="flex-1">
          <BpmSlider bpm={bpm} onChange={setBpm} />
        </div>
        <button
          onClick={() => onCountInChange(!countIn)}
          className={`px-2 py-1 rounded text-xs font-semibold transition-colors border whitespace-nowrap ${
            countIn
              ? 'border-amber-500/50 bg-amber-500/20 text-amber-400'
              : 'border-slate-600 bg-slate-700 text-slate-500 hover:text-slate-300'
          }`}
          title="1-bar count-in before playback starts"
        >
          Count-in
        </button>
      </div>

      {/* Click sound selector */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-slate-500">Sound:</span>
        {CLICK_SOUNDS.map((s) => (
          <button
            key={s.value}
            onClick={() => onClickSoundChange(s.value)}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              clickSound === s.value
                ? 'bg-sky-500/20 text-sky-400 ring-1 ring-sky-500/40'
                : 'bg-slate-700 text-slate-500 hover:text-slate-300'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Subdivision selector */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-slate-500">Subdivision:</span>
        {SUBDIVISIONS.map((s) => (
          <button
            key={s.value}
            onClick={() => onSubdivisionChange(s.value)}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              subdivision === s.value
                ? 'bg-violet-500/20 text-violet-400 ring-1 ring-violet-500/40'
                : 'bg-slate-700 text-slate-500 hover:text-slate-300'
            }`}
            title={s.label}
          >
            {s.icon}
          </button>
        ))}
        {/* Swing control (only shown for subdivisions >= 2) */}
        {subdivision >= 2 && (
          <>
            <span className="text-slate-700 mx-0.5">|</span>
            <span className="text-xs text-slate-500">Swing:</span>
            <input
              type="range"
              min={0}
              max={100}
              value={swing}
              onChange={(e) => onSwingChange(Number(e.target.value))}
              className="w-16 h-1 accent-violet-500"
              title={`Swing: ${swing}%`}
            />
            <span className="text-[10px] text-slate-500 tabular-nums w-7 text-right">
              {swing}%
            </span>
          </>
        )}
      </div>
    </div>
  )
}
