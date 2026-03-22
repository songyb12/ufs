/**
 * Call-and-Response Practice Panel
 *
 * The app plays a short melody pattern ("call"), then the user plays it back
 * via MIDI ("response"). Accuracy is scored by comparing MIDI note sequence
 * against the original pattern.
 *
 * Difficulty levels:
 *   - beginner: 3-4 single notes, natural notes, slow tempo
 *   - intermediate: 5-7 notes with rhythm variation, includes sharps/flats
 *   - advanced: 8+ notes, chromatic passages, faster tempo
 */

import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { useAudioContext } from '../../hooks/useAudioContext'
import { playNote, midiNoteToFrequency } from '../../utils/synthEngine'

// ─── Types ──────────────────────────────────────────

type Difficulty = 'beginner' | 'intermediate' | 'advanced'

interface PatternNote {
  midi: number        // MIDI note number
  durationMs: number  // how long the note lasts in playback
}

interface Pattern {
  name: string
  notes: PatternNote[]
  difficulty: Difficulty
}

type Phase = 'idle' | 'listening' | 'responding' | 'result'

interface RoundResult {
  pattern: Pattern
  played: number[]
  correctCount: number
  accuracy: number
}

interface CallResponsePanelProps {
  midiConnected: boolean
  lastMidiNote: { note: number; velocity: number } | null
}

// ─── Pattern Library ────────────────────────────────

const BEGINNER_PATTERNS: Pattern[] = [
  { name: 'C-D-E', difficulty: 'beginner', notes: [
    { midi: 60, durationMs: 500 }, { midi: 62, durationMs: 500 }, { midi: 64, durationMs: 500 },
  ]},
  { name: 'E-D-C', difficulty: 'beginner', notes: [
    { midi: 64, durationMs: 500 }, { midi: 62, durationMs: 500 }, { midi: 60, durationMs: 500 },
  ]},
  { name: 'C-E-G', difficulty: 'beginner', notes: [
    { midi: 60, durationMs: 500 }, { midi: 64, durationMs: 500 }, { midi: 67, durationMs: 500 },
  ]},
  { name: 'G-E-C', difficulty: 'beginner', notes: [
    { midi: 67, durationMs: 500 }, { midi: 64, durationMs: 500 }, { midi: 60, durationMs: 500 },
  ]},
  { name: 'C-D-E-F', difficulty: 'beginner', notes: [
    { midi: 60, durationMs: 450 }, { midi: 62, durationMs: 450 }, { midi: 64, durationMs: 450 }, { midi: 65, durationMs: 450 },
  ]},
  { name: 'G-A-B-C', difficulty: 'beginner', notes: [
    { midi: 67, durationMs: 450 }, { midi: 69, durationMs: 450 }, { midi: 71, durationMs: 450 }, { midi: 72, durationMs: 450 },
  ]},
  { name: 'C-E-D-C', difficulty: 'beginner', notes: [
    { midi: 60, durationMs: 500 }, { midi: 64, durationMs: 500 }, { midi: 62, durationMs: 500 }, { midi: 60, durationMs: 500 },
  ]},
  { name: 'E-G-A-G', difficulty: 'beginner', notes: [
    { midi: 64, durationMs: 500 }, { midi: 67, durationMs: 500 }, { midi: 69, durationMs: 500 }, { midi: 67, durationMs: 500 },
  ]},
]

