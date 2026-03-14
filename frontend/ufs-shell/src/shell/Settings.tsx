import { useState, useEffect } from 'react'
import { APP_REGISTRY } from '../shared/appRegistry.ts'
import { usePlatform } from '../shared/usePlatform.ts'

interface SystemInfo {
  userAgent: string
  language: string
  platform: string
  screenRes: string
  colorDepth: number
  memory?: number
  cores?: number
  online: boolean
}

export default function Settings() {
  const { platform, enterTvMode } = usePlatform()
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null)
  const [gatewayHealth, setGatewayHealth] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    setSystemInfo({
      userAgent: navigator.userAgent,
      language: navigator.language,
      platform: navigator.platform,
      screenRes: `${screen.width}x${screen.height}`,
      colorDepth: screen.colorDepth,
      memory: (navigator as unknown as Record<string, unknown>).deviceMemory as number | undefined,
      cores: navigator.hardwareConcurrency,
      online: navigator.onLine,
    })

    fetch('/api/health')
      .then((r) => r.ok ? r.json() : null)
      .then(setGatewayHealth)
      .catch(() => null)
  }, [])

  const clearLocalStorage = () => {
    const keys = Object.keys(localStorage).filter((k) => k.startsWith('ufs-'))
    keys.forEach((k) => localStorage.removeItem(k))
    window.location.reload()
  }

  return (
    <div className="max-w-3xl mx-auto animate-fade-in">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-white mb-1">Settings</h1>
        <p className="text-ufs-400 text-sm">System configuration and information</p>
      </div>

      {/* Display Mode */}
      <section className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-5 mb-4">
        <h3 className="text-sm font-semibold text-white mb-3">Display Mode</h3>
        <div className="flex items-center gap-3 mb-3">
          <span className="text-xs text-ufs-400">Current:</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-accent/20 text-accent font-medium">{platform}</span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={enterTvMode}
            className="text-xs px-3 py-1.5 rounded-lg bg-ufs-700 text-ufs-400 hover:bg-ufs-600 hover:text-white transition-colors"
          >
            Switch to TV Mode
          </button>
        </div>
        <p className="text-[10px] text-ufs-500 mt-2">
          TV mode: full-screen with keyboard navigation, ideal for RPi3 kiosk display.
          Add <code className="bg-ufs-700 px-1 rounded">?mode=tv</code> to URL for persistent kiosk mode.
        </p>
      </section>

      {/* Keyboard Shortcuts */}
      <section className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-5 mb-4">
        <h3 className="text-sm font-semibold text-white mb-3">Keyboard Shortcuts</h3>
        <div className="grid grid-cols-2 gap-2">
          {[
            { keys: 'Ctrl+K', desc: 'Open search' },
            { keys: 'Ctrl+B', desc: 'Toggle sidebar' },
            { keys: 'Ctrl+H', desc: 'Go home' },
            { keys: 'ESC', desc: 'Close overlay / Go back (TV)' },
            ...APP_REGISTRY.filter((a) => a.shortcut).map((a) => ({
              keys: `Alt+${a.shortcut!.toUpperCase()}`,
              desc: `Open ${a.name}`,
            })),
          ].map((s) => (
            <div key={s.keys} className="flex items-center justify-between py-1.5">
              <span className="text-xs text-ufs-400">{s.desc}</span>
              <kbd className="text-[10px] text-ufs-300 px-1.5 py-0.5 rounded bg-ufs-700 border border-ufs-600 font-mono">
                {s.keys}
              </kbd>
            </div>
          ))}
        </div>
      </section>

      {/* Registered Apps */}
      <section className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-5 mb-4">
        <h3 className="text-sm font-semibold text-white mb-3">Registered Applications ({APP_REGISTRY.length})</h3>
        <div className="space-y-2">
          {APP_REGISTRY.map((app) => (
            <div key={app.id} className="flex items-center gap-3 py-2 border-b border-ufs-700/30 last:border-0">
              <div className="w-6 h-6 rounded flex items-center justify-center shrink-0" style={{ backgroundColor: `${app.color}15` }}>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke={app.color} strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d={app.icon} />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-white font-medium">{app.name}</div>
                <div className="text-[10px] text-ufs-500">{app.apiBase} • Port {app.port}</div>
              </div>
              <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${
                app.status === 'active' ? 'bg-emerald-500/20 text-emerald-400'
                  : app.status === 'dev' ? 'bg-yellow-500/20 text-yellow-400'
                    : 'bg-ufs-600 text-ufs-400'
              }`}>
                {app.status}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* System Info */}
      {systemInfo && (
        <section className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-5 mb-4">
          <h3 className="text-sm font-semibold text-white mb-3">System Information</h3>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              { label: 'Language', value: systemInfo.language },
              { label: 'Screen', value: systemInfo.screenRes },
              { label: 'Color Depth', value: `${systemInfo.colorDepth}bit` },
              { label: 'CPU Cores', value: systemInfo.cores?.toString() ?? '—' },
              { label: 'Memory', value: systemInfo.memory ? `${systemInfo.memory}GB` : '—' },
              { label: 'Network', value: systemInfo.online ? 'Online' : 'Offline' },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between py-1">
                <span className="text-ufs-400">{item.label}</span>
                <span className="text-ufs-300 font-mono">{item.value}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Gateway Info */}
      {gatewayHealth && (
        <section className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-5 mb-4">
          <h3 className="text-sm font-semibold text-white mb-3">Gateway Health</h3>
          <pre className="text-[10px] text-ufs-400 font-mono bg-ufs-700 rounded-lg p-3 overflow-auto max-h-40">
            {JSON.stringify(gatewayHealth, null, 2)}
          </pre>
        </section>
      )}

      {/* Docker Ports Reference */}
      <section className="rounded-xl border border-ufs-600/30 bg-ufs-800 p-5 mb-4">
        <h3 className="text-sm font-semibold text-white mb-3">Docker Compose Ports</h3>
        <div className="grid grid-cols-2 gap-1 text-xs">
          {[
            { label: 'UFS Shell', port: 3000 },
            { label: 'Bocchi Frontend', port: 3001 },
            { label: 'Master Core', port: 8000 },
            { label: 'VIBE API', port: 8001 },
            { label: 'Lab-Studio', port: 8002 },
            { label: 'Eng-Ops', port: 8003 },
            { label: 'Life-Master', port: 8004 },
            { label: 'MCP Server', port: 8005 },
            { label: 'Session Manager', port: 8006 },
          ].map((p) => (
            <div key={p.port} className="flex items-center justify-between py-1 px-2 rounded hover:bg-ufs-700/30">
              <span className="text-ufs-400">{p.label}</span>
              <span className="text-ufs-300 font-mono">:{p.port}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Danger Zone */}
      <section className="rounded-xl border border-red-500/20 bg-red-500/5 p-5 mb-4">
        <h3 className="text-sm font-semibold text-red-300 mb-3">Danger Zone</h3>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs text-ufs-300">Clear Local Storage</div>
            <div className="text-[10px] text-ufs-500">Reset sidebar state, platform mode, and all cached preferences</div>
          </div>
          <button
            onClick={clearLocalStorage}
            className="text-xs px-3 py-1.5 rounded-lg bg-red-500/20 text-red-300 hover:bg-red-500/30 transition-colors border border-red-500/30"
          >
            Clear
          </button>
        </div>
      </section>

      {/* Version */}
      <div className="text-center text-[10px] text-ufs-600 py-4">
        UFS v0.1.0 • React 19 • TypeScript 5.9 • Tailwind 4 • Vite 7
      </div>
    </div>
  )
}
