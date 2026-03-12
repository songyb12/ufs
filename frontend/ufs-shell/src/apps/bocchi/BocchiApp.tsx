import { useState, useEffect, useRef, useCallback } from 'react'

interface BocchiHealth {
  service: string
  status: string
  version: string
}

export default function BocchiApp() {
  const [viewMode, setViewMode] = useState<'overview' | 'studio'>('overview')
  const [health, setHealth] = useState<BocchiHealth | null>(null)
  const [iframeState, setIframeState] = useState<'loading' | 'loaded' | 'error'>('loading')
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    fetch('/api/bocchi/health')
      .then((r) => (r.ok ? r.json() : null))
      .then(setHealth)
      .catch(() => null)
  }, [])

  // Reset iframe state when entering studio mode
  useEffect(() => {
    if (viewMode === 'studio') {
      setIframeState('loading')
      // Timeout: if iframe doesn't load within 15s, show error
      timeoutRef.current = setTimeout(() => {
        setIframeState((prev) => (prev === 'loading' ? 'error' : prev))
      }, 15000)
    }
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
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
    if (iframeRef.current) {
      iframeRef.current.src = '/svc/bocchi/'
    }
  }, [])

  const features = [
    { name: 'Fretboard', desc: 'SVG fretboard with multi-overlay (scale, voicing, pattern, chord-tone)' },
    { name: 'Metronome', desc: 'Web Audio metronome with accent, subdivision, swing, pendulum' },
    { name: 'Theory', desc: 'Circle of Fifths, scale library, chord voicing DB (guitar + bass)' },
    { name: 'Practice', desc: 'Fretboard quiz, chord transition timer, practice log export/import' },
    { name: 'Progression', desc: 'Markov-chain random generation, presets, voicing comparison' },
    { name: 'Rhythm', desc: 'Strum pattern (arrow + notation view)' },
    { name: 'MIDI', desc: 'WebMIDI input integration' },
    { name: 'Backing Track', desc: 'Auto-accompaniment with drum + bass patterns' },
    { name: 'Interval Trainer', desc: 'Ear training with interval recognition' },
    { name: 'Keyboard Shortcuts', desc: 'Space=play, arrows=BPM/chord, B=backing, P=practice' },
  ]

  if (viewMode === 'studio') {
    return (
      <div className="flex flex-col -m-6" style={{ height: 'calc(100vh - 3rem)' }}>
        {/* Studio header bar */}
        <div className="flex items-center justify-between px-4 py-2 bg-ufs-800 border-b border-ufs-600/50 shrink-0">
          <span className="text-sm text-white font-medium">Bocchi-master Studio</span>
          <div className="flex items-center gap-2">
            {iframeState === 'loaded' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400">
                Connected
              </span>
            )}
            {iframeState === 'loading' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 animate-pulse">
                Loading...
              </span>
            )}
            <button
              onClick={() => setViewMode('overview')}
              className="text-xs text-ufs-400 hover:text-white px-2 py-1 rounded bg-ufs-700 hover:bg-ufs-600 transition-colors"
            >
              Back to Overview
            </button>
          </div>
        </div>

        {/* iframe container */}
        <div className="flex-1 relative min-h-0">
          {/* Loading overlay */}
          {iframeState === 'loading' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-ufs-900/80 z-10">
              <div className="w-8 h-8 border-2 border-orange-500/30 border-t-orange-500 rounded-full animate-spin mb-3" />
              <span className="text-sm text-ufs-400">Bocchi Studio 로딩 중...</span>
            </div>
          )}

          {/* Error state */}
          {iframeState === 'error' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-ufs-900 z-10">
              <div className="text-3xl mb-3">⚠️</div>
              <p className="text-sm text-ufs-300 mb-1">Studio를 불러올 수 없습니다</p>
              <p className="text-xs text-ufs-500 mb-4">서비스가 실행 중인지 확인해주세요</p>
              <div className="flex gap-2">
                <button
                  onClick={handleRetry}
                  className="text-xs px-3 py-1.5 rounded bg-orange-500/20 text-orange-300 hover:bg-orange-500/30 transition-colors border border-orange-500/30"
                >
                  다시 시도
                </button>
                <button
                  onClick={() => setViewMode('overview')}
                  className="text-xs px-3 py-1.5 rounded bg-ufs-700 text-ufs-400 hover:bg-ufs-600 hover:text-white transition-colors"
                >
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
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-white mb-1">
          Bocchi<span className="text-orange-500">-master</span>
        </h1>
        <p className="text-ufs-400 text-sm">Guitar &amp; Bass Practice Studio</p>
      </div>

      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => setViewMode('studio')}
          className="px-4 py-2 rounded-lg bg-orange-500/20 text-orange-300 text-sm hover:bg-orange-500/30 transition-colors border border-orange-500/30"
        >
          Open Studio
        </button>
        {health && (
          <span
            className={`text-xs px-2 py-1 rounded-full ${
              health.status === 'healthy'
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'bg-yellow-500/20 text-yellow-400'
            }`}
          >
            {health.status} v{health.version}
          </span>
        )}
        {!health && (
          <span className="text-xs px-2 py-1 rounded-full bg-red-500/20 text-red-400">
            Backend unreachable
          </span>
        )}
      </div>

      <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Features</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {features.map((f) => (
          <div key={f.name} className="p-3 rounded-lg bg-ufs-800 border border-ufs-600/30">
            <div className="text-sm font-medium text-white">{f.name}</div>
            <div className="text-xs text-ufs-400 mt-0.5">{f.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
