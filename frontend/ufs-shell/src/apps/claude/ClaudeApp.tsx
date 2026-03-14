import { useState, useEffect, useRef, useCallback } from 'react'

interface SessionManagerHealth {
  status: string
  sessions?: number
}

const ENABLED_KEY = 'ufs-claude-session-enabled'

export default function ClaudeApp() {
  const [enabled, setEnabled] = useState(() => localStorage.getItem(ENABLED_KEY) === 'true')
  const [viewMode, setViewMode] = useState<'overview' | 'manager'>('overview')
  const [health, setHealth] = useState<SessionManagerHealth | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [iframeState, setIframeState] = useState<'loading' | 'loaded' | 'error'>('loading')
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const toggleEnabled = useCallback(() => {
    setEnabled((prev) => {
      const next = !prev
      localStorage.setItem(ENABLED_KEY, String(next))
      if (!next) setViewMode('overview')
      return next
    })
  }, [])

  useEffect(() => {
    if (!enabled) { setHealth(null); setHealthLoading(false); return }
    const checkHealth = () => {
      fetch('/api/claude/health')
        .then((r) => r.ok ? r.json() : null)
        .then((data) => { setHealth(data); setHealthLoading(false) })
        .catch(() => { setHealth(null); setHealthLoading(false) })
    }
    checkHealth()
    const interval = setInterval(checkHealth, 30_000)
    return () => clearInterval(interval)
  }, [enabled])

  useEffect(() => {
    if (viewMode === 'manager') {
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
    if (iframeRef.current) { iframeRef.current.src = '/svc/claude/' }
  }, [])

  const features = [
    { name: 'Multi-Session', desc: '독립 작업 디렉토리별 동시 세션 관리', icon: '🔀' },
    { name: 'WebSocket Streaming', desc: '실시간 출력 스트리밍 (WebSocket)', icon: '⚡' },
    { name: 'Prompt Queue', desc: '세션당 프롬프트 큐잉 (순차 실행)', icon: '📋' },
    { name: 'Session Resume', desc: '--resume 플래그로 이전 대화 이어하기', icon: '🔄' },
    { name: 'Model Selection', desc: 'claude-sonnet-4-20250514 등 모델 선택', icon: '🧠' },
    { name: 'Auto Cleanup', desc: '10분 유휴 시 자동 정리, 프로세스 관리', icon: '🧹' },
  ]

  if (viewMode === 'manager') {
    return (
      <div className="flex flex-col -m-6" style={{ height: 'calc(100vh - 3.5rem)' }}>
        <div className="flex items-center justify-between px-4 py-2 bg-ufs-800 border-b border-ufs-600/50 shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-sm text-white font-medium">Claude Session Manager</span>
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
              <button onClick={handleRetry} className="text-xs text-amber-400 hover:text-amber-300 px-2 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20 transition-colors">
                Retry
              </button>
            )}
            <a href="/svc/claude/" target="_blank" rel="noopener noreferrer"
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
              <div className="w-8 h-8 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin mb-3" />
              <span className="text-sm text-ufs-400">Session Manager 로딩 중...</span>
            </div>
          )}
          {iframeState === 'error' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-ufs-900 z-10">
              <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
              </div>
              <p className="text-sm text-ufs-300 mb-1">Session Manager를 불러올 수 없습니다</p>
              <p className="text-xs text-ufs-500 mb-4">서비스 확인 (port 8006)</p>
              <div className="flex gap-2">
                <button onClick={handleRetry} className="text-xs px-3 py-1.5 rounded bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 transition-colors border border-amber-500/30">다시 시도</button>
                <button onClick={() => setViewMode('overview')} className="text-xs px-3 py-1.5 rounded bg-ufs-700 text-ufs-400 hover:bg-ufs-600 hover:text-white transition-colors">Overview로 돌아가기</button>
              </div>
            </div>
          )}
          <iframe ref={iframeRef} src="/svc/claude/" className="w-full h-full border-0" title="Claude Session Manager" onLoad={handleIframeLoad} onError={handleIframeError} />
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: '#d9770615' }}>
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="#d97706" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.5 14.5A2.5 2.5 0 0011 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 11-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 002.5 2.5z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">
              Claude <span className="text-amber-500">Session Manager</span>
            </h1>
            <p className="text-ufs-400 text-xs">AI CLI Session Management Web UI</p>
          </div>
        </div>
      </div>

      {/* On/Off Toggle */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={toggleEnabled}
          className={`relative w-11 h-6 rounded-full transition-colors ${enabled ? 'bg-amber-500' : 'bg-ufs-600'}`}
        >
          <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${enabled ? 'translate-x-5' : ''}`} />
        </button>
        <span className={`text-sm font-medium ${enabled ? 'text-amber-400' : 'text-ufs-500'}`}>
          {enabled ? 'Enabled' : 'Disabled'}
        </span>
      </div>

      {!enabled ? (
        /* Disabled state — cost info */
        <div className="space-y-4">
          <div className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-5">
            <h3 className="text-sm font-semibold text-white mb-3">API Cost Estimate</h3>
            <p className="text-xs text-ufs-400 mb-4">
              Session Manager는 Anthropic API 키를 사용합니다. 별도 과금이 발생하므로 필요 시에만 활성화하세요.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-ufs-900 border border-ufs-600/20 p-3">
                <div className="text-[10px] text-ufs-500 uppercase tracking-wider mb-1">Opus 4.6</div>
                <div className="text-xs text-ufs-300">Input: <span className="text-amber-400 font-mono">$15</span>/MTok</div>
                <div className="text-xs text-ufs-300">Output: <span className="text-amber-400 font-mono">$75</span>/MTok</div>
              </div>
              <div className="rounded-lg bg-ufs-900 border border-ufs-600/20 p-3">
                <div className="text-[10px] text-ufs-500 uppercase tracking-wider mb-1">Sonnet 4.6</div>
                <div className="text-xs text-ufs-300">Input: <span className="text-amber-400 font-mono">$3</span>/MTok</div>
                <div className="text-xs text-ufs-300">Output: <span className="text-amber-400 font-mono">$15</span>/MTok</div>
              </div>
            </div>
            <div className="mt-3 rounded-lg bg-amber-500/5 border border-amber-500/20 p-3">
              <div className="text-[10px] text-amber-400 uppercase tracking-wider mb-1">Estimated per Session</div>
              <div className="text-xs text-ufs-300">
                Simple task: <span className="text-amber-400 font-mono">$0.5~2</span> | Complex task: <span className="text-amber-400 font-mono">$5~20+</span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-4">
            <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Alternative: Claude Code Desktop</h3>
            <p className="text-xs text-ufs-400">
              Max 플랜 ($100~200/월) 구독 시 Claude Code Desktop에서 무제한 사용 가능.
              API 과금 대비 훨씬 경제적입니다.
            </p>
          </div>
        </div>
      ) : (
        /* Enabled state — normal UI */
        <>
          <div className="flex items-center gap-3 mb-6 flex-wrap">
            <button
              onClick={() => setViewMode('manager')}
              className="px-4 py-2.5 rounded-lg bg-amber-500/20 text-amber-300 text-sm hover:bg-amber-500/30 transition-all border border-amber-500/30 hover:border-amber-400/50 active:scale-[0.98]"
            >
              Open Manager
            </button>
            <a href="/svc/claude/" target="_blank" rel="noopener noreferrer"
              className="px-3 py-2.5 rounded-lg bg-amber-500/10 text-amber-400 text-sm hover:bg-amber-500/20 transition-all border border-amber-500/20 hover:border-amber-400/40">
              ↗ 새 탭에서 열기
            </a>
            {healthLoading ? (
              <span className="text-xs px-2 py-1 rounded-full bg-ufs-600 text-ufs-400 animate-pulse">checking...</span>
            ) : health ? (
              <span className="text-xs px-2 py-1 rounded-full bg-emerald-500/20 text-emerald-400">
                healthy{health.sessions != null ? ` (${health.sessions} sessions)` : ''}
              </span>
            ) : (
              <span className="text-xs px-2 py-1 rounded-full bg-red-500/20 text-red-400">Backend unreachable</span>
            )}
          </div>

          <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 mb-6">
            <div className="flex items-center gap-6 text-xs">
              <div><span className="text-amber-300 font-bold text-lg">WebSocket</span> <span className="text-ufs-400">Real-time</span></div>
              <div><span className="text-amber-300 font-bold text-lg">Multi</span> <span className="text-ufs-400">Sessions</span></div>
              <div><span className="text-amber-300 font-bold text-lg">:8006</span> <span className="text-ufs-400">Port</span></div>
            </div>
          </div>

          <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Features ({features.length})</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 stagger-children">
            {features.map((f) => (
              <div key={f.name} className="group p-3 rounded-lg bg-ufs-800 border border-ufs-600/30 hover:border-amber-500/30 hover:bg-ufs-700/50 transition-all">
                <div className="flex items-center gap-2">
                  <span className="text-base">{f.icon}</span>
                  <span className="text-sm font-medium text-white">{f.name}</span>
                </div>
                <div className="text-xs text-ufs-400 mt-1 ml-7">{f.desc}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
