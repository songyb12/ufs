/**
 * CurriculumView — 레벨 맵 (메인 커리큘럼 화면)
 *
 * 게임의 월드맵처럼 레벨을 시각적으로 표시.
 * 각 레벨의 진행률, 잠금 상태, 레슨 목록을 보여줌.
 */

import type { Level, Lesson } from '../../data/curriculum'
import type { CurriculumState, CurriculumActions } from '../../hooks/useCurriculum'

interface CurriculumViewProps {
  state: CurriculumState
  actions: CurriculumActions
}

export function CurriculumView({ state, actions }: CurriculumViewProps) {
  const { curriculum, profile } = state
  const { selectLevel, selectLesson, isUnlocked, getLevelProgressPercent, xpInfo, levelInfo } = actions

  return (
    <div className="space-y-6">
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
      </div>

      {/* Curriculum Title */}
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

      {/* Level Map */}
      <div className="space-y-4">
        {curriculum.levels.map((level) => (
          <LevelCard
            key={level.id}
            level={level}
            unlocked={isUnlocked(level)}
            progress={getLevelProgressPercent(level)}
            completedLessons={state.profile.completedLessons}
            isExpanded={state.selectedLevel?.id === level.id}
            onToggle={() => selectLevel(level.id)}
            onSelectLesson={selectLesson}
          />
        ))}
      </div>
    </div>
  )
}

// ─── Level Card ─────────────────────────────────────

interface LevelCardProps {
  level: Level
  unlocked: boolean
  progress: number
  completedLessons: string[]
  isExpanded: boolean
  onToggle: () => void
  onSelectLesson: (lessonId: string) => void
}

function LevelCard({ level, unlocked, progress, completedLessons, isExpanded, onToggle, onSelectLesson }: LevelCardProps) {
  const isComplete = progress === 100

  return (
    <div
      className={`rounded-xl border transition-all ${
        !unlocked
          ? 'border-slate-700 bg-slate-800/50 opacity-60'
          : isComplete
            ? 'border-green-600/50 bg-slate-800'
            : 'border-slate-600 bg-slate-800'
      }`}
    >
      {/* Level Header */}
      <button
        onClick={unlocked ? onToggle : undefined}
        disabled={!unlocked}
        className="w-full p-4 flex items-center gap-4 text-left"
      >
        <div className={`text-3xl ${!unlocked ? 'grayscale' : ''}`}>
          {unlocked ? level.icon : '🔒'}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Level {level.index + 1}</span>
            {isComplete && <span className="text-xs text-green-400">✓ Complete</span>}
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
