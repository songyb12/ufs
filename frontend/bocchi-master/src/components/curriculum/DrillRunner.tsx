/**
 * DrillRunner — 드릴 실행 화면
 *
 * DrillType에 따라 인터랙티브 컴포넌트를 임베드하거나 셀프 평가로 폴백.
 * - fretboard-quiz → 인라인 노트 퀴즈 (다지선다)
 * - ear-training → useIntervalTrainer 훅 직접 활용
 * - chord-change, strum-pattern 등 → 강화된 셀프 평가
 */

import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import type { Drill, DrillScore, DrillType } from '../../data/curriculum'
import { useIntervalTrainer } from '../../hooks/useIntervalTrainer'
import { INTERVAL_SETS, INTERVAL_SHORT, INTERVAL_NAMES } from '../../utils/intervalTrainer'
import { adaptDrillConfig, TIER_LABELS, TIER_COLORS, TIER_ICONS, type AdaptedDrill } from '../../utils/adaptiveDifficulty'

// ─── Types ──────────────────────────────────────────

interface DrillRunnerProps {
  drill: Drill
  bestScore?: DrillScore
  onComplete: (drillId: string, score: DrillScore) => void
  onCancel: () => void
}

type Phase = 'ready' | 'running' | 'result'

interface DrillResult {
  accuracy: number
  elapsedSeconds: number
  details?: string
}

// ─── Interactive drill types (auto-scored) ──────────
const INTERACTIVE_TYPES: Set<DrillType> = new Set(['fretboard-quiz', 'ear-training'])

function isInteractive(type: DrillType): boolean {
  return INTERACTIVE_TYPES.has(type)
}

// ─── Main Component ─────────────────────────────────

export function DrillRunner({ drill, bestScore, onComplete, onCancel }: DrillRunnerProps) {
  const [phase, setPhase] = useState<Phase>('ready')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [result, setResult] = useState<DrillResult | null>(null)
  const [attemptCount, setAttemptCount] = useState(0)

  // Adaptive difficulty: compute adapted config from historical performance
  const adapted = useMemo<AdaptedDrill>(
    () => adaptDrillConfig(drill, bestScore),
    [drill, bestScore],
  )
  const adaptedDrill = useMemo<Drill>(
    () => ({ ...drill, config: adapted.config }),
    [drill, adapted.config],
  )
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startTimeRef = useRef(0)

  // Timer
  useEffect(() => {
    if (phase === 'running') {
      startTimeRef.current = Date.now()
      timerRef.current = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000))
      }, 1000)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [phase])

  const startDrill = useCallback(() => {
    setPhase('running')
    setElapsedSeconds(0)
    setResult(null)
    setAttemptCount(prev => prev + 1)
  }, [])

  const finishDrill = useCallback((accuracy: number, details?: string) => {
    if (timerRef.current) clearInterval(timerRef.current)
    const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000)

    const drillResult: DrillResult = { accuracy, elapsedSeconds: elapsed, details }
    setResult(drillResult)
    setPhase('result')
  }, [])

  const confirmResult = useCallback(() => {
    if (!result) return
    const score: DrillScore = {
      accuracy: result.accuracy,
      completedAt: new Date().toISOString(),
      attempts: attemptCount,
    }
    onComplete(drill.id, score)
  }, [drill.id, result, onComplete, attemptCount])

  const retryDrill = useCallback(() => {
    setPhase('ready')
    setElapsedSeconds(0)
    setResult(null)
  }, [])

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onCancel()
      } else if (e.key === 'Enter' || e.key === ' ') {
        if (phase === 'ready') {
          e.preventDefault()
          startDrill()
        } else if (phase === 'result') {
          e.preventDefault()
          confirmResult()
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [phase, onCancel, startDrill, confirmResult])

  // Improvement tracking
  const improvement = result && bestScore
    ? result.accuracy - bestScore.accuracy
    : null
  const isNewRecord = improvement !== null && improvement > 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <DrillHeader
        drill={drill}
        phase={phase}
        elapsedSeconds={elapsedSeconds}
        formatTime={formatTime}
        onCancel={onCancel}
      />

      {/* Ready Phase */}
      {phase === 'ready' && (
        <ReadyScreen drill={adaptedDrill} bestScore={bestScore} adapted={adapted} onStart={startDrill} />
      )}

      {/* Running Phase */}
      {phase === 'running' && (
        <RunningPhase drill={adaptedDrill} onFinish={finishDrill} />
      )}

      {/* Result Phase */}
      {phase === 'result' && result && (
        <ResultScreen
          drill={drill}
          result={result}
          bestScore={bestScore}
          improvement={improvement}
          isNewRecord={isNewRecord}
          formatTime={formatTime}
          attemptCount={attemptCount}
          onConfirm={confirmResult}
          onRetry={retryDrill}
        />
      )}
    </div>
  )
}

