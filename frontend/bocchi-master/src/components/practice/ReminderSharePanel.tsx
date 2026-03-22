/**
 * Practice Reminder & Share Panel
 *
 * Two sections:
 * 1. Reminder — schedules browser Notification API alerts at user-set times
 * 2. Share — formats session stats as text, copies to clipboard or shares via Web Share API
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import {
  loadReminderSettings,
  saveReminderSettings,
  loadDailyGoal,
  loadSettings,
  type ReminderSettings,
} from '../../utils/storage'
import { loadPlayerProfile, getPlayerLevel } from '../../data/gamification'

// ─── Constants ──────────────────────────────────────

const DAY_LABELS = ['일', '월', '화', '수', '목', '금', '토'] as const

type NotifPermission = 'default' | 'granted' | 'denied' | 'unsupported'

// ─── Component ──────────────────────────────────────

export function ReminderSharePanel() {
  const [expanded, setExpanded] = useState(false)
  const [tab, setTab] = useState<'reminder' | 'share'>('reminder')

  return (
    <div className="bg-slate-800/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">🔔</span>
          <span className="font-semibold text-white text-sm">리마인더 & 공유</span>
        </div>
        <svg className={`w-4 h-4 text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Tab switch */}
          <div className="flex gap-1 bg-slate-700/50 rounded-lg p-0.5">
            <button
              onClick={() => setTab('reminder')}
              className={`flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                tab === 'reminder' ? 'bg-slate-600 text-white' : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              🔔 리마인더
            </button>
            <button
              onClick={() => setTab('share')}
              className={`flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                tab === 'share' ? 'bg-slate-600 text-white' : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              📤 성과 공유
            </button>
          </div>

          {tab === 'reminder' ? <ReminderTab /> : <ShareTab />}
        </div>
      )}
    </div>
  )
}

// ─── Reminder Tab ───────────────────────────────────

