import { useState, useEffect, useRef, useCallback } from 'react'

// ── Types ──

interface Vibe2Health {
  service: string
  status: string
  version: string
  uptime?: number
  database?: string
}

interface SignalDetails {
  technical?: Record<string, unknown>
  leverage?: Record<string, unknown>
  macro?: Record<string, unknown>
}

interface SignalResult {
  signal: 'GREEN' | 'YELLOW' | 'RED'
  score: number
  summary: string
  action: string
  risks: string[]
  details: SignalDetails
}

interface BriefingData {
  date: string
  signal: SignalResult
  commentary: string | null
  generated_at: string | null
}

const SIGNAL_COLORS = {
  GREEN: { bg: 'bg-emerald-500/20', border: 'border-emerald-500/40', text: 'text-emerald-400', dot: 'bg-emerald-400', label: 'SAFE' },
  YELLOW: { bg: 'bg-yellow-500/20', border: 'border-yellow-500/40', text: 'text-yellow-400', dot: 'bg-yellow-400', label: 'CAUTION' },
  RED: { bg: 'bg-red-500/20', border: 'border-red-500/40', text: 'text-red-400', dot: 'bg-red-400', label: 'DANGER' },
} as const

const TOKEN_KEY = 'vibe2_token'

// ── Auth helpers ──

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