const INTERMEDIATE_PATTERNS: Pattern[] = [
  { name: 'Am arpeggio up', difficulty: 'intermediate', notes: [
    { midi: 57, durationMs: 400 }, { midi: 60, durationMs: 400 }, { midi: 64, durationMs: 400 },
    { midi: 69, durationMs: 400 }, { midi: 64, durationMs: 400 },
  ]},
  { name: 'G penta lick', difficulty: 'intermediate', notes: [
    { midi: 67, durationMs: 350 }, { midi: 69, durationMs: 350 }, { midi: 71, durationMs: 350 },
    { midi: 67, durationMs: 500 }, { midi: 64, durationMs: 350 }, { midi: 62, durationMs: 500 },
  ]},
  { name: 'Bluesy bend', difficulty: 'intermediate', notes: [
    { midi: 60, durationMs: 300 }, { midi: 63, durationMs: 300 }, { midi: 65, durationMs: 300 },
    { midi: 66, durationMs: 400 }, { midi: 65, durationMs: 300 }, { midi: 63, durationMs: 300 }, { midi: 60, durationMs: 400 },
  ]},
  { name: 'Dm scale down', difficulty: 'intermediate', notes: [
    { midi: 74, durationMs: 350 }, { midi: 72, durationMs: 350 }, { midi: 70, durationMs: 350 },
    { midi: 69, durationMs: 350 }, { midi: 67, durationMs: 350 }, { midi: 65, durationMs: 500 },
  ]},
  { name: 'Em penta', difficulty: 'intermediate', notes: [
    { midi: 64, durationMs: 350 }, { midi: 67, durationMs: 350 }, { midi: 69, durationMs: 350 },
    { midi: 71, durationMs: 350 }, { midi: 76, durationMs: 500 },
  ]},
  { name: 'F maj phrase', difficulty: 'intermediate', notes: [
    { midi: 65, durationMs: 400 }, { midi: 69, durationMs: 300 }, { midi: 72, durationMs: 300 },
    { midi: 69, durationMs: 300 }, { midi: 65, durationMs: 300 }, { midi: 60, durationMs: 500 },
  ]},
]

const ADVANCED_PATTERNS: Pattern[] = [
  { name: 'Chromatic ascend', difficulty: 'advanced', notes: [
    { midi: 60, durationMs: 250 }, { midi: 61, durationMs: 250 }, { midi: 62, durationMs: 250 },
    { midi: 63, durationMs: 250 }, { midi: 64, durationMs: 250 }, { midi: 65, durationMs: 250 },
    { midi: 66, durationMs: 250 }, { midi: 67, durationMs: 350 },
  ]},
  { name: 'Jazz lick 1', difficulty: 'advanced', notes: [
    { midi: 67, durationMs: 250 }, { midi: 65, durationMs: 250 }, { midi: 63, durationMs: 250 },
    { midi: 62, durationMs: 250 }, { midi: 60, durationMs: 250 }, { midi: 63, durationMs: 250 },
    { midi: 65, durationMs: 250 }, { midi: 67, durationMs: 350 },
  ]},
  { name: 'Bebop phrase', difficulty: 'advanced', notes: [
    { midi: 64, durationMs: 200 }, { midi: 66, durationMs: 200 }, { midi: 67, durationMs: 200 },
    { midi: 69, durationMs: 200 }, { midi: 71, durationMs: 200 }, { midi: 72, durationMs: 300 },
    { midi: 71, durationMs: 200 }, { midi: 69, durationMs: 200 }, { midi: 67, durationMs: 300 },
  ]},
  { name: 'Minor sweep', difficulty: 'advanced', notes: [
    { midi: 57, durationMs: 200 }, { midi: 60, durationMs: 200 }, { midi: 64, durationMs: 200 },
    { midi: 69, durationMs: 200 }, { midi: 72, durationMs: 200 }, { midi: 76, durationMs: 300 },
    { midi: 72, durationMs: 200 }, { midi: 69, durationMs: 200 }, { midi: 64, durationMs: 300 },
  ]},
  { name: 'Dorian run', difficulty: 'advanced', notes: [
    { midi: 62, durationMs: 220 }, { midi: 64, durationMs: 220 }, { midi: 65, durationMs: 220 },
    { midi: 67, durationMs: 220 }, { midi: 69, durationMs: 220 }, { midi: 71, durationMs: 220 },
    { midi: 72, durationMs: 220 }, { midi: 74, durationMs: 350 },
  ]},
]

const PATTERN_SETS: Record<Difficulty, Pattern[]> = {
  beginner: BEGINNER_PATTERNS,
  intermediate: INTERMEDIATE_PATTERNS,
  advanced: ADVANCED_PATTERNS,
}

const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  beginner: '초급',
  intermediate: '중급',
  advanced: '고급',
}

const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'] as const

function midiToNoteName(midi: number): string {
  return `${NOTE_NAMES[midi % 12]}${Math.floor(midi / 12) - 1}`
}

// ─── Component ──────────────────────────────────────

