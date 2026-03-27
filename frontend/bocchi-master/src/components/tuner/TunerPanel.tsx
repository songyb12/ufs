import { useState, useRef, useCallback, useEffect } from 'react'
import type { InstrumentConfig, NoteName } from '../../types/music'
import { CHROMATIC_SCALE } from '../../constants/notes'
import { detectPitch, frequencyToNote } from '../../utils/pitchDetector'
import { getSharedAudioContext } from '../../utils/audioContextSingleton'

interface TunerPanelProps {
  instrument: InstrumentConfig
}

interface TunerReading {
  frequency: number
  noteName: NoteName
  octave: number
  cents: number
  targetString: number | null  // index of nearest string, or null
}

/** Map ±50 cents to a visual bar offset (-100% to +100% from center) */
function centsToBarPercent(cents: number): number {
  return Math.max(-100, Math.min(100, cents * 2))
}

function centsColor(absCents: number): string {
  if (absCents <= 5) return 'text-emerald-400'
  if (absCents <= 10) return 'text-sky-400'
  if (absCents <= 25) return 'text-amber-400'
  return 'text-rose-400'
}

function centsBgColor(absCents: number): string {
  if (absCents <= 5) return 'bg-emerald-500'
  if (absCents <= 10) return 'bg-sky-500'
  if (absCents <= 25) return 'bg-amber-500'
  return 'bg-rose-500'
}

