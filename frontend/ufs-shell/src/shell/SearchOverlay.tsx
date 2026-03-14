import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { APP_REGISTRY, searchApps } from '../shared/appRegistry.ts'

interface SearchOverlayProps {
  open: boolean
  onClose: () => void
}

interface SearchResult {
  type: 'app' | 'action'
  id: string
  title: string
  subtitle: string
  icon?: string
  color?: string
  path?: string
  action?: () => void
}

export function SearchOverlay({ open, onClose }: SearchOverlayProps) {
  const [query, setQuery] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIdx(0)
      const timer = setTimeout(() => inputRef.current?.focus(), 50)
      return () => clearTimeout(timer)
    }
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  // Build results
  const getResults = useCallback((): SearchResult[] => {
    const results: SearchResult[] = []

    // App results
    const apps = searchApps(query)
    for (const app of apps) {
      results.push({
        type: 'app',
        id: app.id,
        title: app.name,
        subtitle: app.description,
        color: app.color,
        path: app.path,
      })
    }

    // Quick actions (only when no query or matching query)
    const actions: SearchResult[] = [
      { type: 'action', id: 'home', title: 'Go Home', subtitle: 'Navigate to dashboard', path: '/' },
      { type: 'action', id: 'health', title: 'Check Health', subtitle: 'View system health status', path: '/' },
    ]

    if (!query) {
      results.push(...actions)
    } else {
      const q = query.toLowerCase()
      results.push(
        ...actions.filter(
          (a) => a.title.toLowerCase().includes(q) || a.subtitle.toLowerCase().includes(q),
        ),
      )
    }

    return results
  }, [query])

  const results = getResults()

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIdx((i) => Math.min(i + 1, results.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIdx((i) => Math.max(i - 1, 0))
      } else if (e.key === 'Enter' && results[selectedIdx]) {
        e.preventDefault()
        const result = results[selectedIdx]
        if (result.path) navigate(result.path)
        if (result.action) result.action()
        onClose()
      }
    },
    [results, selectedIdx, navigate, onClose],
  )

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[90] flex items-start justify-center pt-[20vh] search-overlay-bg"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg mx-4 rounded-xl border border-ufs-600/50 bg-ufs-800 shadow-2xl overflow-hidden search-overlay-content"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-ufs-600/30">
          <svg className="w-5 h-5 text-ufs-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIdx(0) }}
            onKeyDown={handleKeyDown}
            placeholder="Search apps, features, actions..."
            className="flex-1 bg-transparent text-white text-sm outline-none placeholder:text-ufs-500"
            autoComplete="off"
          />
          <kbd className="text-[10px] text-ufs-500 px-1.5 py-0.5 rounded border border-ufs-600 bg-ufs-700">ESC</kbd>
        </div>

        {/* Results */}
        <div className="max-h-64 overflow-y-auto py-2">
          {results.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-ufs-400">
              No results found
            </div>
          ) : (
            results.map((result, idx) => (
              <button
                key={result.id}
                onClick={() => {
                  if (result.path) navigate(result.path)
                  if (result.action) result.action()
                  onClose()
                }}
                className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                  idx === selectedIdx ? 'bg-accent/10 text-white' : 'text-ufs-400 hover:bg-ufs-700'
                }`}
                onMouseEnter={() => setSelectedIdx(idx)}
              >
                {result.type === 'app' ? (
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                    style={{ backgroundColor: `${result.color}15` }}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke={result.color} strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round"
                        d={APP_REGISTRY.find((a) => a.id === result.id)?.icon ?? 'M3 3v18h18'}
                      />
                    </svg>
                  </div>
                ) : (
                  <div className="w-8 h-8 rounded-lg bg-ufs-700 flex items-center justify-center shrink-0">
                    <svg className="w-4 h-4 text-ufs-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate" style={result.color ? { color: result.color } : undefined}>
                    {result.title}
                  </div>
                  <div className="text-xs text-ufs-500 truncate">{result.subtitle}</div>
                </div>
                {result.type === 'app' && (
                  <span className="text-[10px] text-ufs-600 shrink-0">Alt+{APP_REGISTRY.find(a => a.id === result.id)?.shortcut}</span>
                )}
              </button>
            ))
          )}
        </div>

        {/* Footer hints */}
        <div className="flex items-center gap-4 px-4 py-2 border-t border-ufs-600/30 text-[10px] text-ufs-500">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>ESC Close</span>
        </div>
      </div>
    </div>
  )
}