export function CallResponsePanel({ midiConnected, lastMidiNote }: CallResponsePanelProps) {
  const [expanded, setExpanded] = useState(false)
  const [difficulty, setDifficulty] = useState<Difficulty>('beginner')
  const [phase, setPhase] = useState<Phase>('idle')
  const [currentPattern, setCurrentPattern] = useState<Pattern | null>(null)
  const [playedNotes, setPlayedNotes] = useState<number[]>([])
  const [currentPlayIndex, setCurrentPlayIndex] = useState(-1)
  const [roundResults, setRoundResults] = useState<RoundResult[]>([])
  const [listenCountdown, setListenCountdown] = useState(0)

  const { ensureResumed } = useAudioContext()
  const playedNotesRef = useRef<number[]>([])
  const lastProcessedRef = useRef<{ note: number; time: number }>({ note: -1, time: 0 })
  const phaseRef = useRef<Phase>('idle')
  phaseRef.current = phase

  // Pick random pattern from current difficulty, avoiding last used
  const lastPatternRef = useRef<string>('')
  const pickPattern = useCallback((): Pattern => {
    const pool = PATTERN_SETS[difficulty]
    let pick: Pattern
    do {
      pick = pool[Math.floor(Math.random() * pool.length)]
    } while (pick.name === lastPatternRef.current && pool.length > 1)
    lastPatternRef.current = pick.name
    return pick
  }, [difficulty])

  // Play pattern through synthEngine
  const playPattern = useCallback(async (pattern: Pattern) => {
    const ctx = await ensureResumed()
    const now = ctx.currentTime
    let offset = 0
    pattern.notes.forEach((n, i) => {
      playNote(ctx, {
        frequency: midiNoteToFrequency(n.midi),
        time: now + offset / 1000,
        duration: n.durationMs / 1000,
        gain: 0.35,
        pluckAttack: true,
      })
      // Highlight current note during playback
      setTimeout(() => {
        if (phaseRef.current === 'listening') setCurrentPlayIndex(i)
      }, offset)
      offset += n.durationMs
    })
    // After pattern finishes → switch to responding
    setTimeout(() => {
      if (phaseRef.current === 'listening') {
        setCurrentPlayIndex(-1)
        setPhase('responding')
      }
    }, offset + 200)
  }, [ensureResumed])

  // Start a round
  const startRound = useCallback(() => {
    const pattern = pickPattern()
    setCurrentPattern(pattern)
    setPlayedNotes([])
    playedNotesRef.current = []
    setCurrentPlayIndex(-1)
    setPhase('listening')
    setListenCountdown(3)
  }, [pickPattern])

  // Countdown before playing
  useEffect(() => {
    if (phase !== 'listening' || listenCountdown <= 0) return
    if (listenCountdown > 0) {
      const timer = setTimeout(() => {
        const next = listenCountdown - 1
        setListenCountdown(next)
        if (next === 0 && currentPattern) {
          playPattern(currentPattern)
        }
      }, 600)
      return () => clearTimeout(timer)
    }
  }, [phase, listenCountdown, currentPattern, playPattern])

  // Process MIDI input during response phase
  useEffect(() => {
    if (phase !== 'responding' || !lastMidiNote || !currentPattern) return

    // Deduplicate within 100ms
    if (
      lastProcessedRef.current.note === lastMidiNote.note &&
      Date.now() - lastProcessedRef.current.time < 100
    ) return
    lastProcessedRef.current = { note: lastMidiNote.note, time: Date.now() }

    const newPlayed = [...playedNotesRef.current, lastMidiNote.note]
    playedNotesRef.current = newPlayed
    setPlayedNotes(newPlayed)

    // Check if we've received enough notes
    if (newPlayed.length >= currentPattern.notes.length) {
      // Score the response
      let correct = 0
      currentPattern.notes.forEach((expected, i) => {
        if (i < newPlayed.length && newPlayed[i] === expected.midi) correct++
      })
      const accuracy = Math.round((correct / currentPattern.notes.length) * 100)

      const result: RoundResult = {
        pattern: currentPattern,
        played: newPlayed,
        correctCount: correct,
        accuracy,
      }
      setRoundResults(prev => [result, ...prev].slice(0, 10))
      setPhase('result')
    }
  }, [lastMidiNote, phase, currentPattern])

  // Replay the current pattern
  const replayPattern = useCallback(async () => {
    if (!currentPattern || phase === 'listening') return
    const ctx = await ensureResumed()
    const now = ctx.currentTime
    let offset = 0
    currentPattern.notes.forEach((n, i) => {
      playNote(ctx, {
        frequency: midiNoteToFrequency(n.midi),
        time: now + offset / 1000,
        duration: n.durationMs / 1000,
        gain: 0.35,
        pluckAttack: true,
      })
      setTimeout(() => setCurrentPlayIndex(i), offset)
      offset += n.durationMs
    })
    setTimeout(() => setCurrentPlayIndex(-1), offset)
  }, [currentPattern, phase, ensureResumed])

  // Cancel current round
  const cancelRound = useCallback(() => {
    setPhase('idle')
    setCurrentPattern(null)
    setPlayedNotes([])
    playedNotesRef.current = []
    setCurrentPlayIndex(-1)
  }, [])

  // Stats
  const stats = useMemo(() => {
    if (roundResults.length === 0) return null
    const avg = Math.round(roundResults.reduce((s, r) => s + r.accuracy, 0) / roundResults.length)
    const perfect = roundResults.filter(r => r.accuracy === 100).length
    return { avg, perfect, total: roundResults.length }
  }, [roundResults])

  const handleToggle = useCallback(() => {
    setExpanded(v => !v)
    if (phase !== 'idle') cancelRound()
  }, [phase, cancelRound])

  return (
    <div className="bg-slate-800/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 overflow-hidden">
      {/* Header */}
      <button
        onClick={handleToggle}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">🎵</span>
          <span className="font-semibold text-white text-sm">콜 앤 리스폰스</span>
          {stats && (
            <span className="text-[10px] text-slate-400 ml-1">
              평균 {stats.avg}% · {stats.total}회
            </span>
          )}
        </div>
        <svg className={`w-4 h-4 text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* MIDI check */}
          {!midiConnected && (
            <div className="text-xs text-amber-400 bg-amber-900/20 rounded-lg px-3 py-2">
              MIDI 컨트롤러를 연결하세요
            </div>
          )}

          {/* Difficulty selector */}
          <div className="flex gap-1.5">
            {(['beginner', 'intermediate', 'advanced'] as Difficulty[]).map(d => (
              <button
                key={d}
                onClick={() => { setDifficulty(d); if (phase !== 'idle') cancelRound() }}
                disabled={phase === 'listening' || phase === 'responding'}
                className={`flex-1 px-2 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  difficulty === d
                    ? 'bg-violet-600 text-white'
                    : 'bg-slate-700 text-slate-400 hover:text-slate-300'
                }`}
              >
                {DIFFICULTY_LABELS[d]}
              </button>
            ))}
          </div>

          {/* Phase: Idle */}
          {phase === 'idle' && (
            <button
              onClick={startRound}
              disabled={!midiConnected}
              className="w-full py-3 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-slate-700 disabled:text-slate-500
                text-white font-bold transition-colors"
            >
              ▶ 패턴 듣기 시작
            </button>
          )}

          {/* Phase: Listening (countdown + playback) */}
          {phase === 'listening' && currentPattern && (
            <div className="text-center space-y-3">
              {listenCountdown > 0 ? (
                <div className="py-4">
                  <div className="text-4xl font-bold text-violet-400 animate-pulse">{listenCountdown}</div>
                  <div className="text-xs text-slate-400 mt-1">잘 들어보세요...</div>
                </div>
              ) : (
                <>
                  <div className="text-xs text-slate-400">🔊 패턴 재생 중...</div>
                  <PatternDisplay
                    pattern={currentPattern}
                    highlightIndex={currentPlayIndex}
                    playedNotes={[]}
                  />
                </>
              )}
              <button onClick={cancelRound} className="text-xs text-slate-500 hover:text-slate-400">
                취소
              </button>
            </div>
          )}

          {/* Phase: Responding */}
          {phase === 'responding' && currentPattern && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-xs text-emerald-400 font-medium">🎸 따라 연주하세요!</div>
                <span className="text-[10px] text-slate-500">
                  {playedNotes.length}/{currentPattern.notes.length}
                </span>
              </div>
              <PatternDisplay
                pattern={currentPattern}
                highlightIndex={-1}
                playedNotes={playedNotes}
              />
              <div className="flex gap-2">
                <button
                  onClick={replayPattern}
                  className="flex-1 px-3 py-2 rounded-lg bg-slate-700 text-slate-400 text-xs hover:bg-slate-600 transition-colors"
                >
                  🔁 다시 듣기
                </button>
                <button
                  onClick={cancelRound}
                  className="px-3 py-2 rounded-lg bg-slate-700 text-slate-500 text-xs hover:bg-slate-600 transition-colors"
                >
                  취소
                </button>
              </div>
            </div>
          )}

          {/* Phase: Result */}
          {phase === 'result' && roundResults[0] && (
            <ResultView
              result={roundResults[0]}
              onNext={startRound}
              onReplay={replayPattern}
              midiConnected={midiConnected}
            />
          )}

          {/* History */}
          {roundResults.length > 1 && (
            <div className="border-t border-slate-700/50 pt-2">
              <div className="text-[10px] text-slate-500 mb-1.5">최근 기록</div>
              <div className="flex gap-1 flex-wrap">
                {roundResults.slice(0, 10).map((r, i) => (
                  <span
                    key={i}
                    className={`text-[10px] px-1.5 py-0.5 rounded ${
                      r.accuracy === 100 ? 'bg-emerald-900/30 text-emerald-400' :
                      r.accuracy >= 70 ? 'bg-blue-900/30 text-blue-400' :
                      r.accuracy >= 40 ? 'bg-amber-900/30 text-amber-400' :
                      'bg-rose-900/30 text-rose-400'
                    }`}
                  >
                    {r.accuracy}%
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Pattern Display ────────────────────────────────

function PatternDisplay({ pattern, highlightIndex, playedNotes }: {
  pattern: Pattern; highlightIndex: number; playedNotes: number[]
}) {
  return (
    <div className="flex gap-1 flex-wrap justify-center">
      {pattern.notes.map((n, i) => {
        const isHighlighted = i === highlightIndex
        const isPlayed = i < playedNotes.length
        const isCorrect = isPlayed && playedNotes[i] === n.midi
        const isWrong = isPlayed && playedNotes[i] !== n.midi

        return (
          <div
            key={i}
            className={`px-2 py-1.5 rounded-lg text-xs font-mono font-medium min-w-[38px] text-center transition-all ${
              isHighlighted ? 'bg-violet-500 text-white scale-110 shadow-lg shadow-violet-500/30' :
              isCorrect ? 'bg-emerald-600/30 text-emerald-400 border border-emerald-500/40' :
              isWrong ? 'bg-rose-600/30 text-rose-400 border border-rose-500/40' :
              isPlayed ? 'bg-slate-600 text-slate-300' :
              'bg-slate-700 text-slate-400'
            }`}
          >
            {isPlayed ? (
              <div>
                <div className={isCorrect ? 'text-emerald-400' : 'text-rose-400'}>
                  {midiToNoteName(playedNotes[i])}
                </div>
                {isWrong && (
                  <div className="text-[8px] text-slate-500 line-through">{midiToNoteName(n.midi)}</div>
                )}
              </div>
            ) : (
              isHighlighted || highlightIndex === -1 && playedNotes.length === 0
                ? midiToNoteName(n.midi)
                : '•'
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── Result View ────────────────────────────────────

function ResultView({ result, onNext, onReplay, midiConnected }: {
  result: RoundResult; onNext: () => void; onReplay: () => void; midiConnected: boolean
}) {
  const emoji = result.accuracy === 100 ? '🎉' : result.accuracy >= 70 ? '👏' : result.accuracy >= 40 ? '💪' : '🔄'

  return (
    <div className="space-y-3">
      <div className="text-center">
        <div className="text-3xl mb-1">{emoji}</div>
        <div className={`text-2xl font-bold font-mono ${
          result.accuracy === 100 ? 'text-emerald-400' :
          result.accuracy >= 70 ? 'text-blue-400' :
          result.accuracy >= 40 ? 'text-amber-400' : 'text-rose-400'
        }`}>
          {result.accuracy}%
        </div>
        <div className="text-[10px] text-slate-500">
          {result.correctCount}/{result.pattern.notes.length} 정답
          {result.accuracy === 100 && ' · Perfect!'}
        </div>
      </div>

      {/* Note-by-note comparison */}
      <PatternDisplay
        pattern={result.pattern}
        highlightIndex={-1}
        playedNotes={result.played}
      />

      <div className="flex gap-2">
        <button
          onClick={onReplay}
          className="flex-1 px-3 py-2 rounded-lg bg-slate-700 text-slate-400 text-xs hover:bg-slate-600 transition-colors"
        >
          🔁 다시 듣기
        </button>
        <button
          onClick={onNext}
          disabled={!midiConnected}
          className="flex-1 px-3 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:bg-slate-700
            disabled:text-slate-500 text-white text-xs font-medium transition-colors"
        >
          다음 패턴 →
        </button>
      </div>
    </div>
  )
}
