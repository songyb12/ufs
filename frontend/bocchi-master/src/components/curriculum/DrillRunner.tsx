/**
 * DrillRunner — 드릴 실행 화면
 *
 * 드릴 타입에 따라 적절한 기존 컴포넌트를 조합하여 드릴을 실행.
 * 완료 시 점수를 계산하고 콜백.
 *
 * Phase 1에서는 간단한 인터페이스만 구현하고,
 * 기존 컴포넌트와의 깊은 통합은 Phase 2+에서 진행.
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import type { Drill, DrillScore } from '../../data/curriculum'

interface DrillRunnerProps {
  drill: Drill
  onComplete: (drillId: string, score: DrillScore) => void
  onCancel: () => void
}

export function DrillRunner({ drill, onComplete, onCancel }: DrillRunnerProps) {
  const [phase, setPhase] = useState<'ready' | 'running' | 'complete'>('ready')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [attempts, setAttempts] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startTimeRef = useRef<number>(0)

  // Timer
  useEffect(() => {
    if (phase === 'running') {
      startTimeRef.current = Date.now()
      timerRef.current = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000))
      }, 1000)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [phase])

  const startDrill = useCallback(() => {
    setPhase('running')
    setElapsedSeconds(0)
    setAttempts(0)
  }, [])

  const completeDrill = useCallback((finalAccuracy: number) => {
    if (timerRef.current) clearInterval(timerRef.current)
    setPhase('complete')

    const score: DrillScore = {
      accuracy: finalAccuracy,
      completedAt: new Date().toISOString(),
      attempts: attempts + 1,
    }
    onComplete(drill.id, score)
  }, [drill.id, attempts, onComplete])

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const typeDescriptions: Record<string, string> = {
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

  return (
    <div className="space-y-6">
      {/* Header */}
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

      {/* Ready Phase */}
      {phase === 'ready' && (
        <div className="bg-slate-800 rounded-xl p-6 text-center space-y-4">
          <div className="text-5xl mb-2">
            {drill.type === 'chord-change' ? '🔄' :
              drill.type === 'fretboard-quiz' ? '🧠' :
              drill.type === 'ear-training' ? '👂' :
              drill.type === 'progression-play' ? '🎹' :
              drill.type === 'strum-pattern' ? '🎶' : '🎸'}
          </div>
          <h3 className="text-xl font-bold text-white">{drill.title}</h3>
          <p className="text-slate-400">{typeDescriptions[drill.type] ?? drill.description}</p>

          {/* Drill Config Display */}
          <div className="bg-slate-700/50 rounded-lg p-4 text-left space-y-2">
            {drill.config.chords && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">코드:</span>
                <div className="flex gap-1.5">
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

          {/* Pass Criteria */}
          <div className="bg-slate-700/30 rounded-lg p-3 text-left">
            <h4 className="text-xs text-slate-400 mb-1">통과 조건</h4>
            <div className="flex flex-wrap gap-2">
              {drill.passCriteria.minAccuracy && (
                <span className="text-xs bg-slate-700 px-2 py-1 rounded text-slate-300">
                  정확도 ≥{drill.passCriteria.minAccuracy}%
                </span>
              )}
              {drill.passCriteria.minBpm && (
                <span className="text-xs bg-slate-700 px-2 py-1 rounded text-slate-300">
                  BPM ≥{drill.passCriteria.minBpm}
                </span>
              )}
              {drill.passCriteria.minCompletions && (
                <span className="text-xs bg-slate-700 px-2 py-1 rounded text-slate-300">
                  반복 ≥{drill.passCriteria.minCompletions}회
                </span>
              )}
              {drill.passCriteria.minCorrectStreak && (
                <span className="text-xs bg-slate-700 px-2 py-1 rounded text-slate-300">
                  연속 정답 ≥{drill.passCriteria.minCorrectStreak}
                </span>
              )}
            </div>
          </div>

          <button
            onClick={startDrill}
            className="w-full py-3 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-bold text-lg transition-colors"
          >
            ▶ 드릴 시작
          </button>
        </div>
      )}

      {/* Running Phase — 기존 컴포넌트 연동 영역 */}
      {phase === 'running' && (
        <div className="space-y-4">
          <div className="bg-slate-800 rounded-xl p-6">
            <div className="text-center mb-6">
              <p className="text-slate-400 mb-2">{typeDescriptions[drill.type]}</p>
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

            {/* Instruction */}
            <div className="bg-slate-700/50 rounded-lg p-4 text-center text-sm text-slate-300">
              <p>💡 메트로놈을 {drill.config.bpm ?? 80} BPM으로 설정하고</p>
              <p>Free Practice 모드의 도구들을 활용하여 연습하세요.</p>
              <p className="text-xs text-slate-500 mt-2">
                (향후 업데이트에서 자동 채점 기능이 추가됩니다)
              </p>
            </div>
          </div>

          {/* Self-Assessment Completion */}
          <div className="bg-slate-800 rounded-xl p-4">
            <h4 className="font-medium text-white mb-3">연습을 마쳤나요? 자기 평가를 해주세요:</h4>
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => completeDrill(60)}
                className="py-3 rounded-lg bg-yellow-600/20 border border-yellow-600/30 hover:bg-yellow-600/30 text-yellow-400 font-medium"
              >
                😅 어려웠음
              </button>
              <button
                onClick={() => completeDrill(80)}
                className="py-3 rounded-lg bg-blue-600/20 border border-blue-600/30 hover:bg-blue-600/30 text-blue-400 font-medium"
              >
                😊 괜찮았음
              </button>
              <button
                onClick={() => completeDrill(95)}
                className="py-3 rounded-lg bg-green-600/20 border border-green-600/30 hover:bg-green-600/30 text-green-400 font-medium"
              >
                😎 완벽함!
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
