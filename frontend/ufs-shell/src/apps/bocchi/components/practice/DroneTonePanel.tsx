import { useState, useRef, useCallback, useEffect } from 'react'
import type { NoteName } from '../../types/music'
import { CHROMATIC_SCALE } from '../../constants/notes'
import { getSharedAudioContext } from '../../utils/audioContextSingleton'

const WAVEFORMS: { value: OscillatorType; label: string }[] = [
  { value: 'sine', label: 'Sine' },
  { value: 'triangle', label: 'Tri' },
  { value: 'sawtooth', label: 'Saw' },
]

const OCTAVES = [2, 3, 4, 5]

/** Convert note name + octave to frequency (A4 = 440 Hz) */
function noteToFreq(name: NoteName, octave: number): number {
  const idx = CHROMATIC_SCALE.indexOf(name)
  const midi = (octave + 1) * 12 + idx
  return 440 * Math.pow(2, (midi - 69) / 12)
}

/**
 * Drone/reference tone player.
 * Plays a sustained note for tuning or practicing against a tonal center.
 */
export function DroneTonePanel({ activeRoot }: { activeRoot?: NoteName | null }) {
  const [expanded, setExpanded] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [note, setNote] = useState<NoteName>('A')
  const [octave, setOctave] = useState(3)
  const [waveform, setWaveform] = useState<OscillatorType>('sine')
  const [volume, setVolume] = useState(0.3)

  const oscRef = useRef<OscillatorNode | null>(null)
  const gainRef = useRef<GainNode | null>(null)
  const ctxRef = useRef<AudioContext | null>(null)

  // Sync with active root from progression/scale
  useEffect(() => {
    if (activeRoot && !playing) setNote(activeRoot)
  }, [activeRoot, playing])

  const startDrone = useCallback(async () => {
    const ctx = await getSharedAudioContext()
    ctxRef.current = ctx

    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = waveform
    osc.frequency.value = noteToFreq(note, octave)
    gain.gain.value = volume
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()

    oscRef.current = osc
    gainRef.current = gain
    setPlaying(true)
  }, [waveform, note, octave, volume])

  const stopDrone = useCallback(() => {
    if (oscRef.current && gainRef.current) {
      // Fade out to avoid click
      gainRef.current.gain.exponentialRampToValueAtTime(
        0.001,
        (ctxRef.current?.currentTime ?? 0) + 0.05,
      )
      const osc = oscRef.current
      setTimeout(() => { try { osc.stop() } catch { /* already stopped */ } }, 60)
    }
    oscRef.current = null
    gainRef.current = null
    setPlaying(false)
  }, [])

  // Update live params while playing
  useEffect(() => {
    if (oscRef.current) {
      oscRef.current.frequency.value = noteToFreq(note, octave)
    }
  }, [note, octave])

  useEffect(() => {
    if (oscRef.current) oscRef.current.type = waveform
  }, [waveform])

  useEffect(() => {
    if (gainRef.current) gainRef.current.gain.value = volume
  }, [volume])

  // Cleanup on unmount
  useEffect(() => () => { stopDrone() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full text-xs text-slate-600 hover:text-slate-400 py-1 transition-colors"
      >
        Drone Tone (reference pitch)...
      </button>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg px-4 py-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Drone Tone
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={playing ? stopDrone : startDrone}
            className={`px-3 py-1 rounded text-xs font-semibold transition-colors ${
              playing
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                : 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
            }`}
          >
            {playing ? 'Stop' : 'Start'}
          </button>
          <button
            onClick={() => { stopDrone(); setExpanded(false) }}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Collapse
          </button>
        </div>
      </div>

      {/* Note + Octave selector */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-xs text-slate-500">Note:</span>
        {CHROMATIC_SCALE.map((n) => (
          <button
            key={n}
            onClick={() => setNote(n)}
            className={`w-7 h-6 rounded text-[10px] font-medium transition-colors ${
              note === n
                ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40'
                : 'bg-slate-700/50 text-slate-600 hover:text-slate-400'
            }`}
          >
            {n}
          </button>
        ))}
        <span className="text-slate-700 mx-0.5">|</span>
        <span className="text-xs text-slate-500">Oct:</span>
        {OCTAVES.map((o) => (
          <button
            key={o}
            onClick={() => setOctave(o)}
            className={`w-6 h-6 rounded text-[10px] font-medium transition-colors ${
              octave === o
                ? 'bg-sky-500/20 text-sky-400 ring-1 ring-sky-500/40'
                : 'bg-slate-700/50 text-slate-600 hover:text-slate-400'
            }`}
          >
            {o}
          </button>
        ))}
      </div>

      {/* Waveform + Volume */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-slate-500">Wave:</span>
        {WAVEFORMS.map((w) => (
          <button
            key={w.value}
            onClick={() => setWaveform(w.value)}
            className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
              waveform === w.value
                ? 'bg-violet-500/20 text-violet-400 ring-1 ring-violet-500/40'
                : 'bg-slate-700/50 text-slate-600 hover:text-slate-400'
            }`}
          >
            {w.label}
          </button>
        ))}
        <span className="text-slate-700 mx-0.5">|</span>
        <span className="text-xs text-slate-500">Vol:</span>
        <input
          type="range"
          min={0}
          max={100}
          value={Math.round(volume * 100)}
          onChange={(e) => setVolume(Number(e.target.value) / 100)}
          className="w-16 h-1 accent-emerald-500"
        />
        <span className="text-[10px] text-slate-500 tabular-nums w-7 text-right">
          {Math.round(volume * 100)}%
        </span>
      </div>

      {/* Frequency display */}
      <div className="text-center text-[10px] text-slate-600">
        {note}{octave} = {noteToFreq(note, octave).toFixed(1)} Hz
      </div>
    </div>
  )
}