// ─── Drill Header ───────────────────────────────────

function DrillHeader({
  drill, phase, elapsedSeconds, formatTime, onCancel,
}: {
  drill: Drill; phase: Phase; elapsedSeconds: number
  formatTime: (s: number) => string; onCancel: () => void
}) {
  return (
    <div className="flex items-center gap-3">
      <button
        onClick={onCancel}
        className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
      <div className="flex-1">
        <h2 className="text-lg font-bold text-white">{drill.title}</h2>
        <p className="text-sm text-slate-400">{drill.description}</p>
      </div>
      {phase === 'running' && (
        <div className="text-right">
          <div className="text-lg font-mono text-orange-400">{formatTime(elapsedSeconds)}</div>
          <div className="text-xs text-slate-400">경과 시간</div>
        </div>
      )}
    </div>
  )
}

// ─── Ready Screen ───────────────────────────────────

const TYPE_ICONS: Record<string, string> = {
  'chord-change': '🔄', 'strum-pattern': '🎶', 'arpeggio': '🌊',
  'scale-run': '🎼', 'fretboard-quiz': '🧠', 'rhythm': '🥁',
  'ear-training': '👂', 'song-section': '🎵', 'voicing-match': '🎸',
  'progression-play': '🎹',
}

const TYPE_DESCRIPTIONS: Record<string, string> = {
  'chord-change': '아래 코드들을 메트로놈에 맞춰 전환 연습하세요',
  'strum-pattern': '스트럼 패턴을 따라 연습하세요',
  'arpeggio': '코드를 아르페지오로 연주하세요',
  'scale-run': '스케일을 지판 위에서 연주하세요',
  'fretboard-quiz': '지판의 음이름을 맞춰보세요',
  'rhythm': '리듬 패턴을 정확하게 따라하세요',
  'ear-training': '들리는 음정을 맞춰보세요',
  'song-section': '곡의 지정된 구간을 연습하세요',
  'voicing-match': '코드 다이어그램을 보고 정확히 짚으세요',
  'progression-play': '코드 진행을 따라 연주하세요',
}

