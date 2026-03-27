/**
 * CurriculumMode — 커리큘럼 모드 전체를 감싸는 컨테이너
 *
 * view state에 따라 CurriculumView / LessonView / DrillRunner 전환.
 * useCurriculum hook으로 상태 관리.
 * ErrorBoundary로 감싸서 에러 시 자유 연습으로 복귀 가능.
 */

import { Component, type ReactNode, useState, useEffect, useRef } from 'react'
import type { AchievementRarity } from '../../data/gamification'
import { useCurriculum, type LessonCompleteResult } from '../../hooks/useCurriculum'
import { CurriculumView } from './CurriculumView'
import { LessonView } from './LessonView'
import { DrillRunner } from './DrillRunner'
import { AchievementGallery } from './AchievementGallery'
import { playSuccessSound, playLevelUpSound } from './soundEffects'

// ─── Error Boundary ─────────────────────────────────

interface EBProps { children: ReactNode; onFallback: () => void }
interface EBState { error: Error | null }

class CurriculumErrorBoundary extends Component<EBProps, EBState> {
  state: EBState = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }

  render() {
    if (this.state.error) {
      return (
        <div className="bg-red-900/20 border border-red-700/50 rounded-xl p-6 text-center space-y-3">
          <div className="text-3xl">⚠️</div>
          <h3 className="text-lg font-bold text-red-400">커리큘럼 로딩 오류</h3>
          <p className="text-sm text-slate-400">{this.state.error.message}</p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => this.setState({ error: null })}
              className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-sm"
            >
              다시 시도
            </button>
            <button
              onClick={this.props.onFallback}
              className="px-4 py-2 rounded-lg bg-orange-600 hover:bg-orange-500 text-white text-sm"
            >
              자유 연습으로
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

// ─── Main ───────────────────────────────────────────

interface CurriculumModeProps {
  onSwitchToFreeMode: () => void
}

export function CurriculumMode({ onSwitchToFreeMode }: CurriculumModeProps) {
  return (
    <CurriculumErrorBoundary onFallback={onSwitchToFreeMode}>
      <CurriculumModeInner onSwitchToFreeMode={onSwitchToFreeMode} />
    </CurriculumErrorBoundary>
  )
}

function CurriculumModeInner({ onSwitchToFreeMode }: CurriculumModeProps) {
  const [state, actions] = useCurriculum()

  // Escape key to go back (except when in map view or drill — drill has its own handler)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && (state.view === 'lesson' || state.view === 'achievements')) {
        e.preventDefault()
        actions.goBack()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [state.view, actions.goBack])

  return (
    <div className="max-w-3xl mx-auto">
      {/* Mode Switch Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-700">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-white">📚 커리큘럼</h1>
          {state.view !== 'map' && state.view !== 'achievements' && (
            <button
              onClick={actions.goToMap}
              className="text-xs text-slate-400 hover:text-slate-300 underline"
            >
              맵으로
            </button>
          )}
        </div>
        <button
          onClick={onSwitchToFreeMode}
          className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm"
        >
          🎸 자유 연습 모드
        </button>
      </div>

      {/* Lesson Complete Celebration Modal */}
      {state.lessonCompleteResult && (
        <LessonCelebrationModal
          result={state.lessonCompleteResult}
          onDismiss={actions.dismissLessonComplete}
        />
      )}

      {/* Achievement Popup */}
      {state.pendingAchievements.length > 0 && !state.lessonCompleteResult && (
        <AchievementPopup
          achievement={state.pendingAchievements[0]}
          onDismiss={actions.dismissAchievement}
        />
      )}

      {/* Content by View */}
      {state.view === 'map' && (
        <CurriculumView state={state} actions={actions} />
      )}

      {state.view === 'lesson' && state.selectedLesson && (
        <LessonView
          lesson={state.selectedLesson}
          completedDrills={state.profile.completedDrills}
          drillScores={state.profile.drillScores}
          actions={actions}
        />
      )}

      {state.view === 'drill' && state.activeDrill && (
        <DrillRunner
          drill={state.activeDrill}
          bestScore={state.profile.drillScores[state.activeDrill.id]}
          onComplete={actions.completeDrill}
          onCancel={actions.goBack}
        />
      )}

      {state.view === 'achievements' && (
        <AchievementGallery
          earnedIds={state.profile.achievements}
          onBack={actions.goBack}
        />
      )}
    </div>
  )
}

// ─── Lesson Celebration Modal ────────────────────────

function LessonCelebrationModal({
  result,
  onDismiss,
}: {
  result: LessonCompleteResult
  onDismiss: () => void
}) {
  const [displayXP, setDisplayXP] = useState(0)
  const animFrameRef = useRef(0)
  const soundPlayed = useRef(false)

  // XP count-up animation
  useEffect(() => {
    const target = result.xpEarned
    const duration = 600 // ms
    const startTime = performance.now()

    const animate = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      // ease-out quad
      const eased = 1 - (1 - progress) * (1 - progress)
      setDisplayXP(Math.round(target * eased))

      if (progress < 1) {
        animFrameRef.current = requestAnimationFrame(animate)
      }
    }
    animFrameRef.current = requestAnimationFrame(animate)

    return () => cancelAnimationFrame(animFrameRef.current)
  }, [result.xpEarned])

  // Play sound effect once on mount
  useEffect(() => {
    if (soundPlayed.current) return
    soundPlayed.current = true
    if (result.leveledUp) {
      playLevelUpSound()
    } else {
      playSuccessSound()
    }
  }, [result.leveledUp])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="relative bg-slate-800 border border-slate-600 rounded-2xl p-8 text-center max-w-sm mx-4 shadow-2xl overflow-hidden">
        {/* Level-up particle effect */}
        {result.leveledUp && (
          <div className="absolute inset-0 pointer-events-none overflow-hidden">
            {['🌟', '✨', '⭐', '🎉', '🎊', '💫', '✨', '🌟'].map((emoji, i) => (
              <span
                key={i}
                className="absolute text-2xl animate-bounce"
                style={{
                  left: `${10 + (i * 11) % 80}%`,
                  top: `${5 + (i * 17) % 60}%`,
                  animationDelay: `${i * 0.12}s`,
                  animationDuration: `${0.8 + (i % 3) * 0.3}s`,
                  opacity: 0.8,
                }}
              >
                {emoji}
              </span>
            ))}
          </div>
        )}

        {/* Header */}
        <div className="relative z-10">
          <div className="text-5xl mb-3">{result.leveledUp ? '🏆' : '🎉'}</div>
          <h3 className="text-xs text-slate-400 uppercase tracking-widest mb-1">레슨 완료!</h3>
          <h2 className="text-xl font-bold text-white mb-1">{result.lessonTitle}</h2>

          {/* XP count-up */}
          <div className="my-4 py-3 rounded-xl bg-slate-700/50">
            <div className="text-3xl font-bold font-mono text-orange-400">
              +{displayXP} XP
            </div>
          </div>

          {/* Level-up section */}
          {result.leveledUp && result.newLevel && (
            <div className="my-4 py-4 px-3 rounded-xl bg-yellow-900/30 border border-yellow-600/40">
              <div className="text-xs text-yellow-400 uppercase tracking-widest mb-2">
                Level Up!
              </div>
              <div className="text-4xl mb-2">{result.newLevel.icon}</div>
              <div className="text-lg font-bold text-yellow-300">
                Lv.{result.newLevel.level} {result.newLevel.title}
              </div>
              {result.newLevel.titleJa && (
                <div className="text-sm text-yellow-400/70 mt-0.5">
                  {result.newLevel.titleJa}
                </div>
              )}
              <div className="text-xs text-slate-400 mt-2">
                새로운 칭호를 획득했습니다!
              </div>
            </div>
          )}

          {/* Continue button */}
          <button
            onClick={onDismiss}
            className={`w-full py-3 rounded-xl font-bold text-lg transition-colors mt-2 ${
              result.leveledUp
                ? 'bg-yellow-600 hover:bg-yellow-500 text-white'
                : 'bg-orange-600 hover:bg-orange-500 text-white'
            }`}
          >
            계속하기
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Achievement Popup ──────────────────────────────

function AchievementPopup({
  achievement,
  onDismiss,
}: {
  achievement: { name: string; icon: string; description: string; xpReward: number; rarity: AchievementRarity }
  onDismiss: () => void
}) {
  const soundPlayed = useRef(false)
  useEffect(() => {
    if (soundPlayed.current) return
    soundPlayed.current = true
    import('./soundEffects').then(m => m.playAchievementSound())
  }, [])

  const rarityColors: Record<AchievementRarity, string> = {
    common: 'border-slate-500',
    rare: 'border-blue-500',
    epic: 'border-purple-500',
    legendary: 'border-yellow-500',
  }

  const rarityBg: Record<AchievementRarity, string> = {
    common: 'from-slate-800',
    rare: 'from-blue-900/50',
    epic: 'from-purple-900/50',
    legendary: 'from-yellow-900/50',
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 animate-fade-in">
      <div
        className={`bg-gradient-to-b ${rarityBg[achievement.rarity] ?? rarityBg.common} to-slate-800
          border-2 ${rarityColors[achievement.rarity] ?? rarityColors.common}
          rounded-2xl p-8 text-center max-w-sm mx-4 shadow-2xl`}
      >
        <div className="text-5xl mb-3">{achievement.icon}</div>
        <h3 className="text-xs text-slate-400 uppercase tracking-widest mb-1">업적 달성!</h3>
        <h2 className="text-xl font-bold text-white mb-2">{achievement.name}</h2>
        <p className="text-sm text-slate-400 mb-4">{achievement.description}</p>
        <div className="text-orange-400 font-bold mb-4">+{achievement.xpReward} XP</div>
        <button
          onClick={onDismiss}
          className="px-6 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white font-medium"
        >
          확인
        </button>
      </div>
    </div>
  )
}
