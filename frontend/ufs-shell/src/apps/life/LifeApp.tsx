import { useState, useEffect, useRef, useCallback } from 'react'

interface DashboardData {
  routines_total: number
  habits_total: number
  active_goals: number
  routines_completion: number
  top_streaks: { name: string; streak: number }[]
}

export default function LifeApp() {
  const [viewMode, setViewMode] = useState<'overview' | 'dashboard'>('overview')
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [iframeState, setIframeState] = useState<'loading' | 'loaded' | 'error'>('loading')
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const fetchDashboard = () => {
      fetch('/api/life/dashboard')
        .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
        .then((d) => { setDashboard(d); setError(null) })
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false))
    }
    fetchDashboard()
    const interval = setInterval(fetchDashboard, 30_000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (viewMode === 'dashboard') {
      setIframeState('loading')
      timeoutRef.current = setTimeout(() => {
        setIframeState((prev) => (prev === 'loading' ? 'error' : prev))
      }, 15000)
    }
    return () => { if (timeoutRef.current) clearTimeout(timeoutRef.current) }
  }, [viewMode])

  const handleIframeLoad = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    setIframeState('loaded')
  }, [])

  const handleIframeError = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    setIframeState('error')
  }, [])

  const handleRetry = useCallback(() => {
    setIframeState('loading')
    timeoutRef.current = setTimeout(() => {
      setIframeState((prev) => (prev === 'loading' ? 'error' : prev))
    }, 15000)
    if (iframeRef.current) { iframeRef.current.src = '/svc/life/' }
  }, [])

  if (viewMode === 'dashboard') {
    return (
      <div className="flex flex-col -m-6" style={{ height: 'calc(100vh - 3.5rem)' }}>
        <div className="flex items-center justify-between px-4 py-2 bg-ufs-800 border-b border-ufs-600/50 shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-sm text-white font-medium">Life-Master Dashboard</span>
            {iframeState === 'loaded' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400">Connected</span>
            )}
            {iframeState === 'loading' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 animate-pulse">Loading...</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {iframeState === 'error' && (
              <button onClick={handleRetry} className="text-xs text-violet-400 hover:text-violet-300 px-2 py-1 rounded bg-violet-500/10 hover:bg-violet-500/20 transition-colors">
                Retry
              </button>
            )}
            <a href="/svc/life/" target="_blank" rel="noopener noreferrer"
              className="text-xs text-ufs-400 hover:text-white px-2 py-1 rounded bg-ufs-700 hover:bg-ufs-600 transition-colors"
              title="새 탭에서 열기"
            >
              ↗
            </a>
            <button onClick={() => setViewMode('overview')} className="text-xs text-ufs-400 hover:text-white px-2 py-1 rounded bg-ufs-700 hover:bg-ufs-600 transition-colors">
              Back to Overview
            </button>
          </div>
        </div>
        <div className="flex-1 relative min-h-0">
          {iframeState === 'loading' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-ufs-900/80 z-10">
              <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin mb-3" />
              <span className="text-sm text-ufs-400">Life-Master Dashboard 로딩 중...</span>
            </div>
          )}
          {iframeState === 'error' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-ufs-900 z-10">
              <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
              </div>
              <p className="text-sm text-ufs-300 mb-1">Dashboard를 불러올 수 없습니다</p>
              <p className="text-xs text-ufs-500 mb-4">Life-Master 서비스 확인 (port 8004)</p>
              <div className="flex gap-2">
                <button onClick={handleRetry} className="text-xs px-3 py-1.5 rounded bg-violet-500/20 text-violet-300 hover:bg-violet-500/30 transition-colors border border-violet-500/30">다시 시도</button>
                <button onClick={() => setViewMode('overview')} className="text-xs px-3 py-1.5 rounded bg-ufs-700 text-ufs-400 hover:bg-ufs-600 hover:text-white transition-colors">Overview로 돌아가기</button>
              </div>
            </div>
          )}
          <iframe ref={iframeRef} src="/svc/life/" className="w-full h-full border-0" title="Life-Master Dashboard" onLoad={handleIframeLoad} onError={handleIframeError} />
        </div>
      </div>
    )
  }

  const features = [
    { name: 'Routines', desc: '일일/주간 루틴 관리', icon: '🔄' },
    { name: 'Habits', desc: '습관 트래커 (스트릭, 히트맵)', icon: '✅' },
    { name: 'Goals', desc: '목표 시스템, 진행률 추적', icon: '🎯' },
    { name: 'Scheduler', desc: '동적 스케줄 최적화', icon: '📅' },
    { name: 'Japanese', desc: '일본어 SRS 학습, JLPT 퀴즈', icon: '🇯🇵' },
    { name: 'Gamification', desc: '80+ 업적, RPG 칭호, XP 시스템', icon: '🏆' },
  ]

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: '#8b5cf615' }}>
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="#8b5cf6" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">
              Life<span className="text-violet-400">-Master</span>
            </h1>
            <p className="text-ufs-400 text-xs">Routine &amp; Schedule Optimizer</p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <button
          onClick={() => setViewMode('dashboard')}
          className="px-4 py-2.5 rounded-lg bg-violet-500/20 text-violet-300 text-sm hover:bg-violet-500/30 transition-all border border-violet-500/30 hover:border-violet-400/50 active:scale-[0.98]"
        >
          Open Dashboard
        </button>
        {!loading && !error && (
          <span className="text-xs px-2 py-1 rounded-full bg-emerald-500/20 text-emerald-400">healthy</span>
        )}
        {error && (
          <span className="text-xs px-2 py-1 rounded-full bg-red-500/20 text-red-400">unreachable</span>
        )}
      </div>

      {/* Dashboard Summary */}
      {loading ? (
        <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-5 mb-6">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-violet-300 text-sm">Loading dashboard...</span>
          </div>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-5 mb-6">
          <p className="text-red-300 text-sm">
            Backend unreachable ({error}). Start with{' '}
            <code className="bg-ufs-700 px-1.5 py-0.5 rounded text-xs">docker compose up life-master</code>
          </p>
        </div>
      ) : dashboard ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Routines', value: dashboard.routines_total, color: 'text-violet-400' },
            { label: 'Habits', value: dashboard.habits_total, color: 'text-blue-400' },
            { label: 'Goals', value: dashboard.active_goals, color: 'text-emerald-400' },
            { label: 'Completion', value: `${Math.round((dashboard.routines_completion ?? 0) * 100)}%`, color: 'text-amber-400' },
          ].map((stat) => (
            <div key={stat.label} className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-3 text-center hover:border-violet-500/30 transition-colors">
              <div className={`text-xl font-bold ${stat.color}`}>{stat.value}</div>
              <div className="text-[10px] text-ufs-400 mt-0.5">{stat.label}</div>
            </div>
          ))}
        </div>
      ) : null}

      {/* Top Streaks */}
      {dashboard?.top_streaks && dashboard.top_streaks.length > 0 && (
        <div className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-4 mb-6">
          <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Top Streaks 🔥</h3>
          <div className="space-y-2">
            {dashboard.top_streaks.map((s, i) => (
              <div key={s.name} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-ufs-500 w-4">{i + 1}.</span>
                  <span className="text-white">{s.name}</span>
                </div>
                <span className="text-amber-400 font-mono font-bold">{s.streak} days</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feature Modules */}
      <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Modules ({features.length})</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 stagger-children">
        {features.map((f) => (
          <div key={f.name} className="group p-3 rounded-lg bg-ufs-800 border border-ufs-600/30 hover:border-violet-500/30 hover:bg-ufs-700/50 transition-all">
            <div className="flex items-center gap-2">
              <span className="text-base">{f.icon}</span>
              <span className="text-sm font-medium text-white">{f.name}</span>
            </div>
            <div className="text-xs text-ufs-400 mt-1 ml-7">{f.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
