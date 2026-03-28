import { useState, useMemo, useCallback } from 'react'
import type { Song } from '../../types/song'
import { getAllSongs, deleteSong } from '../../data/songStore'
import { SongSearchBar } from './SongSearchBar'
import { ChordSheet } from './ChordSheet'
import { LiveMode } from './LiveMode'

type ViewMode = 'search' | 'sheet' | 'live'

interface SongChordPageProps {
  onViewOnFretboard?: (chordName: string) => void
}

export function SongChordPage({ onViewOnFretboard }: SongChordPageProps) {
  const [selectedSong, setSelectedSong] = useState<Song | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('search')
  const [copiedChords, setCopiedChords] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const recommended = useMemo(() => {
    const all = getAllSongs()
    const shuffled = [...all].sort(() => Math.random() - 0.5)
    return shuffled.slice(0, 5)
  }, [])

  const handleSelect = (song: Song) => {
    setSelectedSong(song)
    setViewMode('sheet')
    setConfirmDelete(false)
  }

  const handleBackToSearch = () => {
    setSelectedSong(null)
    setViewMode('search')
    setConfirmDelete(false)
  }

  const handleChordClick = useCallback((chord: string) => {
    if (onViewOnFretboard) {
      onViewOnFretboard(chord)
    }
  }, [onViewOnFretboard])

  const handleCopyChords = useCallback(() => {
    if (!selectedSong) return
    const unique = new Set<string>()
    for (const section of selectedSong.sections) {
      for (const c of section.chords) {
        unique.add(c.chord)
      }
    }
    const text = `${selectedSong.title}${selectedSong.artist ? ` - ${selectedSong.artist}` : ''}\n코드: ${[...unique].join(', ')}`
    navigator.clipboard.writeText(text).then(() => {
      setCopiedChords(true)
      setTimeout(() => setCopiedChords(false), 2000)
    })
  }, [selectedSong])

  const handleDelete = useCallback(() => {
    if (!selectedSong) return
    deleteSong(selectedSong.id)
    setSelectedSong(null)
    setViewMode('search')
    setConfirmDelete(false)
  }, [selectedSong])

  if (selectedSong && viewMode === 'live') {
    return <LiveMode song={selectedSong} onExit={() => setViewMode('sheet')} />
  }

  if (selectedSong && viewMode === 'sheet') {
    const canDelete = selectedSong.source !== 'seed'

    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <button
            onClick={handleBackToSearch}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            검색으로 돌아가기
          </button>
          <div className="flex-1" />
          {canDelete && !confirmDelete && (
            <button
              onClick={() => setConfirmDelete(true)}
              className="px-3 py-1.5 rounded-lg text-sm text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-colors"
            >
              삭제
            </button>
          )}
          {canDelete && confirmDelete && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-red-400">삭제하시겠습니까?</span>
              <button
                onClick={handleDelete}
                className="px-2.5 py-1 rounded text-xs font-medium bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
              >
                확인
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="px-2.5 py-1 rounded text-xs text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
              >
                취소
              </button>
            </div>
          )}
          <button
            onClick={handleCopyChords}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-700/50 hover:bg-slate-700 text-slate-400 hover:text-slate-200 text-sm transition-colors"
          >
            {copiedChords ? '복사됨!' : '코드 목록 복사'}
          </button>
          <button
            onClick={() => setViewMode('live')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-orange-600/20 hover:bg-orange-600/30 text-orange-400 text-sm font-medium transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            라이브 모드
          </button>
        </div>
        <ChordSheet
          song={selectedSong}
          onChordClick={onViewOnFretboard ? handleChordClick : undefined}
        />
        {onViewOnFretboard && (
          <p className="text-xs text-slate-600 text-center">
            코드를 클릭하면 프렛보드에서 볼 수 있습니다
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <SongSearchBar onSelect={handleSelect} />

      <div>
        <h3 className="text-sm font-medium text-slate-500 mb-2">추천 곡</h3>
        <div className="grid gap-2">
          {recommended.map(song => (
            <button
              key={song.id}
              onClick={() => handleSelect(song)}
              className="flex items-center gap-3 px-4 py-3 rounded-lg bg-slate-800/60 hover:bg-slate-700/60 text-left transition-colors"
            >
              <div className="flex-1 min-w-0">
                <span className="text-sm text-slate-200 font-medium block truncate">{song.title}</span>
                {song.artist && <span className="text-xs text-slate-500">{song.artist}</span>}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {song.key && (
                  <span className="text-xs font-mono text-slate-400 px-1.5 py-0.5 rounded bg-slate-900/50">
                    {song.key}
                  </span>
                )}
                {song.bpm && (
                  <span className="text-xs font-mono text-slate-500">
                    {song.bpm}
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
