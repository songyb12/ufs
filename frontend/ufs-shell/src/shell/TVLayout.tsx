import { useState, useEffect, useCallback } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { APP_REGISTRY } from '../shared/appRegistry.ts'

interface TVLayoutProps {
  onExitTv: () => void
}

export function TVLayout({ onExitTv }: TVLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [clock, setClock] = useState('')
  const [date, setDate] = useState('')

  // Clock + date
  useEffect(() => {
    const update = () => {
      const now = new Date()
      setClock(now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
      setDate(now.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }))
    }
    update()
    const t = setInterval(update, 1000)
    return () => clearInterval(t)
  }, [])

  // Keyboard navigation
  const isHome = location.pathname === '/'
  const [focusIdx, setFocusIdx] = useState(0)

  const handleKey = useCallback((e: KeyboardEvent) => {
    if (!isHome) {
      if (e.key === 'Escape' || e.key === 'Backspace') {
        e.preventDefault()
        navigate('/')
      }
      return
    }

    const max = APP_REGISTRY.length - 1
    switch (e.key) {
      case 'ArrowRight':
        setFocusIdx((i) => Math.min(i + 1, max))
        break
      case 'ArrowLeft':
        setFocusIdx((i) => Math.max(i - 1, 0))
        break
      case 'ArrowDown':
        setFocusIdx((i) => Math.min(i + 2, max))
        break
      case 'ArrowUp':
        setFocusIdx((i) => Math.max(i - 2, 0))
        break
      case 'Enter':
        navigate(APP_REGISTRY[focusIdx].path)
        break
      case 'Escape':
        onExitTv()
        break
    }
  }, [isHome, focusIdx, navigate, onExitTv])

  useEffect(() => {
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [handleKey])

  // Sub-app full-screen mode
  if (!isHome) {
    return (
      <div className="min-h-screen bg-ufs-900 flex flex-col">
        <div className="h-10 flex items-center justify-between px-6 bg-ufs-800 border-b border-ufs-600/50 shrink-0">
          <div className="flex items-center gap-4">
            <span className="text-sm text-white font-medium">{clock}</span>
            <span className="text-xs text-ufs-500">{date}</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[10px] text-ufs-500">
              {APP_REGISTRY.find((a) => location.pathname.startsWith(a.path))?.name ?? ''}
            </span>
            <span className="text-xs text-ufs-400 bg-ufs-700 px-2 py-0.5 rounded">ESC to go back</span>
          </div>
        </div>
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    )
  }

  // TV Home
  const focusedApp = APP_REGISTRY[focusIdx]

  return (
    <div className="min-h-screen bg-ufs-900 flex flex-col">
      {/* Top bar */}
      <div className="h-14 flex items-center justify-between px-8 bg-ufs-800 border-b border-ufs-600/50 shrink-0">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center text-white font-bold text-sm">
            U
          </div>
          <div>
            <span className="text-white font-semibold text-lg">UFS</span>
            <span className="text-ufs-500 text-xs ml-2">Personal AI OS</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-ufs-400 text-sm">{date}</span>
          <span className="text-white text-2xl font-mono tabular-nums">{clock}</span>
        </div>
      </div>

      {/* App grid */}
      <main className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-4xl">
          <div className="grid grid-cols-2 gap-6 mb-8">
            {APP_REGISTRY.map((app, idx) => (
              <button
                key={app.id}
                onClick={() => navigate(app.path)}
                className={`relative rounded-2xl border-2 p-8 text-left transition-all duration-200 ${
                  idx === focusIdx
                    ? 'border-white bg-ufs-700 scale-105 shadow-2xl shadow-black/40'
                    : 'border-ufs-600/50 bg-ufs-800 hover:border-ufs-500'
                }`}
              >
                <div
                  className="w-16 h-16 rounded-xl flex items-center justify-center mb-4"
                  style={{ backgroundColor: `${app.color}20` }}
                >
                  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke={app.color} strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d={app.icon} />
                  </svg>
                </div>
                <h2 className="text-white font-bold text-xl mb-1">{app.name}</h2>
                <p className="text-ufs-400 text-sm mb-3">{app.description}</p>

                {/* Feature tags */}
                {app.features && (
                  <div className="flex flex-wrap gap-1">
                    {app.features.slice(0, 4).map((f) => (
                      <span key={f} className="text-[10px] px-2 py-0.5 rounded-full bg-ufs-700 text-ufs-400">{f}</span>
                    ))}
                  </div>
                )}

                {app.status !== 'active' && (
                  <span className="absolute top-4 right-4 text-xs px-2 py-0.5 rounded-full bg-yellow-500/20 text-yellow-400">
                    {app.status}
                  </span>
                )}

                {idx === focusIdx && (
                  <div className="absolute bottom-4 right-4">
                    <svg className="w-6 h-6 text-white/50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                )}
              </button>
            ))}
          </div>

          {/* Focused app info panel */}
          {focusedApp && (
            <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke={focusedApp.color} strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d={focusedApp.icon} />
                </svg>
                <span className="text-white font-medium">{focusedApp.name}</span>
                <span className="text-ufs-400 text-sm">— {focusedApp.description}</span>
              </div>
              <span className="text-ufs-500 text-sm">Press Enter to open</span>
            </div>
          )}
        </div>
      </main>

      {/* Bottom hint bar */}
      <div className="h-12 flex items-center justify-center gap-8 bg-ufs-800 border-t border-ufs-600/50 text-sm text-ufs-500 shrink-0">
        <span className="flex items-center gap-2">
          <kbd className="px-1.5 py-0.5 rounded bg-ufs-700 text-ufs-400 text-xs">←→↑↓</kbd>
          Navigate
        </span>
        <span className="flex items-center gap-2">
          <kbd className="px-1.5 py-0.5 rounded bg-ufs-700 text-ufs-400 text-xs">Enter</kbd>
          Select
        </span>
        <span className="flex items-center gap-2">
          <kbd className="px-1.5 py-0.5 rounded bg-ufs-700 text-ufs-400 text-xs">ESC</kbd>
          Exit TV Mode
        </span>
      </div>
    </div>
  )
}
