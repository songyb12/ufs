import { useState, useEffect } from 'react'

interface EngOpsHealth {
  service: string
  status: string
  version: string
}

export default function EngOpsApp() {
  const [health, setHealth] = useState<EngOpsHealth | null>(null)

  useEffect(() => {
    fetch('/api/eng-ops/health')
      .then((r) => r.ok ? r.json() : null)
      .then(setHealth)
      .catch(() => null)
  }, [])

  const features = [
    { name: 'Log Parser', desc: 'C-language HW verification log parsing', status: 'planned' },
    { name: 'Daily Report', desc: 'Automated daily summary generation', status: 'planned' },
    { name: 'CSV Export', desc: 'Parsed data export to CSV', status: 'planned' },
    { name: 'Pattern Detection', desc: 'Error pattern recognition in logs', status: 'planned' },
  ]

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-xl font-bold text-white">
            Engineering<span className="text-emerald-400">-Ops</span>
          </h1>
          {health && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">
              {health.status} v{health.version}
            </span>
          )}
        </div>
        <p className="text-ufs-400 text-sm">HW Verification Log Analysis</p>
      </div>

      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-5 mb-6">
        <p className="text-emerald-300 text-sm">
          Prototype stage - Service skeleton running on port 8003.
          Log parsing and analysis features in development.
        </p>
      </div>

      <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Planned Features</h3>
      <div className="grid grid-cols-2 gap-2">
        {features.map((f) => (
          <div
            key={f.name}
            className="p-3 rounded-lg bg-ufs-800 border border-ufs-600/30"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-white">{f.name}</span>
              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ufs-600 text-ufs-400">
                {f.status}
              </span>
            </div>
            <div className="text-xs text-ufs-400 mt-0.5">{f.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
