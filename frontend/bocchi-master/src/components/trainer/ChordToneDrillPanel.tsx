import { useState, useCallback, useEffect, useRef } from 'react'
import type { NoteName } from '../../types/music'
import { CHROMATIC_SCALE } from '../../constants/notes'

/** Interval labels for chord tones */
const TONE_LABELS: Record<number, string> = {
  0: 'R',
  1: 'b2', 2: '2',
  3: 'b3', 4: '3',
  5: '4',
  6: 'b5', 7: '5', 8: '#5',
  9: '6', 10: 'b7', 11: '7',
}

interface ChordToneTarget {
  noteName: NoteName
  intervalLabel: string
  semitones: number
}

interface DrillStats {
  total: number
  correct: number
  perTone: Record<string, { total: number; correct: number }>
}

interface ChordToneDrillPanelProps {
  /** Current chord root from active progression */
  chordRoot: NoteName | null
  /** Current chord quality (matches CHORDS[].name) */
  chordQuality: string | null
  /** Current chord display name */
  chordName: string | null
  /** Chord tone note names from resolvedChord.notes */
  chordNotes: NoteName[]
  /** Chord intervals (semitones from root) from ChordDefinition */
  chordIntervals: number[]
  /** Whether MIDI is connected */
  midiConnected: boolean
  /** Last MIDI note event */
  lastMidiNote: { note: number; velocity: number } | null
}

const EMPTY_STATS: DrillStats = { total: 0, correct: 0, perTone: {} }

