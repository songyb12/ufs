import { useState, useEffect } from 'react'

interface VibeHealth {
  service: string
  status: string
  version: string
}

export default function VibeApp() {
  const [viewMode, setViewMode] = useState<'overview' | 'dashboard'>('overview')
  const [health, setHealth] = useState<VibeHealth | null>(null)

  useEffect(() => {
    fetch('/api/vibe/health')
      .then((r) => r.ok ? r.json() : null)
      .then(setHealth)
      .catch(() => null)
  }, [])

  const modules = [
    { name: 'Overview', desc: 'Portfolio summary & key metrics', endpoint: '/dashboard/overview' },
    { name: 'Signals', desc: 'Trading signal aggregation', endpoint: '/dashboard/signals' },
    { name: 'Portfolio', desc: 'Position tracking & allocation', endpoint: '/dashboard/portfolio' },
    { name: 'Backtest', desc: 'Strategy backtesting engine', endpoint: '/backtest' },
    { name: 'Market Brief', desc: 'Daily market intelligence', endpoint: '/briefing/today' },
    { name: 'Macro', desc: 'Macro indicator analysis', endpoint: '/macro' },
    { name: 'Risk', desc: 'Risk assessment & alerts', endpoint: '/risk/alerts' },
    { name: 'Screening', desc: 'Stock screening filters', endpoint: '/screening' },
    { name: 'Strategy', desc: 'Strategy builder & management', endpoint: '/strategies' },
    { name: 'Guru', desc: 'Expert portfolio tracking', endpoint: '/guru/insights' },
  ]

  if (viewMode === 'dashboard') {
    return (
      <div className="flex flex-col h-full -m-6">
        <div className="flex items-center justify-between px-4 py-2 bg-ufs-800 border-b border-ufs-600/50">
          <span className="text-sm text-white font-medium">VIBE Dashboard</span>
          <button
            onClick={() => setViewMode('overview')}
            className="text-xs text-ufs-400 hover:text-white px-2 py-1 rounded bg-ufs-700 hover:bg-ufs-600 transition-colors"
          >
            Back to Overview
          </button>
        </div>
        <iframe
          src="/api/vibe/ui/"
          className="flex-1 w-full border-0"
          title="VIBE Dashboard"
        />
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-white mb-1">
          VIBE <span className="text-blue-400">Intelligence</span>
        </h1>
        <p className="text-ufs-400 text-sm">Investment Intelligence Dashboard</p>
      </div>

      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => setViewMode('dashboard')}
          className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-300 text-sm hover:bg-blue-500/30 transition-colors border border-blue-500/30"
        >
          Open Dashboard
        </button>
        {health && (
          <span className={`text-xs px-2 py-1 rounded-full ${
            health.status === 'healthy'
              ? 'bg-emerald-500/20 text-emerald-400'
              : 'bg-yellow-500/20 text-yellow-400'
          }`}>
            {health.status} v{health.version}
          </span>
        )}
        {!health && (
          <span className="text-xs px-2 py-1 rounded-full bg-red-500/20 text-red-400">
            Backend unreachable
          </span>
        )}
      </div>

      <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Modules</h3>
      <div className="grid grid-cols-2 gap-2">
        {modules.map((m) => (
          <div
            key={m.name}
            className="p-3 rounded-lg bg-ufs-800 border border-ufs-600/30"
          >
            <div className="text-sm font-medium text-white">{m.name}</div>
            <div className="text-xs text-ufs-400 mt-0.5">{m.desc}</div>
            <code className="text-[10px] text-ufs-500 mt-1 block">{m.endpoint}</code>
          </div>
        ))}
      </div>
    </div>
  )
}
