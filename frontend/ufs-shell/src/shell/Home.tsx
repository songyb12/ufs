import { Link } from 'react-router-dom'
import { APP_REGISTRY } from '../shared/appRegistry.ts'
import type { AppInfo } from '../shared/appRegistry.ts'

function AppCard({ app }: { app: AppInfo }) {
  const isAvailable = app.status !== 'planned'

  const card = (
    <div
      className={`group relative rounded-xl border p-5 transition-all ${
        isAvailable
          ? 'border-ufs-600/50 bg-ufs-800 hover:border-ufs-500 hover:bg-ufs-700 cursor-pointer'
          : 'border-ufs-700/30 bg-ufs-800/50 opacity-60 cursor-default'
      }`}
    >
      {/* Icon */}
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
        style={{ backgroundColor: `${app.color}15` }}
      >
        <svg
          className="w-6 h-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke={app.color}
          strokeWidth={1.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d={app.icon} />
        </svg>
      </div>

      {/* Info */}
      <h3 className="text-white font-semibold text-sm mb-1">{app.name}</h3>
      <p className="text-ufs-400 text-xs leading-relaxed">{app.description}</p>

      {/* Status badge */}
      {app.status !== 'active' && (
        <span
          className={`absolute top-3 right-3 text-[9px] px-2 py-0.5 rounded-full font-medium ${
            app.status === 'dev'
              ? 'bg-yellow-500/20 text-yellow-400'
              : 'bg-ufs-600 text-ufs-400'
          }`}
        >
          {app.status === 'dev' ? 'Prototype' : 'Planned'}
        </span>
      )}

      {/* Hover arrow */}
      {isAvailable && (
        <svg
          className="absolute bottom-4 right-4 w-4 h-4 text-ufs-500 opacity-0 group-hover:opacity-100 transition-opacity"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      )}
    </div>
  )

  if (!isAvailable) return card
  return <Link to={app.path}>{card}</Link>
}

export default function Home() {
  return (
    <div className="max-w-4xl mx-auto">
      {/* Hero */}
      <div className="mb-10">
        <h1 className="text-2xl font-bold text-white mb-2">
          UFS <span className="text-accent">Dashboard</span>
        </h1>
        <p className="text-ufs-400 text-sm">
          Personal AI OS - Microservice Architecture
        </p>
      </div>

      {/* App Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {APP_REGISTRY.map((app) => (
          <AppCard key={app.id} app={app} />
        ))}
      </div>

      {/* System Status */}
      <div className="mt-10 rounded-xl border border-ufs-600/50 bg-ufs-800 p-5">
        <h2 className="text-sm font-semibold text-white mb-4">System Status</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Gateway', port: 8000, id: 'master-core' },
            { label: 'VIBE API', port: 8001, id: 'vibe' },
            { label: 'Lab-Studio', port: 8002, id: 'lab-studio' },
            { label: 'Eng-Ops', port: 8003, id: 'eng-ops' },
          ].map((svc) => (
            <div
              key={svc.id}
              className="flex items-center gap-2 text-xs text-ufs-400"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-ufs-500" />
              <span>{svc.label}</span>
              <span className="text-ufs-500 ml-auto">:{svc.port}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