export function ChordToneDrillPanel({
  chordRoot,
  chordName,
  chordNotes,
  chordIntervals,
  midiConnected,
  lastMidiNote,
}: ChordToneDrillPanelProps) {
  const [active, setActive] = useState(false)
  const [stats, setStats] = useState<DrillStats>(EMPTY_STATS)
  const [currentToneIndex, setCurrentToneIndex] = useState(0)
  const [lastResult, setLastResult] = useState<'correct' | 'incorrect' | null>(null)
  const [mode, setMode] = useState<'free' | 'sequence'>('sequence')

  // Build targets from chord intervals
  const targets: ChordToneTarget[] = chordRoot && chordIntervals.length > 0
    ? chordIntervals.map((semi, i) => ({
        noteName: chordNotes[i] ?? CHROMATIC_SCALE[(CHROMATIC_SCALE.indexOf(chordRoot) + semi) % 12],
        intervalLabel: TONE_LABELS[semi] ?? `${semi}st`,
        semitones: semi,
      }))
    : []

  const currentTarget = targets[currentToneIndex] ?? null

  // Reset tone index when chord changes
  const prevChordRef = useRef(chordName)
  useEffect(() => {
    if (chordName !== prevChordRef.current) {
      prevChordRef.current = chordName
      if (active) setCurrentToneIndex(0)
    }
  }, [chordName, active])

  // Evaluate MIDI input
  const lastProcessedRef = useRef<{ note: number; time: number } | null>(null)
  useEffect(() => {
    if (!active || !lastMidiNote || targets.length === 0) return

    // Deduplicate same note event
    if (
      lastProcessedRef.current &&
      lastProcessedRef.current.note === lastMidiNote.note &&
      Date.now() - lastProcessedRef.current.time < 100
    ) return
    lastProcessedRef.current = { note: lastMidiNote.note, time: Date.now() }

    const playedName = CHROMATIC_SCALE[lastMidiNote.note % 12]

    if (mode === 'sequence') {
      // Must play the specific target tone
      const isCorrect = currentTarget !== null && playedName === currentTarget.noteName
      const label = currentTarget?.intervalLabel ?? 'R'

      setLastResult(isCorrect ? 'correct' : 'incorrect')
      setStats(prev => {
        const toneStat = prev.perTone[label] ?? { total: 0, correct: 0 }
        return {
          total: prev.total + 1,
          correct: prev.correct + (isCorrect ? 1 : 0),
          perTone: {
            ...prev.perTone,
            [label]: {
              total: toneStat.total + 1,
              correct: toneStat.correct + (isCorrect ? 1 : 0),
            },
          },
        }
      })

      if (isCorrect) {
        // Advance to next tone
        setCurrentToneIndex(i => (i + 1) % targets.length)
      }
    } else {
      // Free mode: any chord tone counts
      const matchedIdx = targets.findIndex(t => t.noteName === playedName)
      const isCorrect = matchedIdx >= 0
      const label = matchedIdx >= 0 ? targets[matchedIdx].intervalLabel : 'miss'

      setLastResult(isCorrect ? 'correct' : 'incorrect')
      setStats(prev => {
        if (!isCorrect) return { ...prev, total: prev.total + 1 }
        const toneStat = prev.perTone[label] ?? { total: 0, correct: 0 }
        return {
          total: prev.total + 1,
          correct: prev.correct + 1,
          perTone: {
            ...prev.perTone,
            [label]: { total: toneStat.total + 1, correct: toneStat.correct + 1 },
          },
        }
      })
    }
  }, [lastMidiNote, active, targets, currentTarget, mode])

  const handleToggle = useCallback(() => {
    setActive(prev => {
      if (!prev) {
        setStats(EMPTY_STATS)
        setCurrentToneIndex(0)
        setLastResult(null)
      }
      return !prev
    })
  }, [])

  const handleReset = useCallback(() => {
    setStats(EMPTY_STATS)
    setCurrentToneIndex(0)
    setLastResult(null)
  }, [])

  const accuracy = stats.total > 0 ? Math.round((stats.correct / stats.total) * 100) : 0
  const hasChord = chordRoot !== null && targets.length > 0

  return (
    <section className="bg-slate-800 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300">
          Chord Tone Drill
        </h3>
        <button
          onClick={handleToggle}
          disabled={!hasChord}
          className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
            active
              ? 'bg-rose-500/20 text-rose-400 hover:bg-rose-500/30'
              : hasChord
                ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
                : 'bg-slate-700 text-slate-600 cursor-not-allowed'
          }`}
        >
          {active ? 'Stop' : 'Start'}
        </button>
      </div>

      {/* No chord message */}
      {!hasChord && !active && (
        <p className="text-xs text-slate-600">
          코드 진행을 선택하면 해당 코드의 구성음(R, 3, 5, 7)을 순서대로 연습할 수 있습니다.
        </p>
      )}

      {/* Settings (when inactive) */}
      {!active && hasChord && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Mode:</span>
            {(['sequence', 'free'] as const).map(m => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                  mode === m
                    ? 'bg-sky-500/20 text-sky-400 ring-1 ring-sky-500/40'
                    : 'bg-slate-700 text-slate-500 hover:text-slate-300'
                }`}
              >
                {m === 'sequence' ? 'R→3→5→7' : 'Free'}
              </button>
            ))}
          </div>
          <p className="text-[10px] text-slate-600">
            {mode === 'sequence'
              ? '루트부터 순서대로 코드톤을 연주하세요.'
              : '아무 코드톤이나 자유롭게 연주하세요.'}
          </p>
          {!midiConnected && (
            <p className="text-[10px] text-amber-500/80">
              MIDI 기기를 연결하면 자동 채점됩니다.
            </p>
          )}
        </div>
      )}

      {/* Active drill */}
      {active && hasChord && (
        <div className="space-y-3">
          {/* Current chord display */}
          <div className="text-center">
            <span className="text-xs text-slate-500">Current chord</span>
            <div className="text-xl font-bold text-white">{chordName}</div>
          </div>

          {/* Chord tone buttons / targets */}
          <div className="flex justify-center gap-2">
            {targets.map((t, i) => {
              const isCurrent = mode === 'sequence' && i === currentToneIndex
              const toneAcc = stats.perTone[t.intervalLabel]
              const hitCount = toneAcc?.correct ?? 0

              return (
                <div
                  key={`${t.noteName}-${i}`}
                  className={`flex flex-col items-center px-3 py-2 rounded-lg border-2 transition-all ${
                    isCurrent
                      ? 'border-orange-500 bg-orange-500/15 scale-110'
                      : hitCount > 0
                        ? 'border-emerald-500/30 bg-emerald-500/5'
                        : 'border-slate-600 bg-slate-700/50'
                  }`}
                >
                  <span className={`text-lg font-bold ${
                    isCurrent ? 'text-orange-400' : hitCount > 0 ? 'text-emerald-400' : 'text-slate-300'
                  }`}>
                    {t.noteName}
                  </span>
                  <span className={`text-[10px] font-medium ${
                    isCurrent ? 'text-orange-500/70' : 'text-slate-500'
                  }`}>
                    {t.intervalLabel}
                  </span>
                  {hitCount > 0 && (
                    <span className="text-[9px] text-emerald-500/60 mt-0.5">
                      {hitCount}x
                    </span>
                  )}
                </div>
              )
            })}
          </div>

          {/* Feedback */}
          {lastResult && (
            <div className="flex justify-center">
              <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                lastResult === 'correct'
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-rose-500/20 text-rose-400'
              }`}>
                {lastResult === 'correct' ? 'HIT' : 'MISS'}
              </span>
            </div>
          )}

          {/* Stats bar */}
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-3">
              <span className={`font-bold ${
                accuracy >= 80 ? 'text-emerald-400' : accuracy >= 50 ? 'text-amber-400' : 'text-rose-400'
              }`}>
                {accuracy}%
              </span>
              <span className="text-slate-500">
                {stats.correct}/{stats.total}
              </span>
            </div>
            <button
              onClick={handleReset}
              className="text-slate-600 hover:text-slate-400 transition-colors"
            >
              Reset
            </button>
          </div>

          {/* Per-tone breakdown */}
          {Object.keys(stats.perTone).length > 0 && (
            <div className="flex gap-2 flex-wrap">
              {targets.map(t => {
                const s = stats.perTone[t.intervalLabel]
                if (!s) return null
                const pct = s.total > 0 ? Math.round((s.correct / s.total) * 100) : 0
                return (
                  <span
                    key={t.intervalLabel}
                    className={`text-[10px] px-1.5 py-0.5 rounded ${
                      pct >= 80 ? 'bg-emerald-500/10 text-emerald-400'
                        : pct >= 50 ? 'bg-amber-500/10 text-amber-400'
                        : 'bg-rose-500/10 text-rose-400'
                    }`}
                  >
                    {t.intervalLabel}: {pct}%
                  </span>
                )
              })}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
