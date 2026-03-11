import { useState, useEffect } from 'react'

interface DashboardData {
  active_routines: number
  active_habits: number
  active_goals: number
  completion_rate: number
  top_streaks: { name: string; streak: number }[]
}

export default function LifeApp() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/life/dashboard')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setDashboard)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const features = [
    { name: 'Routines', desc: 'Daily/weekly routine manager', endpoint: '/routines' },
    { name: 'Habits', desc: 'Habit tracker with streaks & heatmaps', endpoint: '/habits' },
    { name: 'Goals', desc: 'Goal system with progress tracking', endpoint: '/goals' },
    { name: 'Scheduler', desc: 'Dynamic schedule optimizer', endpoint: '/schedule' },
    { name: 'Japanese', desc: 'Vocabulary SRS & quiz system', endpoint: '/japanese' },
    { name: 'Notifications', desc: 'Smart notification engine', endpoint: '/notifications' },
  ]

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-white mb-1">
          Life<span className="text-violet-400">-Master</span>
        </h1>
        <p className="text-ufs-400 text-sm">Routine & Schedule Optimizer</p>
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
            { label: 'Routines', value: dashboard.active_routines, color: 'text-violet-400' },
            { label: 'Habits', value: dashboard.active_habits, color: 'text-blue-400' },
            { label: 'Goals', value: dashboard.active_goals, color: 'text-emerald-400' },
            { label: 'Completion', value: `${Math.round((dashboard.completion_rate ?? 0) * 100)}%`, color: 'text-amber-400' },
          ].map((stat) => (
            <div key={stat.label} className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-3 text-center">
              <div className={`text-xl font-bold ${stat.color}`}>{stat.value}</div>
              <div className="text-[10px] text-ufs-400 mt-0.5">{stat.label}</div>
            </div>
          ))}
        </div>
      ) : null}

      {/* Top Streaks */}
      {dashboard?.top_streaks && dashboard.top_streaks.length > 0 && (
        <div className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-4 mb-6">
          <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Top Streaks</h3>
          <div className="space-y-2">
            {dashboard.top_streaks.map((s) => (
              <div key={s.name} className="flex items-center justify-between text-sm">
                <span className="text-white">{s.name}</span>
                <span className="text-amber-400 font-mono">{s.streak} days</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feature Modules */}
      <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Modules</h3>
      <div className="grid grid-cols-2 gap-2">
        {features.map((f) => (
          <div
            key={f.name}
            className="p-3 rounded-lg bg-ufs-800 border border-ufs-600/30"
          >
            <div className="text-sm font-medium text-white">{f.name}</div>
            <div className="text-xs text-ufs-400 mt-0.5">{f.desc}</div>
            <code className="text-[10px] text-ufs-500 mt-1 block">{f.endpoint}</code>
          </div>
        ))}
      </div>
    </div>
  )
}
