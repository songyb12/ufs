import { useState, useCallback, useRef, forwardRef, useImperativeHandle } from 'react'
import type { NoteName } from '../../types/music'
import { CHROMATIC_SCALE } from '../../constants/notes'

type QuizDifficulty = 'beginner' | 'intermediate' | 'advanced'

const DIFFICULTY_CONFIG: Record<QuizDifficulty, {
  label: string
  description: string
  notes: NoteName[]
  activeClass: string
}> = {
  beginner: {
    label: 'Beginner',
    description: 'Natural notes only (no sharps/flats)',
    notes: ['C', 'D', 'E', 'F', 'G', 'A', 'B'],
    activeClass: 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40',
  },
  intermediate: {
    label: 'Intermediate',
    description: 'All 12 notes',
    notes: [...CHROMATIC_SCALE],
    activeClass: 'bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/40',
  },
  advanced: {
    label: 'Advanced',
    description: 'All 12 notes + timed (5s per answer)',
    notes: [...CHROMATIC_SCALE],
    activeClass: 'bg-rose-500/20 text-rose-400 ring-1 ring-rose-500/40',
  },
}

interface FretboardQuizPanelProps {
  /** Currently active — when true, fretboard clicks are intercepted */
  active: boolean
  onToggle: () => void
}

export interface FretboardQuizHandle {
  checkAnswer: (noteName: NoteName) => boolean
}

interface QuizStats {
  total: number
  correct: number
  streak: number
  bestStreak: number
}

/**
 * Fretboard note identification quiz.
 * Shows a random note name; player must find it on the fretboard.
 */
