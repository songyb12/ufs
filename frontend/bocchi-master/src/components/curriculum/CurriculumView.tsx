/**
 * CurriculumView — 레벨 맵 (메인 커리큘럼 화면)
 *
 * 게임의 월드맵처럼 레벨을 시각적으로 표시.
 * 일일 미션, 전체 진행도, 레벨 경로 맵.
 */

import { useState, useMemo } from 'react'
import type { Level, Lesson } from '../../data/curriculum'
import type { CurriculumState, CurriculumActions, DailyMissionStatus } from '../../hooks/useCurriculum'
import { playSuccessSound } from './soundEffects'

interface CurriculumViewProps {
  state: CurriculumState
  actions: CurriculumActions
}

export function CurriculumView({ state, actions }: CurriculumViewProps) {
  const { curriculum, profile } = state
  const { selectLevel, selectLesson, isUnlocked, getLevelProgressPercent, xpInfo, levelInfo, resetProgress, overallProgress, openAchievements } = actions

  const handleReset = () => {
    if (window.confirm('커리큘럼 진행도를 초기화하시겠습니까?\n\nXP, 업적, 드릴 기록이 모두 리셋됩니다.\n(설정, 악기 선택 등 기본 설정은 유지됩니다)')) {
      resetProgress()
    }
  }

  // Determine which level is "current" (first unlocked, incomplete level)
  const currentLevelId = useMemo(() => {
    for (const level of curriculum.levels) {
      if (isUnlocked(level) && getLevelProgressPercent(level) < 100) {
        return level.id
      }
    }
    return null
  }, [curriculum.levels, isUnlocked, getLevelProgressPercent])

  return (
    <div className="space-y-5">
      {/* Player Status Bar */}
      <div className="bg-slate-800 rounded-xl p-4 flex items-center gap-4">
        <div className="text-3xl">{levelInfo.icon}</div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Lv.{levelInfo.level}</span>
            <span className="font-bold text-white">{levelInfo.title}</span>
          </div>
          <div className="mt-1 flex items-center gap-3">
            <div className="flex-1 bg-slate-700 rounded-full h-2.5">
              <div
                className="bg-orange-500 h-2.5 rounded-full transition-all duration-500"
                style={{ width: `${xpInfo.progress}%` }}
              />
            </div>
            <span className="text-xs text-slate-400 whitespace-nowrap">
              {xpInfo.current} / {xpInfo.required} XP
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-400">총 XP</div>
          <div className="text-lg font-bold text-orange-400">{profile.xp.toLocaleString()}</div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-400">🔥 스트릭</div>
          <div className="text-lg font-bold text-orange-400">{profile.streakDays}일</div>
        </div>
        <button
          onClick={openAchievements}
          className="text-xs text-slate-400 hover:text-yellow-400 px-2 py-1 rounded hover:bg-slate-700/50 transition-colors"
          title="업적 갤러리"
        >
          🏆
        </button>
        <button
          onClick={handleReset}
          className="text-xs text-slate-500 hover:text-red-400 px-2 py-1 rounded hover:bg-slate-700/50 transition-colors"
          title="커리큘럼 진행도 초기화"
        >
          ↺
        </button>
      </div>

      {/* Daily Mission Bar */}
      <DailyMissionBar
        missions={state.dailyMissions}
        allComplete={state.allMissionsComplete}
        onComplete={actions.completeMission}
      />

      {/* Overall Curriculum Progress */}
      <div className="bg-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-white">전체 커리큘럼 진행률</span>
          <span className="text-sm text-slate-400">
            {overallProgress.completed} / {overallProgress.total} 레슨 · {overallProgress.percent}%
          </span>
        </div>
        <div className="bg-slate-700 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all duration-700 ${
              overallProgress.percent === 100 ? 'bg-green-500' : 'bg-gradient-to-r from-orange-500 to-orange-400'
            }`}
            style={{ width: `${overallProgress.percent}%` }}
          />
        </div>
      </div>

      {/* Curriculum Title + Instrument Switch */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">{curriculum.name}</h2>
          <p className="text-sm text-slate-400">{curriculum.description}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => actions.switchCurriculum('guitar')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              profile.instrument === 'guitar'
                ? 'bg-orange-600 text-white'
                : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
            }`}
          >
            🎸 기타
          </button>
          <button
            onClick={() => actions.switchCurriculum('bass')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              profile.instrument === 'bass'
                ? 'bg-orange-600 text-white'
                : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
            }`}
          >
            🎵 베이스
          </button>
        </div>
      </div>

      {/* Level Path Map */}
      <div className="relative">
        {curriculum.levels.map((level, i) => {
          const unlocked = isUnlocked(level)
          const progress = getLevelProgressPercent(level)
          const isCurrent = level.id === currentLevelId
          const isLast = i === curriculum.levels.length - 1

          return (
            <div key={level.id} className="relative">
              {/* Connector line to next level */}
              {!isLast && (
                <div className="absolute left-6 top-full w-0.5 h-4 z-0">
                  <div className={`w-full h-full ${
                    unlocked && progress === 100
                      ? 'bg-green-600'
                      : 'border-l-2 border-dashed border-slate-600'
                  }`} />
                </div>
              )}

              {/* Level Card */}
              <div className="mb-4">
                <LevelCard
                  level={level}
                  unlocked={unlocked}
                  progress={progress}
                  isCurrent={isCurrent}
                  completedLessons={state.profile.completedLessons}
                  isExpanded={state.selectedLevel?.id === level.id}
                  onToggle={() => selectLevel(level.id)}
                  onSelectLesson={selectLesson}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Daily Mission Bar ──────────────────────────────

interface DailyMissionBarProps {
  missions: DailyMissionStatus[]
  allComplete: boolean
  onComplete: (missionId: string) => void
}

const MISSION_ICONS: Record<string, string> = {
  'practice-time': '⏱️',
  'drill-complete': '🏋️',
  'chord-practice': '🎸',
  'song-section': '🎵',
  'streak-maintain': '🔥',
}

function DailyMissionBar({ missions, allComplete, onComplete }: DailyMissionBarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const completedCount = missions.filter(m => m.completed).length
  const totalBonus = allComplete ? 30 : 0

  const handleComplete = (missionId: string) => {
    onComplete(missionId)
    playSuccessSound()
  }

  return (
    <div className={`rounded-xl border transition-all ${
      allComplete
        ? 'border-yellow-600/50 bg-yellow-900/10'
        : 'border-slate-700 bg-slate-800'
    }`}>
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full p-3 flex items-center gap-3 text-left"
      >
        <span className="text-lg">{allComplete ? '🌟' : '📋'}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-white">오늘의 미션</span>
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
              allComplete
                ? 'bg-yellow-600/30 text-yellow-400'
                : 'bg-slate-700 text-slate-400'
            }`}>
              {completedCount}/{missions.length}
            </span>
            {allComplete && (
              <span className="text-xs text-yellow-400 font-medium">
                +{totalBonus} XP 보너스!
              </span>
            )}
          </div>
        </div>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform ${collapsed ? '' : 'rotate-180'}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Mission Cards */}
      {!collapsed && (
        <div className="px-3 pb-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
          {missions.map(({ mission, completed }) => (
            <div
              key={mission.id}
              className={`relative rounded-lg p-3 transition-all ${
                completed
                  ? 'bg-green-900/20 border border-green-700/30'
                  : 'bg-slate-700/50 border border-slate-600/30 hover:bg-slate-700/70'
              }`}
            >
              <div className="flex items-start gap-2">
                <span className="text-lg">{MISSION_ICONS[mission.type] ?? '📝'}</span>
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-medium ${completed ? 'text-green-400 line-through' : 'text-white'}`}>
                    {mission.title}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">{mission.description}</div>
                  <div className="text-xs text-orange-400 mt-1">+{mission.xpReward} XP</div>
                </div>
                {completed ? (
                  <span className="text-green-400 text-lg">✓</span>
                ) : (
                  <button
                    onClick={() => handleComplete(mission.id)}
                    className="text-xs px-2 py-1 rounded bg-slate-600 hover:bg-slate-500 text-slate-300 whitespace-nowrap"
                  >
                    완료
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Level Card ─────────────────────────────────────

interface LevelCardProps {
  level: Level
  unlocked: boolean
  progress: number
  isCurrent: boolean
  completedLessons: string[]
  isExpanded: boolean
  onToggle: () => void
  onSelectLesson: (lessonId: string) => void
}

function LevelCard({ level, unlocked, progress, isCurrent, completedLessons, isExpanded, onToggle, onSelectLesson }: LevelCardProps) {
  const isComplete = progress === 100

  return (
    <div
      className={`rounded-xl border transition-all ${
        !unlocked
          ? 'border-slate-700 bg-slate-800/50 opacity-50'
          : isCurrent
            ? 'border-blue-500/60 bg-slate-800 shadow-lg shadow-blue-500/10 animate-pulse-subtle'
            : isComplete
              ? 'border-green-600/50 bg-slate-800'
              : 'border-slate-600 bg-slate-800'
      }`}
      style={isCurrent ? { animationDuration: '3s' } : undefined}
    >
      {/* Level Header */}
      <button
        onClick={unlocked ? onToggle : undefined}
        disabled={!unlocked}
        className="w-full p-4 flex items-center gap-4 text-left"
      >
        {/* Level node indicator */}
        <div className={`relative w-12 h-12 rounded-full flex items-center justify-center text-2xl shrink-0 ${
          !unlocked
            ? 'bg-slate-700 text-slate-500'
            : isComplete
              ? 'bg-green-600/20 ring-2 ring-green-500'
              : isCurrent
                ? 'bg-blue-600/20 ring-2 ring-blue-500'
                : 'bg-slate-700'
        }`}>
          {!unlocked ? '🔒' : isComplete ? '✓' : level.icon}
          {isComplete && (
            <span className="absolute -top-1 -right-1 text-xs">✅</span>
          )}
        </div>

        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Level {level.index + 1}</span>
            {isComplete && <span className="text-xs text-green-400 font-medium">Complete</span>}
            {isCurrent && !isComplete && <span className="text-xs text-blue-400 font-medium">진행 중</span>}
          </div>
          <h3 className="font-bold text-white">{level.name}</h3>
          <p className="text-sm text-slate-400">{level.subtitle}</p>
        </div>
        <div className="text-right">
          {unlocked ? (
            <>
              <div className="text-sm font-medium text-white">{progress}%</div>
              <div className="w-20 bg-slate-700 rounded-full h-1.5 mt-1">
                <div
                  className={`h-1.5 rounded-full transition-all ${
                    isComplete ? 'bg-green-500' : 'bg-orange-500'
                  }`}
                  style={{ width: `${progress}%` }}
                />
              </div>
            </>
          ) : (
            <div className="text-xs text-slate-500">
              {level.requiredXP} XP 필요
            </div>
          )}
        </div>
        {unlocked && (
          <svg
            className={`w-5 h-5 text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>

      {/* Lesson List (expanded) */}
      {isExpanded && unlocked && (
        <div className="border-t border-slate-700 p-4 space-y-2">
          <p className="text-sm text-slate-400 mb-3">{level.description}</p>
          {level.lessons.map((lesson, i) => (
            <LessonRow
              key={lesson.id}
              lesson={lesson}
              index={i}
              isCompleted={completedLessons.includes(lesson.id)}
              onClick={() => onSelectLesson(lesson.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Lesson Row ─────────────────────────────────────

interface LessonRowProps {
  lesson: Lesson
  index: number
  isCompleted: boolean
  onClick: () => void
}

function LessonRow({ lesson, index, isCompleted, onClick }: LessonRowProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 p-3 rounded-lg text-left transition-colors ${
        isCompleted
          ? 'bg-green-900/20 hover:bg-green-900/30'
          : 'bg-slate-700/50 hover:bg-slate-700'
      }`}
    >
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
        isCompleted
          ? 'bg-green-600 text-white'
          : 'bg-slate-600 text-slate-300'
      }`}>
        {isCompleted ? '✓' : index + 1}
      </div>
      <div className="flex-1">
        <h4 className="font-medium text-white text-sm">{lesson.title}</h4>
        <p className="text-xs text-slate-400">{lesson.drills.length}개 드릴 · +{lesson.xpReward} XP</p>
      </div>
      <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </button>
  )
}
