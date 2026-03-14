import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { APP_REGISTRY } from '../shared/appRegistry.ts'
import type { AppInfo } from '../shared/appRegistry.ts'

// ── App Card ──
function AppCard({ app, idx }: { app: AppInfo; idx: number }) {
  const isAvailable = app.status !== 'planned'

  const card = (
    <div
      className={`group relative rounded-xl border p-5 transition-all ${
        isAvailable
          ? 'border-ufs-600/50 bg-ufs-800 hover:border-ufs-500 hover:bg-ufs-700 cursor-pointer hover:shadow-lg hover:shadow-black/20 hover:-translate-y-0.5'
          : 'border-ufs-700/30 bg-ufs-800/50 opacity-60 cursor-default'
      }`}
      style={{ animationDelay: `${idx * 0.05}s` }}
    >
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center mb-4 transition-transform group-hover:scale-110"
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
      <p className="text-ufs-400 text-xs leading-relaxed mb-2">{app.description}</p>

      {/* Feature tags */}
      {app.features && app.features.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {app.features.slice(0, 3).map((f) => (
            <span key={f} className="text-[9px] px-1.5 py-0.5 rounded-full bg-ufs-700 text-ufs-400">
              {f}
            </span>
          ))}
          {app.features.length > 3 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-ufs-700 text-ufs-500">
              +{app.features.length - 3}
            </span>
          )}
        </div>
      )}

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

      {/* Shortcut hint */}
      {app.shortcut && isAvailable && (
        <span className="absolute bottom-3 right-3 text-[9px] text-ufs-600 opacity-0 group-hover:opacity-100 transition-opacity">
          Alt+{app.shortcut}
        </span>
      )}

      {isAvailable && (
        <svg
          className="absolute top-4 right-4 w-4 h-4 text-ufs-500 opacity-0 group-hover:opacity-100 transition-opacity"
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

// ── Service Status ──
interface ServiceStatus {
  label: string
  port: number
  id: string
  status: 'checking' | 'healthy' | 'unhealthy' | 'unreachable'
  version?: string
  responseTime?: number
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

const STATUS_LABELS: Record<ServiceStatus['status'], string> = {
  checking: 'Checking...',
  healthy: 'Healthy',
  unhealthy: 'Unhealthy',
  unreachable: 'Unreachable',
}

export default function Home() {
  const [services, setServices] = useState(INITIAL_SERVICES)
  const [lastChecked, setLastChecked] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [uptime, setUptime] = useState<string | null>(null)

  const checkHealth = useCallback(async () => {
    setRefreshing(true)
    const startTime = Date.now()
    try {
      const resp = await fetch('/api/health')
      const responseTime = Date.now() - startTime
      if (!resp.ok) throw new Error('Gateway unreachable')
      const data = await resp.json()

      setServices((prev) =>
        prev.map((svc) => {
          if (svc.id === 'master-core') {
            return {
              ...svc,
              status: data.gateway === 'healthy' ? 'healthy' : 'unhealthy',
              responseTime,
              version: data.version,
            }
          }
          if (svc.id === 'mcp-server') return svc
          const svcStatus = data.services?.[svc.id]
          if (svcStatus) {
            return {
              ...svc,
              status: svcStatus.status as ServiceStatus['status'],
              version: svcStatus.version,
            }
          }
          return { ...svc, status: 'unreachable' }
        }),
      )

      // Parse uptime if available
      if (data.uptime) {
        const secs = data.uptime
        const d = Math.floor(secs / 86400)
        const h = Math.floor((secs % 86400) / 3600)
        const m = Math.floor((secs % 3600) / 60)
        setUptime(d > 0 ? `${d}d ${h}h` : `${h}h ${m}m`)
      }

      setLastChecked(new Date().toLocaleTimeString('ko-KR'))
    } catch {
      setServices((prev) =>
        prev.map((svc) => ({ ...svc, status: 'unreachable' as const })),
      )
      setLastChecked(new Date().toLocaleTimeString('ko-KR'))
    } finally {
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    checkHealth()
    const interval = setInterval(checkHealth, 30_000)
    return () => clearInterval(interval)
  }, [checkHealth])

  const healthyCount = services.filter((s) => s.status === 'healthy').length
  const totalCount = services.length

  return (
    <div className="max-w-5xl mx-auto animate-fade-in">
      {/* Hero */}
      <div className="mb-8">
        <div className="flex items-center gap-4 mb-3">
          <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center text-white font-bold text-sm">
              U
            </div>
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">
              UFS <span className="gradient-text">Dashboard</span>
            </h1>
            <p className="text-ufs-400 text-sm">
              Personal AI OS — Microservice Architecture
            </p>
          </div>
        </div>
      </div>

      {/* Quick Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-4">
          <div className="text-2xl font-bold text-white">{APP_REGISTRY.length}</div>
          <div className="text-xs text-ufs-400 mt-0.5">Applications</div>
        </div>
        <div className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-4">
          <div className={`text-2xl font-bold ${healthyCount === totalCount ? 'text-emerald-400' : healthyCount > 0 ? 'text-yellow-400' : 'text-red-400'}`}>
            {healthyCount}/{totalCount}
          </div>
          <div className="text-xs text-ufs-400 mt-0.5">Services Healthy</div>
        </div>
        <div className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-4">
          <div className="text-2xl font-bold text-blue-400">{uptime ?? '—'}</div>
          <div className="text-xs text-ufs-400 mt-0.5">Uptime</div>
        </div>
        <div className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-4">
          <div className="text-2xl font-bold text-violet-400">6</div>
          <div className="text-xs text-ufs-400 mt-0.5">Microservices</div>
        </div>
      </div>

      {/* App Grid */}
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider">Applications</h2>
        <span className="text-[10px] text-ufs-500">
          {APP_REGISTRY.filter((a) => a.status === 'active').length} active,{' '}
          {APP_REGISTRY.filter((a) => a.status === 'dev').length} dev
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 stagger-children">
        {APP_REGISTRY.map((app, idx) => (
          <AppCard key={app.id} app={app} idx={idx} />
        ))}
      </div>

      {/* System Status */}
      <div className="mt-10 rounded-xl border border-ufs-600/50 bg-ufs-800 p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-white">System Status</h2>
            {/* Health summary badge */}
            <span className={`text-[10px] px-2 py-0.5 rounded-full ${
              healthyCount === totalCount
                ? 'bg-emerald-500/20 text-emerald-400'
                : healthyCount > 0
                  ? 'bg-yellow-500/20 text-yellow-400'
                  : 'bg-red-500/20 text-red-400'
            }`}>
              {healthyCount === totalCount ? 'All Systems Operational' : `${healthyCount}/${totalCount} Healthy`}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {lastChecked && (
              <span className="text-[10px] text-ufs-500">
                {lastChecked}
              </span>
            )}
            <button
              onClick={checkHealth}
              disabled={refreshing}
              className="text-[10px] text-ufs-400 hover:text-white transition-colors px-2 py-0.5 rounded bg-ufs-700 hover:bg-ufs-600 disabled:opacity-50"
              aria-label="Refresh health status"
            >
              {refreshing ? (
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 border border-ufs-400 border-t-transparent rounded-full animate-spin" />
                  Checking
                </span>
              ) : (
                'Refresh'
              )}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {services.map((svc) => (
            <div
              key={svc.id}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-ufs-700/30 border border-ufs-700/50"
            >
              <span
                className={`w-2 h-2 rounded-full shrink-0 ${STATUS_COLORS[svc.status]}`}
                aria-label={svc.status}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-white font-medium">{svc.label}</span>
                  {svc.version && (
                    <span className="text-[9px] text-ufs-500">v{svc.version}</span>
                  )}
                </div>
                <div className="text-[10px] text-ufs-500 flex items-center gap-2">
                  <span>:{svc.port}</span>
                  <span>{STATUS_LABELS[svc.status]}</span>
                  {svc.responseTime && (
                    <span className="text-ufs-600">{svc.responseTime}ms</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Architecture Info */}
      <div className="mt-6 rounded-xl border border-ufs-600/30 bg-ufs-800/50 p-5">
        <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Architecture</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs text-ufs-400">
          <div>
            <div className="text-ufs-300 font-medium mb-1">Infrastructure</div>
            <div>Local Home Server</div>
            <div>Docker Compose</div>
            <div>SQLite per Service</div>
          </div>
          <div>
            <div className="text-ufs-300 font-medium mb-1">Backend</div>
            <div>FastAPI + Python</div>
            <div>REST API</div>
            <div>JWT Auth</div>
          </div>
          <div>
            <div className="text-ufs-300 font-medium mb-1">Frontend</div>
            <div>React 19 + TypeScript</div>
            <div>Tailwind CSS 4</div>
            <div>Vite 7</div>
          </div>
        </div>
      </div>

      {/* Keyboard shortcuts hint */}
      <div className="mt-6 flex items-center justify-center gap-6 text-[10px] text-ufs-600 mb-4">
        <span>⌘K Search</span>
        <span>⌘B Toggle Sidebar</span>
        <span>Alt+V VIBE</span>
        <span>Alt+B Bocchi</span>
        <span>Alt+L Life</span>
        <span>Alt+E Eng-Ops</span>
      </div>
    </div>
  )
}