function ReminderTab() {
  const [settings, setSettings] = useState<ReminderSettings>(loadReminderSettings)
  const [permission, setPermission] = useState<NotifPermission>(() => {
    if (typeof Notification === 'undefined') return 'unsupported'
    return Notification.permission as NotifPermission
  })
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Persist settings on change
  useEffect(() => {
    saveReminderSettings(settings)
  }, [settings])

  // Request notification permission — must be inside user click handler
  const requestPermission = useCallback(async () => {
    if (typeof Notification === 'undefined') return
    const result = await Notification.requestPermission()
    setPermission(result as NotifPermission)
    if (result === 'granted') {
      setSettings(prev => ({ ...prev, enabled: true }))
    }
  }, [])

  const toggleEnabled = useCallback(() => {
    if (permission !== 'granted') {
      requestPermission()
      return
    }
    setSettings(prev => {
      const next = { ...prev, enabled: !prev.enabled }
      return next
    })
  }, [permission, requestPermission])

  const toggleDay = useCallback((day: number) => {
    setSettings(prev => {
      const days = prev.days.includes(day)
        ? prev.days.filter(d => d !== day)
        : [...prev.days, day].sort()
      return { ...prev, days }
    })
  }, [])

  const setTime = useCallback((time: string) => {
    setSettings(prev => ({ ...prev, time }))
  }, [])

  // Scheduler: check every 30s if it's time to fire a notification
  useEffect(() => {
    if (!settings.enabled || permission !== 'granted') {
      if (timerRef.current) clearInterval(timerRef.current)
      return
    }

    const firedToday = new Set<string>()

    const check = () => {
      const now = new Date()
      const dayOfWeek = now.getDay()
      const hhmm = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
      const key = `${now.toISOString().slice(0, 10)}-${hhmm}`

      if (
        settings.days.includes(dayOfWeek) &&
        hhmm === settings.time &&
        !firedToday.has(key)
      ) {
        firedToday.add(key)
        new Notification('🎸 연습 시간이에요!', {
          body: '오늘도 기타 연습을 시작해보세요. Bocchi-master가 기다리고 있어요!',
          icon: '/favicon.ico',
          tag: 'bocchi-reminder',
        })
      }
    }

    check()
    timerRef.current = setInterval(check, 30_000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [settings.enabled, settings.time, settings.days, permission])

  return (
    <div className="space-y-3">
      {/* Permission status */}
      {permission === 'unsupported' && (
        <div className="text-xs text-rose-400 bg-rose-900/20 rounded-lg px-3 py-2">
          이 브라우저는 알림을 지원하지 않습니다
        </div>
      )}
      {permission === 'denied' && (
        <div className="text-xs text-rose-400 bg-rose-900/20 rounded-lg px-3 py-2">
          알림 권한이 차단되었습니다. 브라우저 설정에서 허용해주세요.
        </div>
      )}

      {/* Enable toggle */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-300">연습 리마인더</span>
        <button
          onClick={toggleEnabled}
          className={`relative w-10 h-5 rounded-full transition-colors ${
            settings.enabled && permission === 'granted' ? 'bg-violet-600' : 'bg-slate-600'
          }`}
        >
          <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            settings.enabled && permission === 'granted' ? 'translate-x-5' : 'translate-x-0.5'
          }`} />
        </button>
      </div>

      {/* Time picker */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-400">알림 시간</span>
        <input
          type="time"
          value={settings.time}
          onChange={e => setTime(e.target.value)}
          className="bg-slate-700 border border-slate-600 rounded-lg px-2 py-1 text-sm text-white
            focus:outline-none focus:border-violet-500"
        />
      </div>

      {/* Day selector */}
      <div>
        <span className="text-xs text-slate-400 block mb-1.5">요일 선택</span>
        <div className="flex gap-1">
          {DAY_LABELS.map((label, i) => (
            <button
              key={i}
              onClick={() => toggleDay(i)}
              className={`w-8 h-8 rounded-lg text-xs font-medium transition-colors ${
                settings.days.includes(i)
                  ? 'bg-violet-600 text-white'
                  : 'bg-slate-700 text-slate-500 hover:text-slate-400'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Test notification */}
      {permission === 'granted' && (
        <button
          onClick={() => {
            new Notification('🎸 테스트 알림', {
              body: '리마인더가 정상적으로 작동합니다!',
              tag: 'bocchi-test',
            })
          }}
          className="w-full py-2 rounded-lg bg-slate-700 text-slate-400 text-xs hover:bg-slate-600 transition-colors"
        >
          테스트 알림 보내기
        </button>
      )}

      {permission === 'default' && (
        <button
          onClick={requestPermission}
          className="w-full py-2 rounded-lg bg-violet-600/20 text-violet-400 text-xs
            border border-violet-600/30 hover:bg-violet-600/30 transition-colors"
        >
          알림 권한 허용하기
        </button>
      )}
    </div>
  )
}

// ─── Share Tab ──────────────────────────────────────

function ShareTab() {
  const [copied, setCopied] = useState(false)
  const [shared, setShared] = useState(false)

  const buildShareText = useCallback((): string => {
    const profile = loadPlayerProfile()
    const dailyGoal = loadDailyGoal()
    const settings = loadSettings()
    const today = new Date().toISOString().slice(0, 10)

    const lines: string[] = ['🎸 Bocchi-master 연습 기록', '']

    // Player info
    if (profile) {
      const level = getPlayerLevel(profile.xp)
      lines.push(`${level.icon} Lv.${level.level} ${level.title}`)
      lines.push(`XP: ${profile.xp} · 연속 ${profile.streakDays}일`)
      lines.push(`업적: ${profile.achievements.length}개 달성`)
      lines.push(`드릴: ${profile.completedDrills.length}개 완료`)
      lines.push('')
    }

    // Today's practice
    const todaySec = dailyGoal.dailyLog[today] ?? 0
    if (todaySec > 0) {
      const min = Math.floor(todaySec / 60)
      const pct = dailyGoal.targetMinutes > 0
        ? Math.min(100, Math.round((todaySec / (dailyGoal.targetMinutes * 60)) * 100))
        : 0
      lines.push(`오늘 연습: ${min}분 (목표 ${pct}%)`)
    }

    // Recent sessions summary
    const recent = settings.practiceHistory.slice(0, 5)
    if (recent.length > 0) {
      const avgAcc = Math.round(recent.reduce((s, r) => s + r.accuracy, 0) / recent.length)
      lines.push(`최근 ${recent.length}세션 평균 정확도: ${avgAcc}%`)
    }

    // Weekly practice (last 7 days)
    if (profile) {
      let weekTotal = 0
      for (let i = 0; i < 7; i++) {
        const d = new Date()
        d.setDate(d.getDate() - i)
        const key = d.toISOString().slice(0, 10)
        weekTotal += profile.dailyPracticeLog[key] ?? 0
      }
      if (weekTotal > 0) {
        lines.push(`이번 주 연습: ${Math.floor(weekTotal / 60)}분`)
      }
    }

    lines.push('')
    lines.push('#BocchiMaster #기타연습')

    return lines.join('\n')
  }, [])

  const handleCopy = useCallback(async () => {
    const text = buildShareText()
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback: textarea copy
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [buildShareText])

  const handleShare = useCallback(async () => {
    const text = buildShareText()

    // Web Share API
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Bocchi-master 연습 기록',
          text,
        })
        setShared(true)
        setTimeout(() => setShared(false), 2000)
        return
      } catch {
        // User cancelled or error — fall through to clipboard
      }
    }

    // Fallback to clipboard
    handleCopy()
  }, [buildShareText, handleCopy])

  // Preview text
  const preview = buildShareText()

  return (
    <div className="space-y-3">
      <div className="text-xs text-slate-400">연습 성과를 공유하세요</div>

      {/* Preview */}
      <div className="bg-slate-900/50 rounded-lg p-3 text-[11px] text-slate-300 font-mono whitespace-pre-line leading-relaxed max-h-48 overflow-y-auto">
        {preview}
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={handleCopy}
          className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
            copied
              ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-600/30'
              : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
          }`}
        >
          {copied ? '✓ 복사됨!' : '📋 클립보드 복사'}
        </button>
        <button
          onClick={handleShare}
          className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
            shared
              ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-600/30'
              : 'bg-violet-600/20 text-violet-400 border border-violet-600/30 hover:bg-violet-600/30'
          }`}
        >
          {shared ? '✓ 공유됨!' : '📤 공유하기'}
        </button>
      </div>

      {!navigator.share && (
        <div className="text-[10px] text-slate-500 text-center">
          이 브라우저에서는 클립보드 복사만 지원됩니다
        </div>
      )}
    </div>
  )
}
