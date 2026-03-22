import { useState, useEffect, useMemo, memo } from 'react'
import { loadSettings, loadDailyGoal, type PracticeSession } from '../../utils/storage'
import { loadPlayerProfile, type PlayerProfile, type DrillBestScore } from '../../data/gamification'
import type { CurriculumProgress, DrillScore } from '../../data/curriculum'

// ── Drill type labels ──
const DRILL_TYPE_LABELS: Record<string, string> = {
  'chord-change': 'Chord Change',
  'strum-pattern': 'Strum Pattern',
  'arpeggio': 'Arpeggio',
  'scale-run': 'Scale Run',
  'fretboard-quiz': 'Fretboard Quiz',
  'rhythm': 'Rhythm',
  'ear-training': 'Ear Training',
  'song-section': 'Song Section',
  'voicing-match': 'Voicing Match',
  'progression-play': 'Progression',
}

interface DrillTypeStats {
  type: string
  label: string
  avgAccuracy: number
  totalAttempts: number
  drillCount: number
  worstDrillId: string | null
  worstAccuracy: number
}

interface WeeklyActivity {
  weekLabel: string
  sessions: number
  totalMinutes: number
  avgAccuracy: number
}

interface Insight {
  icon: string
  text: string
  severity: 'good' | 'warn' | 'bad'
}

function loadCurriculumProgress(): CurriculumProgress | null {
  try {
    const raw = localStorage.getItem('bocchi-curriculum-progress')
    return raw ? JSON.parse(raw) as CurriculumProgress : null
  } catch { return null }
}

function inferDrillType(drillId: string): string {
  // Drill IDs often contain the type (e.g., "l1-d1-chord-change", "level2-strum-pattern-basic")
  for (const type of Object.keys(DRILL_TYPE_LABELS)) {
    if (drillId.includes(type)) return type
  }
  // Fallback heuristics
  if (drillId.includes('chord') || drillId.includes('voicing')) return 'chord-change'
  if (drillId.includes('strum')) return 'strum-pattern'
  if (drillId.includes('scale') || drillId.includes('pattern')) return 'scale-run'
  if (drillId.includes('quiz') || drillId.includes('fret')) return 'fretboard-quiz'
  if (drillId.includes('ear') || drillId.includes('interval')) return 'ear-training'
  if (drillId.includes('rhythm')) return 'rhythm'
  if (drillId.includes('song')) return 'song-section'
  return 'unknown'
}

function analyzeDrillTypes(
  profileScores: Record<string, DrillBestScore>,
  progressScores: Record<string, DrillScore>,
): DrillTypeStats[] {
  // Merge both score sources
  const allScores: Record<string, { accuracy: number; attempts: number; id: string }[]> = {}
  const addScore = (id: string, acc: number, att: number) => {
    const type = inferDrillType(id)
    if (!allScores[type]) allScores[type] = []
    allScores[type].push({ accuracy: acc, attempts: att, id })
  }

  for (const [id, s] of Object.entries(profileScores)) addScore(id, s.accuracy, s.attempts)
  for (const [id, s] of Object.entries(progressScores)) {
    if (!profileScores[id]) addScore(id, s.accuracy, s.attempts)
  }

  const results: DrillTypeStats[] = []
  for (const [type, scores] of Object.entries(allScores)) {
    if (type === 'unknown') continue
    const totalAcc = scores.reduce((s, d) => s + d.accuracy, 0)
    const totalAtt = scores.reduce((s, d) => s + d.attempts, 0)
    const avgAccuracy = scores.length > 0 ? Math.round(totalAcc / scores.length) : 0

    // Find worst drill
    let worstDrillId: string | null = null
    let worstAccuracy = 101
    for (const d of scores) {
      if (d.accuracy < worstAccuracy && d.attempts >= 1) {
        worstAccuracy = d.accuracy
        worstDrillId = d.id
      }
    }

    results.push({
      type,
      label: DRILL_TYPE_LABELS[type] ?? type,
      avgAccuracy,
      totalAttempts: totalAtt,
      drillCount: scores.length,
      worstDrillId,
      worstAccuracy: worstAccuracy <= 100 ? worstAccuracy : 0,
    })
  }

  return results.sort((a, b) => a.avgAccuracy - b.avgAccuracy)
}