export const FretboardQuizPanel = forwardRef<FretboardQuizHandle, FretboardQuizPanelProps>(
  function FretboardQuizPanel({ active, onToggle }, ref) {
  const [targetNote, setTargetNote] = useState<NoteName | null>(null)
  const [stats, setStats] = useState<QuizStats>({ total: 0, correct: 0, streak: 0, bestStreak: 0 })
  const [lastResult, setLastResult] = useState<'correct' | 'wrong' | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [difficulty, setDifficulty] = useState<QuizDifficulty>('beginner')
  const [timeLeft, setTimeLeft] = useState<number | null>(null)
  const prevNoteRef = useRef<NoteName | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const difficultyRef = useRef(difficulty)
  difficultyRef.current = difficulty

  const stopTimer = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    setTimeLeft(null)
  }, [])

  const generateNote = useCallback(() => {
    const config = DIFFICULTY_CONFIG[difficultyRef.current]
    let note: NoteName
    do {
      note = config.notes[Math.floor(Math.random() * config.notes.length)]
    } while (note === prevNoteRef.current && config.notes.length > 1)
    prevNoteRef.current = note
    setTargetNote(note)
    setLastResult(null)
    if (difficultyRef.current === 'advanced') {
      stopTimer()
      setTimeLeft(5)
      timerRef.current = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev === null || prev <= 1) {
            setStats((s) => ({ ...s, total: s.total + 1, streak: 0 }))
            setLastResult('wrong')
            setTimeout(() => generateNote(), 400)
            return null
          }
          return prev - 1
        })
      }, 1000)
    }
  }, [stopTimer])

  const handleStart = useCallback(() => {
    setStats({ total: 0, correct: 0, streak: 0, bestStreak: 0 })
    generateNote()
    onToggle()
  }, [generateNote, onToggle])

  const handleStop = useCallback(() => {
    setTargetNote(null)
    setLastResult(null)
    stopTimer()
    onToggle()
  }, [onToggle, stopTimer])

  /** Called from parent when user clicks a note on the fretboard */
  const checkAnswer = useCallback(
    (clickedNote: NoteName): boolean => {
      if (!targetNote) return false
      const isCorrect = clickedNote === targetNote

      setStats((prev) => {
        const newStreak = isCorrect ? prev.streak + 1 : 0
        return {
          total: prev.total + 1,
          correct: prev.correct + (isCorrect ? 1 : 0),
          streak: newStreak,
          bestStreak: Math.max(prev.bestStreak, newStreak),
        }
      })

      setLastResult(isCorrect ? 'correct' : 'wrong')

      if (isCorrect) {
        stopTimer()
        // Move to next note after brief delay
        setTimeout(generateNote, 400)
      }

      return isCorrect
    },
    [targetNote, generateNote],
  )

  // Expose checkAnswer to parent via imperative handle
  useImperativeHandle(ref, () => ({ checkAnswer }), [checkAnswer])

  if (!expanded && !active) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full text-xs text-slate-600 hover:text-slate-400 py-1 transition-colors"
      >
        Fretboard Quiz (note identification)...
      </button>
    )
  }

  const accuracy = stats.total > 0 ? Math.round((stats.correct / stats.total) * 100) : 0

  return (
    <div className="bg-slate-800 rounded-lg px-4 py-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Fretboard Quiz
        </h2>
        <div className="flex items-center gap-2">
          {!active && (
            <div className="flex items-center gap-1">
              {(Object.entries(DIFFICULTY_CONFIG) as [QuizDifficulty, typeof DIFFICULTY_CONFIG[QuizDifficulty]][]).map(([key, cfg]) => (
                <button
                  key={key}
                  onClick={() => setDifficulty(key)}
                  className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors ${
                    difficulty === key
                      ? cfg.activeClass
                      : 'bg-slate-700 text-slate-500 hover:text-slate-300'
                  }`}
                  title={cfg.description}
                >
                  {cfg.label}
                </button>
              ))}
            </div>
          )}
          <button
            onClick={active ? handleStop : handleStart}
            className={`px-3 py-1 rounded text-xs font-semibold transition-colors ${
              active
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                : 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
            }`}
          >
            {active ? 'Stop' : 'Start'}
          </button>
          {!active && (
            <button
              onClick={() => setExpanded(false)}
              className="text-xs text-slate-500 hover:text-slate-300"
            >
              Collapse
            </button>
          )}
        </div>
      </div>

      {active && targetNote && (
        <>
          {/* Target note display */}
          <div className="flex items-center justify-center gap-4 py-2">
            <div className="text-center">
              <div className="text-xs text-slate-500 mb-1">Find this note:</div>
              <div
                className={`text-5xl font-bold tabular-nums transition-colors ${
                  lastResult === 'correct'
                    ? 'text-emerald-400'
                    : lastResult === 'wrong'
                      ? 'text-red-400'
                      : 'text-white'
                }`}
              >
                {targetNote}
              </div>
              {lastResult === 'wrong' && (
                <div className="text-xs text-red-400 mt-1">
                  {timeLeft === null && difficulty === 'advanced' ? "Time's up!" : 'Try again!'}
                </div>
              )}
              {lastResult === 'correct' && (
                <div className="text-xs text-emerald-400 mt-1">Correct!</div>
              )}
              {timeLeft !== null && (
                <div className={`text-sm font-bold mt-1 tabular-nums ${
                  timeLeft <= 2 ? 'text-red-400' : 'text-slate-400'
                }`}>
                  {timeLeft}s
                </div>
              )}
            </div>
          </div>

          {/* Stats */}
          <div className="flex items-center justify-center gap-4 text-xs">
            <span className="text-slate-500">
              Score: <span className="text-slate-300 font-semibold">{stats.correct}/{stats.total}</span>
            </span>
            <span className="text-slate-500">
              Accuracy: <span className="text-slate-300 font-semibold">{accuracy}%</span>
            </span>
            <span className="text-slate-500">
              Streak: <span className="text-amber-400 font-semibold">{stats.streak}</span>
            </span>
            {stats.bestStreak > 0 && (
              <span className="text-slate-500">
                Best: <span className="text-amber-400 font-semibold">{stats.bestStreak}</span>
              </span>
            )}
          </div>

          <p className="text-[10px] text-slate-600 text-center">
            Click the correct note on the fretboard above
          </p>
        </>
      )}

      {!active && expanded && (
        <p className="text-xs text-slate-600 text-center py-1">
          Test your fretboard knowledge! A random note name will appear — find it on the fretboard.
        </p>
      )}
    </div>
  )
})