async function authFetch<T>(url: string): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(url, { headers })
  if (res.status === 401) {
    clearToken()
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

// ── Component ──

export default function Vibe2App() {
  const [viewMode, setViewMode] = useState<'overview' | 'dashboard'>('overview')
  const [health, setHealth] = useState<Vibe2Health | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [iframeState, setIframeState] = useState<'loading' | 'loaded' | 'error'>('loading')
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Auth state
  const [token, setTokenState] = useState<string | null>(getToken)
  const [loginForm, setLoginForm] = useState({ username: '', password: '' })
  const [loginError, setLoginError] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)

  // Data state
  const [signal, setSignal] = useState<SignalResult | null>(null)
  const [briefing, setBriefing] = useState<BriefingData | null>(null)
  const [dataLoading, setDataLoading] = useState(false)
  const [dataError, setDataError] = useState('')

  // Health check with 30s polling
  useEffect(() => {
    const checkHealth = () => {
      fetch('/api/vibe2/health')
        .then((r) => r.ok ? r.json() : null)
        .then((data) => { setHealth(data); setHealthLoading(false) })
        .catch(() => { setHealth(null); setHealthLoading(false) })
    }
    checkHealth()
    const interval = setInterval(checkHealth, 30_000)
    return () => clearInterval(interval)
  }, [])

  // Fetch signal + briefing when token is available
  const fetchData = useCallback(() => {
    if (!token) return
    setDataLoading(true)
    setDataError('')
    Promise.all([
      authFetch<SignalResult>('/api/vibe2/signal/current').catch(() => null),
      authFetch<BriefingData>('/api/vibe2/briefing/latest').catch(() => null),
    ]).then(([sig, brief]) => {
      setSignal(sig)
      setBriefing(brief)
      setDataLoading(false)
    }).catch(() => {
      setDataLoading(false)
      setDataError('Failed to fetch data')
    })
  }, [token])

  useEffect(() => {
    if (token) fetchData()
  }, [token, fetchData])

  // Login handler
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoginLoading(true)
    setLoginError('')
    try {
      const res = await fetch('/api/vibe2/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: 'Login failed' }))
        throw new Error(body.detail || 'Login failed')
      }
      const data = await res.json()
      setToken(data.token)
      setTokenState(data.token)
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoginLoading(false)
    }
  }

  const handleLogout = () => {
    clearToken()
    setTokenState(null)
    setSignal(null)
    setBriefing(null)
  }

  // Iframe lifecycle management
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
    if (iframeRef.current) { iframeRef.current.src = '/svc/vibe2/' }
  }, [])

  const modules = [
    { name: 'Signal Engine', desc: '3축 시그널 (기술/레버리지/매크로) → GREEN/YELLOW/RED', endpoint: '/signal/current', icon: '🚦' },
    { name: 'Daily Briefing', desc: 'LLM 또는 룰 기반 일일 투자 브리핑', endpoint: '/briefing/latest', icon: '📰' },
    { name: 'Signal History', desc: '14일 신호등 이력 타임라인', endpoint: '/signal/history', icon: '📊' },
    { name: 'Price Data', desc: 'SOXL 가격 + MA20 + 거래량 차트', endpoint: '/data/price', icon: '📈' },
    { name: 'Macro Scoring', desc: 'VIX, DXY, 금리, Fear & Greed 분석', endpoint: '/data/macro', icon: '🌍' },
    { name: 'Briefing Refresh', desc: '파이프라인 재실행 + 브리핑 재생성', endpoint: '/briefing/refresh', icon: '⚡' },
  ]

  // ── Dashboard (iframe) mode ──
  if (viewMode === 'dashboard') {
    return (
      <div className="flex flex-col -m-6" style={{ height: 'calc(100vh - 3.5rem)' }}>
        <div className="flex items-center justify-between px-4 py-2 bg-ufs-800 border-b border-ufs-600/50 shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-sm text-white font-medium">VIBE 2.0 Dashboard</span>
            {iframeState === 'loaded' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400">Connected</span>
            )}
            {iframeState === 'loading' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 animate-pulse">Loading...</span>
            )}
            {iframeState === 'error' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400">Disconnected</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {iframeState === 'error' && (
              <button onClick={handleRetry} className="text-xs text-cyan-400 hover:text-cyan-300 px-2 py-1 rounded bg-cyan-500/10 hover:bg-cyan-500/20 transition-colors">
                Retry
              </button>
            )}
            <button
              onClick={() => window.open('/svc/vibe2/', '_blank')}
              className="text-xs text-ufs-400 hover:text-white px-2 py-1 rounded bg-ufs-700 hover:bg-ufs-600 transition-colors"
              title="새 탭에서 열기"
            >
              ↗
            </button>
            <button onClick={() => setViewMode('overview')} className="text-xs text-ufs-400 hover:text-white px-2 py-1 rounded bg-ufs-700 hover:bg-ufs-600 transition-colors">
              Back to Overview
            </button>
          </div>
        </div>

        <div className="flex-1 relative min-h-0">
          {iframeState === 'loading' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-ufs-900/80 z-10">
              <div className="w-8 h-8 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mb-3" />
              <span className="text-sm text-ufs-400">VIBE 2.0 Dashboard 로딩 중...</span>
              <span className="text-xs text-ufs-500 mt-1">서비스 연결 확인 중</span>
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
              <p className="text-xs text-ufs-500 mb-4">VIBE 2.0 서비스가 실행 중인지 확인해주세요 (port 8010)</p>
              <div className="flex gap-2">
                <button onClick={handleRetry} className="text-xs px-3 py-1.5 rounded bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 transition-colors border border-cyan-500/30">
                  다시 시도
                </button>
                <button onClick={() => setViewMode('overview')} className="text-xs px-3 py-1.5 rounded bg-ufs-700 text-ufs-400 hover:bg-ufs-600 hover:text-white transition-colors">
                  Overview로 돌아가기
                </button>
              </div>
            </div>
          )}
          <iframe ref={iframeRef} src="/svc/vibe2/" className="w-full h-full border-0" title="VIBE 2.0 Dashboard" onLoad={handleIframeLoad} onError={handleIframeError} />
        </div>
      </div>
    )
  }

  // ── Signal color config ──
  const sc = signal ? SIGNAL_COLORS[signal.signal] : null

  // ── Overview mode ──
  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: '#06b6d415' }}>
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="#06b6d4" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2 12l5-5v3h7V7l5 5-5 5v-3H7v3z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">VIBE <span className="text-cyan-400">2.0</span></h1>
              <p className="text-ufs-400 text-xs">SOXL Investment Intelligence Briefing</p>
            </div>
          </div>
          {/* Health indicator */}
          <div className="flex items-center gap-2">
            {healthLoading ? (
              <span className="text-xs px-2.5 py-1 rounded-full bg-ufs-600 text-ufs-400 animate-pulse">checking...</span>
            ) : health ? (
              <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                v{health.version}
                {health.uptime != null && <span className="text-emerald-500/60">| {Math.floor(health.uptime / 60)}m</span>}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-red-500/15 text-red-400 border border-red-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                Offline
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Dashboard CTA — prominent */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => setViewMode('dashboard')}
          className="flex-1 sm:flex-none px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-600/30 to-cyan-500/20 text-cyan-200 text-sm font-medium hover:from-cyan-600/40 hover:to-cyan-500/30 transition-all border border-cyan-500/30 hover:border-cyan-400/50 hover:shadow-lg hover:shadow-cyan-500/10 active:scale-[0.98]"
        >
          Open Full Dashboard
        </button>
        <a href="/svc/vibe2/" target="_blank" rel="noopener noreferrer"
          className="px-3 py-3 rounded-xl bg-ufs-800 text-ufs-400 text-sm hover:text-cyan-400 hover:bg-ufs-700 transition-all border border-ufs-600/30 hover:border-cyan-500/30">
          ↗
        </a>
        {token && (
          <button onClick={handleLogout} className="text-xs text-ufs-500 hover:text-red-400 px-2 py-1 transition-colors">
            Logout
          </button>
        )}
      </div>

      {/* Login / Signal+Briefing area */}
      {!token ? (
        /* ── Login Form ── */
        <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-5 mb-6">
          <h3 className="text-sm font-semibold text-cyan-300 mb-3">Login to view live data</h3>
          <form onSubmit={handleLogin} className="flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[140px]">
              <label className="text-[11px] text-ufs-400 block mb-1">Username</label>
              <input
                type="text"
                value={loginForm.username}
                onChange={(e) => setLoginForm(f => ({ ...f, username: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg bg-ufs-800 border border-ufs-600/50 text-sm text-white placeholder-ufs-500 focus:border-cyan-500/50 focus:outline-none transition-colors"
                placeholder="dev"
                autoComplete="username"
              />
            </div>
            <div className="flex-1 min-w-[140px]">
              <label className="text-[11px] text-ufs-400 block mb-1">Password</label>
              <input
                type="password"
                value={loginForm.password}
                onChange={(e) => setLoginForm(f => ({ ...f, password: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg bg-ufs-800 border border-ufs-600/50 text-sm text-white placeholder-ufs-500 focus:border-cyan-500/50 focus:outline-none transition-colors"
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
            <button
              type="submit"
              disabled={loginLoading}
              className="px-4 py-2 rounded-lg bg-cyan-500/20 text-cyan-300 text-sm hover:bg-cyan-500/30 transition-colors border border-cyan-500/30 disabled:opacity-50"
            >
              {loginLoading ? 'Logging in...' : 'Login'}
            </button>
          </form>
          {loginError && <p className="text-xs text-red-400 mt-2">{loginError}</p>}
        </div>
      ) : (
        /* ── Live Data Cards ── */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          {/* Signal Summary Card */}
          <div className={`rounded-xl border p-4 ${sc ? `${sc.bg} ${sc.border}` : 'border-ufs-600/30 bg-ufs-800'}`}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider">Current Signal</h3>
              <button onClick={fetchData} disabled={dataLoading} className="text-[10px] text-ufs-500 hover:text-cyan-400 transition-colors disabled:opacity-50">
                {dataLoading ? 'loading...' : 'refresh'}
              </button>
            </div>
            {dataLoading && !signal ? (
              <div className="flex items-center justify-center py-6">
                <div className="w-5 h-5 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
              </div>
            ) : signal ? (
              <>
                <div className="flex items-center gap-3 mb-3">
                  <div className={`w-12 h-12 rounded-xl ${sc!.bg} flex items-center justify-center`}>
                    <span className={`w-4 h-4 rounded-full ${sc!.dot}`} />
                  </div>
                  <div>
                    <div className={`text-2xl font-bold ${sc!.text}`}>{signal.signal}</div>
                    <div className="text-xs text-ufs-400">Score: {signal.score}/100</div>
                  </div>
                </div>
                {signal.summary && (
                  <p className="text-xs text-ufs-300 mb-2 leading-relaxed">{signal.summary}</p>
                )}
                {signal.action && (
                  <div className="text-[11px] text-ufs-400 bg-ufs-900/50 rounded-lg px-3 py-2">
                    <span className="text-cyan-400 font-medium">Action:</span> {signal.action}
                  </div>
                )}
                {signal.risks.length > 0 && (
                  <div className="mt-2">
                    <span className="text-[10px] text-ufs-500 uppercase">Risks:</span>
                    <ul className="mt-1 space-y-0.5">
                      {signal.risks.slice(0, 3).map((r, i) => (
                        <li key={i} className="text-[11px] text-red-400/80 flex items-start gap-1">
                          <span className="mt-0.5 shrink-0">!</span> {r}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : dataError ? (
              <p className="text-xs text-red-400 py-4">{dataError}</p>
            ) : (
              <p className="text-xs text-ufs-500 py-4">No signal data available</p>
            )}
          </div>

          {/* Briefing Preview Card */}
          <div className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider">Latest Briefing</h3>
              {briefing?.date && (
                <span className="text-[10px] text-ufs-500">{briefing.date}</span>
              )}
            </div>
            {dataLoading && !briefing ? (
              <div className="flex items-center justify-center py-6">
                <div className="w-5 h-5 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
              </div>
            ) : briefing ? (
              <>
                {briefing.commentary ? (
                  <p className="text-xs text-ufs-300 leading-relaxed line-clamp-6 whitespace-pre-line">
                    {briefing.commentary}
                  </p>
                ) : (
                  <p className="text-xs text-ufs-500 italic">No commentary available</p>
                )}
                {briefing.generated_at && (
                  <p className="text-[10px] text-ufs-500 mt-3">
                    Generated: {new Date(briefing.generated_at).toLocaleString('ko-KR')}
                  </p>
                )}
                <button
                  onClick={() => setViewMode('dashboard')}
                  className="mt-3 text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
                >
                  View full briefing in Dashboard →
                </button>
              </>
            ) : (
              <p className="text-xs text-ufs-500 py-4">No briefing data available</p>
            )}
          </div>
        </div>
      )}

      {/* Quick API Test */}
      <div className="rounded-xl border border-ufs-600/20 bg-ufs-800/50 p-4 mb-6">
        <span className="text-xs font-semibold text-ufs-500 block mb-2">Quick API Test</span>
        <div className="flex flex-wrap gap-2">
          {[
            { label: 'Health', url: '/api/vibe2/health' },
            { label: 'Signal', url: '/api/vibe2/signal/current' },
            { label: 'Briefing', url: '/api/vibe2/briefing/latest' },
            { label: 'Macro', url: '/api/vibe2/data/macro' },
          ].map(ep => (
            <a key={ep.label} href={ep.url} target="_blank" rel="noopener noreferrer"
              className="text-[11px] px-2 py-1 rounded bg-ufs-700 text-ufs-400 hover:text-cyan-300 hover:bg-ufs-600 transition-colors font-mono">
              {ep.label}
            </a>
          ))}
        </div>
      </div>

      {/* Modules Grid */}
      <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Modules ({modules.length})</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {modules.map((m) => (
          <div key={m.name} className="group p-3 rounded-lg bg-ufs-800 border border-ufs-600/30 hover:border-cyan-500/30 hover:bg-ufs-700/50 transition-all cursor-default">
            <div className="flex items-center gap-2">
              <span className="text-base">{m.icon}</span>
              <span className="text-sm font-medium text-white">{m.name}</span>
            </div>
            <div className="text-xs text-ufs-400 mt-1 ml-7">{m.desc}</div>
            {m.endpoint && <code className="text-[10px] text-ufs-500 mt-1 block ml-7 group-hover:text-cyan-400/60 transition-colors">{m.endpoint}</code>}
          </div>
        ))}
      </div>
    </div>
  )
}
