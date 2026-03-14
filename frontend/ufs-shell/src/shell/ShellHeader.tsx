import { useState, useEffect } from 'react'
import { useLocation, Link } from 'react-router-dom'
import { getAppByPath } from '../shared/appRegistry.ts'
import { useOnlineStatus } from '../shared/usePlatform.ts'

interface ShellHeaderProps {
  sidebarOpen: boolean
  onToggleSidebar: () => void
  onSearch?: () => void
}

export function ShellHeader({ sidebarOpen, onToggleSidebar, onSearch }: ShellHeaderProps) {
  const location = useLocation()
  const isOnline = useOnlineStatus()
  const [clock, setClock] = useState('')

  const currentApp = getAppByPath(location.pathname)

  // Clock update every minute
  useEffect(() => {
    const update = () => setClock(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }))
    update()
    const interval = setInterval(update, 60_000)
    return () => clearInterval(interval)
  }, [])

  // Build breadcrumb segments
  const segments = location.pathname.split('/').filter(Boolean)

  return (
    <header className="h-12 flex items-center justify-between px-4 bg-ufs-800 border-b border-ufs-600/50 shrink-0 no-print">
      <div className="flex items-center gap-3">
        {/* Sidebar toggle */}
        <button
          onClick={onToggleSidebar}
          className="p-1.5 rounded-lg hover:bg-ufs-700 text-ufs-400 hover:text-white transition-colors"
          aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          title={`${sidebarOpen ? 'Close' : 'Open'} sidebar (Ctrl+B)`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {sidebarOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>

        {/* Breadcrumb */}
        <nav className="flex items-center gap-1.5 text-sm" aria-label="Breadcrumb">
          <Link to="/" className="text-ufs-400 hover:text-white transition-colors text-xs">
            Home
          </Link>
          {segments.map((seg, i) => (
            <span key={i} className="flex items-center gap-1.5">
              <span className="text-ufs-600 text-xs">/</span>
              {i === 0 && currentApp ? (
                <Link
                  to={currentApp.path}
                  className="font-medium transition-colors text-xs"
                  style={{ color: currentApp.color }}
                >
                  {currentApp.name}
                </Link>
              ) : (
                <span className="text-ufs-400 text-xs capitalize">{decodeURIComponent(seg)}</span>
              )}
            </span>
          ))}
          {segments.length === 0 && (
            <span className="text-ufs-600 text-xs">/</span>
          )}
        </nav>
      </div>

      <div className="flex items-center gap-3">
        {/* Search button */}
        {onSearch && (
          <button
            onClick={onSearch}
            className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-ufs-700 hover:bg-ufs-600 text-ufs-400 hover:text-white transition-colors text-xs"
            title="Search (Ctrl+K)"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span className="hidden sm:inline">Search</span>
            <kbd className="hidden sm:inline text-[9px] text-ufs-500 px-1 py-0.5 rounded border border-ufs-600 bg-ufs-800">⌘K</kbd>
          </button>
        )}

        {/* Online status indicator */}
        {!isOnline && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 animate-pulse">
            Offline
          </span>
        )}

        {/* Clock */}
        <span className="text-ufs-500 text-xs font-mono hidden sm:block">{clock}</span>

        {/* Version */}
        <span className="text-ufs-600 text-[10px] hidden md:block">UFS v0.1</span>
      </div>
    </header>
  )
}
