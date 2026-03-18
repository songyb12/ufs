/**
 * CurriculumMode — 커리큘럼 모드 전체를 감싸는 컨테이너
 *
 * view state에 따라 CurriculumView / LessonView / DrillRunner 전환.
 * useCurriculum hook으로 상태 관리.
 * ErrorBoundary로 감싸서 에러 시 자유 연습으로 복귀 가능.
 */

import { Component, type ReactNode } from 'react'
import { useCurriculum } from '../../hooks/useCurriculum'
import { CurriculumView } from './CurriculumView'
import { LessonView } from './LessonView'
import { DrillRunner } from './DrillRunner'

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

  return (
    <div className="max-w-3xl mx-auto">
      {/* Mode Switch Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-700">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-white">📚 커리큘럼</h1>
          {state.view !== 'map' && (
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

      {/* Achievement Popup */}
      {state.pendingAchievements.length > 0 && (
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
          onComplete={actions.completeDrill}
          onCancel={actions.goBack}
        />
      )}
    </div>
  )
}

// ─── Achievement Popup ──────────────────────────────

function AchievementPopup({
  achievement,
  onDismiss,
}: {
  achievement: { name: string; icon: string; description: string; xpReward: number; rarity: string }
  onDismiss: () => void
}) {
  const rarityColors: Record<string, string> = {
    common: 'border-slate-500',
    rare: 'border-blue-500',
    epic: 'border-purple-500',
    legendary: 'border-yellow-500',
  }

  const rarityBg: Record<string, string> = {
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