function analyzeWeeklyActivity(sessions: PracticeSession[]): WeeklyActivity[] {
  if (sessions.length === 0) return []

  const weeks: Record<string, { sessions: number; totalSec: number; totalAcc: number; accCount: number }> = {}
  const now = new Date()

  for (const s of sessions) {
    const d = new Date(s.date)
    const weekStart = new Date(d)
    weekStart.setDate(d.getDate() - d.getDay())
    const key = weekStart.toISOString().slice(0, 10)

    // Only last 8 weeks
    const diffWeeks = Math.floor((now.getTime() - weekStart.getTime()) / (7 * 86400000))
    if (diffWeeks > 7) continue

    if (!weeks[key]) weeks[key] = { sessions: 0, totalSec: 0, totalAcc: 0, accCount: 0 }
    weeks[key].sessions++
    weeks[key].totalSec += s.durationSeconds
    if (s.totalAttempts > 0) {
      weeks[key].totalAcc += Math.round((s.correctAttempts / s.totalAttempts) * 100)
      weeks[key].accCount++
    }
  }

  return Object.entries(weeks)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, w]) => ({
      weekLabel: `${new Date(key).getMonth() + 1}/${new Date(key).getDate()}`,
      sessions: w.sessions,
      totalMinutes: Math.round(w.totalSec / 60),
      avgAccuracy: w.accCount > 0 ? Math.round(w.totalAcc / w.accCount) : 0,
    }))
}

function generateInsights(
  sessions: PracticeSession[],
  drillStats: DrillTypeStats[],
  profile: PlayerProfile | null,
  dailyGoalMinutes: number,
  weeklyActivity: WeeklyActivity[],
): Insight[] {
  const insights: Insight[] = []

  // 1. Weakest drill type
  if (drillStats.length > 0) {
    const weakest = drillStats[0]
    if (weakest.avgAccuracy < 60) {
      insights.push({
        icon: '🎯',
        text: `${weakest.label} 정확도가 ${weakest.avgAccuracy}%로 가장 낮습니다. 집중 연습이 필요합니다.`,
        severity: 'bad',
      })
    } else if (weakest.avgAccuracy < 80) {
      insights.push({
        icon: '📈',
        text: `${weakest.label}(${weakest.avgAccuracy}%)이 상대적으로 약합니다. 반복 연습으로 80% 이상을 목표하세요.`,
        severity: 'warn',
      })
    }
  }

  // 2. Strongest drill type
  if (drillStats.length > 1) {
    const strongest = drillStats[drillStats.length - 1]
    if (strongest.avgAccuracy >= 90) {
      insights.push({
        icon: '🌟',
        text: `${strongest.label}(${strongest.avgAccuracy}%)은 매우 좋습니다! 다음 난이도로 넘어갈 준비가 되었습니다.`,
        severity: 'good',
      })
    }
  }

  // 3. Practice consistency
  const recentWeeks = weeklyActivity.slice(-4)
  const activeDays = recentWeeks.reduce((s, w) => s + w.sessions, 0)
  if (recentWeeks.length >= 2 && activeDays < 4) {
    insights.push({
      icon: '📅',
      text: `최근 4주간 ${activeDays}회만 연습했습니다. 매일 ${dailyGoalMinutes}분이라도 꾸준히 연습하세요.`,
      severity: 'bad',
    })
  } else if (activeDays >= 12) {
    insights.push({
      icon: '🔥',
      text: `최근 4주간 ${activeDays}회 연습 — 꾸준한 연습 습관이 만들어지고 있습니다!`,
      severity: 'good',
    })
  }

  // 4. Accuracy trend (last 10 sessions vs. previous 10)
  if (sessions.length >= 10) {
    const recent10 = sessions.slice(0, 10)
    const prev10 = sessions.slice(10, 20)
    const recentAvg = recent10.reduce((s, x) => s + (x.totalAttempts > 0 ? x.correctAttempts / x.totalAttempts : 0), 0) / 10
    const prevAvg = prev10.length > 0
      ? prev10.reduce((s, x) => s + (x.totalAttempts > 0 ? x.correctAttempts / x.totalAttempts : 0), 0) / prev10.length
      : recentAvg
    const delta = Math.round((recentAvg - prevAvg) * 100)
    if (delta > 5) {
      insights.push({ icon: '📊', text: `최근 정확도가 +${delta}%p 향상되었습니다!`, severity: 'good' })
    } else if (delta < -5) {
      insights.push({ icon: '📉', text: `최근 정확도가 ${delta}%p 하락했습니다. 기본기 복습을 추천합니다.`, severity: 'warn' })
    }
  }

  // 5. Session duration check
  const recentSessions = sessions.slice(0, 5)
  const avgDuration = recentSessions.length > 0
    ? recentSessions.reduce((s, x) => s + x.durationSeconds, 0) / recentSessions.length
    : 0
  if (avgDuration > 0 && avgDuration < 300) {
    insights.push({
      icon: '⏱',
      text: `평균 연습 시간이 ${Math.round(avgDuration / 60)}분입니다. 최소 10분 이상 연습하면 효과가 높아집니다.`,
      severity: 'warn',
    })
  }

  // 6. Unexplored drill types
  const explored = new Set(drillStats.map(d => d.type))
  const unexplored = Object.keys(DRILL_TYPE_LABELS).filter(t => !explored.has(t))
  if (unexplored.length > 0 && unexplored.length <= 5) {
    const labels = unexplored.slice(0, 3).map(t => DRILL_TYPE_LABELS[t]).join(', ')
    insights.push({
      icon: '🆕',
      text: `아직 시도하지 않은 연습: ${labels}. 커리큘럼 모드에서 도전해보세요.`,
      severity: 'warn',
    })
  }

  // 7. Streak
  if (profile && profile.streakDays >= 7) {
    insights.push({
      icon: '🏆',
      text: `${profile.streakDays}일 연속 연습 중! 최고 기록: ${profile.bestStreakDays}일`,
      severity: 'good',
    })
  }

  return insights
}

