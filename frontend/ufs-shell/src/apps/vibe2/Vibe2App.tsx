import { useState, useEffect, useRef, useCallback } from 'react'

interface Vibe2Health {
  service: string
  status: string
  version: string
  uptime?: number
  database?: string
}

export default function Vibe2App() {
  const [viewMode, setViewMode] = useState<'overview' | 'dashboard'>('overview')
  const [health, setHealth] = useState<Vibe2Health | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [iframeState, setIframeState] = useState<'loading' | 'loaded' | 'error'>('loading')
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Health check with auto-refresh
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

  // ── Overview mode ──
  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: '#06b6d415' }}>
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="#06b6d4" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2 12l5-5v3h7V7l5 5-5 5v-3H7v3z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">
              VIBE <span className="text-cyan-400">2.0</span>
            </h1>
            <p className="text-ufs-400 text-xs">SOXL Investment Intelligence Briefing</p>
          </div>
        </div>
      </div>

      {/* Actions + Status */}
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <button
          onClick={() => setViewMode('dashboard')}
          className="px-4 py-2.5 rounded-lg bg-cyan-500/20 text-cyan-300 text-sm hover:bg-cyan-500/30 transition-all border border-cyan-500/30 hover:border-cyan-400/50 hover:shadow-lg hover:shadow-cyan-500/10 active:scale-[0.98]"
        >
          Open Dashboard
        </button>
        <a href="/svc/vibe2/" target="_blank" rel="noopener noreferrer"
          className="px-3 py-2.5 rounded-lg bg-cyan-500/10 text-cyan-400 text-sm hover:bg-cyan-500/20 transition-all border border-cyan-500/20 hover:border-cyan-400/40">
          ↗ 새 탭에서 열기
        </a>
        {healthLoading ? (
          <span className="text-xs px-2 py-1 rounded-full bg-ufs-600 text-ufs-400 animate-pulse">checking...</span>
        ) : health ? (
          <span className={`text-xs px-2 py-1 rounded-full ${health.status === 'healthy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
            {health.status} v{health.version}
          </span>
        ) : (
          <span className="text-xs px-2 py-1 rounded-full bg-red-500/20 text-red-400">Backend unreachable</span>
        )}
      </div>

      {/* Quick API Test */}
      <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4 mb-6">
        <span className="text-xs font-semibold text-cyan-300 block mb-2">Quick API Test</span>
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
