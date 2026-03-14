import { useState, useEffect, useRef, useCallback } from 'react'

interface BocchiHealth {
  service: string
  status: string
  version: string
}

export default function BocchiApp() {
  const [viewMode, setViewMode] = useState<'overview' | 'studio'>('overview')
  const [health, setHealth] = useState<BocchiHealth | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [iframeState, setIframeState] = useState<'loading' | 'loaded' | 'error'>('loading')
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const check = () => {
      fetch('/api/bocchi/health')
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => { setHealth(d); setHealthLoading(false) })
        .catch(() => { setHealth(null); setHealthLoading(false) })
    }
    check()
    const interval = setInterval(check, 30_000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (viewMode === 'studio') {
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
    if (iframeRef.current) { iframeRef.current.src = '/svc/bocchi/' }
  }, [])

  const features = [
    { name: 'Fretboard', desc: 'SVG 프렛보드, multi-overlay (scale, voicing, pattern, chord-tone)', icon: '🎸' },
    { name: 'Metronome', desc: 'Web Audio 메트로놈 (accent, subdivision, swing, pendulum)', icon: '🥁' },
    { name: 'Theory', desc: 'Circle of Fifths, 스케일 라이브러리, 코드 보이싱 DB', icon: '🎵' },
    { name: 'Practice', desc: '프렛보드 퀴즈, 코드 전환 타이머, 연습 기록', icon: '📝' },
    { name: 'Progression', desc: 'Markov-chain 랜덤 생성, 프리셋, 보이싱 비교', icon: '🔄' },
    { name: 'Rhythm', desc: '스트럼 패턴 (arrow + notation view)', icon: '🎼' },
    { name: 'MIDI', desc: 'WebMIDI 입력 연동', icon: '🎹' },
    { name: 'Backing Track', desc: '자동 반주 (드럼 + 베이스 패턴)', icon: '🎧' },
    { name: 'Interval Trainer', desc: '이어 트레이닝, 인터벌 인식', icon: '👂' },
    { name: 'Shortcuts', desc: 'Space=play, arrows=BPM, B=backing, P=practice', icon: '⌨️' },
  ]

  if (viewMode === 'studio') {
    return (
      <div className="flex flex-col -m-6" style={{ height: 'calc(100vh - 3.5rem)' }}>
        <div className="flex items-center justify-between px-4 py-2 bg-ufs-800 border-b border-ufs-600/50 shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-sm text-white font-medium">Bocchi-master Studio</span>
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
              <button onClick={handleRetry} className="text-xs text-orange-400 hover:text-orange-300 px-2 py-1 rounded bg-orange-500/10 hover:bg-orange-500/20 transition-colors">
                Retry
              </button>
            )}
            <button
              onClick={() => window.open('/svc/bocchi/', '_blank')}
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
              <div className="w-8 h-8 border-2 border-orange-500/30 border-t-orange-500 rounded-full animate-spin mb-3" />
              <span className="text-sm text-ufs-400">Bocchi Studio 로딩 중...</span>
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
              <p className="text-sm text-ufs-300 mb-1">Studio를 불러올 수 없습니다</p>
              <p className="text-xs text-ufs-500 mb-4">서비스가 실행 중인지 확인해주세요 (port 3001)</p>
              <div className="flex gap-2">
                <button onClick={handleRetry} className="text-xs px-3 py-1.5 rounded bg-orange-500/20 text-orange-300 hover:bg-orange-500/30 transition-colors border border-orange-500/30">
                  다시 시도
                </button>
                <button onClick={() => setViewMode('overview')} className="text-xs px-3 py-1.5 rounded bg-ufs-700 text-ufs-400 hover:bg-ufs-600 hover:text-white transition-colors">
                  Overview로 돌아가기
                </button>
              </div>
            </div>
          )}
          <iframe
            ref={iframeRef}
            src="/svc/bocchi/"
            className="w-full h-full border-0"
            title="Bocchi-master Studio"
            allow="autoplay; midi"
            onLoad={handleIframeLoad}
            onError={handleIframeError}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: '#f9731615' }}>
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="#f97316" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 19V6l12-3v13" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">
              Bocchi<span className="text-orange-500">-master</span>
            </h1>
            <p className="text-ufs-400 text-xs">Guitar &amp; Bass Practice Studio</p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <button
          onClick={() => setViewMode('studio')}
          className="px-4 py-2.5 rounded-lg bg-orange-500/20 text-orange-300 text-sm hover:bg-orange-500/30 transition-all border border-orange-500/30 hover:border-orange-400/50 active:scale-[0.98]"
        >
          Open Studio
        </button>
        <a href="/svc/bocchi/" target="_blank" rel="noopener noreferrer"
          className="px-3 py-2.5 rounded-lg bg-orange-500/10 text-orange-400 text-sm hover:bg-orange-500/20 transition-all border border-orange-500/20 hover:border-orange-400/40">
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

      {/* Stats */}
      <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4 mb-6">
        <div className="flex items-center gap-6 text-xs">
          <div><span className="text-orange-300 font-bold text-lg">50+</span> <span className="text-ufs-400">Features</span></div>
          <div><span className="text-orange-300 font-bold text-lg">2</span> <span className="text-ufs-400">Instruments</span></div>
          <div><span className="text-orange-300 font-bold text-lg">B30</span> <span className="text-ufs-400">Batch</span></div>
        </div>
      </div>

      <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Features ({features.length})</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 stagger-children">
        {features.map((f) => (
          <div key={f.name} className="group p-3 rounded-lg bg-ufs-800 border border-ufs-600/30 hover:border-orange-500/30 hover:bg-ufs-700/50 transition-all">
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
