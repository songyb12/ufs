import { useState, useEffect, useCallback } from 'react'
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

      <h3 className="text-white font-semibold text-sm mb-1">{app.name}</h3>
      <p className="text-ufs-400 text-xs leading-relaxed">{app.description}</p>

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

interface ServiceStatus {
  label: string
  port: number
  id: string
  status: 'checking' | 'healthy' | 'unhealthy' | 'unreachable'
}

const INITIAL_SERVICES: ServiceStatus[] = [
  { label: 'Gateway', port: 8000, id: 'master-core', status: 'checking' },
  { label: 'VIBE API', port: 8001, id: 'vibe', status: 'checking' },
  { label: 'Lab-Studio', port: 8002, id: 'lab-studio', status: 'checking' },
  { label: 'Eng-Ops', port: 8003, id: 'engineering-ops', status: 'checking' },
  { label: 'Life-Master', port: 8004, id: 'life-master', status: 'checking' },
  { label: 'MCP Server', port: 8005, id: 'mcp-server', status: 'checking' },
]

const STATUS_COLORS: Record<ServiceStatus['status'], string> = {
  checking: 'bg-ufs-500 animate-pulse',
  healthy: 'bg-emerald-400',
  unhealthy: 'bg-yellow-400',
  unreachable: 'bg-red-400',
}

export default function Home() {
  const [services, setServices] = useState(INITIAL_SERVICES)
  const [lastChecked, setLastChecked] = useState<string | null>(null)

  const checkHealth = useCallback(async () => {
    try {
      const resp = await fetch('/api/health')
      if (!resp.ok) throw new Error('Gateway unreachable')
      const data = await resp.json()

      setServices((prev) =>
        prev.map((svc) => {
          if (svc.id === 'master-core') {
            return { ...svc, status: data.gateway === 'healthy' ? 'healthy' : 'unhealthy' }
          }
          if (svc.id === 'mcp-server') {
            // MCP server health not included in gateway response
            return svc
          }
          const svcStatus = data.services?.[svc.id]
          if (svcStatus) {
            return { ...svc, status: svcStatus.status as ServiceStatus['status'] }
          }
          return { ...svc, status: 'unreachable' }
        }),
      )
      setLastChecked(new Date().toLocaleTimeString())
    } catch {
      setServices((prev) =>
        prev.map((svc) => ({ ...svc, status: 'unreachable' as const })),
      )
      setLastChecked(new Date().toLocaleTimeString())
    }
  }, [])

  useEffect(() => {
    checkHealth()
    const interval = setInterval(checkHealth, 30_000)
    return () => clearInterval(interval)
  }, [checkHealth])

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
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-white">System Status</h2>
          <div className="flex items-center gap-2">
            {lastChecked && (
              <span className="text-[10px] text-ufs-500">
                {lastChecked}
              </span>
            )}
            <button
              onClick={checkHealth}
              className="text-[10px] text-ufs-400 hover:text-white transition-colors px-2 py-0.5 rounded bg-ufs-700 hover:bg-ufs-600"
              aria-label="Refresh health status"
            >
              Refresh
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {services.map((svc) => (
            <div
              key={svc.id}
              className="flex items-center gap-2 text-xs text-ufs-400"
            >
              <span
                className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_COLORS[svc.status]}`}
                aria-label={svc.status}
              />
              <span>{svc.label}</span>
              <span className="text-ufs-500 ml-auto">:{svc.port}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
