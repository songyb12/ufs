import { useRef, useEffect, useCallback, useState } from 'react'
import { BpmSlider } from './BpmSlider'
import { TapTempo, QuickTempos } from './TapTempo'
import { MetronomePendulum } from './MetronomePendulum'
import { TempoTrainer } from './TempoTrainer'
import type { ClickSound, Subdivision, AccentLevel } from '../../utils/audioScheduler'

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
  accentPattern: AccentLevel[] | null
  onAccentPatternChange: (pattern: AccentLevel[] | null) => void
  beatFlash?: boolean
  onBeatFlashChange?: (enabled: boolean) => void
  volume?: number
  onVolumeChange?: (vol: number) => void
}

/**
 * Beat dot with CSS scale pulse animation.
 * Click to cycle accent level: normal(1) → accent(2) → ghost(0) → normal(1).
 */
function BeatDot({
  active,
  isDownbeat,
  accentLevel,
  onClick,
}: {
  active: boolean
  isDownbeat: boolean
  accentLevel: AccentLevel
  onClick?: () => void
}) {
  const dotRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (active && dotRef.current) {
      dotRef.current.classList.remove('animate-beat-pulse')
      void dotRef.current.offsetWidth
      dotRef.current.classList.add('animate-beat-pulse')
    }
  }, [active])

  // Size based on accent level: ghost=small, normal=medium, accent=large
  const sizeClass = accentLevel === 0
    ? 'w-2.5 h-2.5'
    : accentLevel === 2
      ? 'w-5 h-5'
      : 'w-4 h-4'

  const baseColor = active
    ? accentLevel === 2
      ? 'bg-orange-500 shadow-orange-500/50 shadow-lg'
      : accentLevel === 0
        ? 'bg-slate-500 shadow-slate-500/30 shadow-sm'
        : 'bg-sky-400 shadow-sky-400/40 shadow-md'
    : accentLevel === 2
      ? 'bg-slate-600'
      : accentLevel === 0
        ? 'bg-slate-800 border border-slate-700'
        : 'bg-slate-700'

  return (
    <div
      ref={dotRef}
      onClick={onClick}
      className={`${sizeClass} rounded-full transition-colors duration-75 cursor-pointer ${baseColor}`}
      title={`Accent: ${accentLevel === 2 ? 'strong' : accentLevel === 1 ? 'normal' : 'ghost'} — click to cycle`}
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
  accentPattern,
  onAccentPatternChange,
  beatFlash,
  onBeatFlashChange,
  volume = 0.8,
  onVolumeChange,
}: MetronomePanelProps) {
  // Build effective accent array (default: beat 0 = accent, rest = normal)
  const effectiveAccents: AccentLevel[] = accentPattern
    ?? Array.from({ length: beatsPerMeasure }, (_, i) => (i === 0 ? 2 : 1) as AccentLevel)

  // Cycle accent level on beat dot click: 1 → 2 → 0 → 1
  const cycleAccent = useCallback((beatIndex: number) => {
    const current = effectiveAccents[beatIndex] ?? 1
    const next: AccentLevel = current === 1 ? 2 : current === 2 ? 0 : 1
    const newPattern = effectiveAccents.map((a, i) => (i === beatIndex ? next : a))
    onAccentPatternChange(newPattern)
  }, [effectiveAccents, onAccentPatternChange])

  // Reset accent pattern (back to default)
  const hasCustomAccent = accentPattern !== null
  const [showPendulum, setShowPendulum] = useState(false)

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

      {/* Beat indicator dots (click to cycle accent: normal → strong → ghost) */}
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
            accentLevel={effectiveAccents[i] ?? 1}
            onClick={() => cycleAccent(i)}
          />
        ))}
        {hasCustomAccent && (
          <button
            onClick={() => onAccentPatternChange(null)}
            className="text-[10px] text-slate-500 hover:text-slate-300 ml-1"
            title="Reset accent pattern to default"
          >
            Reset
          </button>
        )}
      </div>

      {/* Pendulum animation */}
      {showPendulum && (
        <MetronomePendulum bpm={bpm} isPlaying={isPlaying} currentBeat={currentBeat} />
      )}

      {/* Quick tempo presets */}
      <QuickTempos currentBpm={bpm} onSelect={setBpm} />

      {/* BPM slider + options row */}
      <div className="flex items-center gap-2">
        <div className="flex-1">
          <BpmSlider bpm={bpm} onChange={setBpm} />
        </div>
        <button
          onClick={() => setShowPendulum((v) => !v)}
          className={`px-2 py-1 rounded text-xs font-semibold transition-colors border whitespace-nowrap ${
            showPendulum
              ? 'border-sky-500/50 bg-sky-500/20 text-sky-400'
              : 'border-slate-600 bg-slate-700 text-slate-500 hover:text-slate-300'
          }`}
          title="Show animated pendulum"
        >
          Pendulum
        </button>
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
        {onBeatFlashChange && (
          <button
            onClick={() => onBeatFlashChange(!beatFlash)}
            className={`px-2 py-1 rounded text-xs font-semibold transition-colors border whitespace-nowrap ${
              beatFlash
                ? 'border-orange-500/50 bg-orange-500/20 text-orange-400'
                : 'border-slate-600 bg-slate-700 text-slate-500 hover:text-slate-300'
            }`}
            title="Flash screen border on each beat"
          >
            Flash
          </button>
        )}
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
        {onVolumeChange && (
          <>
            <span className="text-slate-700 mx-0.5">|</span>
            <span className="text-xs text-slate-500">Vol:</span>
            <input
              type="range"
              min={0}
              max={100}
              value={Math.round(volume * 100)}
              onChange={(e) => onVolumeChange(Number(e.target.value) / 100)}
              className="w-16 h-1 accent-sky-500"
              title={`Volume: ${Math.round(volume * 100)}%`}
            />
            <span className="text-[10px] text-slate-500 tabular-nums w-7 text-right">
              {Math.round(volume * 100)}%
            </span>
          </>
        )}
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

      {/* Tempo Trainer */}
      <TempoTrainer
        currentBpm={bpm}
        setBpm={setBpm}
        isPlaying={isPlaying}
        currentMeasure={currentMeasure}
      />
    </div>
  )
}