const SEVERITY_STYLES: Record<string, string> = {
  good: 'border-emerald-500/20 bg-emerald-500/5',
  warn: 'border-amber-500/20 bg-amber-500/5',
  bad: 'border-rose-500/20 bg-rose-500/5',
}

function accColor(acc: number): string {
  if (acc >= 80) return 'text-emerald-400'
  if (acc >= 50) return 'text-amber-400'
  return 'text-rose-400'
}

function accBg(acc: number): string {
  if (acc >= 80) return 'bg-emerald-500'
  if (acc >= 50) return 'bg-amber-500'
  return 'bg-rose-500'
}

export const WeaknessAnalysisPanel = memo(function WeaknessAnalysisPanel() {
  const [sessions, setSessions] = useState<PracticeSession[]>([])
  const [profile, setProfile] = useState<PlayerProfile | null>(null)
  const [progress, setProgress] = useState<CurriculumProgress | null>(null)
  const [dailyGoalMinutes, setDailyGoalMinutes] = useState(30)
  const [expanded, setExpanded] = useState(true)

  useEffect(() => {
    setSessions(loadSettings().practiceHistory)
    setProfile(loadPlayerProfile())
    setProgress(loadCurriculumProgress())
    setDailyGoalMinutes(loadDailyGoal().targetMinutes)
  }, [])

  // Refresh periodically
  useEffect(() => {
    const interval = setInterval(() => {
      setSessions(loadSettings().practiceHistory)
      setProfile(loadPlayerProfile())
      setProgress(loadCurriculumProgress())
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const drillStats = useMemo(
    () => analyzeDrillTypes(profile?.drillScores ?? {}, progress?.drillBestScores ?? {}),
    [profile, progress],
  )

  const weeklyActivity = useMemo(() => analyzeWeeklyActivity(sessions), [sessions])

  const insights = useMemo(
    () => generateInsights(sessions, drillStats, profile, dailyGoalMinutes, weeklyActivity),
    [sessions, drillStats, profile, dailyGoalMinutes, weeklyActivity],
  )

  const hasData = sessions.length > 0 || drillStats.length > 0

  if (!hasData) {
    return (
      <section className="bg-slate-800 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">
          Weakness Analysis
        </h3>
        <p className="text-xs text-slate-600">
          연습 데이터가 쌓이면 약점 분석과 맞춤 추천이 제공됩니다.
        </p>
      </section>
    )
  }

  return (
    <section className="bg-slate-800 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300">Weakness Analysis</h3>
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          {expanded ? 'Collapse' : 'Details'}
        </button>
      </div>

      {/* Insights (always shown) */}
      {insights.length > 0 && (
        <div className="space-y-1.5 mb-3">
          {insights.slice(0, expanded ? insights.length : 3).map((ins, i) => (
            <div
              key={i}
              className={`flex items-start gap-2 px-2.5 py-1.5 rounded-lg border text-xs ${SEVERITY_STYLES[ins.severity]}`}
            >
              <span className="flex-shrink-0">{ins.icon}</span>
              <span className="text-slate-300">{ins.text}</span>
            </div>
          ))}
          {!expanded && insights.length > 3 && (
            <button
              onClick={() => setExpanded(true)}
              className="text-[10px] text-slate-500 hover:text-slate-400 ml-1"
            >
              +{insights.length - 3} more...
            </button>
          )}
        </div>
      )}

      {/* Drill type breakdown */}
      {drillStats.length > 0 && (
        <div className="space-y-1">
          <h4 className="text-[10px] text-slate-500 uppercase tracking-wider">By Drill Type</h4>
          {drillStats.map(d => (
            <div key={d.type} className="flex items-center gap-2 text-xs">
              <span className="w-24 text-slate-400 truncate">{d.label}</span>
              <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${accBg(d.avgAccuracy)}`}
                  style={{ width: `${d.avgAccuracy}%` }}
                />
              </div>
              <span className={`w-8 text-right font-mono ${accColor(d.avgAccuracy)}`}>
                {d.avgAccuracy}%
              </span>
              <span className="w-8 text-right text-slate-600 text-[10px]">
                x{d.drillCount}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Expanded details */}
      {expanded && (
        <div className="mt-3 space-y-3">
          {/* Weekly activity chart */}
          {weeklyActivity.length > 0 && (
            <div className="space-y-1">
              <h4 className="text-[10px] text-slate-500 uppercase tracking-wider">Weekly Activity</h4>
              <div className="flex items-end gap-1 h-16">
                {weeklyActivity.map((w, i) => {
                  const maxMin = Math.max(...weeklyActivity.map(x => x.totalMinutes), 1)
                  const height = (w.totalMinutes / maxMin) * 100
                  return (
                    <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
                      <div className="w-full flex items-end justify-center" style={{ height: '48px' }}>
                        <div
                          className={`w-full max-w-5 rounded-t ${accBg(w.avgAccuracy)}`}
                          style={{ height: `${Math.max(height, 4)}%`, opacity: 0.7 }}
                          title={`${w.sessions} sessions, ${w.totalMinutes}min, ${w.avgAccuracy}% acc`}
                        />
                      </div>
                      <span className="text-[8px] text-slate-600">{w.weekLabel}</span>
                    </div>
                  )
                })}
              </div>
              <div className="flex justify-between text-[9px] text-slate-600">
                <span>Sessions per week</span>
                <span>
                  Total: {weeklyActivity.reduce((s, w) => s + w.totalMinutes, 0)}min
                </span>
              </div>
            </div>
          )}

          {/* Practice targets by type */}
          {sessions.length > 0 && (
            <div className="space-y-1">
              <h4 className="text-[10px] text-slate-500 uppercase tracking-wider">Most Practiced</h4>
              {(() => {
                const targetCounts: Record<string, { count: number; totalAcc: number }> = {}
                for (const s of sessions) {
                  const desc = s.targetDescription || 'Unknown'
                  if (!targetCounts[desc]) targetCounts[desc] = { count: 0, totalAcc: 0 }
                  targetCounts[desc].count++
                  if (s.totalAttempts > 0) {
                    targetCounts[desc].totalAcc += Math.round((s.correctAttempts / s.totalAttempts) * 100)
                  }
                }
                return Object.entries(targetCounts)
                  .sort(([, a], [, b]) => b.count - a.count)
                  .slice(0, 5)
                  .map(([desc, data]) => {
                    const avg = data.count > 0 ? Math.round(data.totalAcc / data.count) : 0
                    return (
                      <div key={desc} className="flex items-center gap-2 text-xs">
                        <span className="flex-1 text-slate-400 truncate">{desc}</span>
                        <span className={`font-mono ${accColor(avg)}`}>{avg}%</span>
                        <span className="text-slate-600 text-[10px]">x{data.count}</span>
                      </div>
                    )
                  })
              })()}
            </div>
          )}
        </div>
      )}
    </section>
  )
})
