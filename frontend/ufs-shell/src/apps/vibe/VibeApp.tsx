/**
 * VIBE sub-app entry point.
 *
 * Migration path:
 * 1. [Current] Placeholder with module overview
 * 2. [Next] Embed VIBE dashboard via iframe (quick integration)
 * 3. [Later] Migrate JSX -> TSX, integrate with shell routing
 */
export default function VibeApp() {
  const modules = [
    { name: 'Overview', desc: 'Portfolio summary & key metrics' },
    { name: 'Signals', desc: 'Trading signal aggregation' },
    { name: 'Portfolio', desc: 'Position tracking & allocation' },
    { name: 'Backtest', desc: 'Strategy backtesting engine' },
    { name: 'Market Brief', desc: 'Daily market intelligence' },
    { name: 'Macro', desc: 'Macro indicator analysis' },
    { name: 'Risk', desc: 'Risk assessment & alerts' },
    { name: 'Screening', desc: 'Stock screening filters' },
    { name: 'Strategy', desc: 'Strategy builder & management' },
    { name: 'Guru', desc: 'Expert portfolio tracking' },
  ]

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-white mb-1">
          VIBE <span className="text-blue-400">Intelligence</span>
        </h1>
        <p className="text-ufs-400 text-sm">Investment Intelligence Dashboard</p>
      </div>

      <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-5 mb-6">
        <p className="text-blue-300 text-sm">
          VIBE dashboard migration planned. Currently accessible at{' '}
          <code className="bg-ufs-700 px-1.5 py-0.5 rounded text-xs">localhost:8001/ui/</code>
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {modules.map((m) => (
          <div
            key={m.name}
            className="p-3 rounded-lg bg-ufs-800 border border-ufs-600/30"
          >
            <div className="text-sm font-medium text-white">{m.name}</div>
            <div className="text-xs text-ufs-400 mt-0.5">{m.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
