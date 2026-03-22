/**
 * AchievementGallery — 업적 갤러리 페이지
 *
 * 카테고리별 그룹, 잠금/해제/히든 상태, 진행도 표시.
 */

import { useMemo } from 'react'
import {
  ACHIEVEMENTS,
  type Achievement,
  type AchievementCategory,
  type AchievementRarity,
} from '../../data/gamification'

interface AchievementGalleryProps {
  earnedIds: string[]
  onBack: () => void
}

const CATEGORY_META: Record<AchievementCategory, { label: string; icon: string }> = {
  milestone: { label: '마일스톤', icon: '🏁' },
  streak: { label: '연속 기록', icon: '🔥' },
  mastery: { label: '마스터리', icon: '💎' },
  collection: { label: '수집', icon: '📚' },
  challenge: { label: '도전', icon: '🏆' },
  hidden: { label: '히든', icon: '🔮' },
}

const RARITY_STYLES: Record<AchievementRarity, { border: string; bg: string; label: string }> = {
  common: { border: 'border-slate-600', bg: 'bg-slate-700/50', label: '일반' },
  rare: { border: 'border-blue-600/60', bg: 'bg-blue-900/20', label: '레어' },
  epic: { border: 'border-purple-600/60', bg: 'bg-purple-900/20', label: '에픽' },
  legendary: { border: 'border-yellow-500/60', bg: 'bg-yellow-900/20', label: '전설' },
}

const CATEGORY_ORDER: AchievementCategory[] = [
  'milestone', 'streak', 'mastery', 'collection', 'challenge', 'hidden',
]

export function AchievementGallery({ earnedIds, onBack }: AchievementGalleryProps) {
  const earnedSet = useMemo(() => new Set(earnedIds), [earnedIds])
  const totalEarned = earnedIds.length
  // Don't count hidden achievements that haven't been earned toward total
  const totalVisible = ACHIEVEMENTS.filter(a => a.category !== 'hidden' || earnedSet.has(a.id)).length
  const progressPercent = totalVisible > 0 ? Math.round((totalEarned / totalVisible) * 100) : 0

  const grouped = useMemo(() => {
    const map = new Map<AchievementCategory, Achievement[]>()
    for (const cat of CATEGORY_ORDER) {
      map.set(cat, [])
    }
    for (const ach of ACHIEVEMENTS) {
      map.get(ach.category)!.push(ach)
    }
    return map
  }, [])

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h2 className="text-xl font-bold text-white">업적 갤러리</h2>
        <span className="text-sm text-slate-400 ml-auto" title="Esc로 돌아가기">
          {totalEarned} / {totalVisible} 달성
        </span>
      </div>

      {/* Overall progress */}
      <div className="bg-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-white">업적 진행률</span>
          <span className="text-sm text-slate-400">{progressPercent}%</span>
        </div>
        <div className="bg-slate-700 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all duration-700 ${
              progressPercent === 100 ? 'bg-yellow-500' : 'bg-gradient-to-r from-purple-500 to-purple-400'
            }`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Category sections */}
      {CATEGORY_ORDER.map(cat => {
        const achievements = grouped.get(cat)!
        if (achievements.length === 0) return null
        const meta = CATEGORY_META[cat]
        const earnedInCat = achievements.filter(a => earnedSet.has(a.id)).length

        return (
          <div key={cat}>
            {/* Category header */}
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">{meta.icon}</span>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">{meta.label}</h3>
              <span className="text-xs text-slate-500">
                {earnedInCat}/{cat === 'hidden' ? '?' : achievements.length}
              </span>
            </div>

            {/* Achievement grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {achievements.map(ach => {
                const earned = earnedSet.has(ach.id)
                const isHidden = ach.category === 'hidden' && !earned

                return (
                  <AchievementCard
                    key={ach.id}
                    achievement={ach}
                    earned={earned}
                    isHidden={isHidden}
                  />
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function AchievementCard({
  achievement,
  earned,
  isHidden,
}: {
  achievement: Achievement
  earned: boolean
  isHidden: boolean
}) {
  const rarity = RARITY_STYLES[achievement.rarity]

  if (isHidden) {
    return (
      <div className="rounded-lg border border-slate-700/50 bg-slate-800/50 p-3 flex items-center gap-3 opacity-50">
        <div className="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center text-xl">
          ?
        </div>
        <div className="flex-1">
          <div className="text-sm font-medium text-slate-500">???</div>
          <div className="text-xs text-slate-600">히든 업적</div>
        </div>
      </div>
    )
  }

  return (
    <div className={`rounded-lg border ${earned ? rarity.border : 'border-slate-700/50'} ${earned ? rarity.bg : 'bg-slate-800/50'} p-3 flex items-center gap-3 ${!earned ? 'opacity-40 grayscale' : ''}`}>
      <div className={`w-10 h-10 rounded-full flex items-center justify-center text-xl shrink-0 ${
        earned ? 'bg-slate-700/50' : 'bg-slate-700'
      }`}>
        {achievement.icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${earned ? 'text-white' : 'text-slate-500'}`}>
            {achievement.name}
          </span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
            earned
              ? achievement.rarity === 'legendary' ? 'bg-yellow-600/30 text-yellow-400'
                : achievement.rarity === 'epic' ? 'bg-purple-600/30 text-purple-400'
                : achievement.rarity === 'rare' ? 'bg-blue-600/30 text-blue-400'
                : 'bg-slate-600/30 text-slate-400'
              : 'bg-slate-700 text-slate-600'
          }`}>
            {rarity.label}
          </span>
        </div>
        <div className={`text-xs ${earned ? 'text-slate-400' : 'text-slate-600'} truncate`}>
          {achievement.description}
        </div>
        <div className={`text-xs mt-0.5 ${earned ? 'text-orange-400' : 'text-slate-600'}`}>
          +{achievement.xpReward} XP
        </div>
      </div>
      {earned && <span className="text-green-400 text-lg shrink-0">✓</span>}
    </div>
  )
}
