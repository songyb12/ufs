import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import type { Song, SongSearchResult } from '../../types/song'
import { searchSongs, getSongById, saveSong, getAllSongs } from '../../data/songStore'

const API_BASE = 'http://localhost:8000/api/chord-search'

interface SongSearchBarProps {
  onSelect: (song: Song) => void
}

const SOURCE_ICONS: Record<string, { icon: string; label: string; color: string }> = {
  seed: { icon: '\u2713', label: '검증됨', color: 'bg-emerald-500/20 text-emerald-400' },
  llm: { icon: '\u2728', label: 'AI', color: 'bg-purple-500/20 text-purple-400' },
  user: { icon: '\u270E', label: '사용자', color: 'bg-sky-500/20 text-sky-400' },
  api: { icon: '\u21C5', label: 'API', color: 'bg-amber-500/20 text-amber-400' },
}

export function SongSearchBar({ onSelect }: SongSearchBarProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SongSearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)
  const [songsVersion, setSongsVersion] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Popular songs for empty query suggestions
  const suggestions = useMemo(() => {
    void songsVersion
    const all = getAllSongs()
    const seeds = all.filter(s => s.source === 'seed')
    const shuffled = [...seeds].sort(() => Math.random() - 0.5)
    return shuffled.slice(0, 5).map(s => ({
      id: s.id, title: s.title, artist: s.artist, source: s.source,
    } as SongSearchResult))
  }, [songsVersion])

  const doSearch = useCallback((q: string) => {
    if (!q.trim()) {
      setResults([])
      setOpen(false)
      return
    }
    const found = searchSongs(q)
    setResults(found)
    setOpen(true)
    setAiError(null)
  }, [])

  const handleChange = (value: string) => {
    setQuery(value)
    setAiError(null)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => doSearch(value), 300)
  }

  const handleFocus = () => {
    if (!query.trim() && suggestions.length > 0) {
      setResults(suggestions)
      setOpen(true)
    }
  }

  const handleSelect = (result: SongSearchResult) => {
    const song = getSongById(result.id)
    if (song) {
      onSelect(song)
      setQuery('')
      setOpen(false)
    }
  }

  const handleAiSearch = async () => {
    const trimmed = query.trim()
    if (!trimmed) return

    setAiLoading(true)
    setAiError(null)

    // Parse "title - artist" or just "title"
    const dashIdx = trimmed.indexOf(' - ')
    const title = dashIdx > 0 ? trimmed.slice(0, dashIdx).trim() : trimmed
    const artist = dashIdx > 0 ? trimmed.slice(dashIdx + 3).trim() : undefined

    try {
      const resp = await fetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, artist: artist || null }),
      })

      if (!resp.ok) {
        const body = await resp.json().catch(() => null)
        const detail = body?.detail ?? `Server error (${resp.status})`
        if (resp.status === 503) setAiError('API 키가 설정되지 않았습니다')
        else if (resp.status === 429) setAiError('일일 호출 한도 초과')
        else setAiError(detail)
        return
      }

      const song: Song = await resp.json()
      saveSong(song)
      setSongsVersion(v => v + 1)
      onSelect(song)
      setQuery('')
      setOpen(false)
    } catch {
      setAiError('서버에 연결할 수 없습니다 (master-core 실행 확인)')
    } finally {
      setAiLoading(false)
    }
  }

  // Close on ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Close on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Cleanup timer
  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current)
  }, [])

  const sourceBadge = (source: string) => {
    const info = SOURCE_ICONS[source] ?? { icon: '?', label: source, color: 'bg-slate-700 text-slate-400' }
    return (
      <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium ${info.color}`}>
        <span>{info.icon}</span>
        <span>{info.label}</span>
      </span>
    )
  }

  const showNoResults = open && results.length === 0 && query.trim().length > 0
  const isSuggestionMode = open && !query.trim() && results.length > 0

  return (
    <div ref={containerRef} className="relative">
      <input
        type="text"
        value={query}
        onChange={e => handleChange(e.target.value)}
        onFocus={handleFocus}
        placeholder="곡 제목 또는 아티스트 검색..."
        className="w-full px-4 py-2.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 focus:border-orange-500/50"
      />
      <svg className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>

      {open && (
        <div className="absolute z-20 mt-1 w-full rounded-lg bg-slate-800 border border-slate-700 shadow-xl max-h-80 overflow-y-auto">
          {isSuggestionMode && (
            <div className="px-4 py-1.5 text-[10px] text-slate-600 uppercase tracking-wider">
              인기곡
            </div>
          )}

          {results.length > 0 ? (
            results.map(r => (
              <button
                key={r.id}
                onClick={() => handleSelect(r)}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-slate-700/60 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <span className="text-sm text-slate-200 font-medium truncate block">{r.title}</span>
                  {r.artist && <span className="text-xs text-slate-500">{r.artist}</span>}
                </div>
                {sourceBadge(r.source)}
              </button>
            ))
          ) : null}

          {showNoResults && (
            <div className="px-4 py-3 flex flex-col gap-2">
              <span className="text-sm text-slate-500">로컬에 없는 곡입니다</span>
              <button
                onClick={handleAiSearch}
                disabled={aiLoading}
                className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 text-purple-400 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {aiLoading ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    AI 검색 중...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    AI로 코드 검색
                  </>
                )}
              </button>
              {aiError && (
                <span className="text-xs text-red-400">{aiError}</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
