/**
 * LessonView — 개별 레슨 상세 화면
 *
 * 이론 설명 + 드릴 목록 + 관련 곡.
 * 드릴을 선택하면 DrillRunner로 전환.
 */

import type { Lesson, Drill } from '../../data/curriculum'
import type { CurriculumActions } from '../../hooks/useCurriculum'
import type { DrillScore } from '../../data/curriculum'

interface LessonViewProps {
  lesson: Lesson
  completedDrills: string[]
  drillScores: Record<string, DrillScore>
  actions: CurriculumActions
}

export function LessonView({ lesson, completedDrills, drillScores, actions }: LessonViewProps) {
  const { goBack, startDrill, completeLesson, getLessonProgressPercent } = actions
  const progress = getLessonProgressPercent(lesson)
  const allDrillsComplete = lesson.drills.every(d => completedDrills.includes(d.id))

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={goBack}
          className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex-1">
          <h2 className="text-lg font-bold text-white">{lesson.title}</h2>
          <p className="text-sm text-slate-400">{lesson.titleEn}</p>
        </div>
        <div className="text-right">
          <div className="text-sm font-medium text-white">{progress}%</div>
          <div className="text-xs text-slate-400">+{lesson.xpReward} XP</div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="bg-slate-700 rounded-full h-2">
        <div
          className="bg-orange-500 h-2 rounded-full transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Objectives */}
      <div className="bg-slate-800 rounded-xl p-4">
        <h3 className="font-semibold text-white mb-2">🎯 학습 목표</h3>
        <ul className="space-y-1.5">
          {lesson.objectives.map((obj, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
              <span className="text-slate-500 mt-0.5">•</span>
              <span>{obj}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Theory Section */}
      {lesson.theory && (
        <div className="bg-slate-800 rounded-xl p-4">
          <h3 className="font-semibold text-white mb-3">📖 이론</h3>
          <div className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
            <SimpleMarkdown content={lesson.theory.markdown} />
          </div>
        </div>
      )}

      {/* Drills */}
      <div>
        <h3 className="font-semibold text-white mb-3">🏋️ 드릴</h3>
        <div className="space-y-2">
          {lesson.drills.map((drill) => (
            <DrillCard
              key={drill.id}
              drill={drill}
              isCompleted={completedDrills.includes(drill.id)}
              bestScore={drillScores[drill.id]}
              onStart={() => startDrill(drill.id)}
            />
          ))}
        </div>
      </div>

      {/* Complete Lesson Button */}
      {allDrillsComplete && (
        <button
          onClick={() => completeLesson(lesson.id)}
          className="w-full py-3 rounded-xl bg-green-600 hover:bg-green-500 text-white font-bold text-lg transition-colors"
        >
          ✅ 레슨 완료! (+{lesson.xpReward} XP)
        </button>
      )}

      {/* Related Songs */}
      {lesson.songs && lesson.songs.length > 0 && (
        <div className="bg-slate-800 rounded-xl p-4">
          <h3 className="font-semibold text-white mb-2">🎵 관련 곡</h3>
          {lesson.songs.map((song, i) => (
            <div key={i} className="flex items-center gap-2 text-sm text-slate-300 py-1">
              <span>🎶</span>
              <span>{song.songId}</span>
              {song.note && <span className="text-slate-500">— {song.note}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Drill Card ─────────────────────────────────────

interface DrillCardProps {
  drill: Drill
  isCompleted: boolean
  bestScore?: DrillScore
  onStart: () => void
}

function DrillCard({ drill, isCompleted, bestScore, onStart }: DrillCardProps) {
  const typeIcons: Record<string, string> = {
    'chord-change': '🔄',
    'strum-pattern': '🎶',
    'arpeggio': '🌊',
    'scale-run': '🎼',
    'fretboard-quiz': '🧠',
    'rhythm': '🥁',
    'ear-training': '👂',
    'song-section': '🎵',
    'voicing-match': '🎸',
    'progression-play': '🎹',
  }

  const typeLabels: Record<string, string> = {
    'chord-change': '코드 체인지',
    'strum-pattern': '스트럼 패턴',
    'arpeggio': '아르페지오',
    'scale-run': '스케일 런',
    'fretboard-quiz': '지판 퀴즈',
    'rhythm': '리듬',
    'ear-training': '청음 훈련',
    'song-section': '곡 구간',
    'voicing-match': '보이싱 매칭',
    'progression-play': '진행 연주',
  }

  return (
    <button
      onClick={onStart}
      className={`w-full flex items-center gap-3 p-4 rounded-xl text-left transition-all ${
        isCompleted
          ? 'bg-green-900/20 border border-green-700/30 hover:bg-green-900/30'
          : 'bg-slate-700/50 border border-slate-600/30 hover:bg-slate-700'
      }`}
    >
      <div className="text-2xl">{typeIcons[drill.type] ?? '📝'}</div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h4 className="font-medium text-white text-sm">{drill.title}</h4>
          {isCompleted && <span className="text-green-400 text-xs">✓</span>}
        </div>
        <p className="text-xs text-slate-400">{drill.description}</p>
        <div className="flex items-center gap-3 mt-1">
          <span className="text-xs text-slate-500">{typeLabels[drill.type] ?? drill.type}</span>
          <span className="text-xs text-slate-500">~{drill.estimatedMinutes}분</span>
          <span className="text-xs text-orange-400">+{drill.xpReward} XP</span>
        </div>
      </div>
      {bestScore && (
        <div className="text-right">
          <div className="text-sm font-medium text-green-400">{bestScore.accuracy}%</div>
          <div className="text-xs text-slate-500">최고 기록</div>
        </div>
      )}
      <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7-7 7M5 12h16" />
      </svg>
    </button>
  )
}

// ─── Simple Markdown Renderer ───────────────────────

function SimpleMarkdown({ content }: { content: string }) {
  const lines = content.split('\n')

  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        const trimmed = line.trimStart()
        if (trimmed.startsWith('### ')) {
          return <h5 key={i} className="font-semibold text-orange-300 mt-3 mb-1">{trimmed.slice(4)}</h5>
        }
        if (trimmed.startsWith('## ')) {
          return <h4 key={i} className="font-bold text-white text-base mt-3 mb-1">{trimmed.slice(3)}</h4>
        }
        if (trimmed.startsWith('- **')) {
          const match = trimmed.match(/^- \*\*(.+?)\*\*(.*)$/)
          if (match) {
            return (
              <p key={i} className="pl-3">
                <span className="text-white font-medium">{match[1]}</span>
                <span className="text-slate-400">{match[2]}</span>
              </p>
            )
          }
        }
        if (trimmed.startsWith('- ')) {
          return <p key={i} className="pl-3 text-slate-300">• {trimmed.slice(2)}</p>
        }
        if (/^\d+\./.test(trimmed)) {
          return <p key={i} className="pl-3 text-slate-300">{trimmed}</p>
        }
        if (trimmed === '') return <div key={i} className="h-1" />
        // Bold inline
        const withBold = trimmed.replace(/\*\*(.+?)\*\*/g, '<b class="text-white font-medium">$1</b>')
        return <p key={i} dangerouslySetInnerHTML={{ __html: withBold }} />
      })}
    </div>
  )
}