export function TunerPanel({ instrument }: TunerPanelProps) {
  const [expanded, setExpanded] = useState(true)
  const [listening, setListening] = useState(false)
  const [reading, setReading] = useState<TunerReading | null>(null)
  const [error, setError] = useState<string | null>(null)

  const startingRef = useRef(false)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const rafRef = useRef<number>(0)
  const bufferRef = useRef<Float32Array | null>(null)

  const findNearestString = useCallback((midi: number): number | null => {
    let bestIdx: number | null = null
    let bestDist = Infinity
    for (let i = 0; i < instrument.tuning.length; i++) {
      const d = Math.abs(midi - instrument.tuning[i].midiNumber)
      if (d < bestDist) {
        bestDist = d
        bestIdx = i
      }
    }
    // Only highlight if within 3 semitones of a string
    return bestDist <= 3 ? bestIdx : null
  }, [instrument.tuning])

  const analyze = useCallback(() => {
    const analyser = analyserRef.current
    const buffer = bufferRef.current
    if (!analyser || !buffer) return

    analyser.getFloatTimeDomainData(buffer as Float32Array<ArrayBuffer>)

    // Check signal level (skip if too quiet)
    let rms = 0
    for (let i = 0; i < buffer.length; i++) rms += buffer[i] * buffer[i]
    rms = Math.sqrt(rms / buffer.length)

    if (rms < 0.01) {
      setReading(null)
      rafRef.current = requestAnimationFrame(analyze)
      return
    }

    const freq = detectPitch(buffer, audioCtxRef.current!.sampleRate)
    if (freq && freq > 50 && freq < 1200) {
      const { midi, cents } = frequencyToNote(freq)
      const noteIdx = ((midi % 12) + 12) % 12
      const noteName = CHROMATIC_SCALE[noteIdx]
      const octave = Math.floor(midi / 12) - 1
      const targetString = findNearestString(midi)
      setReading({ frequency: freq, noteName, octave, cents, targetString })
    } else {
      setReading(null)
    }

    rafRef.current = requestAnimationFrame(analyze)
  }, [findNearestString])

  const startListening = useCallback(async () => {
    if (startingRef.current) return
    startingRef.current = true
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      })
      streamRef.current = stream

      // Use shared AudioContext to avoid hitting browser limit (~6 contexts)
      const ctx = await getSharedAudioContext()
      audioCtxRef.current = ctx

      const source = ctx.createMediaStreamSource(stream)
      sourceRef.current = source

      const analyser = ctx.createAnalyser()
      analyser.fftSize = 4096
      analyserRef.current = analyser
      bufferRef.current = new Float32Array(analyser.fftSize)

      source.connect(analyser)
      // Don't connect analyser to destination (no feedback)

      setListening(true)
      rafRef.current = requestAnimationFrame(analyze)
    } catch {
      setError('마이크 접근이 거부되었습니다.')
    } finally {
      startingRef.current = false
    }
  }, [analyze])

  const stopListening = useCallback(() => {
    cancelAnimationFrame(rafRef.current)

    if (sourceRef.current) {
      sourceRef.current.disconnect()
      sourceRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    // Do NOT close the shared AudioContext — other components (metronome, synth) may be using it
    audioCtxRef.current = null
    analyserRef.current = null
    bufferRef.current = null

    setListening(false)
    setReading(null)
  }, [])

  // Cleanup on unmount — use ref so the latest stopListening is called without adding it to deps
  const stopListeningRef = useRef(stopListening)
  stopListeningRef.current = stopListening
  useEffect(() => () => { stopListeningRef.current() }, [])

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full text-xs text-slate-600 hover:text-slate-400 py-1 transition-colors"
      >
        Chromatic Tuner (microphone)...
      </button>
    )
  }

  const absCents = reading ? Math.abs(reading.cents) : 0
  const inTune = reading !== null && absCents <= 5

  return (
    <section className="bg-slate-800 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300">Chromatic Tuner</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={listening ? stopListening : startListening}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              listening
                ? 'bg-rose-500/20 text-rose-400 hover:bg-rose-500/30'
                : 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
            }`}
          >
            {listening ? 'Stop' : 'Start'}
          </button>
          <button
            onClick={() => { stopListening(); setExpanded(false) }}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Collapse
          </button>
        </div>
      </div>

      {/* Error */}
      {error && <p className="text-xs text-rose-400 mb-2">{error}</p>}

      {/* Listening state */}
      {listening && (
        <div className="space-y-3">
          {/* Note display */}
          <div className="text-center">
            {reading ? (
              <>
                <div className={`text-4xl font-bold transition-colors ${centsColor(absCents)}`}>
                  {reading.noteName}
                  <span className="text-lg text-slate-500">{reading.octave}</span>
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {reading.frequency.toFixed(1)} Hz
                </div>
              </>
            ) : (
              <div className="text-2xl text-slate-600">—</div>
            )}
          </div>

          {/* Cents offset bar */}
          <div className="relative h-6 bg-slate-900 rounded-lg overflow-hidden">
            {/* Tick marks */}
            {[-50, -25, 0, 25, 50].map(c => (
              <div
                key={c}
                className={`absolute top-0 bottom-0 w-px ${c === 0 ? 'bg-slate-500' : 'bg-slate-700'}`}
                style={{ left: `${50 + c}%` }}
              />
            ))}
            {/* In-tune zone */}
            <div
              className="absolute top-0 bottom-0 bg-emerald-500/10 border-x border-emerald-500/20"
              style={{ left: '45%', width: '10%' }}
            />
            {/* Needle */}
            {reading && (
              <div
                className={`absolute top-0.5 bottom-0.5 w-2 rounded-full transition-all duration-75 ${centsBgColor(absCents)}`}
                style={{ left: `calc(${50 + centsToBarPercent(reading.cents) / 2}% - 4px)` }}
              />
            )}
            {/* Labels */}
            <span className="absolute left-1 top-0.5 text-[8px] text-slate-600">-50</span>
            <span className="absolute right-1 top-0.5 text-[8px] text-slate-600">+50</span>
          </div>

          {/* Cents readout */}
          {reading && (
            <div className="text-center">
              <span className={`text-sm font-bold ${centsColor(absCents)}`}>
                {reading.cents > 0 ? '+' : ''}{reading.cents} cents
              </span>
              {inTune && (
                <span className="ml-2 text-xs text-emerald-400 font-medium">IN TUNE</span>
              )}
            </div>
          )}

          {/* String indicators */}
          <div className="flex justify-center gap-2">
            {instrument.tuning.map((note, i) => {
              const isTarget = reading?.targetString === i
              return (
                <div
                  key={i}
                  className={`flex flex-col items-center px-2 py-1.5 rounded-lg border transition-all ${
                    isTarget
                      ? inTune
                        ? 'border-emerald-500 bg-emerald-500/15'
                        : 'border-orange-500 bg-orange-500/10'
                      : 'border-slate-700 bg-slate-700/30'
                  }`}
                >
                  <span className={`text-sm font-bold ${
                    isTarget
                      ? inTune ? 'text-emerald-400' : 'text-orange-400'
                      : 'text-slate-500'
                  }`}>
                    {note.name}
                  </span>
                  <span className="text-[9px] text-slate-600">{note.octave}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Idle hint */}
      {!listening && !error && (
        <p className="text-xs text-slate-600">
          Start를 눌러 마이크로 튜닝을 확인하세요. 기타 줄을 하나씩 튕기면 음정이 표시됩니다.
        </p>
      )}
    </section>
  )
}