function ReadyScreen({ drill, bestScore, adapted, onStart }: {
  drill: Drill; bestScore?: DrillScore; adapted: AdaptedDrill; onStart: () => void
}) {
  return (
    <div className="bg-slate-800 rounded-xl p-6 text-center space-y-4">
      <div className="text-5xl mb-2">{TYPE_ICONS[drill.type] ?? '🎸'}</div>
      <h3 className="text-xl font-bold text-white">{drill.title}</h3>
      <p className="text-slate-400">{TYPE_DESCRIPTIONS[drill.type] ?? drill.description}</p>

      {isInteractive(drill.type) && (
        <div className="text-xs text-blue-400 bg-blue-900/20 rounded-lg px-3 py-2">
          이 드릴은 자동 채점됩니다
        </div>
      )}

      {/* Adaptive difficulty badge */}
      {adapted.changes.length > 0 && (
        <div className={`rounded-lg px-3 py-2 border text-left ${TIER_COLORS[adapted.tier]}`}>
          <div className="flex items-center gap-1.5 text-xs font-medium mb-1">
            <span>{TIER_ICONS[adapted.tier]}</span>
            <span>적응형 난이도: {TIER_LABELS[adapted.tier]}</span>
          </div>
          <div className="text-[10px] opacity-80 space-y-0.5">
            {adapted.changes.map((change, i) => (
              <div key={i}>• {change}</div>
            ))}
          </div>
        </div>
      )}

      {/* Drill Config Display */}
      <div className="bg-slate-700/50 rounded-lg p-4 text-left space-y-2">
        {drill.config.chords && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">코드:</span>
            <div className="flex gap-1.5 flex-wrap">
              {drill.config.chords.map((chord, i) => (
                <span key={i} className="px-2 py-0.5 bg-slate-600 rounded text-sm text-white font-mono">
                  {chord}
                </span>
              ))}
            </div>
          </div>
        )}
        {drill.config.bpm && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">BPM:</span>
            <span className="text-sm text-white font-mono">{drill.config.bpm}</span>
          </div>
        )}
        {drill.config.scaleName && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">스케일:</span>
            <span className="text-sm text-white">{drill.config.rootNote} {drill.config.scaleName}</span>
          </div>
        )}
        {drill.config.progressionName && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">진행:</span>
            <span className="text-sm text-white">{drill.config.progressionName}</span>
          </div>
        )}
        <div className="flex items-center gap-4 pt-1 border-t border-slate-600">
          <span className="text-xs text-slate-500">예상 시간: ~{drill.estimatedMinutes}분</span>
          <span className="text-xs text-orange-400">보상: +{drill.xpReward} XP</span>
        </div>
      </div>

      {/* Best Score */}
      {bestScore && (
        <div className="bg-slate-700/30 rounded-lg p-3 flex items-center justify-between">
          <span className="text-xs text-slate-400">최고 기록</span>
          <span className="text-sm font-bold text-green-400">{bestScore.accuracy}%</span>
        </div>
      )}

      {/* Pass Criteria */}
      <div className="bg-slate-700/30 rounded-lg p-3 text-left">
        <h4 className="text-xs text-slate-400 mb-1">통과 조건</h4>
        <div className="flex flex-wrap gap-2">
          {drill.passCriteria.minAccuracy != null && (
            <span className="text-xs bg-slate-700 px-2 py-1 rounded text-slate-300">
              정확도 ≥{drill.passCriteria.minAccuracy}%
            </span>
          )}
          {drill.passCriteria.minBpm != null && (
            <span className="text-xs bg-slate-700 px-2 py-1 rounded text-slate-300">
              BPM ≥{drill.passCriteria.minBpm}
            </span>
          )}
          {drill.passCriteria.minCompletions != null && (
            <span className="text-xs bg-slate-700 px-2 py-1 rounded text-slate-300">
              반복 ≥{drill.passCriteria.minCompletions}회
            </span>
          )}
          {drill.passCriteria.minCorrectStreak != null && (
            <span className="text-xs bg-slate-700 px-2 py-1 rounded text-slate-300">
              연속 정답 ≥{drill.passCriteria.minCorrectStreak}
            </span>
          )}
        </div>
      </div>

      <button
        onClick={onStart}
        className="w-full py-3 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-bold text-lg transition-colors"
      >
        ▶ 드릴 시작
      </button>
    </div>
  )
}

// ─── Running Phase Router ───────────────────────────

function RunningPhase({ drill, onFinish }: {
  drill: Drill; onFinish: (accuracy: number, details?: string) => void
}) {
  switch (drill.type) {
    case 'fretboard-quiz':
      return <FretboardQuizDrill drill={drill} onFinish={onFinish} />
    case 'ear-training':
      return <EarTrainingDrill onFinish={onFinish} />
    default:
      return <SelfAssessmentDrill drill={drill} onFinish={onFinish} />
  }
}

// ─── Fretboard Quiz Drill (Inline) ──────────────────

const NATURAL_NOTES = ['C', 'D', 'E', 'F', 'G', 'A', 'B'] as const
const ALL_NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'] as const

