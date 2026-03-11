import { useState, useEffect, useCallback } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { APP_REGISTRY } from '../shared/appRegistry.ts'

interface TVLayoutProps {
  onExitTv: () => void
}

export function TVLayout({ onExitTv }: TVLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [clock, setClock] = useState(new Date().toLocaleTimeString())

  // Clock
  useEffect(() => {
    const t = setInterval(() => setClock(new Date().toLocaleTimeString()), 1000)
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
        <div className="h-10 flex items-center justify-between px-6 bg-ufs-800 border-b border-ufs-600/50">
          <span className="text-sm text-white font-medium">{clock}</span>
          <span className="text-xs text-ufs-400">ESC to go back</span>
        </div>
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    )
  }

  // TV Home
  return (
    <div className="min-h-screen bg-ufs-900 flex flex-col">
      {/* Top bar */}
      <div className="h-12 flex items-center justify-between px-8 bg-ufs-800 border-b border-ufs-600/50">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center text-white font-bold text-xs">
            U
          </div>
          <span className="text-white font-semibold text-lg">UFS</span>
        </div>
        <span className="text-white text-lg font-mono">{clock}</span>
      </div>

      {/* App grid — 2x2 large cards */}
      <main className="flex-1 flex items-center justify-center p-8">
        <div className="grid grid-cols-2 gap-6 max-w-3xl w-full">
          {APP_REGISTRY.map((app, idx) => (
            <button
              key={app.id}
              onClick={() => navigate(app.path)}
              className={`relative rounded-2xl border-2 p-8 text-left transition-all ${
                idx === focusIdx
                  ? 'border-white bg-ufs-700 scale-105'
                  : 'border-ufs-600/50 bg-ufs-800 hover:border-ufs-500'
              }`}
            >
              <div
                className="w-16 h-16 rounded-xl flex items-center justify-center mb-4"
                style={{ backgroundColor: `${app.color}20` }}
              >
                <svg
                  className="w-8 h-8"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke={app.color}
                  strokeWidth={1.5}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d={app.icon} />
                </svg>
              </div>
              <h2 className="text-white font-bold text-xl mb-1">{app.name}</h2>
              <p className="text-ufs-400 text-sm">{app.description}</p>
              {app.status !== 'active' && (
                <span className="absolute top-4 right-4 text-xs px-2 py-0.5 rounded-full bg-yellow-500/20 text-yellow-400">
                  {app.status}
                </span>
              )}
            </button>
          ))}
        </div>
      </main>

      {/* Bottom hint */}
      <div className="h-10 flex items-center justify-center gap-6 bg-ufs-800 border-t border-ufs-600/50 text-xs text-ufs-500">
        <span>Arrow keys to navigate</span>
        <span>Enter to select</span>
        <span>ESC to exit TV mode</span>
      </div>
    </div>
  )
}