function FretboardQuizDrill({ drill, onFinish }: {
  drill: Drill; onFinish: (accuracy: number, details?: string) => void
}) {
  const difficulty = drill.config.quizDifficulty ?? 'beginner'
  const notePool = difficulty === 'beginner' ? NATURAL_NOTES : ALL_NOTES
  const totalQuestions = 10

  const [questionIndex, setQuestionIndex] = useState(0)
  const [correct, setCorrect] = useState(0)
  const [targetNote, setTargetNote] = useState(() => notePool[Math.floor(Math.random() * notePool.length)])
  const [feedback, setFeedback] = useState<'correct' | 'wrong' | null>(null)
  const [streak, setStreak] = useState(0)
  const [bestStreak, setBestStreak] = useState(0)
  const prevNote = useRef(targetNote)

  const generateNext = useCallback(() => {
    let note: typeof targetNote
    do {
      note = notePool[Math.floor(Math.random() * notePool.length)]
    } while (note === prevNote.current && notePool.length > 1)
    prevNote.current = note
    setTargetNote(note)
    setFeedback(null)
  }, [notePool])

  // Compute choices deterministically from targetNote — useMemo triggers re-render on change
  const choices = useMemo(() => {
    const pool = [...notePool].filter(n => n !== targetNote)
    const distractors: string[] = []
    while (distractors.length < Math.min(3, pool.length)) {
      const idx = Math.floor(Math.random() * pool.length)
      distractors.push(pool.splice(idx, 1)[0])
    }
    return [targetNote, ...distractors].sort(() => Math.random() - 0.5)
  }, [targetNote, notePool])

  const handleAnswer = useCallback((note: string) => {
    if (feedback !== null) return
    const isCorrect = note === targetNote
    setFeedback(isCorrect ? 'correct' : 'wrong')

    const newCorrect = correct + (isCorrect ? 1 : 0)
    const newStreak = isCorrect ? streak + 1 : 0
    setCorrect(newCorrect)
    setStreak(newStreak)
    if (newStreak > bestStreak) setBestStreak(newStreak)

    const nextIdx = questionIndex + 1
    if (nextIdx >= totalQuestions) {
      const accuracy = Math.round((newCorrect / totalQuestions) * 100)
      setTimeout(() => onFinish(accuracy, `${newCorrect}/${totalQuestions} 정답`), 600)
    } else {
      setTimeout(() => {
        setQuestionIndex(nextIdx)
        generateNext()
      }, 500)
    }
  }, [feedback, targetNote, correct, streak, bestStreak, questionIndex, totalQuestions, onFinish, generateNext])

  const progress = Math.round(((questionIndex) / totalQuestions) * 100)

  return (
    <div className="space-y-4">
      {/* Progress bar */}
      <div className="bg-slate-700 rounded-full h-2">
        <div className="bg-blue-500 h-2 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>

      <div className="bg-slate-800 rounded-xl p-6 text-center">
        {/* Stats */}
        <div className="flex items-center justify-center gap-4 text-xs text-slate-400 mb-4">
          <span>문제 {questionIndex + 1}/{totalQuestions}</span>
          <span>정답 {correct}</span>
          <span className="text-amber-400">연속 {streak}</span>
        </div>

        {/* Target note */}
        <div className="text-xs text-slate-400 mb-2">이 음은 지판의 어디에 있을까요?</div>
        <div className={`text-6xl font-bold mb-6 transition-colors ${
          feedback === 'correct' ? 'text-green-400' :
          feedback === 'wrong' ? 'text-red-400' : 'text-white'
        }`}>
          {targetNote}
        </div>

        {feedback === 'correct' && <div className="text-green-400 text-sm mb-4">정답!</div>}
        {feedback === 'wrong' && <div className="text-red-400 text-sm mb-4">오답 — 정답은 {targetNote}</div>}

        {/* Answer buttons */}
        <div className="grid grid-cols-2 gap-3">
          {choices.map(note => (
            <button
              key={note}
              onClick={() => handleAnswer(note)}
              disabled={feedback !== null}
              className={`py-4 rounded-xl text-xl font-bold transition-all ${
                feedback !== null && note === targetNote
                  ? 'bg-green-600/30 border-2 border-green-500 text-green-400'
                  : feedback === 'wrong' && note !== targetNote
                    ? 'bg-slate-700/50 text-slate-500'
                    : 'bg-slate-700 hover:bg-slate-600 text-white border-2 border-transparent'
              }`}
            >
              {note}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Ear Training Drill ─────────────────────────────

function EarTrainingDrill({ onFinish }: {
  onFinish: (accuracy: number, details?: string) => void
}) {
  const trainer = useIntervalTrainer()
  const totalQuestions = 10
  const startedRef = useRef(false)
  const finishedRef = useRef(false)

  // Auto-start on mount — empty deps: trainer reference changes every render (new object),
  // so [trainer] would call stop() on every re-render (timer ticks every second).
  useEffect(() => {
    if (!startedRef.current) {
      startedRef.current = true
      trainer.start().catch(console.error)
    }
    return () => { trainer.stop() }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-finish after N questions
  useEffect(() => {
    if (trainer.stats.total >= totalQuestions && !finishedRef.current) {
      finishedRef.current = true
      const accuracy = Math.round(trainer.stats.accuracy * 100)
      setTimeout(() => onFinish(accuracy, `${trainer.stats.correct}/${trainer.stats.total} 정답`), 800)
    }
  }, [trainer.stats.total, trainer.stats.accuracy, trainer.stats.correct, onFinish])

  const progress = Math.round((trainer.stats.total / totalQuestions) * 100)
  const currentSet = INTERVAL_SETS[trainer.setIndex]

  return (
    <div className="space-y-4">
      {/* Progress bar */}
      <div className="bg-slate-700 rounded-full h-2">
        <div className="bg-purple-500 h-2 rounded-full transition-all duration-300" style={{ width: `${Math.min(progress, 100)}%` }} />
      </div>

      <div className="bg-slate-800 rounded-xl p-6">
        {/* Stats */}
        <div className="flex items-center justify-center gap-4 text-xs text-slate-400 mb-4">
          <span>문제 {Math.min(trainer.stats.total + 1, totalQuestions)}/{totalQuestions}</span>
          <span>정답 {trainer.stats.correct}</span>
          {trainer.stats.total > 0 && (
            <span className={trainer.stats.accuracy >= 0.8 ? 'text-green-400' : trainer.stats.accuracy >= 0.5 ? 'text-yellow-400' : 'text-red-400'}>
              {Math.round(trainer.stats.accuracy * 100)}%
            </span>
          )}
        </div>

        {/* Question display */}
        {trainer.question && (
          <div className="text-center mb-4">
            <div className="text-xs text-slate-400 mb-2">
              {trainer.question.direction === 'ascending' ? '↑ 상행' : '↓ 하행'} —{' '}
              <span className="text-white font-mono">{trainer.question.rootNote}</span>에서
            </div>

            {trainer.revealed && trainer.lastAnswer && (
              <div className="mb-3">
                <span className={`text-lg font-bold ${trainer.lastAnswer.correct ? 'text-green-400' : 'text-red-400'}`}>
                  {trainer.lastAnswer.correct ? '✓ ' : '✗ '}
                  {INTERVAL_NAMES[trainer.question.semitones]}
                </span>
                {!trainer.lastAnswer.correct && (
                  <div className="text-xs text-slate-500 mt-0.5">
                    선택: {INTERVAL_NAMES[trainer.lastAnswer.semitones]}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Answer buttons */}
        {!trainer.revealed && currentSet && (
          <div className="grid grid-cols-3 gap-2 mb-4">
            {currentSet.intervals.map((semitones) => (
              <button
                key={semitones}
                onClick={() => trainer.answer(semitones)}
                className="px-2 py-3 rounded-lg bg-slate-700 text-slate-300 text-sm font-medium
                  hover:bg-purple-500/20 hover:text-purple-300 transition-colors active:bg-purple-500/40"
              >
                {INTERVAL_SHORT[semitones]}
              </button>
            ))}
          </div>
        )}

        {/* Controls */}
        <div className="flex gap-2">
          <button
            onClick={trainer.replay}
            className="flex-1 px-3 py-2 rounded-lg bg-slate-700 text-slate-400 text-sm
              hover:bg-slate-600 hover:text-slate-300 transition-colors"
          >
            🔁 다시 듣기
          </button>
          {trainer.revealed && (
            <button
              onClick={trainer.next}
              className="flex-1 px-3 py-2 rounded-lg bg-purple-600/30 text-purple-400 text-sm
                ring-1 ring-purple-500/40 hover:bg-purple-600/40 transition-colors"
            >
              다음 →
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Self-Assessment Drill (Fallback) ───────────────

function SelfAssessmentDrill({ drill, onFinish }: {
  drill: Drill; onFinish: (accuracy: number, details?: string) => void
}) {
  return (
    <div className="space-y-4">
      <div className="bg-slate-800 rounded-xl p-6">
        <div className="text-center mb-6">
          <p className="text-slate-400 mb-2">{TYPE_DESCRIPTIONS[drill.type]}</p>
          {drill.config.chords && (
            <div className="flex justify-center gap-3 flex-wrap mb-4">
              {drill.config.chords.map((chord, i) => (
                <span key={i} className="px-4 py-2 bg-slate-700 rounded-lg text-lg text-white font-mono font-bold">
                  {chord}
                </span>
              ))}
            </div>
          )}
          {drill.config.progressionName && (
            <div className="text-lg text-orange-300 font-medium mb-4">
              {drill.config.progressionName}
              {drill.config.key && ` (Key: ${drill.config.key})`}
            </div>
          )}
          {drill.config.bpm && (
            <div className="text-3xl font-mono text-orange-400 mb-2">
              ♩ = {drill.config.bpm}
            </div>
          )}
        </div>

        {/* Tool shortcuts for non-interactive drills */}
        <ToolShortcuts drillType={drill.type} />
      </div>

      {/* Self-Assessment */}
      <div className="bg-slate-800 rounded-xl p-4">
        <h4 className="font-medium text-white mb-3">연습을 마쳤나요? 자기 평가를 해주세요:</h4>
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => onFinish(60, '자기 평가: 어려웠음')}
            className="py-3 rounded-lg bg-yellow-600/20 border border-yellow-600/30 hover:bg-yellow-600/30 text-yellow-400 font-medium"
          >
            😅 어려웠음
          </button>
          <button
            onClick={() => onFinish(80, '자기 평가: 괜찮았음')}
            className="py-3 rounded-lg bg-blue-600/20 border border-blue-600/30 hover:bg-blue-600/30 text-blue-400 font-medium"
          >
            😊 괜찮았음
          </button>
          <button
            onClick={() => onFinish(95, '자기 평가: 완벽함')}
            className="py-3 rounded-lg bg-green-600/20 border border-green-600/30 hover:bg-green-600/30 text-green-400 font-medium"
          >
            😎 완벽함!
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Tool Shortcuts ─────────────────────────────────

const TOOL_HINTS: Record<string, { label: string; icon: string; tip: string }> = {
  'chord-change': { label: '코드 전환 타이머', icon: '⏱️', tip: '자유 연습 모드에서 코드 전환 타이머를 사용해보세요' },
  'strum-pattern': { label: '스트럼 패턴', icon: '🎶', tip: '자유 연습 모드에서 스트럼 패턴 뷰어를 사용해보세요' },
  'scale-run': { label: '스케일 패턴', icon: '🎼', tip: '자유 연습 모드에서 스케일 패턴 오버레이를 사용해보세요' },
  'rhythm': { label: '메트로놈', icon: '🥁', tip: '자유 연습 모드에서 메트로놈을 활용하세요' },
  'arpeggio': { label: '아르페지오 패턴', icon: '🌊', tip: '코드 보이싱을 확인하며 연습하세요' },
  'song-section': { label: '곡 연습', icon: '🎵', tip: '해당 곡의 구간을 반복 연습하세요' },
  'voicing-match': { label: '코드 보이싱', icon: '🎸', tip: '코드 다이어그램을 참고하세요' },
  'progression-play': { label: '코드 진행', icon: '🎹', tip: '메트로놈과 함께 연습하세요' },
}

function ToolShortcuts({ drillType }: { drillType: DrillType }) {
  const hint = TOOL_HINTS[drillType]
  if (!hint) return null

  return (
    <div className="bg-slate-700/50 rounded-lg p-4 text-center text-sm text-slate-300">
      <div className="flex items-center justify-center gap-2 mb-2">
        <span className="text-lg">{hint.icon}</span>
        <span className="font-medium">{hint.label}</span>
      </div>
      <p className="text-xs text-slate-400">{hint.tip}</p>
    </div>
  )
}

// ─── Result Screen ──────────────────────────────────

function ResultScreen({
  drill, result, bestScore, improvement, isNewRecord, formatTime, attemptCount, onConfirm, onRetry,
}: {
  drill: Drill; result: DrillResult; bestScore?: DrillScore
  improvement: number | null; isNewRecord: boolean
  formatTime: (s: number) => string; attemptCount: number
  onConfirm: () => void; onRetry: () => void
}) {
  const passed = drill.passCriteria.minAccuracy != null
    ? result.accuracy >= drill.passCriteria.minAccuracy
    : result.accuracy >= 60

  return (
    <div className="bg-slate-800 rounded-xl p-6 text-center space-y-4">
      {/* Result icon */}
      <div className="text-5xl">
        {isNewRecord ? '🏆' : passed ? '✅' : '💪'}
      </div>

      <h3 className="text-xl font-bold text-white">
        {isNewRecord ? '기록 갱신!' : passed ? '드릴 통과!' : '다시 도전!'}
      </h3>

      {/* Score */}
      <div className={`text-5xl font-bold font-mono ${
        result.accuracy >= 90 ? 'text-green-400' :
        result.accuracy >= 70 ? 'text-blue-400' :
        result.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'
      }`}>
        {result.accuracy}%
      </div>

      {/* Details grid */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-slate-700/50 rounded-lg p-3">
          <div className="text-xs text-slate-400">소요 시간</div>
          <div className="text-lg font-mono text-white">{formatTime(result.elapsedSeconds)}</div>
        </div>
        <div className="bg-slate-700/50 rounded-lg p-3">
          <div className="text-xs text-slate-400">보상</div>
          <div className="text-lg font-bold text-orange-400">+{drill.xpReward} XP</div>
        </div>
      </div>

      {/* Details */}
      {result.details && (
        <div className="text-sm text-slate-400">{result.details}</div>
      )}

      {/* Improvement vs best score */}
      {bestScore && improvement !== null && (
        <div className={`rounded-lg p-3 ${
          isNewRecord ? 'bg-green-900/20 border border-green-700/40' : 'bg-slate-700/30'
        }`}>
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-400">이전 최고</span>
            <span className="text-slate-300">{bestScore.accuracy}%</span>
          </div>
          <div className="flex items-center justify-between text-sm mt-1">
            <span className="text-slate-400">변화</span>
            <span className={improvement > 0 ? 'text-green-400 font-bold' : improvement < 0 ? 'text-red-400' : 'text-slate-400'}>
              {improvement > 0 ? '+' : ''}{improvement}%
              {isNewRecord && ' 🎉'}
            </span>
          </div>
        </div>
      )}

      {/* Pass criteria result */}
      {drill.passCriteria.minAccuracy != null && (
        <div className={`text-xs px-3 py-1.5 rounded-full inline-block ${
          passed ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
        }`}>
          {passed ? '✓' : '✗'} 통과 기준: {drill.passCriteria.minAccuracy}%
        </div>
      )}

      {/* Attempt counter */}
      {attemptCount > 1 && (
        <div className="text-xs text-slate-500">
          이번 세션 시도 횟수: {attemptCount}회
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-3">
        <button
          onClick={onRetry}
          className="flex-1 py-3 rounded-xl bg-slate-700 hover:bg-slate-600 text-slate-300 font-bold text-lg transition-colors"
        >
          다시 도전
        </button>
        <button
          onClick={onConfirm}
          className="flex-1 py-3 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-bold text-lg transition-colors"
        >
          완료
        </button>
      </div>
    </div>
  )
}
